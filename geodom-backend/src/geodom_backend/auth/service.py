from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from geodom_backend.auth.exceptions import (
    InvalidCredentialsError,
    InvalidSessionError,
    LoginAlreadyExistsError,
)
from geodom_backend.auth.security import (
    generate_session_token,
    hash_password,
    hash_session_token,
    verify_password,
)
from geodom_backend.config import settings
from geodom_backend.db.models import User
from geodom_backend.db.repositories import UserRepository, UserSessionRepository


@dataclass(slots=True)
class AuthenticatedSession:
    user: User
    token: str

class AuthService:
    def __init__(self, session: AsyncSession, user_repository: UserRepository, session_repository: UserSessionRepository):
        self._session = session
        self._users = user_repository
        self._sessions = session_repository

    async def register(self, *, login: str, password: str) -> AuthenticatedSession:
        existing_user = await self._users.get_by_login(login)
        if existing_user is not None: raise LoginAlreadyExistsError

        try:
            user = await self._users.create(
                login=login, password_hash=hash_password(password)
            )

            token = await self._create_session(user_id=user.id)

            await self._session.commit()
            await self._session.refresh(user)
        except IntegrityError as e:
            await self._session.rollback()
            raise LoginAlreadyExistsError from e
        except Exception:
            await self._session.rollback()
            raise

        return AuthenticatedSession(user=user, token=token)

    async def login(self, *, login: str, password: str) -> AuthenticatedSession:
        user = await self._users.get_by_login(login)
        if user is None: raise InvalidCredentialsError
        if not verify_password(password, user.password_hash): raise InvalidCredentialsError

        try:
            token = await self._create_session(user_id=user.id)
            await self._session.commit()
        except Exception:
            await self._session.rollback()
            raise

        return AuthenticatedSession(user=user, token=token)

    async def get_user_by_token(self, token: str) -> User:
        token_hash = hash_session_token(token)

        user_session = await self._sessions.get_by_token_hash(token_hash)
        if user_session is None: raise InvalidSessionError
        if user_session.expires_at <= datetime.now(UTC):
            await self._sessions.delete_by_token_hash(token_hash)
            await self._session.commit()
            raise InvalidSessionError

        return user_session.user

    async def logout(self, token: str):
        try:
            await self._sessions.delete_by_token_hash(hash_session_token(token))
            await self._session.commit()
        except Exception:
            await self._session.rollback()
            raise

    async def _create_session(self, *, user_id: int) -> str:
        token = generate_session_token()
        expires_at = datetime.now(UTC) + timedelta(hours=settings.auth_session_ttl_hours)

        await self._sessions.create(
            user_id=user_id,
            token_hash=hash_session_token(token),
            expires_at=expires_at,
        )

        return token
