"""
Async SQLAlchemy base — used by IAM, Patient, Clinical, Reporting services.
"""
from __future__ import annotations

from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


# Registra AuditLog no metadata compartilhado.
# Garante que Base.metadata.create_all() crie a tabela audit_logs
# em QUALQUER banco que usar este Base.
# A importação é feita aqui (não no início) para evitar importação circular:
# audit → database (já carregada → Base já definida)
from shared.audit import AuditLog as _AuditLog  # noqa: F401, E402


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


async def get_session(session_factory: async_sessionmaker) -> AsyncGenerator[AsyncSession, None]:
    async with session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
