# Frontend Data Layer

## Слои

### 1. Transport

Файл: `apps/web/src/lib/api/client.ts`

Отвечает за:

- базовый `API_BASE_URL`
- `Authorization: Bearer` при наличии сохранённой сессии
- `X-Dev-User` в локальной development-среде
- `X-Request-Id` для корреляции запросов
- нормализацию error envelope в `ApiError`
- отсутствие неявного `user_admin` fallback в production-сборках

### 1.1. Auth policy

Файл: `apps/web/src/lib/auth/config.ts`

Отвечает за:

- dev session enable/disable
- strict auth mode
- фронтовое различение development и production auth behavior

### 2. Session storage

Файл: `apps/web/src/lib/api/session.ts`

Хранит локальную сессию:

- access token
- user metadata
- roles

### 3. Query config

Файл: `apps/web/src/lib/query/client.ts`

Используемые defaults:

- `staleTime = 30s`
- `gcTime = 5m`
- нет агрессивного `refetchOnWindowFocus`
- retry только для ограниченного круга ошибок

### 4. Query keys

Файл: `apps/web/src/lib/query/keys.ts`

Все query keys централизованы, чтобы:

- делать предсказуемый invalidation
- не разносить строковые ключи по компонентам
- упростить эволюцию hooks

### 5. Hooks

Файлы:

- `apps/web/src/hooks/queries/*`
- `apps/web/src/hooks/mutations/*`

Назначение:

- page orchestration без прямых API вызовов
- единая стратегия загрузки, ошибок и invalidation

### 6. Adapter layer

Файлы:

- `apps/web/src/adapters/*.ts`

Назначение:

- backend snake_case -> frontend camelCase
- сглаживание контрактов
- преобразование nested payloads в page-friendly view models

Сервисы теперь в идеале:

- собирают query params
- вызывают transport
- делегируют shape mapping adapter-функциям

## Mutation invalidation

### Upload lifecycle

После `upload / save mapping / validate / apply` инвалидируются:

- `uploads`
- `quality`
- `dashboard`
- детальная query по конкретному файлу

### Reserve calculation

После расчёта резерва инвалидируются:

- `reserve`
- `dashboard`
- `clients`
- `stock`

## Server-driven table state

Для тяжёлых списков frontend теперь умеет работать в controlled/manual table mode:

- `manualFiltering`
- `manualSorting`
- `manualPagination`

Это уже подключено для:

- `Stock & Coverage`
- `Data Quality`
- `Upload history`

## Error strategy

Пользовательские surfaces не показывают raw exceptions.

Используются:

- `ApiError`
- `QueryErrorState`
- request id в UI для trace/debug

## URL state decisions

URL state используется там, где deep-linking действительно полезен:

- reserve calculator
- sku explorer
- stock filters
- quality filters
- upload list / selected file
- mapping selected file
- server-side page/sort state для тяжёлых таблиц

Не используется там, где это пока добавило бы шум без практической ценности:

- transient drawer-internal tabs
- локальные client-side search поля таблиц

## Route loading strategy

- App routes переведены на `React.lazy`
- защищённый shell грузится через `AuthGuard`
- `Suspense` fallback сделан нейтральным и совместимым с premium shell, без грубых спиннеров

## Remaining extension points

- расширить server pagination/sorting на оставшиеся длинные списки
- при росте доменных контрактов разрезать `adapters/` ещё глубже
- добавить optimistic updates для части mutation flows
- при необходимости добавить refresh/session renewal поверх текущего bearer flow
