from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from apps.api.app.core.config import Settings
from apps.api.app.core.errors import DomainError
from apps.api.app.core.security import create_access_token, hash_password, verify_password
from apps.api.app.db.models import User
from apps.api.app.modules.access.service import resolve_user_capabilities
from apps.api.app.modules.auth.schemas import CurrentUserResponse, TokenResponse


def _split_full_name(full_name: str) -> tuple[str, str]:
    parts = full_name.strip().split(maxsplit=1)
    if not parts:
        return "", ""
    return parts[0], parts[1] if len(parts) > 1 else ""


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
    first_name, last_name = _split_full_name(user.full_name)
    return CurrentUserResponse(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        first_name=first_name,
        last_name=last_name,
        roles=[user_role.role.code for user_role in user.roles],
        capabilities=resolve_user_capabilities(db, user),
    )


def update_current_user(
    db: Session,
    user: User,
    *,
    first_name: str,
    last_name: str,
    current_password: str | None = None,
    new_password: str | None = None,
) -> CurrentUserResponse:
    normalized_first_name = first_name.strip()
    normalized_last_name = last_name.strip()
    if not normalized_first_name:
        raise DomainError(
            code="profile_first_name_required",
            message="Имя обязательно",
            status_code=422,
        )

    if new_password:
        if not current_password or not verify_password(current_password, user.password_hash):
            raise DomainError(
                code="invalid_current_password",
                message="Текущий пароль указан неверно",
                status_code=400,
            )
        user.password_hash = hash_password(new_password)

    user.full_name = " ".join(part for part in (normalized_first_name, normalized_last_name) if part)
    db.add(user)
    db.commit()
    db.refresh(user)
    return to_current_user(db, user)
