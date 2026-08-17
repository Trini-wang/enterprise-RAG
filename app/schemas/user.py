import re
from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


class UserRegister(BaseModel):
    email: str = Field(min_length=5, max_length=254)
    password: str = Field(min_length=8, max_length=128)
    full_name: str = Field(min_length=1, max_length=100)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        value = value.strip().lower()
        if not EMAIL_RE.match(value):
            raise ValueError("邮箱格式不正确")
        return value

    @field_validator("full_name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        return value.strip()


class LoginRequest(BaseModel):
    email: str
    password: str

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return value.strip().lower()


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    email: str
    full_name: str
    role: Literal["admin", "user"]
    is_active: bool
    created_at: datetime
    updated_at: datetime


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserResponse


class UserUpdate(BaseModel):
    full_name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    password: Optional[str] = Field(default=None, min_length=8, max_length=128)

    @field_validator("full_name")
    @classmethod
    def normalize_name(cls, value: Optional[str]) -> Optional[str]:
        return value.strip() if value is not None else None


class AdminUserUpdate(UserUpdate):
    role: Optional[Literal["admin", "user"]] = None
    is_active: Optional[bool] = None
