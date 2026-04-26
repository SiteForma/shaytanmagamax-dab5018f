# Assistant Architecture

Phase 5 добавляет в `Shaytan Machine` не чат-обёртку, а отдельный assistant boundary поверх реальных продуктовых модулей.

## Принцип

- assistant не является источником истины;
- source of truth остаётся в `reserve`, `stock`, `inbound`, `uploads`, `quality`, `dashboard`;
- assistant только маршрутизирует вопрос, собирает контекст, вызывает domain tools и композит объяснимый ответ.

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
   Сейчас production path детерминированный.
   Если выбран `openai_compatible`, но провайдер не включён, идёт graceful fallback в deterministic mode.
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
- `get_reserve_explanation`
- `get_sku_summary`
- `get_client_summary`
- `get_inbound_impact`
- `get_stock_coverage`
- `get_upload_status`
- `get_quality_issues`
- `get_dashboard_summary`

Именно tool outputs становятся основой ответа и source refs.

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
