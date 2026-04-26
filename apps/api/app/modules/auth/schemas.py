from __future__ import annotations

from pydantic import Field

from apps.api.app.common.schemas import ORMModel


class LoginRequest(ORMModel):
    email: str
    password: str


class TokenResponse(ORMModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str
    email: str
    full_name: str
    roles: list[str]
    capabilities: list[str]


class CurrentUserResponse(ORMModel):
    id: str
    email: str
    full_name: str
    first_name: str = ""
    last_name: str = ""
    roles: list[str]
    capabilities: list[str]


class UpdateCurrentUserRequest(ORMModel):
    first_name: str = Field(min_length=1, max_length=120)
    last_name: str = Field(default="", max_length=120)
    current_password: str | None = Field(default=None, min_length=1, max_length=255)
    new_password: str | None = Field(default=None, min_length=8, max_length=255)
