# ETAPA 6 — AI SERVICE (FASTAPI)

# 1. OBJETIVO

O `ai-service` será responsável por:

* Geração de resumos clínicos
* Simulação NLP
* Sugestões diagnósticas
* Processamento assíncrono
* Consumo de eventos clínicos
* Geração de insights
* Pipeline de IA desacoplado

---

# RESPONSABILIDADES

| Módulo                 | Responsabilidade       |
| ---------------------- | ---------------------- |
| NLP Engine             | Processamento textual  |
| Clinical Summary       | Resumo clínico         |
| Diagnostic Suggestions | Sugestões diagnósticas |
| Insight Generator      | Insights clínicos      |
| Async Consumers        | Consumo RabbitMQ       |
| AI Abstraction         | Provider abstraction   |

---

# 2. CLEAN ARCHITECTURE

```mermaid
graph TD

API[API Layer]

SERVICE[AI Service Layer]

NLP[NLP Engine]

ABSTRACTION[AI Provider Abstraction]

RABBIT[(RabbitMQ)]

DB[(PostgreSQL)]

API --> SERVICE

SERVICE --> NLP

SERVICE --> ABSTRACTION

SERVICE --> DB

RABBIT --> SERVICE
```

---

# 3. ESTRUTURA DO PROJETO

```text
ai-service/
├── app/
│
│   ├── api/
│   │   ├── router.py
│   │   └── v1/
│   │       ├── summary_routes.py
│   │       └── suggestion_routes.py
│   │
│   ├── core/
│   │   ├── config.py
│   │   ├── database.py
│   │   └── logging.py
│   │
│   ├── domain/
│   │   ├── models/
│   │   │   ├── clinical_summary.py
│   │   │   └── diagnostic_suggestion.py
│   │   │
│   │   └── enums/
│   │       └── insight_type.py
│   │
│   ├── schemas/
│   │   ├── summary_schema.py
│   │   └── suggestion_schema.py
│   │
│   ├── repositories/
│   │   ├── summary_repository.py
│   │   └── suggestion_repository.py
│   │
│   ├── services/
│   │   ├── ai_service.py
│   │   ├── summary_service.py
│   │   ├── suggestion_service.py
│   │   └── insight_service.py
│   │
│   ├── providers/
│   │   ├── base_provider.py
│   │   ├── local_nlp_provider.py
│   │   └── openai_provider.py
│   │
│   ├── messaging/
│   │   ├── rabbitmq.py
│   │   ├── consumer.py
│   │   └── handlers.py
│   │
│   ├── workers/
│   │   └── ai_worker.py
│   │
│   └── main.py
│
├── alembic/
├── Dockerfile
├── requirements.txt
├── docker-compose.yml
└── .env
```

---

# 4. REQUIREMENTS.TXT

```txt
fastapi
uvicorn[standard]

sqlalchemy
psycopg2-binary
alembic

pydantic
pydantic-settings

pika

httpx

asyncio

python-dotenv
```

---

# 5. CONFIGURAÇÃO

# app/core/config.py

```python
from pydantic_settings import BaseSettings


class Settings(BaseSettings):

    DATABASE_URL: str

    RABBITMQ_URL: str

    OPENAI_API_KEY: str | None = None

    AI_PROVIDER: str = "local"

    class Config:
        env_file = ".env"


settings = Settings()
```

---

# 6. DATABASE

# app/core/database.py

```python
from sqlalchemy import create_engine

from sqlalchemy.orm import declarative_base
from sqlalchemy.orm import sessionmaker

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

# 7. CLINICAL SUMMARY MODEL

# app/domain/models/clinical_summary.py

```python
import uuid

from sqlalchemy import Column
from sqlalchemy import Text
from sqlalchemy import DateTime

from sqlalchemy.sql import func

from sqlalchemy.dialects.postgresql import UUID

from app.core.database import Base


class ClinicalSummary(Base):

    __tablename__ = "clinical_summaries"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )

    medical_record_id = Column(
        UUID(as_uuid=True),
        nullable=False
    )

    summary = Column(Text, nullable=False)

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now()
    )
```

---

# 8. DIAGNOSTIC SUGGESTION MODEL

# app/domain/models/diagnostic_suggestion.py

```python
import uuid

from sqlalchemy import Column
from sqlalchemy import Text
from sqlalchemy import Float
from sqlalchemy import DateTime

from sqlalchemy.sql import func

from sqlalchemy.dialects.postgresql import UUID

from app.core.database import Base


class DiagnosticSuggestion(Base):

    __tablename__ = "diagnostic_suggestions"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )

    medical_record_id = Column(
        UUID(as_uuid=True),
        nullable=False
    )

    suggestion = Column(Text, nullable=False)

    confidence_score = Column(Float)

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now()
    )
```

---

# 9. SCHEMAS

# app/schemas/summary_schema.py

```python
from uuid import UUID

from pydantic import BaseModel


class SummaryResponse(BaseModel):

    id: UUID

    medical_record_id: UUID

    summary: str

    class Config:
        from_attributes = True
```

---

# app/schemas/suggestion_schema.py

```python
from uuid import UUID

from pydantic import BaseModel


class SuggestionResponse(BaseModel):

    id: UUID

    suggestion: str

    confidence_score: float

    class Config:
        from_attributes = True
```

---

# 10. AI PROVIDER ABSTRACTION

# app/providers/base_provider.py

```python
from abc import ABC
from abc import abstractmethod


class BaseAIProvider(ABC):

    @abstractmethod
    async def generate_summary(self, text: str):
        pass

    @abstractmethod
    async def generate_suggestion(self, text: str):
        pass
```

---

# 11. LOCAL NLP PROVIDER

# app/providers/local_nlp_provider.py

```python
from app.providers.base_provider import BaseAIProvider


class LocalNLPProvider(BaseAIProvider):

    async def generate_summary(self, text: str):

        return (
            "Clinical Summary: "
            + text[:300]
        )

    async def generate_suggestion(self, text: str):

        if "fever" in text.lower():
            return {
                "suggestion": "Possible infection",
                "confidence": 0.83
            }

        return {
            "suggestion": "Further evaluation required",
            "confidence": 0.55
        }
```

---

# 12. AI SERVICE

---

# Detalhes de implementação (extraído do ambiente)

- **Base path:** /api/v1 (rotas internas adicionais começam com `/ai`, ex: `/api/v1/ai/analyze`)
- **Health endpoint:** /healthz
- **Host port mapping (host:container):** 8004:8000
- **Principais variáveis de ambiente:**
    - `MONGODB_URL` (ex: mongodb://ai:ai_pass@db-ai:27017/ai_db?authSource=admin)
    - `RABBITMQ_URL` (ex: amqp://promptuario:promptuario_pass@rabbitmq:5672/)
    - `REDIS_URL` (ex: redis://redis:6379/2)
    - `LLM_API_KEY`, `LLM_MODEL`
    - `JWT_SECRET_KEY`, `JWT_ALGORITHM`
    - `SERVICE_NAME`, `LOG_LEVEL`

Use estes valores para gerar exemplos de `.env` e instruções de deploy locais/CI.

---

# Quickstart padronizado

```bash
curl http://localhost:8004/healthz
curl http://localhost:8004/docs
```

Via gateway, a análise de IA fica em `http://localhost:8000/api/v1/ai/analyze`.