from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from apps.api.app.core.config import Settings
from apps.api.app.core.errors import DomainError
from apps.api.app.core.security import create_access_token, verify_password
from apps.api.app.db.models import User
from apps.api.app.modules.access.service import resolve_user_capabilities
from apps.api.app.modules.auth.schemas import CurrentUserResponse, TokenResponse


def login(db: Session, settings: Settings, email: str, password: str) -> TokenResponse:
    user = db.scalar(select(User).options(joinedload(User.roles)).where(User.email == email))
    if user is None or not verify_password(password, user.password_hash):
        raise DomainError(code="invalid_credentials", message="Неверный email или пароль", status_code=401)
    role_codes = [user_role.role.code for user_role in user.roles]
    token = create_access_token(settings, subject=user.id, extra={"roles": role_codes})
    capabilities = resolve_user_capabilities(db, user)
    return TokenResponse(
        access_token=token,
        user_id=user.id,
        email=user.email,
        full_name=user.full_name,
        roles=role_codes,
        capabilities=capabilities,
    )


def to_current_user(db: Session, user: User) -> CurrentUserResponse:
    return CurrentUserResponse(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        roles=[user_role.role.code for user_role in user.roles],
        capabilities=resolve_user_capabilities(db, user),
    )
