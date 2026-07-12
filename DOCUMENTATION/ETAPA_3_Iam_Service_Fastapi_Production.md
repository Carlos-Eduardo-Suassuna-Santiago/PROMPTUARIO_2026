# ETAPA 3 — IAM SERVICE (FASTAPI)

# 1. OBJETIVO

Implementar o IAM Service responsável por:

* JWT Authentication
* RBAC Authorization
* User Registration
* Login
* Refresh Tokens
* Password Hashing
* Protected Routes
* Session Security
* Role Validation
* OAuth2 Google Integration

Stack:

* FastAPI
* PostgreSQL (async via SQLAlchemy + asyncpg)
* SQLAlchemy (async)
* Alembic
* Pydantic
* JWT (python-jose)
* Redis (blacklist + rate limiting)
* RabbitMQ (event publishing)
* Docker

---

# 2. ESTRUTURA DO PROJETO (REAL)

```text
iam-service/
├── app/
│   ├── __init__.py
│   ├── main.py                    # FastAPI app, startup, seed admin
│   ├── config.py                  # Settings via pydantic-settings
│   │
│   ├── api/
│   │   ├── routers.py             # auth_router, users_router
│   │   └── oauth_router.py        # Google OAuth2 routes
│   │
│   ├── domain/
│   │   ├── models/
│   │   │   ├── user.py            # User model (SQLAlchemy)
│   │   │   └── oauth_account.py   # OAuthAccount model
│   │   │
│   │   └── services/
│   │       ├── auth_service.py    # Login, refresh, logout
│   │       ├── user_service.py    # CRUD de usuários
│   │       └── oauth_service.py   # Google OAuth2 flow
│   │
│   └── infrastructure/
│       └── repositories/
│           ├── user_repository.py
│           └── oauth_repository.py
│
├── tests/
├── requirements.txt
├── Dockerfile
├── .env
└── docker-compose.yml
```

---

# 3. REQUIREMENTS.TXT

```txt
fastapi
uvicorn[standard]
sqlalchemy[asyncio]
asyncpg
alembic
python-jose[cryptography]
passlib[bcrypt]
pydantic
pydantic-settings
python-dotenv
email-validator
httpx
pika
redis[hiredis]
pydantic-extra-types
```

---

# 4. CONFIGURAÇÃO (REAL)

# app/config.py

```python
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # App
    SERVICE_NAME: str = "iam-service"
    LOG_LEVEL: str = "INFO"
    DEBUG: bool = False

    # Database (async)
    DATABASE_URL: str = "postgresql+asyncpg://iam:iam_pass@localhost:5432/iam_db"

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # RabbitMQ
    RABBITMQ_URL: str = "amqp://promptuario:promptuario_pass@localhost:5672/"

    # JWT
    JWT_SECRET_KEY: str = "change-me-in-production"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # OAuth Google
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    OAUTH_REDIRECT_BASE_URL: str = "http://localhost:8000"
    FRONTEND_CALLBACK_URL: str = "http://localhost:3000/auth/callback"

    # First admin user (created on startup)
    FIRST_ADMIN_EMAIL: str = "admin@promptuario.health"
    FIRST_ADMIN_PASSWORD: str = "Admin@12345"
    FIRST_ADMIN_NAME: str = "Administrador"


settings = Settings()
```

---

# 5. DATABASE (ASYNC - REAL)

# shared/models/database.py

```python
"""
Async SQLAlchemy base — used by IAM, Patient, Clinical, Reporting services.
"""
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


def build_engine(database_url: str):
    return create_async_engine(
        database_url,
        echo=False,
        pool_pre_ping=True,
        pool_size=10,
        max_overflow=20,
    )


def build_session_factory(engine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def get_session(session_factory):
    async with session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
```

---

# 6. USER MODEL (REAL)

# app/domain/models/user.py

```python
import uuid

from sqlalchemy import Column, String, Boolean, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from shared.models.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(128), nullable=False)
    full_name = Column(String(255), nullable=False)
    role = Column(String(50), nullable=False, default="ATTENDANT")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    deactivated_at = Column(DateTime(timezone=True), nullable=True)
    deactivation_reason = Column(String(255), nullable=True)
```

---

# 7. USER REPOSITORY (REAL - Async)

# app/infrastructure/repositories/user_repository.py

