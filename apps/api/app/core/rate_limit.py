from __future__ import annotations

import time
from functools import lru_cache
from typing import Any, cast

from fastapi import HTTPException, Request
from redis import Redis
from redis.exceptions import RedisError
from slowapi import Limiter
from slowapi.util import get_remote_address

from apps.api.app.core.config import Settings

_MEMORY_LIMITS: dict[str, tuple[int, int]] = {}


def create_limiter(settings: Settings) -> Limiter:
    storage_uri = settings.redis_url or "memory://"
    return Limiter(key_func=get_remote_address, storage_uri=storage_uri)


@lru_cache
def _redis_client(redis_url: str) -> Redis:
    return Redis.from_url(redis_url)


def _memory_increment(key: str, *, window_seconds: int) -> tuple[int, int]:
    now = int(time.time())
    count, expires_at = _MEMORY_LIMITS.get(key, (0, now + window_seconds))
    if expires_at <= now:
        count = 0
        expires_at = now + window_seconds
    count += 1
    _MEMORY_LIMITS[key] = (count, expires_at)
    return count, max(expires_at - now, 1)


def _redis_increment(settings: Settings, key: str, *, window_seconds: int) -> tuple[int, int]:
    client = cast(Any, _redis_client(settings.redis_url))
    count = int(client.incr(key))
    if count == 1:
        client.expire(key, window_seconds)
    ttl = int(client.ttl(key))
    return count, ttl if ttl > 0 else window_seconds


def _rate_limit_identity(request: Request) -> str:
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        return forwarded_for.split(",", maxsplit=1)[0].strip()
    if request.client is not None:
        return request.client.host
    return "unknown"


def enforce_fixed_window_rate_limit(
    request: Request,
    settings: Settings,
    *,
    key: str,
    limit: int,
    window_seconds: int,
) -> None:
    if not settings.redis_url and settings.app_env != "production":
        return
    rate_key = f"rate_limit:{key}:{int(time.time()) // window_seconds}"
    try:
        if settings.redis_url:
            count, retry_after = _redis_increment(settings, rate_key, window_seconds=window_seconds)
        else:
            count, retry_after = _memory_increment(rate_key, window_seconds=window_seconds)
    except RedisError as exc:
        if settings.app_env == "production":
            raise HTTPException(status_code=503, detail="Rate limiter unavailable") from exc
        count, retry_after = _memory_increment(rate_key, window_seconds=window_seconds)
    if count > limit:
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded",
            headers={"Retry-After": str(retry_after)},
        )


def enforce_ip_rate_limit(
    request: Request,
    settings: Settings,
    *,
    scope: str,
    limit: int,
    window_seconds: int,
) -> None:
    enforce_fixed_window_rate_limit(
        request,
        settings,
        key=f"ip:{scope}:{_rate_limit_identity(request)}",
        limit=limit,
        window_seconds=window_seconds,
    )
