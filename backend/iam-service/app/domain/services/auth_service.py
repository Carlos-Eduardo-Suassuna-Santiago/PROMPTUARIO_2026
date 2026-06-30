from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.domain.models.user import RefreshToken, User
from app.infrastructure.repositories.user_repository import (
    RefreshTokenRepository,
    UserRepository,
)
from shared.events import UserCreatedEvent, UserDeactivatedEvent, UserUpdatedEvent
from shared.events.broker import EventPublisher
from shared.metrics import login_attempts_total, users_registered_total, active_users
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

        # Persist hashed refresh token
        rt = RefreshToken(
            id=str(uuid.uuid4()),
            user_id=user.id,
            token_hash=hashlib.sha256(refresh_token_str.encode()).hexdigest(),
            expires_at=datetime.now(timezone.utc)
            + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
        )
        await self.token_repo.save(rt)
        await self.session.commit()

        return {
            "access_token": access_token,
            "refresh_token": refresh_token_str,
            "token_type": "bearer",
            "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        }

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

    async def _issue_tokens(self, user: User) -> dict:
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
        await self.session.commit()


class UserService:
    def __init__(self, session: AsyncSession, publisher: EventPublisher):
        self.session = session
        self.user_repo = UserRepository(session)
        self.publisher = publisher

    async def create_user(
        self, email: str, password: str, full_name: str, role: str
    ) -> User:
        if await self.user_repo.exists_by_email(email):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Email já cadastrado",
            )
        user = User(
            id=str(uuid.uuid4()),
            email=email.lower(),
            hashed_password=hash_password(password),
            full_name=full_name,
            role=role,
        )
        user = await self.user_repo.create(user)
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
        self, user_id: str, full_name: str | None, email: str | None
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
        if changed:
            user = await self.user_repo.update(user)
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

    async def deactivate_user(
        self, user_id: str, reason: str, deactivated_by: str
    ) -> None:
        user = await self.get_user(user_id)
        user.is_active = False
        user.deactivation_reason = reason
        user.deactivated_at = datetime.now(timezone.utc)
        await self.user_repo.update(user)
        await self.session.commit()
        await self.publisher.publish(
            UserDeactivatedEvent(
                user_id=user_id,
                reason=reason,
                deactivated_by=deactivated_by,
            )
        )
