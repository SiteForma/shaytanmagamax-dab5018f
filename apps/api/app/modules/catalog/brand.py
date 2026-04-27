from __future__ import annotations

import re
from typing import Any

UNKNOWN_BRAND = "Не указан"

BRAND_PATTERNS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("Lemax Prof", ("lemax prof", "lemax-prof", "lemax_prof", "lemaxprof", "лемакс проф")),
    ("Lemax", ("lemax", "лемакс")),
    ("Kerron", ("kerron", "керрон")),
    ("Homakoll", ("homakoll", "хомакол")),
    ("Homaprof", ("homaprof", "хомапроф")),
    ("Zigmund & Shtain", ("zigmund", "shtain", "zigmund&shtain", "зигмунд")),
    ("Cleanelle", ("cleanelle",)),
)


def _normalize(value: Any) -> str:
    text = str(value or "").replace("\xa0", " ").strip().lower().replace("ё", "е")
    return re.sub(r"\s+", " ", text)


def infer_brand(*values: Any) -> str:
    haystack = " ".join(_normalize(value) for value in values if value is not None)
    if not haystack:
        return UNKNOWN_BRAND
    for brand, patterns in BRAND_PATTERNS:
        if any(pattern in haystack for pattern in patterns):
            return brand
    return UNKNOWN_BRAND


def resolve_brand(existing_brand: str | None, *values: Any) -> str:
    inferred = infer_brand(*values)
    if inferred != UNKNOWN_BRAND:
        return inferred
    if existing_brand and existing_brand not in {UNKNOWN_BRAND, "MAGAMAX"}:
        return existing_brand
    return UNKNOWN_BRAND
