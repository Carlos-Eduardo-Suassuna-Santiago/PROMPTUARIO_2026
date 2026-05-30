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

from shared.observability import instrument_sqlalchemy_engine


class Base(DeclarativeBase):
    pass


def build_engine(database_url: str):
    engine = create_async_engine(
        database_url,
        echo=False,
        pool_pre_ping=True,
        pool_size=10,
        max_overflow=20,
    )
    instrument_sqlalchemy_engine(engine)
    return engine


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
