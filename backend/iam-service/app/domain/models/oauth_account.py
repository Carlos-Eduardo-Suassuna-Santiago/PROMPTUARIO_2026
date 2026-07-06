from __future__ import annotations
import uuid
from datetime import datetime, timezone
from sqlalchemy import DateTime, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from shared.models.database import Base


def _now(): return datetime.now(timezone.utc)
def _uuid(): return str(uuid.uuid4())


class OAuthAccount(Base):
    """
    Vincula um usuário do sistema a uma conta de provedor OAuth externo.
    Um usuário pode ter múltiplas contas (ex: GitHub + Google).
    """
    __tablename__ = "oauth_accounts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    # FK para users.id — sem ForeignKey declarado para evitar dependência circular
    # com Base; a integridade é garantida pela lógica da aplicação
    provider: Mapped[str] = mapped_column(String(20), nullable=False)
    # "github" ou "google"
    provider_user_id: Mapped[str] = mapped_column(String(100), nullable=False)
    provider_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    __table_args__ = (
        UniqueConstraint("provider", "provider_user_id", name="uq_oauth_provider_user"),
    )