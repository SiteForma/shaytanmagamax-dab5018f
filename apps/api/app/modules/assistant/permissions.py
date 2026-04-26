from __future__ import annotations

from sqlalchemy.orm import object_session

from apps.api.app.core.errors import DomainError
from apps.api.app.db.models import User
from apps.api.app.modules.access.service import user_has_capability

INTERNAL_ANALYTICS_READ_RESOURCES = frozenset(
    {
        "dashboard",
        "catalog",
        "clients",
        "stock",
        "inbound",
        "sales",
        "reserve",
        "uploads",
        "mapping",
        "quality",
        "reports",
    }
)


def user_has_assistant_internal_analytics(user: User | None) -> bool:
    if user is None:
        return False
    db = object_session(user)
    if db is None:
        return False
    return user_has_capability(db, user, "assistant", "internal_analytics") or user_has_capability(
        db, user, "assistant", "full_access"
    )


def _internal_analytics_covers(user: User | None, resource: str, action: str) -> bool:
    return (
        action == "read"
        and resource in INTERNAL_ANALYTICS_READ_RESOURCES
        and user_has_assistant_internal_analytics(user)
    )


def require_assistant_tool_capabilities(
    user: User | None,
    tool_spec: object,
    params: dict[str, object] | None = None,
) -> None:
    if user is None:
        raise DomainError(
            code="authentication_required",
            message="Требуется аутентификация",
            status_code=401,
        )
    db = object_session(user)
    if db is None:
        raise DomainError(
            code="assistant_permission_context_missing",
            message="Не удалось проверить права пользователя для assistant tool.",
            status_code=403,
        )
    if hasattr(tool_spec, "capabilities_for"):
        required = tool_spec.capabilities_for(params or {})  # type: ignore[attr-defined]
    else:
        required = getattr(tool_spec, "required_capabilities", ())
    for resource, action in required:
        if _internal_analytics_covers(user, resource, action):
            continue
        if not user_has_capability(db, user, resource, action):
            raise DomainError(
                code="permission_denied",
                message="Недостаточно прав для чтения данных через MAGAMAX AI",
                details={
                    "tool": getattr(tool_spec, "name", None),
                    "permission_denied_tool": getattr(tool_spec, "name", None),
                    "resource": resource,
                    "action": action,
                },
                status_code=403,
            )
