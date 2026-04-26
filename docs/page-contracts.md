# Page Contracts

## Overview

Источник:

- `GET /api/dashboard/overview`

UI expects:

- `summary`
- `top_risk_skus`
- `exposed_clients`
- `coverage_distribution`
- `inbound_vs_shortage`
- `freshness`

## Reserve Calculator

Источники:

- `GET /api/clients/diy`
- `GET /api/catalog/skus`
- `POST /api/reserve/calculate`

UI contract:

- selector data отдельно от result dataset
- calculation response должен возвращать `run` и `rows`
- `rows[].explanation_payload` питает drawer
- result table пока остаётся client-scoped на один запуск, без отдельной server pagination

## SKU Explorer

Источники:

- `GET /api/catalog/skus`
- `GET /api/catalog/skus/{id}`

UI contract:

- при `404` сервис возвращает `null`, а не ломает страницу
- drawer должен уметь жить в режимах:
  - loading
  - not found
  - loaded

## DIY Networks

Источники:

- `GET /api/clients/diy`
- `GET /api/clients/diy/{id}/reserve-summary`
- `GET /api/clients/diy/{id}/top-skus`
- `GET /api/clients/diy/{id}/category-exposure`

## Stock & Coverage

Источники:

- `GET /api/stock/coverage`
- `GET /api/stock/potential-stockout`

Фильтры:

- `risk`
- `category`
- `search`
- `page`
- `page_size`
- `sort_by`
- `sort_dir`

Контракт:

- `/api/stock/coverage` теперь возвращает `PaginatedResponse`
- row sorting и page boundaries определяются backend, а не client-side table logic

## Inbound

Источник:

- `GET /api/inbound/timeline`

UI uses:

- статус
- ETA
- affected clients
- reserve impact

## Upload Center

Источники:

- `GET /api/uploads/files`
- `GET /api/uploads/files/{id}`
- `POST /api/uploads/files`
- `POST /api/uploads/files/{id}/validate`
- `POST /api/uploads/files/{id}/apply`

UI expectations:

- selected file detail не должен требовать отдельного orchestration outside hook layer
- status flags и readiness flags приходят из backend
- history list использует `PaginatedResponse`

## Data Mapping

Источники:

- `GET /api/uploads/files/{id}`
- `GET /api/uploads/files/{id}/issues`
- `GET /api/mapping/templates`
- `POST /api/uploads/files/{id}/mapping/suggest`
- `POST /api/uploads/files/{id}/mapping`
- `POST /api/mapping/templates`
- `POST /api/mapping/templates/{id}/apply`

UI expectations:

- preview headers и sample rows приходят из detail response
- suggestion rows и active mapping живут в одном detail contract
- issues endpoint может использовать paginated contract, даже если sidebar показывает только текущую страницу

## Data Quality

Источник:

- `GET /api/quality/issues`

UI expects:

- severity
- type
- entity
- description
- source
- detected_at
- `PaginatedResponse`
- sort fields:
  - `detected_at`
  - `severity`
  - `type`
  - `entity`
  - `source`

## AI Console

Источник:

- `POST /api/assistant/query`

UI expects:

- `answer`
- `sources[]`
- `follow_ups[]`
- `provider`
- optional deterministic context enrichment from:
  - `selectedClient`
  - `selectedSku`
  - `selectedFiles`

## Auth

Источники:

- `POST /api/auth/login`
- `GET /api/auth/me`

Frontend behavior:

- bearer token хранится локально
- в dev fallback остаётся через `X-Dev-User`, но не включается неявно в production
- session UI встроен в top bar, settings и dedicated login route
- core routes проходят через frontend `AuthGuard`
- backend core API routers требуют аутентификацию
