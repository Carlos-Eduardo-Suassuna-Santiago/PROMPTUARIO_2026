from __future__ import annotations
import secrets
import uuid
import logging

import httpx
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.domain.models.oauth_account import OAuthAccount
from app.domain.models.user import User
from app.domain.services.auth_service import AuthService, UserService
from app.infrastructure.repositories.oauth_repository import OAuthRepository
from app.infrastructure.repositories.user_repository import UserRepository
from shared.events.broker import EventPublisher
from shared.utils.security import hash_password

logger = logging.getLogger(__name__)


class OAuthService:
    def __init__(self, session: AsyncSession, publisher: EventPublisher, redis_client):
        self.session = session
        self.publisher = publisher
        self.redis = redis_client
        self._oauth_repo = OAuthRepository(session)
        self._user_repo = UserRepository(session)

    # ── State management ──────────────────────────────────────────────────

    async def _generate_state(self) -> str:
        """Gera state CSRF-safe e persiste no Redis por 5 minutos."""
        state = secrets.token_urlsafe(32)
        await self.redis.setex(f"oauth_state:{state}", 300, "1")
        return state

    async def _validate_state(self, state: str) -> None:
        """Valida o state OAuth e remove do Redis (single-use)."""
        exists = await self.redis.exists(f"oauth_state:{state}")
        if not exists:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="State OAuth inválido ou expirado. Reinicie o login.",
            )
        await self.redis.delete(f"oauth_state:{state}")

    # ── GitHub ────────────────────────────────────────────────────────────

    async def get_github_auth_url(self) -> str:
        if not settings.GITHUB_CLIENT_ID:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Login com GitHub não configurado neste servidor.",
            )
        state = await self._generate_state()
        callback_url = f"{settings.OAUTH_REDIRECT_BASE_URL}/api/v1/auth/oauth/github/callback"
        return (
            f"https://github.com/login/oauth/authorize"
            f"?client_id={settings.GITHUB_CLIENT_ID}"
            f"&redirect_uri={callback_url}"
            f"&scope=user:email"
            f"&state={state}"
        )

    async def handle_github_callback(self, code: str, state: str) -> dict:
        await self._validate_state(state)
        callback_url = f"{settings.OAUTH_REDIRECT_BASE_URL}/api/v1/auth/oauth/github/callback"

        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                # 1. Troca code por access_token
                token_resp = await client.post(
                    "https://github.com/login/oauth/access_token",
                    headers={"Accept": "application/json"},
                    json={
                        "client_id": settings.GITHUB_CLIENT_ID,
                        "client_secret": settings.GITHUB_CLIENT_SECRET,
                        "code": code,
                        "redirect_uri": callback_url,
                    },
                )
                token_resp.raise_for_status()
                token_data = token_resp.json()
                access_token = token_data.get("access_token")
                if not access_token:
                    logger.error("GitHub OAuth não retornou access_token: %s", token_data)
                    raise HTTPException(
                        status_code=status.HTTP_502_BAD_GATEWAY,
                        detail="Erro ao autenticar com GitHub. Tente novamente.",
                    )

                # 2. Busca dados do usuário
                auth_header = {"Authorization": f"token {access_token}",
                               "Accept": "application/vnd.github.v3+json"}
                user_resp = await client.get("https://api.github.com/user", headers=auth_header)
                user_resp.raise_for_status()
                gh_user = user_resp.json()

                # 3. Busca email verificado (pode não estar em /user)
                email = gh_user.get("email")
                if not email:
                    emails_resp = await client.get(
                        "https://api.github.com/user/emails", headers=auth_header
                    )
                    if emails_resp.status_code == 200:
                        emails = emails_resp.json()
                        primary = next(
                            (e["email"] for e in emails if e.get("primary") and e.get("verified")),
                            None,
                        )
                        email = primary or f"github_{gh_user['id']}@users.noreply.github.com"
            except httpx.TimeoutException:
                logger.error("Timeout ao comunicar com GitHub OAuth")
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail="Tempo limite excedido na comunicação com GitHub. Tente novamente.",
                )
            except httpx.HTTPError as e:
                logger.error("Erro HTTP na comunicação com GitHub OAuth: %s", str(e))
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail="Erro de comunicação com GitHub. Tente novamente.",
                )

        user = await self._get_or_create_user(
            provider="github",
            provider_id=str(gh_user["id"]),
            email=email,
            name=gh_user.get("name") or gh_user.get("login") or "GitHub User",
        )
        return await self._issue_tokens_for_user(user)

    # ── Google ────────────────────────────────────────────────────────────

    async def get_google_auth_url(self) -> str:
        if not settings.GOOGLE_CLIENT_ID:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Login com Google não configurado neste servidor.",
            )
        state = await self._generate_state()
        callback_url = f"{settings.OAUTH_REDIRECT_BASE_URL}/api/v1/auth/oauth/google/callback"
        return (
            f"https://accounts.google.com/o/oauth2/v2/auth"
            f"?client_id={settings.GOOGLE_CLIENT_ID}"
            f"&redirect_uri={callback_url}"
            f"&response_type=code"
            f"&scope=openid%20email%20profile"
            f"&state={state}"
            f"&access_type=offline"
        )

    async def handle_google_callback(self, code: str, state: str) -> dict:
        await self._validate_state(state)
        callback_url = f"{settings.OAUTH_REDIRECT_BASE_URL}/api/v1/auth/oauth/google/callback"

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                token_resp = await client.post(
                    "https://oauth2.googleapis.com/token",
                    data={
                        "code": code,
                        "client_id": settings.GOOGLE_CLIENT_ID,
                        "client_secret": settings.GOOGLE_CLIENT_SECRET,
                        "redirect_uri": callback_url,
                        "grant_type": "authorization_code",
                    },
                )
                token_resp.raise_for_status()
                tokens = token_resp.json()
        except httpx.TimeoutException:
            logger.error("Timeout ao comunicar com Google OAuth")
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Tempo limite excedido na comunicação com Google. Tente novamente.",
            )
        except httpx.HTTPError as e:
            logger.error("Erro HTTP na comunicação com Google OAuth: %s", str(e))
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Erro de comunicação com Google. Tente novamente.",
            )

        # Decode id_token (JWT Google) para extrair claims
        # Não verificamos a assinatura aqui pois vieram direto do Google via HTTPS
        import base64 as _b64, json as _json
        id_token = tokens.get("id_token", "")
        parts = id_token.split(".")
        if len(parts) < 2:
            raise HTTPException(status_code=502, detail="id_token Google inválido")
        padding = "=" * (4 - len(parts[1]) % 4)
        try:
            claims = _json.loads(_b64.urlsafe_b64decode(parts[1] + padding))
        except Exception:
            raise HTTPException(status_code=502, detail="Falha ao decodificar id_token Google")

        user = await self._get_or_create_user(
            provider="google",
            provider_id=claims.get("sub", ""),
            email=claims.get("email", ""),
            name=claims.get("name") or claims.get("email", "Google User"),
        )
        return await self._issue_tokens_for_user(user)

    # ── Helpers ────────────────────────────────────────────────────────────

    async def _get_or_create_user(
        self, provider: str, provider_id: str, email: str, name: str
    ) -> User:
        """Busca usuário via OAuthAccount. Se não existe, cria via email ou novo registro."""
        # 1. OAuthAccount existente
        oauth_account = await self._oauth_repo.get_by_provider(provider, provider_id)
        if oauth_account:
            user = await self._user_repo.get_by_id(oauth_account.user_id)
            if not user or not user.is_active:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Conta desativada. Contate o administrador.",
                )
            return user

        # 2. Busca por email
        user = await self._user_repo.get_by_email(email.lower())
        if not user:
            # 3. Cria novo usuário com senha aleatória (não pode logar via senha)
            from shared.events import UserCreatedEvent
            user = User(
                id=str(uuid.uuid4()),
                email=email.lower(),
                hashed_password=hash_password(secrets.token_hex(32)),
                full_name=name,
                role="PATIENT",
            )
            user = await self._user_repo.create(user)
            await self.publisher.publish(
                UserCreatedEvent(
                    user_id=user.id,
                    email=user.email,
                    role=user.role,
                    full_name=user.full_name,
                )
            )

        # 4. Cria OAuthAccount vinculando
        oauth_account = OAuthAccount(
            user_id=user.id,
            provider=provider,
            provider_user_id=provider_id,
            provider_email=email,
        )
        await self._oauth_repo.create(oauth_account)
        await self.session.commit()
        return user

    async def _issue_tokens_for_user(self, user: User) -> dict:
        """Reutiliza _issue_tokens do AuthService para emitir os mesmos tokens JWT."""
        auth_svc = AuthService(self.session, self.publisher, self.redis)
        return await auth_svc._issue_tokens(user)

    async def list_accounts(self, user_id: str) -> list[dict]:
        accounts = await self._oauth_repo.list_by_user(user_id)
        return [{"provider": a.provider, "email": a.provider_email} for a in accounts]