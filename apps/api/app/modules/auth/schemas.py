from __future__ import annotations

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
    roles: list[str]
    capabilities: list[str]
