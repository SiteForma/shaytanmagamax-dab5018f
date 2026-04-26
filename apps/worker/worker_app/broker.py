from __future__ import annotations

import dramatiq
from dramatiq.brokers.redis import RedisBroker

from apps.api.app.core.config import get_settings
from apps.api.app.core.observability import configure_worker_observability
from apps.api.app.db.session import engine

settings = get_settings()
configure_worker_observability(settings, engine)
broker = RedisBroker(url=settings.redis_url)
dramatiq.set_broker(broker)
