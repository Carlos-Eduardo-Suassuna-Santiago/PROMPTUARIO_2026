from __future__ import annotations

import hashlib
from datetime import datetime, timezone

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.models.password_reset import PasswordResetToken


class PasswordResetRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    @staticmethod
    def _hash(token: str) -> str:
        return hashlib.sha256(token.encode()).hexdigest()

    async def save(self, reset_token: PasswordResetToken) -> None:
        self.session.add(reset_token)
        await self.session.flush()

    async def get_valid(self, token: str) -> PasswordResetToken | None:
        token_hash = self._hash(token)
        now = datetime.now(timezone.utc)
        result = await self.session.execute(
            select(PasswordResetToken).where(
                PasswordResetToken.token_hash == token_hash,
                PasswordResetToken.used == False,
                PasswordResetToken.expires_at > now,
            )
        )
        return result.scalar_one_or_none()

    async def mark_used(self, token: str) -> None:
        rt = await self.get_valid(token)
        if rt:
            rt.used = True
            await self.session.flush()

    async def invalidate_all_for_user(self, user_id: str) -> None:
        result = await self.session.execute(
            select(PasswordResetToken).where(
                PasswordResetToken.user_id == user_id,
                PasswordResetToken.used == False,
            )
        )
        for rt in result.scalars().all():
            rt.used = True
        await self.session.flush()