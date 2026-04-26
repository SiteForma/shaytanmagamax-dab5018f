# Assistant Architecture

Phase 5 добавляет в `Shaytan Machine` не чат-обёртку, а отдельный assistant boundary поверх реальных продуктовых модулей.

## Принцип

- assistant не является источником истины;
- source of truth остаётся в `reserve`, `stock`, `inbound`, `uploads`, `quality`, `dashboard`;
- assistant только маршрутизирует вопрос, собирает контекст, вызывает domain tools и композит объяснимый ответ.
- MAGAMAX AI считается внутренним аналитическим ассистентом менеджера по продажам, не публичным ботом;
- основной режим — `truth-first internal analyst`: лучше честно вернуть `no_data`, `insufficient_data` или уточнение, чем придумать цифры.

## Backend Structure

Ключевые файлы:

- `apps/api/app/modules/assistant/schemas.py`
- `apps/api/app/modules/assistant/domain.py`
- `apps/api/app/modules/assistant/routing.py`
- `apps/api/app/modules/assistant/context.py`
- `apps/api/app/modules/assistant/tools.py`
- `apps/api/app/modules/assistant/providers.py`
- `apps/api/app/modules/assistant/orchestration.py`
- `apps/api/app/modules/assistant/repository.py`
- `apps/api/app/modules/assistant/service.py`

## Request Flow

1. API получает `AssistantQueryRequest` или `AssistantMessageCreateRequest`.
2. `routing.py` классифицирует вопрос в typed intent и пытается извлечь клиента, SKU, категорию, uploads и reserve horizon.
3. `context.py` объединяет extracted entities с pinned context из UI/session.
4. `orchestration.py` строит tool plan по intent.
5. `tools.py` вызывает реальные domain services:
   - reserve engine
   - SKU explorer services
   - DIY client services
   - stock coverage
   - inbound timeline
   - upload detail / freshness
   - quality issues
6. `orchestration.py` превращает tool outputs в typed `AssistantResponse`.
7. `providers.py` применяет provider layer.
   Для tool-based ответов финальный LLM polish отключён, чтобы не менять числа из backend tools.
   LLM может помогать planner-слою, но факты и расчёты остаются из tools.
8. При session-based запросе user/assistant messages пишутся в БД.

## Persistence Model

Новые таблицы:

- `assistant_sessions`
- `assistant_messages`

`assistant_sessions` хранит:

- владельца;
- title;
- preferred mode;
- pinned context;
- last intent;
- provider;
- latest trace id;
- last message timestamp;
- message count.

`assistant_messages` хранит:

- role (`user` / `assistant`);
- text;
- intent;
- status;
- provider;
- confidence;
- trace id;
- context payload;
- full structured response payload;
- source refs;
- tool call log;
- warnings.

Это даёт explainable history без “чёрного ящика”.

## Tool-First Design

assistant не считает резерв сам.
Для operational вопросов сначала вызываются реальные сервисы:

- `calculate_reserve`
- `get_reserve`
- `get_reserve_explanation`
- `get_sku_summary`
- `get_client_summary`
- `get_inbound_impact`
- `get_stock_coverage`
- `get_upload_status`
- `get_quality_issues`
- `get_dashboard_summary`
- `get_sales_summary`
- `get_period_comparison`
- `get_analytics_slice`
- `get_data_overview`

Именно tool outputs становятся основой ответа и source refs.

## Read-Only vs Action Tools

Обычные вопросы вида “покажи резерв” читают последний сохранённый reserve run через `get_reserve`.
Они не создают скрытых расчётов и не меняют состояние БД.

Action-запросы вида “пересчитай резерв” используют `calculate_reserve` и требуют отдельное право `reserve:run`.
Это разделение критично: чат не должен запускать дорогие или мутирующие операции только потому, что пользователь попросил “показать”.

Широкие вопросы вида “что есть в БД”, “покажи всё полезное” идут через `get_data_overview`.
Это read-only inventory tool: он показывает наполненность справочников, продаж, склада, резерва, поставок, загрузок, quality issues и управленческого отчёта.
Он не запускает reserve engine, не создаёт runs, не применяет загрузки и не делает скрытых пересчётов.
В ответе обязательны source refs и честные статусы `no_data` / `partial`, если источник пустой или неполный.

## Internal Analytics Permissions

Для доверенных внутренних пользователей введено право `assistant:internal_analytics`.
Оно разрешает MAGAMAX AI читать аналитические справочники и read-only tools по sales, stock, catalog, clients, reports, reserve, inbound, quality и dashboard.

Ограниченные роли без `assistant:internal_analytics` получают `context-options` только по granular capabilities:

- `clients` требует `clients:read`;
- `skus` и `categories` требуют `catalog:read`;
- `uploads` требует `uploads:read`;
- `reserveRuns` требует `reserve:read`.

Write/action tools не покрываются `assistant:internal_analytics`: для них нужны отдельные права вроде `reserve:run`, `uploads:write`, `exports:generate`.

`get_data_overview` предназначен для trusted internal analytics users.
Он требует read-доступ к ключевым аналитическим доменам; `assistant:internal_analytics` покрывает эти read-only capabilities, но не покрывает action capabilities.

## Universal Analytics Slice

`get_analytics_slice` принимает только allowlisted metrics/dimensions/filters.
LLM не генерирует SQL и не передаёт raw query.

Поддерживаемые стартовые метрики:

- `sales_qty`
- `revenue`
- `stock_qty`
- `free_stock`
- `reserve_qty`
- `shortage_qty`
- `coverage_months`
- `inbound_qty`
- `profitability` / `margin` по управленческому отчёту, если данные есть.

Поддерживаемые измерения:

- `client`
- `sku`
- `article`
- `category`
- `product_group`
- `warehouse`
- `month`
- `quarter`
- `year`
- `region`

## Explainability

Каждый `AssistantResponse` содержит:

- `intent`
- `status`
- `confidence`
- `sections`
- `sourceRefs`
- `toolCalls`
- `warnings`
- `traceId`
- `contextUsed`

UI может показать не только narrative, но и:

- какие источники использовались;
- какие tools были вызваны;
- какие ограничения есть у ответа;
- какой pinned context был применён.

## Failure Modes

Если intent или сущности не определены, assistant:

- не выдумывает ответ;
- возвращает `needs_clarification` или `unsupported`;
- указывает, чего не хватает;
- предлагает follow-up действия.

## Extension Points

Архитектура уже готова для:

- real LLM composition;
- richer entity extraction;
- multi-step tool planning;
- role-aware filtering;
- assistant reports;
- proactive suggestions;
- export / deep-link citations.
