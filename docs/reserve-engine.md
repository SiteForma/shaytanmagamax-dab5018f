# Движок резерва

Первый проход Phase 3 реализован как отдельный модуль `apps/api/app/modules/reserve`.

Этот документ фиксирует именно текущий first pass:

- доменные модели и persistence для `ReserveRun` / `ReserveRow`
- DIY policy resolution
- demand strategy abstraction
- fallback hierarchy
- ручной расчёт через `POST /api/reserve/calculate`
- scoped сценарий `один DIY клиент + список SKU`

## Границы первого прохода

Сейчас reserve engine отвечает за:

- подготовку входного скоупа расчёта
- выбор активной DIY-политики клиента
- расчёт спроса по стратегии
- явный fallback между уровнями истории
- расчёт target / available / shortage / coverage
- классификацию статуса
- сохранение run и строк расчёта
- explainability payload для drawer и последующей аналитики

Что не делаем в этом проходе:

- сезонность
- lead-time-aware reserve
- service-level targets
- сценарное сравнение
- полный dashboard refresh surface
- продвинутую forecast-модель

## Доменные объекты

Основные сущности:

- `DiyPolicy`
- `ReserveCalculationInput`
- `ReserveEngineConfig`
- `DemandMetrics`
- `DemandDecision`
- `SupplyPool`
- `ReserveComputationRow`
- `ReserveRun`
- `ReserveRow`

Persistence:

- `ReserveRun` хранит параметры запуска, статус, summary и фильтры
- `ReserveRow` хранит все ключевые метрики по клиенту и SKU

Ручной расчёт из Reserve Calculator теперь всегда создаёт новый persisted run. Reuse matching run оставлен только для read-model сценариев вроде portfolio bootstrap.

## Demand strategy abstraction

Стратегии лежат в `strategies.py`.

Сейчас доступны:

1. `weighted_recent_average`
2. `strict_recent_average`
3. `conservative_fallback`

### Текущий default

`weighted_recent_average`:

- вес `avg_monthly_sales_3m` = `0.65`
- вес `avg_monthly_sales_6m` = `0.35`

Если обе метрики есть:

`demand_per_month = avg_3m * 0.65 + avg_6m * 0.35`

Если 3m нет, но есть 6m, берётся 6m.
Если есть только 3m, берётся 3m.

## Fallback hierarchy

Fallback явный и сохраняется в строке расчёта:

1. `client_sku`
2. `client_category`
3. `global_sku`
4. `category_baseline`
5. `insufficient_history`

По каждой строке сохраняются:

- `demand_basis_type`
- `fallback_level`
- `basis_window_used`
- `status_reason`
- `explanation_payload.fallback_reason`

## DIY policy model

`DiyPolicy` сейчас поддерживает:

- `client_id`
- `reserve_months`
- `safety_factor`
- `priority_level`
- `active`
- `fallback_chain`
- `allowed_fallback_depth`
- `category_overrides`
- `sku_overrides`
- `notes`
- `effective_from`
- `effective_to`

В seed-данных уже лежат реальные seedable policy examples:

- базовые policy values для трёх DIY-клиентов
- `notes`
- `effective_from`
- пример `sku_override`
- пример `category_override`

## Формула резерва

Текущая формула:

- `target_reserve_qty = demand_per_month * reserve_months * safety_factor`
- `available_qty = allocated_free_stock_qty + allocated_inbound_qty`
- `shortage_qty = max(target_reserve_qty - available_qty, 0)`
- `coverage_months = available_qty / demand_per_month`, если спрос положительный

Rounding:

- используется `ReserveEngineConfig.quantity_precision`
- текущий default = `1`

## Available quantity

В first pass считаем:

- текущий свободный остаток
- подтверждённый inbound в горизонте

`available_qty` строится не как наивная сумма на каждую строку, а через общий SKU-level pool.

Это важно: один и тот же physical stock не должен дублироваться на каждом client + SKU ряду.

## Аллокация общего SKU pool

Для каждого SKU:

- сначала собирается общий `free_stock_qty`
- потом собирается общий `confirmed inbound` в горизонте
- затем pool распределяется между клиентами

Порядок аллокации сейчас:

1. меньший `priority_level`
2. больший `target_reserve_qty`
3. имя клиента для стабильного порядка

Это и есть текущий boring-but-correct default для first pass.

## Статусы и thresholds

Поддерживаемые статусы:

- `healthy`
- `warning`
- `critical`
- `no_history`
- `inactive`
- `overstocked`

Текущие thresholds из `ReserveEngineConfig`:

- `critical_shortage_ratio = 0.5`
- `critical_coverage_ratio = 0.4`
- `overstock_ratio = 2.0`

Логика:

- `inactive`: policy неактивна
- `no_history`: спрос не может быть оценён уверенно
- `healthy`: target закрыт
- `warning`: target не закрыт, но провал не критичен
- `critical`: shortage ratio высокий или coverage сильно ниже цели
- `overstocked`: покрытие кратно выше целевого

## Explainability payload

Каждая строка хранит `explanation_payload` с:

- effective policy
- demand strategy
- fallback path
- fallback reason
- `1m / 3m / 6m` sales metrics
- `avg_3m / avg_6m`
- `demand_per_month`
- `reserve_months`
- `safety_factor`
- `target_reserve_qty`
- total stock / inbound pool
- allocated stock / inbound
- shortage / coverage
- warnings
- allocation trail

Этого уже достаточно для:

- Reserve Calculator drawer
- debugging расчёта
- последующего AI explainability слоя

## API первого прохода

Реально используемые endpoints:

- `POST /api/reserve/calculate`
- `GET /api/reserve/runs`
- `GET /api/reserve/runs/{run_id}`
- `GET /api/reserve/runs/{run_id}/rows`
- `GET /api/reserve/runs/{run_id}/summary`

Первый проход фронта использует ручной `calculate` и затем может читать persisted run по `run_id`.

## Extension points

Архитектура уже допускает второй проход без переписывания ядра:

- seasonality multiplier strategy
- lead-time-aware reserve
- service-level reserve target
- inbound confidence weighting
- richer category / SKU policy overrides
- scenario runs
- analyst notes / manual adjustments
- dashboard materialization on top of persisted runs

## Что осталось на второй проход

- полный executive dashboard на новых read models
- richer DIY policy management UI
- SKU / client drill-downs на одном persisted contract
- coverage distributions и inbound-vs-shortage surface
- сценарное сравнение runs
- расширение explainability в assistant layer
