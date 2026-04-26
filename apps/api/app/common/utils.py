from __future__ import annotations

import re
import unicodedata
from datetime import UTC, datetime
from uuid import uuid4


def utc_now() -> datetime:
    return datetime.now(tz=UTC)


def generate_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:12]}"


def normalize_header(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value)
    normalized = normalized.lower().strip()
    normalized = re.sub(r"[\W]+", "_", normalized, flags=re.UNICODE)
    return normalized.strip("_")
