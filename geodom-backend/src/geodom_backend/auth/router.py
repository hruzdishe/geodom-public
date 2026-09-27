from fastapi import APIRouter, HTTPException, Request, Response, status

from geodom_backend.auth.cookies import delete_session_cookie, set_session_cookie
from geodom_backend.auth.dependencies import AuthServiceDep, CurrentUser
from geodom_backend.auth.exceptions import (
    InvalidCredentialsError,
    LoginAlreadyExistsError,
)
from geodom_backend.auth.schemas import AuthResponse, LoginRequest, RegisterRequest
from geodom_backend.config import settings
from geodom_backend.db.models import User
from geodom_backend.users.schemas import UserResponse

router = APIRouter(
    prefix="/auth",
    tags=["Auth"]
)
@router.post(
    "/register",
    response_model=AuthResponse,
    status_code=status.HTTP_201_CREATED
)
async def register(data: RegisterRequest, response: Response, auth_service: AuthServiceDep) -> AuthResponse:
    try:
        auth_session = await auth_service.register(login=data.login, password=data.password)
    except LoginAlreadyExistsError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Login already exists"
        ) from e

    set_session_cookie(response, auth_session.token)

    return AuthResponse(
        user=UserResponse.model_validate(auth_session.user)
    )

@router.post(
    "/login",
    response_model=AuthResponse
)
async def login(data: LoginRequest, response: Response, auth_service: AuthServiceDep) -> AuthResponse:
    try:
        auth_session = await auth_service.login(
            login=data.login,
            password=data.password
        )
    except InvalidCredentialsError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid login or password"
        ) from e

    set_session_cookie(response, auth_session.token)

    return AuthResponse(user=UserResponse.model_validate(auth_session.user))

@router.get(
    "/me",
    response_model=UserResponse
)
async def get_me(user: CurrentUser) -> User:
    return user

@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT
)
async def logout(request: Request, response: Response, auth_service: AuthServiceDep):
    token = request.cookies.get(settings.auth_cookie_name)
    if token is not None: await auth_service.logout(token)

    delete_session_cookie(response)
