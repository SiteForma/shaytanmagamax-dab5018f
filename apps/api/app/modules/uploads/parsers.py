from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Any

import pandas as pd

CSV_ENCODINGS = ("utf-8", "utf-8-sig", "cp1251", "latin1")


@dataclass(slots=True)
class ParseResult:
    frame: pd.DataFrame
    parser: str
    encoding: str | None


def _clean_frame(frame: pd.DataFrame) -> pd.DataFrame:
    normalized = frame.copy()
    normalized.columns = [str(column).strip() for column in normalized.columns]
    normalized = normalized.dropna(how="all")
    normalized = normalized.where(pd.notna(normalized), None)
    return normalized


def read_upload_payload(payload: bytes, file_name: str) -> ParseResult:
    suffix = Path(file_name).suffix.lower()
    if suffix in {".xlsx", ".xls"}:
        frame = pd.read_excel(BytesIO(payload))
        return ParseResult(frame=_clean_frame(frame), parser="xlsx", encoding=None)

    last_error: Exception | None = None
    for encoding in CSV_ENCODINGS:
        try:
            frame = pd.read_csv(BytesIO(payload), encoding=encoding, sep=None, engine="python")
            return ParseResult(frame=_clean_frame(frame), parser="csv", encoding=encoding)
        except UnicodeDecodeError as exc:
            last_error = exc
            continue
        except Exception as exc:
            last_error = exc
            for separator in (",", ";", "\t"):
                try:
                    frame = pd.read_csv(BytesIO(payload), encoding=encoding, sep=separator)
                    return ParseResult(frame=_clean_frame(frame), parser="csv", encoding=encoding)
                except UnicodeDecodeError as unicode_exc:
                    last_error = unicode_exc
                    break
                except Exception as separator_exc:
                    last_error = separator_exc
                    continue
    if last_error is not None:
        raise last_error
    frame = pd.read_csv(BytesIO(payload))
    return ParseResult(frame=_clean_frame(frame), parser="csv", encoding="utf-8")


def read_upload_frame(file_path: Path) -> ParseResult:
    return read_upload_payload(file_path.read_bytes(), file_path.name)


def sanitize_value(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if hasattr(value, "isoformat") and not isinstance(value, str):
        try:
            return value.isoformat()
        except TypeError:
            pass
    if isinstance(value, float) and pd.isna(value):
        return None
    if isinstance(value, str):
        cleaned = value.strip()
        return cleaned or None
    return value


def build_preview_payload(frame: pd.DataFrame, limit: int = 5) -> dict[str, object]:
    sample_rows: list[dict[str, object | None]] = []
    for _, row in frame.head(limit).iterrows():
        sample_rows.append({str(column): sanitize_value(row[column]) for column in frame.columns})
    return {
        "headers": [str(column) for column in frame.columns],
        "sample_rows": sample_rows,
        "sample_row_count": len(sample_rows),
        "empty_row_count": int(frame.isna().all(axis=1).sum()) if not frame.empty else 0,
    }


def raw_row_payload(row: pd.Series) -> dict[str, object | None]:
    return {str(column): sanitize_value(row[column]) for column in row.index}
