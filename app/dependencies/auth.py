import os
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import InvalidTokenError

from app.services.user_store import user_store

JWT_SECRET = os.getenv("JWT_SECRET", "change-this-secret-in-production")
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("JWT_EXPIRE_MINUTES", "60"))
bearer_scheme = HTTPBearer(auto_error=False)


def create_access_token(user_id: str) -> tuple[str, int]:
    expires_in = ACCESS_TOKEN_EXPIRE_MINUTES * 60
    now = datetime.now(timezone.utc)
    payload = {"sub": user_id, "type": "access", "iat": now,
               "exp": now + timedelta(seconds=expires_in)}
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM), expires_in


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> dict[str, Any]:
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="登录凭证无效或已过期",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise unauthorized
    try:
        payload = jwt.decode(credentials.credentials, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        user_id = payload.get("sub")
        if not user_id or payload.get("type") != "access":
            raise unauthorized
    except InvalidTokenError as exc:
        raise unauthorized from exc
    user = user_store.get_user(user_id)
    if user is None or not user["is_active"]:
        raise unauthorized
    return user


def get_current_admin(user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
    if user["role"] != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="需要管理员权限")
    return user
