from __future__ import annotations

import time as time_module
from datetime import UTC, datetime, time, timedelta
from zoneinfo import ZoneInfo

from apps.api.app.core.config import get_settings
from apps.worker.worker_app.tasks import sync_inbound_google_sheet_job

MOSCOW_TZ = ZoneInfo("Europe/Moscow")


def next_moscow_run(now_utc: datetime, *, hour: int) -> datetime:
    now_moscow = now_utc.astimezone(MOSCOW_TZ)
    target = datetime.combine(now_moscow.date(), time(hour=hour), tzinfo=MOSCOW_TZ)
    if target <= now_moscow:
        target += timedelta(days=1)
    return target.astimezone(UTC)


def main() -> None:
    settings = get_settings()
    while True:
        now = datetime.now(tz=UTC)
        run_at = next_moscow_run(now, hour=settings.inbound_google_sheet_sync_hour_moscow)
        sleep_seconds = max((run_at - now).total_seconds(), 1)
        print(
            "Next inbound Google Sheet sync: "
            f"{run_at.isoformat()} UTC / {run_at.astimezone(MOSCOW_TZ).isoformat()} MSK",
            flush=True,
        )
        time_module.sleep(sleep_seconds)
        sync_inbound_google_sheet_job.send()


if __name__ == "__main__":
    main()
