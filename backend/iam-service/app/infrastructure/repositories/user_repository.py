from __future__ import annotations

import hashlib
from datetime import datetime, timezone

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.models.user import RefreshToken, User


class UserRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, user_id: str) -> User | None:
        result = await self.session.execute(
            select(User).where(User.id == user_id)
        )
        return result.scalar_one_or_none()

    async def get_by_email(self, email: str) -> User | None:
        result = await self.session.execute(
            select(User).where(User.email == email.lower())
        )
        return result.scalar_one_or_none()

    async def list_users(
        self,
        page: int = 1,
        size: int = 20,
        role: str | None = None,
        is_active: bool | None = None,
    ) -> tuple[list[User], int]:
        query = select(User)
        count_query = select(func.count()).select_from(User)
        if role:
            query = query.where(User.role == role)
            count_query = count_query.where(User.role == role)
        if is_active is not None:
            query = query.where(User.is_active == is_active)
            count_query = count_query.where(User.is_active == is_active)
        total = await self.session.scalar(count_query) or 0
        result = await self.session.execute(
            query.offset((page - 1) * size).limit(size).order_by(User.created_at.desc())
        )
        return list(result.scalars().all()), total

    async def create(self, user: User) -> User:
        self.session.add(user)
        await self.session.flush()
        await self.session.refresh(user)
        return user

    async def update(self, user: User) -> User:
        await self.session.flush()
        await self.session.refresh(user)
        return user

    async def exists_by_email(self, email: str) -> bool:
        result = await self.session.scalar(
            select(func.count()).select_from(User).where(User.email == email.lower())
        )
        return (result or 0) > 0


class RefreshTokenRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    @staticmethod
    def _hash(token: str) -> str:
        return hashlib.sha256(token.encode()).hexdigest()

    async def save(self, refresh_token: RefreshToken) -> None:
        self.session.add(refresh_token)
        await self.session.flush()

    async def get_valid(self, token: str) -> RefreshToken | None:
        token_hash = self._hash(token)
        now = datetime.now(timezone.utc)
        result = await self.session.execute(
            select(RefreshToken).where(
                RefreshToken.token_hash == token_hash,
                RefreshToken.revoked == False,
                RefreshToken.expires_at > now,
            )
        )
        return result.scalar_one_or_none()

    async def revoke(self, token: str) -> None:
        rt = await self.get_valid(token)
        if rt:
            rt.revoked = True
            await self.session.flush()

    async def revoke_all_for_user(self, user_id: str) -> None:
        result = await self.session.execute(
            select(RefreshToken).where(
                RefreshToken.user_id == user_id,
                RefreshToken.revoked == False,
            )
        )
        for rt in result.scalars().all():
            rt.revoked = True
        await self.session.flush()
