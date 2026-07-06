from __future__ import annotations
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.domain.models.oauth_account import OAuthAccount


class OAuthRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_provider(self, provider: str, provider_user_id: str) -> OAuthAccount | None:
        result = await self.session.execute(
            select(OAuthAccount).where(
                OAuthAccount.provider == provider,
                OAuthAccount.provider_user_id == provider_user_id,
            )
        )
        return result.scalar_one_or_none()

    async def create(self, account: OAuthAccount) -> OAuthAccount:
        self.session.add(account)
        await self.session.flush()
        await self.session.refresh(account)
        return account

    async def list_by_user(self, user_id: str) -> list[OAuthAccount]:
        result = await self.session.execute(
            select(OAuthAccount).where(OAuthAccount.user_id == user_id)
        )
        return list(result.scalars().all())