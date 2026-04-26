from __future__ import annotations

import time as time_module
from datetime import UTC, datetime, time, timedelta
from zoneinfo import ZoneInfo

from apps.api.app.core.config import get_settings
from apps.worker.worker_app.tasks import backup_duckdb, sync_inbound_google_sheet_job

MOSCOW_TZ = ZoneInfo("Europe/Moscow")


def next_moscow_run(now_utc: datetime, *, hour: int) -> datetime:
    now_moscow = now_utc.astimezone(MOSCOW_TZ)
    target = datetime.combine(now_moscow.date(), time(hour=hour), tzinfo=MOSCOW_TZ)
    if target <= now_moscow:
        target += timedelta(days=1)
    return target.astimezone(UTC)


def next_interval_run(now_utc: datetime, *, interval_hours: int) -> datetime:
    next_hour = ((now_utc.hour // interval_hours) + 1) * interval_hours
    target_date = now_utc.date()
    if next_hour >= 24:
        next_hour = 0
        target_date += timedelta(days=1)
    return datetime.combine(target_date, time(hour=next_hour), tzinfo=UTC)


def main() -> None:
    settings = get_settings()
    next_inbound = next_moscow_run(
        datetime.now(tz=UTC),
        hour=settings.inbound_google_sheet_sync_hour_moscow,
    )
    next_duckdb_backup = next_interval_run(datetime.now(tz=UTC), interval_hours=6)
    while True:
        now = datetime.now(tz=UTC)
        run_at = min(next_inbound, next_duckdb_backup)
        sleep_seconds = max((run_at - now).total_seconds(), 1)
        print(
            "Next inbound Google Sheet sync: "
            f"{next_inbound.isoformat()} UTC / {next_inbound.astimezone(MOSCOW_TZ).isoformat()} MSK; "
            f"next DuckDB backup: {next_duckdb_backup.isoformat()} UTC",
            flush=True,
        )
        time_module.sleep(sleep_seconds)
        now = datetime.now(tz=UTC)
        if now >= next_inbound:
            sync_inbound_google_sheet_job.send()
            next_inbound = next_moscow_run(
                now,
                hour=settings.inbound_google_sheet_sync_hour_moscow,
            )
        if now >= next_duckdb_backup:
            backup_duckdb.send()
            next_duckdb_backup = next_interval_run(now, interval_hours=6)


if __name__ == "__main__":
    main()
