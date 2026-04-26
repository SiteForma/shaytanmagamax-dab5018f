from __future__ import annotations

from collections.abc import Callable

from fastapi import Depends, Header
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from apps.api.app.core.config import Settings, get_settings
from apps.api.app.core.errors import DomainError
from apps.api.app.core.security import decode_access_token
from apps.api.app.db.models import User, UserRole
from apps.api.app.db.session import get_db
from apps.api.app.modules.access.service import user_has_capability
from apps.api.app.modules.audit.service import record_audit_event

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)


def get_settings_dependency() -> Settings:
    return get_settings()


def get_current_user(
    token: str | None = Depends(oauth2_scheme),
    x_dev_user: str | None = Header(default=None),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings_dependency),
) -> User | None:
    user_id: str | None = x_dev_user if settings.app_env == "development" else None
    if token:
        payload = decode_access_token(settings, token)
        user_id = payload.get("sub")
    if not user_id:
        return None
    return db.scalar(
        select(User)
        .options(joinedload(User.roles).joinedload(UserRole.role))
        .where(User.id == user_id)
    )


def require_user(current_user: User | None = Depends(get_current_user)) -> User:
    if current_user is None:
        raise DomainError(
            code="authentication_required",
            message="Требуется аутентификация",
            status_code=401,
        )
    return current_user


def require_capability(resource: str, action: str) -> Callable[..., User]:
    def dependency(
        db: Session = Depends(get_db),
        current_user: User = Depends(require_user),
    ) -> User:
        if user_has_capability(db, current_user, resource, action):
            return current_user
        record_audit_event(
            db,
            actor_user_id=current_user.id,
            action="auth.permission_denied",
            target_type=resource,
            target_id=action,
            status="denied",
            context={"resource": resource, "required_action": action},
        )
        db.commit()
        raise DomainError(
            code="permission_denied",
            message="Недостаточно прав для выполнения операции",
            details={"resource": resource, "action": action},
            status_code=403,
        )

    return dependency
