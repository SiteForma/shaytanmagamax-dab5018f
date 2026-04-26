from __future__ import annotations

from datetime import date

from apps.api.app.modules.assistant.periods import parse_period_text


def test_parse_russian_month_with_year() -> None:
    period = parse_period_text("покажи продажи за март 2025")

    assert period.date_from == "2025-03-01"
    assert period.date_to == "2025-03-31"
    assert period.current_period == "2025-03"
    assert period.previous_period == "2025-02"
    assert period.granularity == "month"


def test_parse_month_without_year_uses_default_year() -> None:
    period = parse_period_text("в марте", default_year=2025)

    assert period.date_from == "2025-03-01"
    assert period.date_to == "2025-03-31"


def test_parse_relative_months() -> None:
    today = date(2026, 4, 26)

    previous = parse_period_text("прошлый месяц", today=today)
    current = parse_period_text("этот месяц", today=today)
    recent = parse_period_text("последние 3 месяца", today=today)

    assert previous.date_from == "2026-03-01"
    assert previous.date_to == "2026-03-31"
    assert current.date_from == "2026-04-01"
    assert current.date_to == "2026-04-30"
    assert recent.date_from == "2026-02-01"
    assert recent.date_to == "2026-04-30"
    assert recent.granularity == "range"


def test_parse_quarter_and_month_range() -> None:
    q1 = parse_period_text("1 квартал 2025")
    q_alias = parse_period_text("Q1 2025")
    range_period = parse_period_text("январь-март 2025")

    assert q1.date_from == "2025-01-01"
    assert q1.date_to == "2025-03-31"
    assert q1.granularity == "quarter"
    assert q_alias.date_from == "2025-01-01"
    assert q_alias.date_to == "2025-03-31"
    assert range_period.date_from == "2025-01-01"
    assert range_period.date_to == "2025-03-31"
    assert range_period.granularity == "range"


def test_parse_year_and_previous_year() -> None:
    year = parse_period_text("2025 год")
    previous = parse_period_text("прошлый год", today=date(2026, 4, 26))

    assert year.date_from == "2025-01-01"
    assert year.date_to == "2025-12-31"
    assert year.granularity == "year"
    assert previous.date_from == "2025-01-01"
    assert previous.date_to == "2025-12-31"
