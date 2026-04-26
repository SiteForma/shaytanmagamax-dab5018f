# Frontend Integration

`apps/web` больше не является просто красивым shell с разрозненными вызовами сервисов. Phase 4 переводит приложение на единый query/mutation слой поверх реального backend API, сохраняя существующую MAGAMAX-визуальную систему.

## Что изменилось

- real API orchestration теперь идёт через `@tanstack/react-query`
- транспорт централизован в `apps/web/src/lib/api/client.ts`
- session/token handling вынесен в `apps/web/src/lib/api/session.ts`
- auth policy и dev/prod поведение вынесены в `apps/web/src/lib/auth/config.ts`
- page-level orchestration вынесена в hooks:
  - `apps/web/src/hooks/queries/*`
  - `apps/web/src/hooks/mutations/*`
- API -> UI преобразования теперь вынесены в `apps/web/src/adapters/*`
- ошибки и retry states унифицированы через `QueryErrorState`
- основная фильтрация переведена на URL state там, где это важно для операционной работы
- основные маршруты переведены на route-level lazy loading и защищённый layout

## Принципы

- не переписывать shell и не разрушать визуальный язык
- не тащить `fetch()` в page-компоненты
- держать mapping API -> view model в сервисах
- использовать query invalidation вместо случайного ручного refresh
- поддерживать премиальные loading, empty, error и drawer states

## Реально интегрированные страницы

### Overview

- hook: `useDashboardOverviewQuery`
- backend: `/api/dashboard/overview`
- реальные состояния:
  - KPI strip
  - top risk SKUs
  - exposed DIY clients
  - coverage distribution
  - inbound vs shortage
  - freshness panel

### Reserve Calculator

- hooks:
  - `useClientsQuery`
  - `useSkusQuery`
  - `useReserveCalculationMutation`
- backend:
  - `POST /api/reserve/calculate`
- URL state:
  - `client`
  - `skus`
  - `horizon`
  - `safety`
  - `strategy`
  - `status`

### SKU Explorer

- hooks:
  - `useSkusQuery`
  - `useSkuDetailQuery`
- backend:
  - `/api/catalog/skus`
  - `/api/catalog/skus/{sku_id}`
- URL state:
  - `sku`

### DIY Networks

- hooks:
  - `useClientsQuery`
  - `useClientDetailQuery`
  - `useClientTopSkusQuery`
  - `useClientCategoryExposureQuery`
- backend:
  - `/api/clients/diy`
  - `/api/clients/diy/{client_id}/reserve-summary`
  - `/api/clients/diy/{client_id}/top-skus`
  - `/api/clients/diy/{client_id}/category-exposure`
- URL state:
  - `client`

### Stock & Coverage

- hooks:
  - `useStockCoverageQuery`
  - `usePotentialStockoutQuery`
  - `useSkusQuery`
- backend:
  - `/api/stock/coverage`
  - `/api/stock/potential-stockout`
- URL state:
  - `risk`
  - `category`
  - `query`
  - `page`
  - `pageSize`
  - `sort`
  - `dir`
- server-side:
  - pagination
  - sorting
  - filtering

### Inbound Deliveries

- hook: `useInboundTimelineQuery`
- backend: `/api/inbound/timeline`
- URL state:
  - `status`

### Upload Center

- hooks:
  - `useUploadJobsQuery`
  - `useUploadFileDetailQuery`
  - `useCreateUploadMutation`
  - `useValidateUploadMutation`
  - `useApplyUploadMutation`
- backend:
  - `/api/uploads/files`
  - `/api/uploads/files/{id}`
  - `/api/uploads/files/{id}/validate`
  - `/api/uploads/files/{id}/apply`
- URL state:
  - `file`
  - `status`
  - `source`
  - `page`
  - `pageSize`
- upload history теперь использует реальную серверную пагинацию

### Data Mapping

- hooks:
  - `useUploadFileDetailQuery`
  - `useUploadIssuesQuery`
  - `useMappingTemplatesQuery`
  - mapping mutations
- backend:
  - `/api/uploads/files/{id}/mapping`
  - `/api/uploads/files/{id}/mapping/suggest`
  - `/api/uploads/files/{id}/validate`
  - `/api/mapping/templates`

### Data Quality

- hook: `useQualityIssuesQuery`
- backend: `/api/quality/issues`
- URL state:
  - `severity`
  - `type`
  - `query`
  - `page`
  - `pageSize`
  - `sort`
  - `dir`
- issue table теперь работает через server-side pagination/sorting

### AI Console

- mock fallback удалён
- UI ходит в реальный deterministic assistant backend:
  - `/api/assistant/query`
- selectable context теперь берётся из реальных clients / skus / uploads hooks
- backend now assembles contextual answer fragments for:
  - selected client
  - selected SKU
  - selected upload file
- source blocks в UI ведут на реальные drill-down маршруты

## Auth / session

- bearer token transport поддержан
- `X-Dev-User` сохранён только для local development
- login dialog подключён в top bar и settings
- current user берётся из `/api/auth/me` когда доступен
- добавлена отдельная страница входа `/login`
- основной shell теперь проходит через `AuthGuard`
- backend core routers теперь защищены `require_user`

Важно:
- в `development` допускается dev-session через `X-Dev-User`
- в `production` dev fallback больше не включается по умолчанию
- `VITE_REQUIRE_AUTH=true` позволяет принудительно включить строгий guard и в non-production среде

## Performance hardening

- страницы переведены на `React.lazy` + `Suspense`
- Vite bundle разделён на доменные/vendor chunks
- sidebar перестал тянуть весь `lucide-react` через `import *`, поэтому иконки больше не раздувают основной chunk

## Что ещё остаётся

- расширить server-side table state на те экраны, где backend пока ещё отдаёт только плоские списки
- при необходимости углубить `adapters/` до более мелких domain/view-model слоёв
- развить assistant от deterministic context assembly к tool-orchestrated flow поверх того же контракта
