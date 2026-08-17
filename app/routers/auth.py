from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status

from app.dependencies.auth import create_access_token, get_current_user
from app.schemas.user import LoginRequest, TokenResponse, UserRegister, UserResponse
from app.services.user_store import user_store

router = APIRouter()


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(payload: UserRegister) -> dict[str, Any]:
    try:
        return user_store.create_user(payload.email, payload.password, payload.full_name)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest) -> TokenResponse:
    user = user_store.authenticate(payload.email, payload.password)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="邮箱或密码错误，或用户已被禁用",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token, expires_in = create_access_token(user["id"])
    return TokenResponse(
        access_token=token, expires_in=expires_in, user=UserResponse(**user)
    )


@router.get("/me", response_model=UserResponse)
def current_user(user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
    return user
