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

Stack:

* FastAPI
* PostgreSQL
* SQLAlchemy
* Alembic
* Pydantic
* JWT
* Docker

---

# 2. ESTRUTURA DO PROJETO

```text
iam-service/
├── app/
│   ├── api/
│   │   ├── deps.py
│   │   ├── router.py
│   │   └── v1/
│   │       ├── auth_routes.py
│   │       ├── user_routes.py
│   │       └── admin_routes.py
│   │
│   ├── core/
│   │   ├── config.py
│   │   ├── security.py
│   │   ├── database.py
│   │   └── logging.py
│   │
│   ├── domain/
│   │   ├── models/
│   │   │   ├── user.py
│   │   │   ├── role.py
│   │   │   └── refresh_token.py
│   │   │
│   │   └── enums/
│   │       └── roles.py
│   │
│   ├── schemas/
│   │   ├── auth_schema.py
│   │   ├── user_schema.py
│   │   └── token_schema.py
│   │
│   ├── repositories/
│   │   ├── user_repository.py
│   │   ├── role_repository.py
│   │   └── refresh_repository.py
│   │
│   ├── services/
│   │   ├── auth_service.py
│   │   ├── user_service.py
│   │   ├── token_service.py
│   │   └── rbac_service.py
│   │
│   ├── middleware/
│   │   ├── auth_middleware.py
│   │   └── role_middleware.py
│   │
│   ├── messaging/
│   │   ├── producer.py
│   │   └── events.py
│   │
│   └── main.py
│
├── alembic/
├── alembic.ini
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
sqlalchemy
psycopg2-binary
alembic
python-jose[cryptography]
passlib[bcrypt]
pydantic
pydantic-settings
python-dotenv
email-validator
httpx
pika
```

---

# 4. CONFIGURAÇÃO

# app/core/config.py

```python
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    APP_NAME: str = "iam-service"

    DATABASE_URL: str

    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"

    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    RABBITMQ_URL: str

    class Config:
        env_file = ".env"


settings = Settings()
```

---

# 5. DATABASE CONFIG

# app/core/database.py

```python
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base
from sqlalchemy.orm import sessionmaker

from app.core.config import settings

engine = create_engine(settings.DATABASE_URL)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

---

# 6. ROLE ENUM

# app/domain/enums/roles.py

```python
from enum import Enum


class UserRole(str, Enum):
    ADMIN = "admin"
    DOCTOR = "doctor"
    PATIENT = "patient"
    ATTENDANT = "attendant"
```

---

# 7. USER MODEL

# app/domain/models/user.py

```python
import uuid

from sqlalchemy import Column
from sqlalchemy import String
from sqlalchemy import Boolean
from sqlalchemy.dialects.postgresql import UUID

from app.core.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    full_name = Column(String, nullable=False)

    email = Column(String, unique=True, nullable=False)

    password_hash = Column(String, nullable=False)

    role = Column(String, nullable=False)

    is_active = Column(Boolean, default=True)
```

---

# 8. REFRESH TOKEN MODEL

# app/domain/models/refresh_token.py

```python
import uuid

from sqlalchemy import Column
from sqlalchemy import String
from sqlalchemy import DateTime
from sqlalchemy import ForeignKey

from sqlalchemy.dialects.postgresql import UUID

from app.core.database import Base


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))

    token = Column(String, nullable=False)

    expires_at = Column(DateTime, nullable=False)
```

---

# 9. PYDANTIC SCHEMAS

# app/schemas/user_schema.py

```python
from uuid import UUID

from pydantic import BaseModel
from pydantic import EmailStr


class UserCreate(BaseModel):
    full_name: str
    email: EmailStr
    password: str
    role: str


class UserResponse(BaseModel):
    id: UUID
    full_name: str
    email: EmailStr
    role: str

    class Config:
        from_attributes = True
```

---

# app/schemas/auth_schema.py

```python
from pydantic import BaseModel
from pydantic import EmailStr


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str
```

---

# app/schemas/token_schema.py

```python
from pydantic import BaseModel


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
```

---

# 10. SECURITY UTILITIES

# app/core/security.py

```python
from datetime import datetime
from datetime import timedelta

from jose import jwt
from passlib.context import CryptContext

from app.core.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    return pwd_context.verify(password, hashed)


def create_access_token(data: dict):
    payload = data.copy()

    expire = datetime.utcnow() + timedelta(
        minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
    )

    payload.update({"exp": expire})

    return jwt.encode(
        payload,
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM
    )


def create_refresh_token(data: dict):
    payload = data.copy()

    expire = datetime.utcnow() + timedelta(
        days=settings.REFRESH_TOKEN_EXPIRE_DAYS
    )

    payload.update({"exp": expire})

    return jwt.encode(
        payload,
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM
    )


def decode_token(token: str):
    return jwt.decode(
        token,
        settings.JWT_SECRET_KEY,
        algorithms=[settings.JWT_ALGORITHM]
    )
```

---

# 11. USER REPOSITORY

# app/repositories/user_repository.py

```python
from sqlalchemy.orm import Session

from app.domain.models.user import User


class UserRepository:

    def __init__(self, db: Session):
        self.db = db

        def get_by_email(self, email: str):
                return self.db.query(User).filter(User.email == email).first()

---

# Detalhes de implementação (extraído do ambiente)

- **Base path:** /api/v1
- **Health endpoint:** /healthz
- **Host port mapping (host:container):** 8001:8000
- **Principais variáveis de ambiente:**
    - `DATABASE_URL` (ex: postgresql+asyncpg://iam:iam_pass@db-iam:5432/iam_db)
    - `REDIS_URL` (ex: redis://redis:6379/0)
    - `RABBITMQ_URL` (ex: amqp://promptuario:promptuario_pass@rabbitmq:5672/)
    - `JWT_SECRET_KEY`, `JWT_ALGORITHM`
    - `ACCESS_TOKEN_EXPIRE_MINUTES`, `REFRESH_TOKEN_EXPIRE_DAYS`

Use esses valores como referência ao descrever exemplos de `docker-compose` e `.env` no ambiente de produção/local.

---

# Quickstart padronizado

```bash
curl http://localhost:8001/healthz
curl http://localhost:8001/docs
```

Quando acessado via gateway, o mesmo serviço responde em `http://localhost:8000/api/v1/auth/*` e `http://localhost:8000/api/v1/users/*`.
```
