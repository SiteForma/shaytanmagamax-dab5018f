from __future__ import annotations

import hashlib
import secrets
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from apps.api.app.common.utils import utc_now
from apps.api.app.core.config import Settings
from apps.api.app.core.errors import DomainError
from apps.api.app.core.security import create_access_token, hash_password, verify_password
from apps.api.app.db.models import RefreshToken, User
from apps.api.app.modules.access.service import resolve_user_capabilities
from apps.api.app.modules.auth.schemas import (
    AccessTokenResponse,
    CurrentUserResponse,
    TokenResponse,
)

REFRESH_TOKEN_DAYS = 7


def _split_full_name(full_name: str) -> tuple[str, str]:
    parts = full_name.strip().split(maxsplit=1)
    if not parts:
        return "", ""
    return parts[0], parts[1] if len(parts) > 1 else ""


def _hash_refresh_token(refresh_token: str) -> str:
    return hashlib.sha256(refresh_token.encode("utf-8")).hexdigest()


def _new_refresh_token() -> str:
    return secrets.token_urlsafe(32)


def login(db: Session, settings: Settings, email: str, password: str) -> TokenResponse:
    user = db.scalar(select(User).options(joinedload(User.roles)).where(User.email == email))
    if user is None or not verify_password(password, user.password_hash):
        raise DomainError(
            code="invalid_credentials", message="Неверный email или пароль", status_code=401
        )
    role_codes = [user_role.role.code for user_role in user.roles]
    access_token = create_access_token(settings, subject=user.id, extra={"roles": role_codes})
    refresh_token = _new_refresh_token()
    db.add(
        RefreshToken(
            user_id=user.id,
            token_hash=_hash_refresh_token(refresh_token),
            expires_at=utc_now() + timedelta(days=REFRESH_TOKEN_DAYS),
        )
    )
    capabilities = resolve_user_capabilities(db, user)
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user_id=user.id,
        email=user.email,
        full_name=user.full_name,
        roles=role_codes,
        capabilities=capabilities,
    )


def refresh_access_token(
    db: Session, settings: Settings, refresh_token: str
) -> AccessTokenResponse:
    token_hash = _hash_refresh_token(refresh_token)
    stored = db.scalar(
        select(RefreshToken)
        .join(User, User.id == RefreshToken.user_id)
        .options(joinedload(RefreshToken.user).joinedload(User.roles))
        .where(
            RefreshToken.token_hash == token_hash,
            RefreshToken.revoked_at.is_(None),
            RefreshToken.expires_at > utc_now(),
            User.is_active.is_(True),
        )
    )
    if stored is None:
        raise DomainError(
            code="invalid_refresh_token", message="Refresh token недействителен", status_code=401
        )
    role_codes = [user_role.role.code for user_role in stored.user.roles]
    return AccessTokenResponse(
        access_token=create_access_token(
            settings, subject=stored.user_id, extra={"roles": role_codes}
        )
    )


def revoke_refresh_token(db: Session, user: User, refresh_token: str) -> None:
    stored = db.scalar(
        select(RefreshToken).where(
            RefreshToken.user_id == user.id,
            RefreshToken.token_hash == _hash_refresh_token(refresh_token),
            RefreshToken.revoked_at.is_(None),
        )
    )
    if stored is None:
        raise DomainError(
            code="invalid_refresh_token", message="Refresh token недействителен", status_code=401
        )
    stored.revoked_at = utc_now()
    db.add(stored)


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

    user.full_name = " ".join(
        part for part in (normalized_first_name, normalized_last_name) if part
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return to_current_user(db, user)
