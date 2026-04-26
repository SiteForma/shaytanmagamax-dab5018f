# Assistant Intents

Phase 5 поддерживает typed intents с LLM-first orchestration при включённом provider и deterministic fallback.

## Supported Intents

### `free_chat`

Доменный свободный чат для вопросов о MAGAMAX и о том, как пользоваться AI Console.
Это не общий ChatGPT-режим: внешние темы должны возвращать `unsupported_or_ambiguous`.

Примеры:

- `Привет, как с тобой лучше работать в MAGAMAX?`
- `Объясни, какие вопросы сюда можно задавать`
- `Помоги сформулировать запрос для расчёта резерва`

Primary tools:

- none by default

Поведение:

- не запускает доменные расчёты случайно;
- не добавляет операционные цифры без вызова реальных инструментов;
- может использовать pinned context как conversational context;
- если вопрос требует фактов, предлагает сформулировать операционный запрос, который будет направлен в соответствующий intent.
- если вопрос не связан с MAGAMAX, загруженными данными, резервами, SKU, складом, поставками,
  качеством данных или расчётами по этим данным, возвращается жёсткий отказ.

### `reserve_calculation`

Примеры:

- `Рассчитай резерв для Леман Про на 3 месяца по SKU K-2650-CR`
- `Покажи резерв по этому клиенту и выбранным SKU`

Извлекается:

- client
- sku list
- category
- reserve months
- optional safety factor

Primary tools:

- `calculate_reserve`
- `get_quality_issues`
- `get_upload_status`

### `reserve_explanation`

Примеры:

- `Почему эта позиция критична?`
- `Объясни дефицит по SKU K-2650-CR`
- `Почему был использован fallback?`

Primary tools:

- `get_reserve_explanation`
- `get_sku_summary`
- `get_quality_issues`

### `sku_summary`

Примеры:

- `Суммируй ситуацию по SKU K-2650-CR`
- `Что происходит по этому SKU?`

Primary tools:

- `get_sku_summary`
- `get_quality_issues`

### `client_summary`

Примеры:

- `Что сейчас по Леман Про?`
- `Сводка по клиенту`

Primary tools:

- `get_client_summary`
- `get_dashboard_summary`

### `diy_coverage_check`

Примеры:

- `Покажи позиции ниже резерва по этому клиенту`
- `Какие позиции under reserve у OBI?`

Primary tools:

- `get_client_summary`
- `get_dashboard_summary`

### `inbound_impact`

Примеры:

- `Какие поставки снижают текущий дефицит?`
- `Что из inbound реально помогает?`

Primary tools:

- `get_inbound_impact`
- `get_dashboard_summary`

### `stock_risk_summary`

Примеры:

- `Покажи риск покрытия`
- `Какие категории под stockout risk?`

Primary tools:

- `get_stock_coverage`
- `get_dashboard_summary`

### `upload_status_summary`

Примеры:

- `Когда обновлялись данные?`
- `Какие загрузки использовались?`
- `Какой freshness у текущего ответа?`

Primary tools:

- `get_upload_status`
- `get_dashboard_summary`
- `get_quality_issues`

### `quality_issue_summary`

Примеры:

- `Есть ли проблемы качества данных?`
- `Какие quality issues влияют на этот SKU?`

Primary tools:

- `get_quality_issues`
- `get_upload_status`

### `unsupported_or_ambiguous`

Используется, когда:

- сообщение пустое или непригодное для обработки;
- запрос повреждён или не содержит текста.

Response strategy:

- `unsupported` или `needs_clarification`
- warning block
- next-step suggestions

## Routing Strategy

Роутинг устроен как контролируемая оркестрация, а не как свободный prompt:

1. deterministic router делает быстрый baseline intent и извлечение сущностей;
2. если `openai_compatible` включён, LLM planner первым интерпретирует запрос и выбирает `intent`, `toolQuestion`, `toolNames`;
3. backend валидирует intent/tools по allowlist и не даёт LLM выполнять произвольные действия;
4. backend повторно извлекает сущности из `toolQuestion`;
5. контекст вопроса объединяется с pinned context;
6. запускаются только разрешённые domain tools, которые читают данные из БД и вызывают реальные сервисы;
7. ответ собирается из tool outputs и source refs;
8. LLM finalizer может улучшить язык ответа, но не менять факты, метрики и источники;
9. если вопрос вне MAGAMAX, возвращается `unsupported_or_ambiguous` без запуска domain tools.

Важная гарантия: если deterministic router уверенно нашёл доменный intent, LLM planner не может понизить его до `unsupported_or_ambiguous`.

## Pinned Context Override

Если вопрос явно указывает другой client/SKU, чем pinned context:

- explicit reference побеждает;
- assistant возвращает warning о конфликте контекста.
