# ETAPA 4 — PATIENT SERVICE (FASTAPI)

# 1. OBJETIVO

Implementar o Patient Service responsável por:

* Cadastro de pacientes
* Dados demográficos
* Metadados médicos
* Busca de pacientes
* Publicação de eventos de domínio
* Ownership completo do domínio Patient

Stack:

* FastAPI
* PostgreSQL
* SQLAlchemy
* Alembic
* Pydantic
* RabbitMQ
* Docker

---

# 2. RESPONSABILIDADES DO SERVIÇO

| Responsabilidade      | Descrição              |
| --------------------- | ---------------------- |
| Registro de paciente  | Cadastro inicial       |
| Dados demográficos    | Nome, sexo, nascimento |
| Metadados médicos     | Blood type, allergies  |
| Busca de pacientes    | Busca textual          |
| Integração assíncrona | RabbitMQ               |
| Database ownership    | Banco isolado          |

---

# 3. CLEAN ARCHITECTURE

```mermaid
graph TD

API[API Layer]

SERVICE[Service Layer]

REPOSITORY[Repository Layer]

DOMAIN[Domain Models]

DB[(PostgreSQL)]

RABBIT[(RabbitMQ)]

API --> SERVICE
SERVICE --> REPOSITORY
REPOSITORY --> DB

SERVICE --> DOMAIN

SERVICE --> RABBIT
```

---

# 4. ESTRUTURA DO PROJETO

```text
patient-service/
├── app/
│
│   ├── api/
│   │   ├── deps.py
│   │   ├── router.py
│   │   └── v1/
│   │       └── patient_routes.py
│   │
│   ├── core/
│   │   ├── config.py
│   │   ├── database.py
│   │   ├── security.py
│   │   └── logging.py
│   │
│   ├── domain/
│   │   ├── models/
│   │   │   └── patient.py
│   │   │
│   │   └── enums/
│   │       ├── gender.py
│   │       └── blood_type.py
│   │
│   ├── schemas/
│   │   ├── patient_schema.py
│   │   └── response_schema.py
│   │
│   ├── repositories/
│   │   └── patient_repository.py
│   │
│   ├── services/
│   │   └── patient_service.py
│   │
│   ├── messaging/
│   │   ├── rabbitmq.py
│   │   ├── producer.py
│   │   └── events.py
│   │
│   ├── middleware/
│   │   └── auth_middleware.py
│   │
│   └── main.py
│
├── alembic/
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
└── .env
```

---

# 5. REQUIREMENTS.TXT

```txt
fastapi
uvicorn[standard]

sqlalchemy
psycopg2-binary
alembic

pydantic
pydantic-settings

python-jose[cryptography]

pika

python-dotenv
```

---

# 6. CONFIGURAÇÃO

# app/core/config.py

```python
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    APP_NAME: str = "patient-service"

    DATABASE_URL: str

    RABBITMQ_URL: str

    JWT_SECRET_KEY: str

    class Config:
        env_file = ".env"


settings = Settings()
```

---

# 7. DATABASE

# app/core/database.py

```python
from sqlalchemy import create_engine

from sqlalchemy.orm import sessionmaker
from sqlalchemy.orm import declarative_base

from app.core.config import settings

engine = create_engine(settings.DATABASE_URL)

SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False
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

# 8. ENUMS

# app/domain/enums/gender.py

```python
from enum import Enum


class Gender(str, Enum):
    MALE = "male"
    FEMALE = "female"
    OTHER = "other"
```

---

# app/domain/enums/blood_type.py

```python
from enum import Enum


class BloodType(str, Enum):
    O_POSITIVE = "O+"
    O_NEGATIVE = "O-"

    A_POSITIVE = "A+"
    A_NEGATIVE = "A-"

    B_POSITIVE = "B+"
    B_NEGATIVE = "B-"

    AB_POSITIVE = "AB+"
    AB_NEGATIVE = "AB-"
```

---

# 9. PATIENT MODEL

# app/domain/models/patient.py

```python
import uuid

from sqlalchemy import Column
from sqlalchemy import String
from sqlalchemy import Date
from sqlalchemy import Text
from sqlalchemy import Boolean

from sqlalchemy.dialects.postgresql import UUID

from app.core.database import Base


class Patient(Base):
    __tablename__ = "patients"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )

    full_name = Column(String, nullable=False)

    cpf = Column(String, unique=True, nullable=False)

    email = Column(String, nullable=True)

    phone = Column(String, nullable=True)

    birth_date = Column(Date, nullable=False)

    gender = Column(String, nullable=False)

    blood_type = Column(String, nullable=True)

    allergies = Column(Text, nullable=True)

    chronic_conditions = Column(Text, nullable=True)

    emergency_contact = Column(String, nullable=True)

    is_active = Column(Boolean, default=True)
```

---

# 10. PYDANTIC SCHEMAS

# app/schemas/patient_schema.py

```python
from uuid import UUID
from datetime import date

from pydantic import BaseModel
from pydantic import EmailStr


class PatientCreate(BaseModel):
    full_name: str
    cpf: str

    email: EmailStr | None = None

    phone: str | None = None

    birth_date: date

    gender: str

    blood_type: str | None = None

    allergies: str | None = None

    chronic_conditions: str | None = None

    emergency_contact: str | None = None


class PatientUpdate(BaseModel):
    full_name: str | None = None

    phone: str | None = None

    email: EmailStr | None = None

    allergies: str | None = None

    chronic_conditions: str | None = None

    emergency_contact: str | None = None


class PatientResponse(BaseModel):
    id: UUID

    full_name: str

    cpf: str

    email: str | None

    phone: str | None

    gender: str

    blood_type: str | None

    class Config:
        from_attributes = True
```

---

# 11. REPOSITORY PATTERN

# app/repositories/patient_repository.py

```python
from sqlalchemy.orm import Session

from app.domain.models.patient import Patient


class PatientRepository:

    def __init__(self, db: Session):
        self.db = db

    def create(self, patient: Patient):
        self.db.add(patient)

        self.db.commit()

        self.db.refresh(patient)

        return patient

    def get_by_id(self, patient_id):
        return self.db.query(Patient).filter(
            Patient.id == patient_id
        ).first()

    def get_by_cpf(self, cpf):
        return self.db.query(Patient).filter(
            Patient.cpf == cpf
        ).first()

    def search(self, query: str):
        return self.db.query(Patient).filter(
            Patient.full_name.ilike(f"%{query}%")
                        ).all()
```

---

# Detalhes de implementação (extraído do ambiente)

- **Base path:** /api/v1
- **Health endpoint:** /healthz
- **Host port mapping (host:container):** 8002:8000
- **Principais variáveis de ambiente:**
    - `DATABASE_URL` (ex: postgresql+asyncpg://patient:patient_pass@db-patient:5432/patient_db)
    - `RABBITMQ_URL` (ex: amqp://promptuario:promptuario_pass@rabbitmq:5672/)
    - `JWT_SECRET_KEY`, `JWT_ALGORITHM`
    - `SERVICE_NAME`, `LOG_LEVEL`

Inclua estes detalhes nas seções de Quickstart e exemplos de `docker-compose`/`.env`.

---

# Quickstart padronizado

```bash
curl http://localhost:8002/healthz
curl http://localhost:8002/docs
```

Via gateway, os recursos de paciente ficam em `http://localhost:8000/api/v1/patients/*`.
```