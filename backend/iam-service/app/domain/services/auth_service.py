from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

import secrets

from app.config import settings
from app.domain.models.password_reset import PasswordResetToken
from app.domain.models.user import RefreshToken, User
from app.infrastructure.repositories.password_reset_repository import PasswordResetRepository
from app.infrastructure.repositories.user_repository import (
    RefreshTokenRepository,
    UserRepository,
)
from shared.events import UserCreatedEvent, UserDeactivatedEvent, UserReactivatedEvent, UserUpdatedEvent
from shared.events.broker import EventPublisher
from shared.metrics import login_attempts_total, users_registered_total, active_users
from shared.audit import log_operation
from shared.utils.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.config import settings as _settings


class AuthService:
    def __init__(
        self,
        session: AsyncSession,
        publisher: EventPublisher,
        redis_client,
    ):
        self.session = session
        self.user_repo = UserRepository(session)
        self.token_repo = RefreshTokenRepository(session)
        self.publisher = publisher
        self.redis = redis_client

    async def login(self, email: str, password: str, _bypass: bool = False, _user: User | None = None) -> dict:
        # Normalize inputs to avoid issues with accidental whitespace or casing
        if isinstance(email, str):
            email = email.strip().lower()
        if isinstance(password, str):
            password = password.strip()

        if _bypass and _user:
            user = _user
        else:
            user = await self.user_repo.get_by_email(email)
            if not user or not verify_password(password, user.hashed_password):
                login_attempts_total.labels(
                    service=_settings.SERVICE_NAME, status="failure"
                ).inc()
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Email ou senha inválidos",
                )
        if not user.is_active:
            login_attempts_total.labels(
                service=_settings.SERVICE_NAME, status="failure"
            ).inc()
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Usuário inativo",
            )

        login_attempts_total.labels(
            service=_settings.SERVICE_NAME, status="success"
        ).inc()
        active_users.labels(service=_settings.SERVICE_NAME).inc()

        return await self._issue_tokens(user, log_login=True)



    async def refresh(self, refresh_token: str) -> dict:
        rt = await self.token_repo.get_valid(refresh_token)
        if not rt:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Refresh token inválido ou expirado",
            )
        try:
            payload = decode_token(
                refresh_token, settings.JWT_SECRET_KEY, settings.JWT_ALGORITHM
            )
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token malformado",
            )

        # Rotate: revoke old, issue new
        await self.token_repo.revoke(refresh_token)
        await self.session.commit()
        user = await self.user_repo.get_by_id(payload.sub)
        if not user or not user.is_active:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Usuário inativo")

        return await self._issue_tokens(user)

    async def _issue_tokens(self, user: User, log_login: bool = False) -> dict:
        access_token = create_access_token(
            user_id=user.id,
            role=user.role,
            email=user.email,
            secret=settings.JWT_SECRET_KEY,
            algorithm=settings.JWT_ALGORITHM,
            expire_minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES,
        )
        refresh_token_str = create_refresh_token(
            user_id=user.id,
            secret=settings.JWT_SECRET_KEY,
            algorithm=settings.JWT_ALGORITHM,
            expire_days=settings.REFRESH_TOKEN_EXPIRE_DAYS,
        )
        rt = RefreshToken(
            id=str(uuid.uuid4()),
            user_id=user.id,
            token_hash=hashlib.sha256(refresh_token_str.encode()).hexdigest(),
            expires_at=datetime.now(timezone.utc)
            + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
        )
        await self.token_repo.save(rt)
        
        if log_login:
            await log_operation(
                self.session,
                service="iam-service",
                table="sessions",
                operation="AUTH_LOGIN",
                record_id=user.id,
                user_id=user.id,
                user_role=user.role,
                user_email=user.email,
                ip_address=getattr(self, "_ip_address", None),
            )
            
        await self.session.commit()
        return {
            "access_token": access_token,
            "refresh_token": refresh_token_str,
            "token_type": "bearer",
            "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        }

    async def refresh_tokens(self, refresh_token: str) -> dict:
        rt = await self.token_repo.get_valid(refresh_token)
        if not rt:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Refresh token inválido ou expirado",
            )
        try:
            payload = decode_token(
                refresh_token, settings.JWT_SECRET_KEY, settings.JWT_ALGORITHM
            )
        except ValueError:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token malformado")

        await self.token_repo.revoke(refresh_token)
        await self.session.commit()
        user = await self.user_repo.get_by_id(payload.sub)
        if not user or not user.is_active:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Usuário inativo")

        return await self._issue_tokens(user)

    async def logout(self, refresh_token: str, access_token: str) -> None:
        await self.token_repo.revoke(refresh_token)
        # Buscar user_id do token para auditar
        _user_id = None
        try:
            _payload = decode_token(access_token, settings.JWT_SECRET_KEY, settings.JWT_ALGORITHM)
            _user_id = _payload.sub
        except Exception:
            pass
        await log_operation(
            self.session,
            service="iam-service",
            table="sessions",
            operation="AUTH_LOGOUT",
            user_id=_user_id,
        )
        await self.session.commit()
        # Blacklist access token in Redis (until its natural expiry)
        try:
            payload = decode_token(
                access_token, settings.JWT_SECRET_KEY, settings.JWT_ALGORITHM
            )
            ttl = payload.exp - int(datetime.now(timezone.utc).timestamp())
            if ttl > 0:
                await self.redis.setex(f"blacklist:{access_token}", ttl, "1")
        except Exception:
            pass

    async def change_password(
        self, user_id: str, current_password: str, new_password: str
    ) -> None:
        user = await self.user_repo.get_by_id(user_id)
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuário não encontrado")
        if not verify_password(current_password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Senha atual incorreta"
            )
        user.hashed_password = hash_password(new_password)
        await self.token_repo.revoke_all_for_user(user_id)
        await self.user_repo.update(user)
        await log_operation(
            self.session,
            service="iam-service",
            table="users",
            operation="PASSWORD_CHANGE",
            record_id=user_id,
            user_id=user_id,
        )
        await self.session.commit()

    async def forgot_password(self, email: str) -> dict:
        """Generate a password reset token for the given email."""
        user = await self.user_repo.get_by_email(email)
        # Always return success to avoid email enumeration
        if not user:
            return {"message": "Se o email estiver cadastrado, você receberá um link para redefinir sua senha."}

        # Invalidate any existing tokens for this user
        reset_repo = PasswordResetRepository(self.session)
        await reset_repo.invalidate_all_for_user(user.id)

        # Generate a secure random token
        raw_token = secrets.token_urlsafe(48)
        token_hash = hashlib.sha256(raw_token.encode()).hexdigest()

        reset_token = PasswordResetToken(
            id=str(uuid.uuid4()),
            user_id=user.id,
            token_hash=token_hash,
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        )
        await reset_repo.save(reset_token)
        await self.session.commit()


        # Send email with reset link
        reset_link = f"http://localhost:3000/reset-password?token={raw_token}"
        from app.infrastructure.email_sender import send_reset_password_email
        send_reset_password_email(email, reset_link)

        return {
            "message": "Se o email estiver cadastrado, você receberá um link para redefinir sua senha."
        }

    async def reset_password(self, token: str, new_password: str) -> dict:
        """Reset password using a valid reset token."""
        reset_repo = PasswordResetRepository(self.session)
        reset_token = await reset_repo.get_valid(token)
        if not reset_token:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Token inválido ou expirado",
            )

        user = await self.user_repo.get_by_id(reset_token.user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Usuário não encontrado",
            )

        # Update password
        user.hashed_password = hash_password(new_password)
        await self.user_repo.update(user)

        # Mark token as used and revoke all sessions
        await reset_repo.mark_used(token)
        await self.token_repo.revoke_all_for_user(user.id)

        await log_operation(
            self.session,
            service="iam-service",
            table="users",
            operation="PASSWORD_RESET",
            record_id=user.id,
            user_id=user.id,
        )
        await self.session.commit()

        return {"message": "Senha redefinida com sucesso."}


