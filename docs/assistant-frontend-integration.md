# Assistant Frontend Integration

AI Console больше не держит локальный массив ответов.
Теперь фронтенд работает через реальные assistant sessions/messages APIs.

## Frontend Data Layer

Ключевые файлы:

- `apps/web/src/services/assistant.service.ts`
- `apps/web/src/adapters/assistant.adapter.ts`
- `apps/web/src/hooks/queries/use-assistant.ts`
- `apps/web/src/hooks/mutations/use-assistant.ts`
- `apps/web/src/features/assistant/AiConsolePage.tsx`

## What Changed

### Sessions

UI теперь умеет:

- создавать новую session;
- выбирать existing session;
- загружать session history;
- переименовывать session;
- архивировать и восстанавливать session;
- рендерить persisted user/assistant messages.

Session id синхронизируется с URL query param `session`.

### Pinned Context

Правая панель контекста работает через `/api/assistant/context-options`.

Поддерживаются:

- client
- SKU
- upload file
- category
- reserve run

Pinned context отправляется в backend на каждый message submit и сохраняется в session.
Дополнительно пользователь может явно сохранить текущее pinned state в session без отправки нового вопроса.

### Structured Response Rendering

Фронт больше не ждёт один `answer` string.
AI Console рендерит:

- `summary`
- `sections`
- `sourceRefs`
- `followups`
- `warnings`
- `missingFields`
- `suggestedChips`
- `pendingIntent`

Отдельно рендерятся:

- metric cards;
- preview tables;
- source refs inline под ответом и полный source refs block в `Подробнее`;
- clarification panel с missing fields и chips;
- trace id и tool-call inspector;
- next-step chips;
- warning panel.

### Streaming

Основной режим ответа — настоящий SSE stream через
`POST /api/assistant/sessions/{session_id}/messages/stream`.

Frontend client читает server events:

- `thinking`
- `clarification`
- `tool_call`
- `tool_result`
- `answer_delta`
- `done`
- `error`

Fake typewriter не используется как основной режим. Текст появляется из `answer_delta`,
а `done` заменяет локальные optimistic messages на persisted `userMessage` и `assistantMessage`.

## Query / Mutation Pattern

Queries:

- `useAssistantSessionsQuery()`
- `useAssistantMessagesQuery(sessionId)`
- `useAssistantCapabilitiesQuery()`
- `useAssistantPromptSuggestionsQuery()`
- `useAssistantContextOptionsQuery()`

Mutations:

- `useCreateAssistantSessionMutation()`
- `useAssistantMessageMutation()`
- `useUpdateAssistantSessionMutation()`

## Invalidation

После успешной отправки assistant message инвалидируются:

- `assistant.sessions`
- `assistant.session(sessionId)`
- `assistant.messages(sessionId)`

Это даёт согласованную session sidebar и message history.

## Premium UX Rules Preserved

В ходе интеграции сохранены:

- premium shell;
- тёмная MAGAMAX-тема;
- calm loading states;
- structured panel layout;
- source-aware blocks;
- аккуратные follow-up chips;
- без деградации в “обычный чат”.

## Remaining Extension Points

Следующий шаг без перелома UI:

- richer source deep links;
- saved assistant views;
- LLM-composed prose поверх того же response shape;
- role-aware assistant behavior.
- более богатый realtime tool-progress UI поверх уже существующих `tool_call` / `tool_result`.
