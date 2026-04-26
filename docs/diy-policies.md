# DIY-политики

`DiyPolicy` — это источник правил резерва для конкретного DIY-клиента.

В первом проходе Phase 3 политика уже вынесена в данные, а не зашита в код.

## Что хранит политика

Сейчас модель поддерживает:

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

## Как policy применяется

Effective policy собирается в таком порядке:

1. базовая политика клиента
2. override по категории, если он найден
3. override по SKU, если он найден
4. override из run request, если пользователь явно задал `reserve_months` или `safety_factor`

Результат попадает в `explanation_payload.policy_used`, поэтому frontend и аналитик всегда видят, какое правило реально сработало.

## Priority semantics

`priority_level` влияет не просто на label, а на распределение общего SKU pool:

- меньшее число = выше приоритет
- при дефицитном SKU более приоритетный клиент получает остаток раньше

Это намеренно сделано на backend-уровне, а не в UI.

## Fallback semantics

`fallback_chain` задаёт допустимый путь по истории:

- `client_sku`
- `client_category`
- `global_sku`
- `category_baseline`
- `insufficient_history`

`allowed_fallback_depth` ограничивает, насколько глубоко engine может пройти по этой цепочке.

## Seed data

В seed уже зашиты не только голые defaults, но и примеры реальных policy-настроек:

- разные горизонты резерва
- разные safety factors
- разные priority levels
- `notes`
- `effective_from`
- пример `sku_override`
- пример `category_override`

Этого достаточно, чтобы локальная среда вела себя как настоящий policy-driven backend, а не как демо-математика в контроллере.

## Что остаётся на следующий проход

- UI редактирования политик
- versioning policy changes
- approval trail
- inclusion / exclusion rules в engine
- richer override schema по service level / lead time / client segment