class UserService:
    def __init__(self, session: AsyncSession, publisher: EventPublisher):
        self.session = session
        self.user_repo = UserRepository(session)
        self.publisher = publisher

    async def create_user(
        self, email: str, password: str, full_name: str, role: str, cpf: str | None = None
    ) -> User:
        if await self.user_repo.exists_by_email(email):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Email já cadastrado",
            )
        if cpf and await self.user_repo.exists_by_cpf(cpf):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="CPF já cadastrado",
            )
        user = User(
            id=str(uuid.uuid4()),
            email=email.lower(),
            cpf=cpf,
            hashed_password=hash_password(password),
            full_name=full_name,
            role=role,
        )
        user = await self.user_repo.create(user)
        await log_operation(
            self.session,
            service="iam-service",
            table="users",
            operation="INSERT",
            record_id=user.id,
            new_values={"email": user.email, "role": user.role, "full_name": user.full_name},
        )
        await self.session.commit()
        users_registered_total.labels(
            service=_settings.SERVICE_NAME, role=user.role
        ).inc()
        await self.publisher.publish(
            UserCreatedEvent(
                user_id=user.id,
                email=user.email,
                role=user.role,
                full_name=user.full_name,
            )
        )
        return user

    async def get_user(self, user_id: str) -> User:
        user = await self.user_repo.get_by_id(user_id)
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuário não encontrado")
        return user

    async def list_users(self, page: int, size: int, role: str | None, is_active: bool | None):
        return await self.user_repo.list_users(page, size, role, is_active)

    async def update_user(
        self, user_id: str, full_name: str | None, email: str | None, cpf: str | None = None
    ) -> User:
        user = await self.get_user(user_id)
        changed = []
        if full_name and full_name != user.full_name:
            user.full_name = full_name
            changed.append("full_name")
        if email and email.lower() != user.email:
            if await self.user_repo.exists_by_email(email):
                raise HTTPException(status_code=409, detail="Email já em uso")
            user.email = email.lower()
            changed.append("email")
        if cpf and cpf != user.cpf:
            if await self.user_repo.exists_by_cpf(cpf):
                raise HTTPException(status_code=409, detail="CPF já cadastrado")
            user.cpf = cpf
            changed.append("cpf")
        if changed:
            user = await self.user_repo.update(user)
            await log_operation(
                self.session,
                service="iam-service",
                table="users",
                operation="UPDATE",
                record_id=user_id,
                new_values={"changed_fields": changed},
            )
            await self.session.commit()
            await self.publisher.publish(
                UserUpdatedEvent(
                    user_id=user.id,
                    changed_fields=changed,
                    full_name=user.full_name,
                    email=user.email,
                )
            )
        return user

    async def assign_role(self, user_id: str, role: str) -> User:
        user = await self.get_user(user_id)
        user.role = role
        user = await self.user_repo.update(user)
        await self.session.commit()
        return user

    async def register_patient(
        self, email: str, password: str, full_name: str,
        cpf: str | None = None, date_of_birth: str | None = None,
        gender: str | None = None, phone: str | None = None,
    ) -> User:
        """Register a new patient user (self-registration)."""
        if await self.user_repo.exists_by_email(email):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Email já cadastrado",
            )
        if cpf and await self.user_repo.exists_by_cpf(cpf):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="CPF já cadastrado",
            )
        user = User(
            id=str(uuid.uuid4()),
            email=email.lower(),
            cpf=cpf,
            hashed_password=hash_password(password),
            full_name=full_name,
            role="PATIENT",
        )
        user = await self.user_repo.create(user)
        await log_operation(
            self.session,
            service="iam-service",
            table="users",
            operation="INSERT",
            record_id=user.id,
            new_values={"email": user.email, "role": user.role, "full_name": user.full_name},
        )
        await self.session.commit()
        users_registered_total.labels(
            service=_settings.SERVICE_NAME, role=user.role
        ).inc()
        await self.publisher.publish(
            UserCreatedEvent(
                user_id=user.id,
                email=user.email,
                role=user.role,
                full_name=user.full_name,
                cpf=cpf,
                date_of_birth=date_of_birth,
                gender=gender,
                phone=phone,
            )
        )
        return user

    async def deactivate_user(
        self, user_id: str, reason: str, deactivated_by: str
    ) -> None:
        user = await self.get_user(user_id)
        user.is_active = False
        user.deactivation_reason = reason
        user.deactivated_at = datetime.now(timezone.utc)
        await self.user_repo.update(user)
        await log_operation(
            self.session,
            service="iam-service",
            table="users",
            operation="DELETE",
            record_id=user_id,
            user_id=deactivated_by,
            new_values={"is_active": False, "reason": reason},
        )
        await self.session.commit()
        await self.publisher.publish(
            UserDeactivatedEvent(
                user_id=user_id,
                reason=reason,
                deactivated_by=deactivated_by,
            )
        )

    async def reactivate_user(
        self, user_id: str, reactivated_by: str
    ) -> None:
        user = await self.user_repo.get_by_id(user_id)
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuário não encontrado")
        
        user.deactivated_at = None
        await self.user_repo.update(user)

        # enable in cognito if cogito is used
        try:
            from shared.utils.security import cognito_client
            cognito_client.admin_enable_user(
                UserPoolId=settings.AWS_COGNITO_USER_POOL_ID,
                Username=user.email,
            )
        except Exception as e:
            logger.warning("Falha ao reativar usuário no Cognito: %s", e)

        await log_operation(
            self.session,
            service="iam-service",
            table="users",
            operation="REACTIVATE",
            record_id=user.id,
            user_id=reactivated_by,
            old_values={"deactivated": True},
            new_values={"deactivated": False},
        )
        await self.session.commit()

        await self.event_broker.publish(
            UserReactivatedEvent(
                user_id=user.id,
                reactivated_by=reactivated_by,
            )
        )
