from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from apps.api.app.api.dependencies import (
    get_settings_dependency,
    require_authenticated_rate_limit,
    require_user,
)
from apps.api.app.core.config import Settings
from apps.api.app.core.rate_limit import enforce_ip_rate_limit
from apps.api.app.db.models import User
from apps.api.app.db.session import get_db
from apps.api.app.modules.audit.service import record_audit_event
from apps.api.app.modules.auth.schemas import (
    AccessTokenResponse,
    CurrentUserResponse,
    LoginRequest,
    LogoutResponse,
    RefreshTokenRequest,
    TokenResponse,
    UpdateCurrentUserRequest,
)
from apps.api.app.modules.auth.service import (
    login,
    refresh_access_token,
    revoke_refresh_token,
    to_current_user,
    update_current_user,
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
def login_route(
    request: Request,
    payload: LoginRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings_dependency),
) -> TokenResponse:
    enforce_ip_rate_limit(request, settings, scope="auth_login", limit=10, window_seconds=60)
    token = login(db, settings, payload.email, payload.password)
    record_audit_event(
        db,
        actor_user_id=token.user_id,
        action="auth.login",
        target_type="user",
        target_id=token.user_id,
        context={"email": token.email, "roles": token.roles},
    )
    db.commit()
    return token


@router.post("/refresh", response_model=AccessTokenResponse)
def refresh_route(
    request: Request,
    payload: RefreshTokenRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings_dependency),
) -> AccessTokenResponse:
    enforce_ip_rate_limit(request, settings, scope="auth_refresh", limit=10, window_seconds=60)
    return refresh_access_token(db, settings, payload.refresh_token)


@router.post("/logout", response_model=LogoutResponse)
def logout_route(
    payload: RefreshTokenRequest,
    _: None = Depends(require_authenticated_rate_limit),
    current_user: User = Depends(require_user),
    db: Session = Depends(get_db),
) -> LogoutResponse:
    revoke_refresh_token(db, current_user, payload.refresh_token)
    record_audit_event(
        db,
        actor_user_id=current_user.id,
        action="auth.logout",
        target_type="user",
        target_id=current_user.id,
    )
    db.commit()
    return LogoutResponse()


@router.get("/me", response_model=CurrentUserResponse)
def me_route(
    _: None = Depends(require_authenticated_rate_limit),
    current_user: User = Depends(require_user),
    db: Session = Depends(get_db),
) -> CurrentUserResponse:
    return to_current_user(db, current_user)


@router.patch("/me", response_model=CurrentUserResponse)
def update_me_route(
    payload: UpdateCurrentUserRequest,
    _: None = Depends(require_authenticated_rate_limit),
    current_user: User = Depends(require_user),
    db: Session = Depends(get_db),
) -> CurrentUserResponse:
    updated_user = update_current_user(
        db,
        current_user,
        first_name=payload.first_name,
        last_name=payload.last_name,
        current_password=payload.current_password,
        new_password=payload.new_password,
    )
    record_audit_event(
        db,
        actor_user_id=current_user.id,
        action="auth.profile_update",
        target_type="user",
        target_id=current_user.id,
        context={"password_changed": bool(payload.new_password)},
    )
    db.commit()
    return updated_user
