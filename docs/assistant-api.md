# Assistant API

Base prefix: `/api/assistant`

Все endpoints требуют auth.

## Sessions

### `POST /sessions`

Создать новую assistant session.

Request:

```json
{
  "title": "Резерв по Леман Про",
  "preferredMode": "deterministic",
  "pinnedContext": {
    "selectedClientId": "client_2",
    "selectedSkuId": "sku_1"
  }
}
```

### `GET /sessions`

Возвращает список сессий текущего пользователя.

### `GET /sessions/{session_id}`

Возвращает session detail вместе с message history.

### `PATCH /sessions/{session_id}`

Обновляет session metadata без запуска orchestration.

Можно менять:

- `title`
- `status` (`active` / `archived`)
- `preferredMode`
- `pinnedContext`

### `GET /sessions/{session_id}/messages`

Возвращает messages для выбранной сессии.

### `POST /sessions/{session_id}/messages`

Пишет user message, запускает orchestration и сохраняет assistant response.

Request:

```json
{
  "text": "Почему эта позиция критична?",
  "preferredMode": "deterministic",
  "context": {
    "selectedClientId": "client_2",
    "selectedSkuId": "sku_1"
  }
}
```

Response:

- `session`
- `userMessage`
- `assistantMessage`
- `response`

## Stateless Query

### `POST /query`

Выполняет stateless query.
Если передан `sessionId`, ответ тоже будет записан в session history.

Request:

```json
{
  "text": "Рассчитай резерв на 3 месяца по этому SKU",
  "sessionId": "asess_123",
  "context": {
    "selectedClientId": "client_2",
    "selectedSkuId": "sku_1"
  }
}
```

## Metadata

### `GET /capabilities`

Возвращает:

- активный provider;
- наличие deterministic fallback;
- supported intents;
- session support;
- pinned context support.

### `GET /prompts/suggestions`

Возвращает UI-ready prompt suggestions.

### `GET /context-options`

Возвращает options для pinned context panel:

- clients
- skus
- uploads
- reserveRuns
- categories

## Session UX Notes

Frontend использует `PATCH /sessions/{id}` для:

- rename session;
- archive / restore;
- явного сохранения pinned context из правой панели AI Console.

## AssistantResponse Shape

Ключевые поля:

- `answerId`
- `sessionId`
- `intent`
- `status`
- `confidence`
- `title`
- `summary`
- `sections[]`
- `sourceRefs[]`
- `toolCalls[]`
- `followups[]`
- `warnings[]`
- `generatedAt`
- `traceId`
- `provider`
- `contextUsed`

## Source References

Каждый source ref содержит:

- `sourceType`
- `sourceLabel`
- `entityType`
- `entityId`
- `externalKey`
- `freshnessAt`
- `role`
- `route`
- `detail`

## Safety Contract

Assistant API не делает write-операций над operational данными.
Его mutable surface ограничена собственной session/message history.