```python
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.models.user import User


class UserRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_email(self, email: str) -> User | None:
        result = await self.session.execute(
            select(User).where(User.email == email)
        )
        return result.scalar_one_or_none()

    async def get_by_id(self, user_id: str) -> User | None:
        result = await self.session.execute(
            select(User).where(User.id == user_id)
        )
        return result.scalar_one_or_none()

    async def create(self, user: User) -> User:
        self.session.add(user)
        await self.session.flush()
        return user

    async def update(self, user: User) -> User:
        self.session.add(user)
        await self.session.flush()
        return user
```

---

# 8. SECURITY UTILITIES (REAL)

# shared/utils/security.py

```python
from datetime import datetime, timedelta

from jose import jwt
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    return pwd_context.verify(password, hashed)


def create_access_token(data: dict, secret: str, algorithm: str, expires_minutes: int):
    payload = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=expires_minutes)
    payload.update({"exp": expire, "type": "access"})
    return jwt.encode(payload, secret, algorithm=algorithm)


def create_refresh_token(data: dict, secret: str, algorithm: str, expires_days: int):
    payload = data.copy()
    expire = datetime.utcnow() + timedelta(days=expires_days)
    payload.update({"exp": expire, "type": "refresh"})
    return jwt.encode(payload, secret, algorithm=algorithm)


def decode_token(token: str, secret: str, algorithm: str):
    return jwt.decode(token, secret, algorithms=[algorithm])
```

---

# 9. MAIN APP (REAL)

# app/main.py

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import redis.asyncio as aioredis

from app.api.routers import auth_router, users_router
from app.api.oauth_router import oauth_router
from app.config import settings
from shared.models.database import Base, build_engine, build_session_factory
from shared.events.broker import EventPublisher
from shared.observability import setup_observability

app = FastAPI(title="PROMPTUARIO — IAM Service", version="1.0.0")

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True,
                   allow_methods=["*"], allow_headers=["*"])

setup_observability(app, settings.SERVICE_NAME, settings.LOG_LEVEL)

app.include_router(auth_router, prefix="/api/v1")
app.include_router(users_router, prefix="/api/v1")
app.include_router(oauth_router, prefix="/api/v1")


@app.on_event("startup")
async def startup():
    engine = build_engine(settings.DATABASE_URL)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    app.state.session_factory = build_session_factory(engine)
    app.state.redis = await aioredis.from_url(settings.REDIS_URL, decode_responses=True)
    publisher = EventPublisher(settings.RABBITMQ_URL)
    await publisher.connect()
    app.state.publisher = publisher
    await _seed_admin()


@app.get("/healthz")
async def health():
    return {"status": "ok", "service": settings.SERVICE_NAME}
```

---

# 10. ENDPOINTS

| Método | Endpoint | Descrição | Role |
|--------|----------|-----------|------|
| POST | /api/v1/auth/login | Autenticar usuário | Público |
| POST | /api/v1/auth/refresh | Renovar access token | Público |
| POST | /api/v1/auth/logout | Revogar tokens | Autenticado |
| POST | /api/v1/auth/change-password | Alterar senha | Autenticado |
| POST | /api/v1/auth/oauth/google | Login com Google OAuth2 | Público |
| GET | /api/v1/users | Listar usuários | ADMIN |
| GET | /api/v1/users/me | Dados do usuário logado | Autenticado |
| GET | /api/v1/users/{id} | Obter usuário por ID | ADMIN |
| POST | /api/v1/users | Criar usuário | ADMIN |
| PUT | /api/v1/users/{id} | Atualizar usuário | ADMIN, SELF |
| PUT | /api/v1/users/{id}/role | Atribuir role | ADMIN |
| DELETE | /api/v1/users/{id} | Desativar usuário | ADMIN |

---

# Detalhes de implementação

- **Base path:** /api/v1
- **Health endpoint:** /healthz
- **Host port mapping (host:container):** 8001:8000
- **Principais variáveis de ambiente:**
    - `DATABASE_URL` (ex: postgresql+asyncpg://iam:iam_pass@db-iam:5432/iam_db)
    - `REDIS_URL` (ex: redis://redis:6379/0)
    - `RABBITMQ_URL` (ex: amqp://promptuario:promptuario_pass@rabbitmq:5672/)
    - `JWT_SECRET_KEY`, `JWT_ALGORITHM`
    - `ACCESS_TOKEN_EXPIRE_MINUTES`, `REFRESH_TOKEN_EXPIRE_DAYS`
    - `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` (opcional)

---

# Quickstart padronizado

```bash
curl http://localhost:8001/healthz
curl http://localhost:8001/docs
```

Quando acessado via gateway, o mesmo serviço responde em `http://localhost:8000/api/v1/auth/*` e `http://localhost:8000/api/v1/users/*`.