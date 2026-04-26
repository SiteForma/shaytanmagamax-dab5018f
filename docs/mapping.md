# Mapping

## Goal

Mapping converts source headers into stable canonical fields before validation or apply.

## Suggestion Engine

The engine combines:

- lowercase normalization
- punctuation stripping
- Cyrillic transliteration
- source-specific synonym dictionaries
- fuzzy similarity scoring
- optional template boost

Primary implementation:

- [`normalize_mapping_token()`](/Users/sergeyselyuk/Documents/shaytanmagamax-dab5018f/apps/api/app/modules/mapping/service.py)
- [`suggest_canonical_field()`](/Users/sergeyselyuk/Documents/shaytanmagamax-dab5018f/apps/api/app/modules/mapping/service.py)

## Templates

Endpoints:

- `GET /api/mapping/templates`
- `POST /api/mapping/templates`
- `PATCH /api/mapping/templates/{id}`
- `POST /api/mapping/templates/{id}/apply`

Template payload stores:

- `name`
- `source_type`
- `version`
- `is_default`
- `is_active`
- `required_fields`
- `transformation_hints`
- header to canonical `mappings`

## Alias Tables

Alias support is intentionally explicit and auditable.

Endpoints:

- `GET /api/mapping/aliases/skus`
- `POST /api/mapping/aliases/skus`
- `GET /api/mapping/aliases/clients`
- `POST /api/mapping/aliases/clients`

Alias resolution is used during apply so repeated partner-specific spelling or SKU code variants do not require parser hacks.

## Current Canonical Field Sets

Examples:

- `sales`: `period_date`, `client_name`, `sku_code`, `quantity`, `revenue`
- `stock`: `snapshot_date`, `sku_code`, `stock_total`, `stock_free`, `warehouse_name`
- `diy_clients`: `client_name`, `reserve_months`, `safety_factor`, `priority`, `active`
- `category_structure`: `category_level_1..3`, `sku_code`, `product_name`
- `inbound`: `sku_code`, `eta_date`, `quantity`, `status`
- `raw_report`: storage-only, no operational canonical apply path yet
