from __future__ import annotations

import json
import logging
from datetime import UTC, datetime

from apps.api.app.core.request_context import get_job_id, get_request_id, get_trace_id


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.now(tz=UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": get_request_id(),
            "trace_id": get_trace_id(),
            "job_id": get_job_id(),
        }
        if hasattr(record, "job_id") and getattr(record, "job_id") is not None:
            payload["job_id"] = getattr(record, "job_id")
        if hasattr(record, "trace_id") and getattr(record, "trace_id") is not None:
            payload["trace_id"] = getattr(record, "trace_id")
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def configure_logging() -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(logging.INFO)
