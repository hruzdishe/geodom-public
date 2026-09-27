from typing import Annotated

from fastapi import Depends, HTTPException, Request, status

from geodom_backend.auth.exceptions import InvalidSessionError
from geodom_backend.auth.service import AuthService
from geodom_backend.config import settings
from geodom_backend.db import DatabaseSession
from geodom_backend.db.models import User
from geodom_backend.db.repositories import UserRepository, UserSessionRepository


def get_user_repository(session: DatabaseSession) -> UserRepository:
    return UserRepository(session)

UserRepositoryDep = Annotated[
    UserRepository,
    Depends(get_user_repository)
]

def get_user_session_repository(session: DatabaseSession) -> UserSessionRepository:
    return UserSessionRepository(session)

UserSessionRepositoryDep = Annotated[
    UserSessionRepository,
    Depends(get_user_session_repository)
]

def get_auth_service(session: DatabaseSession, user_repository: UserRepositoryDep, session_repository: UserSessionRepositoryDep) -> AuthService:  # pyright: ignore[reportInvalidTypeForm]
    return AuthService(
        session=session,
        user_repository=user_repository,
        session_repository=session_repository
    )

AuthServiceDep = Annotated[
    AuthService,
    Depends(get_auth_service)
]

async def get_current_user(request: Request, auth_service: AuthServiceDep) -> User:
    token = request.cookies.get(settings.auth_cookie_name)
    if token is None: raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")

    try:
        return await auth_service.get_user_by_token(token)
    except InvalidSessionError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired session") from e

async def get_optional_current_user(request: Request, auth_service: AuthServiceDep) -> User | None:
    token = request.cookies.get(settings.auth_cookie_name)
    if token is None: return None

    try:
        return await auth_service.get_user_by_token(token)
    except InvalidSessionError:
        return None

OptionalCurrentUser = Annotated[
    User | None,
    Depends(get_optional_current_user)
]

CurrentUser = Annotated[
    User,
    Depends(get_current_user)
]
