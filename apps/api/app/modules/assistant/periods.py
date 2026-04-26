from __future__ import annotations

import calendar
import re
from dataclasses import dataclass
from datetime import date

MONTHS_RU = {
    "январ": 1,
    "феврал": 2,
    "март": 3,
    "марта": 3,
    "апрел": 4,
    "мая": 5,
    "май": 5,
    "июн": 6,
    "июл": 7,
    "август": 8,
    "сентябр": 9,
    "октябр": 10,
    "ноябр": 11,
    "декабр": 12,
}


@dataclass(frozen=True, slots=True)
class ParsedPeriod:
    date_from: str | None = None
    date_to: str | None = None
    current_period: str | None = None
    previous_period: str | None = None
    granularity: str | None = None
    label: str | None = None

    def as_range_params(self) -> dict[str, str]:
        result: dict[str, str] = {}
        if self.date_from:
            result["date_from"] = self.date_from
        if self.date_to:
            result["date_to"] = self.date_to
        return result


def _month_start(year: int, month: int) -> date:
    return date(year, month, 1)


def _month_end_marker(year: int, month: int) -> date:
    return date(year, month, calendar.monthrange(year, month)[1])


def _previous_month_marker(year: int, month: int) -> str:
    if month == 1:
        return f"{year - 1}-12"
    return f"{year}-{month - 1:02d}"


def _add_months(year: int, month: int, delta: int) -> tuple[int, int]:
    value = (year * 12 + month - 1) + delta
    return value // 12, value % 12 + 1


def _find_year(text: str, default_year: int | None) -> int:
    match = re.search(r"\b(20\d{2})\b", text)
    if match:
        return int(match.group(1))
    return default_year or date.today().year


def _find_month_token(text: str) -> tuple[str, int] | None:
    for token, month in MONTHS_RU.items():
        if token in text:
            return token, month
    return None


def _range_payload(
    start: date, end_marker: date, label: str, granularity: str = "month"
) -> ParsedPeriod:
    return ParsedPeriod(
        date_from=start.isoformat(),
        date_to=end_marker.isoformat(),
        current_period=start.strftime("%Y-%m"),
        previous_period=_previous_month_marker(start.year, start.month),
        granularity=granularity,
        label=label,
    )


def parse_period_text(
    text: str,
    *,
    default_year: int | None = None,
    today: date | None = None,
) -> ParsedPeriod:
    q = text.lower().replace("ё", "е")
    today = today or date.today()

    if "прошлый год" in q or "прошлом году" in q:
        year = today.year - 1
        return _range_payload(date(year, 1, 1), date(year, 12, 31), f"{year} год", "year")

    if "этот месяц" in q or "текущий месяц" in q:
        return _range_payload(
            _month_start(today.year, today.month),
            _month_end_marker(today.year, today.month),
            "этот месяц",
        )

    if "прошлый месяц" in q or "прошлым месяц" in q:
        year, month = _add_months(today.year, today.month, -1)
        return _range_payload(
            _month_start(year, month), _month_end_marker(year, month), "прошлый месяц"
        )

    recent_match = re.search(r"последн(?:ие|их|ий)?\s+(\d+)\s+месяц", q)
    if recent_match:
        months = max(int(recent_match.group(1)), 1)
        start_year, start_month = _add_months(today.year, today.month, -(months - 1))
        return _range_payload(
            _month_start(start_year, start_month),
            _month_end_marker(today.year, today.month),
            f"последние {months} мес.",
            "range",
        )

    quarter_match = re.search(r"\b(?:([1-4])\s*(?:квартал|кв\.?|q)|q\s*([1-4]))\s*(20\d{2})?\b", q)
    if quarter_match:
        quarter = int(quarter_match.group(1) or quarter_match.group(2))
        year = int(quarter_match.group(3) or _find_year(q, default_year))
        start_month = (quarter - 1) * 3 + 1
        end_month = start_month + 2
        return _range_payload(
            _month_start(year, start_month),
            _month_end_marker(year, end_month),
            f"{quarter} квартал {year}",
            "quarter",
        )

    range_match = re.search(
        r"(январ\w*|феврал\w*|март\w*|апрел\w*|ма[йя]|июн\w*|июл\w*|август\w*|сентябр\w*|октябр\w*|ноябр\w*|декабр\w*)\s*[-–—]\s*"
        r"(январ\w*|феврал\w*|март\w*|апрел\w*|ма[йя]|июн\w*|июл\w*|август\w*|сентябр\w*|октябр\w*|ноябр\w*|декабр\w*)\s*(20\d{2})?",
        q,
    )
    if range_match:
        first = _month_number(range_match.group(1))
        second = _month_number(range_match.group(2))
        if first and second:
            year = int(range_match.group(3) or _find_year(q, default_year))
            return _range_payload(
                _month_start(year, first),
                _month_end_marker(year, second),
                f"{_month_label(first)}-{_month_label(second)} {year}",
                "range",
            )

    month_token = _find_month_token(q)
    if month_token:
        _, month = month_token
        year = _find_year(q, default_year)
        return _range_payload(
            _month_start(year, month),
            _month_end_marker(year, month),
            f"{_month_label(month)} {year}",
        )

    year_match = re.search(r"\b(20\d{2})\b(?:\s*(?:год|г\.?))?", q)
    if year_match:
        year = int(year_match.group(1))
        return _range_payload(date(year, 1, 1), date(year, 12, 31), f"{year} год", "year")

    return ParsedPeriod()


def _month_number(value: str) -> int | None:
    normalized = value.lower().replace("ё", "е")
    for token, month in MONTHS_RU.items():
        if normalized.startswith(token):
            return month
    return None


def _month_label(month: int) -> str:
    labels = {
        1: "январь",
        2: "февраль",
        3: "март",
        4: "апрель",
        5: "май",
        6: "июнь",
        7: "июль",
        8: "август",
        9: "сентябрь",
        10: "октябрь",
        11: "ноябрь",
        12: "декабрь",
    }
    return labels[month]


def previous_month_period(period: str | None) -> str | None:
    if not period:
        return None
    try:
        parsed = date.fromisoformat(period if len(period) > 7 else f"{period}-01")
    except ValueError:
        return None
    return _previous_month_marker(parsed.year, parsed.month)
