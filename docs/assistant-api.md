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

### `POST /sessions/{session_id}/messages/stream`

Пишет user message, запускает orchestration и отдаёт настоящий SSE stream.

Response headers:

- `Content-Type: text/event-stream`
- `Cache-Control: no-cache`
- `X-Accel-Buffering: no`

Server events:

- `thinking` — backend принял запрос, сохранил user message или планирует инструменты.
- `clarification` — assistant просит уточнить параметры; содержит `missingFields`, `suggestedChips`, `pendingIntent`.
- `tool_call` — backend вызывает allowlisted domain tool.
- `tool_result` — domain tool вернул результат или безопасную ошибку.
- `answer_delta` — chunk текста ответа для реального streaming UI.
- `done` — финальный `AssistantSessionMessageResult`.
- `error` — structured stream error.

Frontend не должен имитировать основной typing-режим поверх готового ответа. Основной режим — читать `answer_delta`.

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

`free_chat` входит в supported intents, но это доменный чат MAGAMAX, а не общий ChatGPT-режим.
Он используется только для вопросов о работе с MAGAMAX, загруженными данными, резервами, SKU,
складом, поставками, качеством данных, dashboard и возможностями самой консоли.
Внешние темы возвращают `unsupported_or_ambiguous` с отказом. Если LLM-provider включён, planner может быть вызван
только для классификации запроса; domain tools при отказе не запускаются.

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
- `type` (`answer` / `clarification`)
- `missingFields[]`
- `suggestedChips[]`
- `pendingIntent`
- `traceMetadata`

Для `intent: "free_chat"` поле `toolCalls` обычно пустое, а `sourceRefs` может быть пустым.
Это означает, что ответ был доменным conversational-ответом и не использовал operational data sources.

Для `intent: "unsupported_or_ambiguous"` backend возвращает детерминированный отказ:
Шайтан-машина отвечает только на вопросы, сопряжённые с рабочими данными MAGAMAX.

## Orchestration Order

При включённом LLM-provider запрос проходит так:

1. LLM planner интерпретирует текст и выбирает intent + allowlisted tools.
2. Backend выполняет только валидированные domain tools по БД.
3. Backend собирает structured response с source refs.
4. LLM finalizer, если доступен, улучшает текст без права менять факты.

Если provider отключён или недоступен, используется deterministic router + deterministic answer composition.

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
