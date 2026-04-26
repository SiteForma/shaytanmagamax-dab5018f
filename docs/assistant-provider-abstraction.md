# Assistant Provider Abstraction

Assistant layer спроектирован provider-agnostic.

## Current Providers

### `deterministic`

Текущий production-safe provider.

Что делает:

- использует rules-first routing;
- вызывает реальные domain tools;
- композит structured answer без LLM;
- всегда доступен как fallback mode.

### `openai_compatible`

Это optional provider для двух ограниченных задач:

- planner step: интерпретировать запрос, выбрать `intent`, безопасный `toolQuestion` и allowlisted `toolNames`;
- finalizer step: отредактировать формулировки grounded draft без изменения фактов.

Текущее поведение:

- при включённом LLM provider сначала вызывается planner, даже если deterministic router не распознал запрос;
- provider не получает прямого доступа к БД и не может выполнить произвольный tool;
- backend выполняет только allowlisted domain tools и сохраняет deterministic required tools для каждого intent;
- provider может переписать `title`, `summary` и narrative-тексты секций;
- metrics, tool outputs, source refs и warnings остаются anchored в backend domain layer;
- если конфиг неполный или provider недоступен, assistant автоматически уходит в deterministic fallback;
- out-of-scope запросы могут попадать в planner только для классификации, но ответ остаётся детерминированным отказом без domain tools.

## Config Surface

В `apps/api/app/core/config.py` добавлены:

- `assistant_provider`
- `assistant_llm_enabled`
- `assistant_openai_base_url`
- `assistant_openai_api_key`
- `assistant_openai_model`

Рекомендуемый local/dev runtime:

- `assistant_provider=openai_compatible`
- `assistant_llm_enabled=true`
- `assistant_openai_base_url=https://api.openai.com/v1`
- `assistant_openai_api_key=...`

Секреты должны жить только в локальном `.env`, который игнорируется git.

## Why This Boundary Exists

Провайдер не должен:

- определять source of truth;
- рассчитывать резерв вместо reserve engine;
- обходить domain services;
- зашивать бизнес-логику в prompts.

Провайдер выбирает маршрут и редактирует answer composition, но source of truth остаётся в backend services.

## Future Integration Contract

LLM provider должен получать:

- typed intent;
- structured context bundle;
- explicit source refs;
- tool outputs;
- prompt templates из отдельного prompt layer.
- список разрешённых intents/tools для planner step.

LLM provider не должен получать raw unrestricted database dump.

## Current Network Contract

OpenAI-compatible provider сейчас использует `POST /chat/completions` и просит вернуть JSON-объект:

Planner:

- `intent`
- `confidence`
- `toolQuestion`
- `toolNames`
- `rationale`

Finalizer:

- `title`
- `summary`
- `sections[]` с optional `title`, `body`, `items`

Если формат ответа нарушен, orchestration не ломается и переключается на deterministic mode.

## Safe Fallback Rule

Если provider:

- выключен;
- не сконфигурирован;
- недоступен;
- таймаутится;

assistant обязан остаться полезным за счёт deterministic mode.

Это не optional behavior, а часть product contract.
