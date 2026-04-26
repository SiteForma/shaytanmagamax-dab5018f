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

Это optional provider для финальной редактуры ответа поверх grounded draft.

Текущее поведение:

- deterministic orchestration остаётся source of truth;
- provider получает только already grounded draft, а не доступ к сырой БД;
- provider может переписать `title`, `summary` и narrative-тексты секций;
- metrics, tool outputs, source refs и warnings остаются anchored в deterministic layer;
- если конфиг неполный, провайдер отвечает ошибкой, а assistant автоматически уходит в deterministic fallback.

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

Провайдер только финализирует answer composition поверх already grounded tool outputs.

## Future Integration Contract

LLM provider должен получать:

- typed intent;
- structured context bundle;
- explicit source refs;
- tool outputs;
- prompt templates из отдельного prompt layer.

LLM provider не должен получать raw unrestricted database dump.

## Current Network Contract

OpenAI-compatible provider сейчас использует `POST /chat/completions` и просит вернуть JSON-объект:

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
