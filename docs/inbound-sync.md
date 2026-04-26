# Inbound Google Sheet Sync

Раздел `Товары в пути` использует Google Sheet как авторитетный источник входящих контейнеров.

## Source

Default source:

`https://docs.google.com/spreadsheets/d/19RQsO_tTO1-D8hN_j0GZZvlQZNRCzsLSGgN9GU-K1_k/edit?gid=1657756957`

Runtime settings:

- `INBOUND_GOOGLE_SHEET_ID`
- `INBOUND_GOOGLE_SHEET_GID`
- `INBOUND_GOOGLE_SHEET_EXPORT_URL`
- `INBOUND_GOOGLE_SHEET_SYNC_HOUR_MOSCOW`

If `INBOUND_GOOGLE_SHEET_EXPORT_URL` is set, it wins over sheet id/gid.

## Semantics

- `В пути` is treated as the real quantity in the container for the article.
- `Свободный остаток` is treated as the quantity that will remain free after customer allocations from the same row are distributed.
- Client allocation columns are all non-system columns between the base shipment fields and `Итого заказы клиентов`.
- `Итого заказы клиентов` is persisted as `client_order_qty` and currently also powers `reserve_impact_qty` for compatibility with existing inbound UI/read models.
- Unknown articles are created as minimal MAGAMAX SKU records using the article as the product name. This is source-derived, not sample data.
- Unknown client allocation columns are created as clients with `client_group = Inbound sheet`.

## Idempotency

The sync is snapshot-based. Rows whose `external_ref` starts with `google_sheet_inbound:` are replaced on each sync. Manually uploaded inbound rows from the ingestion pipeline are not deleted.

## Manual Sync

API:

`POST /api/inbound/sync`

Required capabilities:

- `inbound:read` through the protected inbound router
- `inbound:sync` on the endpoint itself

Frontend:

The `/inbound` page exposes `Синхронизировать` for users with `inbound:sync`.

## Daily Sync

Dramatiq actor:

`sync_inbound_google_sheet_job`

Scheduler process:

```bash
make inbound-scheduler
```

The scheduler enqueues the sync job every day at `INBOUND_GOOGLE_SHEET_SYNC_HOUR_MOSCOW`, default `08:00 Europe/Moscow`.

Production should run both:

```bash
dramatiq apps.worker.worker_app.tasks
python -m apps.worker.worker_app.scheduler
```
