from datetime import datetime

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from geodom_backend.db.models import UserSession

class UserSessionRepository:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def create(self, *, user_id: int, token_hash: str, expires_at: datetime) -> UserSession:
        user_session = UserSession(
            user_id=user_id,
            token_hash=token_hash,
            expires_at=expires_at,
        )

        self._session.add(user_session)
        await self._session.flush()

        return user_session

    async def get_by_token_hash(self, token_hash: str) -> UserSession | None:
        statement = (
            select(UserSession)
            .options(joinedload(UserSession.user))
            .where(UserSession.token_hash == token_hash)
        )

        result = await self._session.execute(statement)

        return result.scalar_one_or_none()

    async def delete_by_token_hash(self, token_hash: str):
        statement = delete(UserSession).where(UserSession.token_hash == token_hash)

        await self._session.execute(statement)

    async def delete_expired(self, now: datetime):
        statement = delete(UserSession).where(UserSession.expires_at <= now)
        await self._session.execute(statement)
