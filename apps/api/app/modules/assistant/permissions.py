from __future__ import annotations

from sqlalchemy.orm import object_session

from apps.api.app.core.errors import DomainError
from apps.api.app.db.models import User
from apps.api.app.modules.access.service import user_has_capability


def require_assistant_tool_capabilities(user: User | None, tool_spec: object) -> None:
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
    required = getattr(tool_spec, "required_capabilities", ())
    for resource, action in required:
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
