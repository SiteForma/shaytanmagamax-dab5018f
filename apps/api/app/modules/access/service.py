from __future__ import annotations

from functools import lru_cache

from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.api.app.db.models import AccessPolicy, User

Capability = tuple[str, str]

KNOWN_CAPABILITIES: tuple[Capability, ...] = (
    ("dashboard", "read"),
    ("catalog", "read"),
    ("clients", "read"),
    ("stock", "read"),
    ("inbound", "read"),
    ("inbound", "sync"),
    ("sales", "read"),
    ("reserve", "read"),
    ("reserve", "run"),
    ("uploads", "read"),
    ("uploads", "write"),
    ("uploads", "apply"),
    ("mapping", "read"),
    ("mapping", "write"),
    ("quality", "read"),
    ("quality", "resolve"),
    ("reports", "read"),
    ("assistant", "query"),
    ("assistant", "internal_analytics"),
    ("assistant", "full_access"),
    ("exports", "generate"),
    ("exports", "download"),
    ("admin", "read"),
    ("admin", "manage-users"),
    ("settings", "manage"),
)


@lru_cache
def all_capability_keys() -> tuple[str, ...]:
    return tuple(f"{resource}:{action}" for resource, action in KNOWN_CAPABILITIES)


def role_codes_for_user(user: User | None) -> list[str]:
    if user is None:
        return []
    return [assignment.role.code for assignment in user.roles]


def capability_key(resource: str, action: str) -> str:
    return f"{resource}:{action}"


def _matches(policy: AccessPolicy, resource: str, action: str) -> bool:
    return (policy.resource == "*" or policy.resource == resource) and (
        policy.action == "*" or policy.action == action
    )


def _policies_for_roles(db: Session, role_codes: list[str]) -> list[AccessPolicy]:
    if not role_codes:
        return []
    return db.scalars(select(AccessPolicy).where(AccessPolicy.role_code.in_(role_codes))).all()


def user_has_capability(db: Session, user: User | None, resource: str, action: str) -> bool:
    policies = _policies_for_roles(db, role_codes_for_user(user))
    allowed = False
    for policy in policies:
        if not _matches(policy, resource, action):
            continue
        if policy.effect == "deny":
            return False
        if policy.effect == "allow":
            allowed = True
    return allowed


def resolve_user_capabilities(db: Session, user: User | None) -> list[str]:
    policies = _policies_for_roles(db, role_codes_for_user(user))
    allowed: set[str] = set()
    denied: set[str] = set()
    for policy in policies:
        matching_keys = [
            key
            for resource, action in KNOWN_CAPABILITIES
            if _matches(policy, resource, action)
            for key in [capability_key(resource, action)]
        ]
        if policy.resource == "*" and policy.action == "*":
            matching_keys = list(all_capability_keys())
        if policy.effect == "deny":
            denied.update(matching_keys)
        elif policy.effect == "allow":
            allowed.update(matching_keys)
    return sorted(key for key in allowed if key not in denied)
