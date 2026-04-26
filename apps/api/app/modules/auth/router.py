from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from apps.api.app.api.dependencies import get_settings_dependency, require_user
from apps.api.app.core.config import Settings
from apps.api.app.db.models import User
from apps.api.app.db.session import get_db
from apps.api.app.modules.audit.service import record_audit_event
from apps.api.app.modules.auth.schemas import (
    CurrentUserResponse,
    LoginRequest,
    TokenResponse,
    UpdateCurrentUserRequest,
)
from apps.api.app.modules.auth.service import login, to_current_user, update_current_user

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
def login_route(
    payload: LoginRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings_dependency),
) -> TokenResponse:
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


@router.get("/me", response_model=CurrentUserResponse)
def me_route(
    current_user: User = Depends(require_user),
    db: Session = Depends(get_db),
) -> CurrentUserResponse:
    return to_current_user(db, current_user)


@router.patch("/me", response_model=CurrentUserResponse)
def update_me_route(
    payload: UpdateCurrentUserRequest,
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
