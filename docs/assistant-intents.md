# Assistant Intents

Phase 5 поддерживает rules-first routing с typed intents.

## Supported Intents

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

- intent не определён уверенно;
- вопрос слишком общий;
- нет enough entity signal;
- pinned context не помогает.

Response strategy:

- `unsupported` или `needs_clarification`
- warning block
- next-step suggestions

## Routing Strategy

Роутинг идёт не через prompt magic, а через:

1. deterministic intent detection;
2. extraction of entities;
3. merge with pinned context;
4. warning emission on ambiguity or conflicts.

## Pinned Context Override

Если вопрос явно указывает другой client/SKU, чем pinned context:

- explicit reference побеждает;
- assistant возвращает warning о конфликте контекста.
