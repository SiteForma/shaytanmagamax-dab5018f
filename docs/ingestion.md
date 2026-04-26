# Ingestion

Phase 2 turns uploads into a real ingestion subsystem with explicit lineage, mapping, validation, and apply stages.

## Source Types

- `sales`
- `stock`
- `diy_clients`
- `category_structure`
- `inbound`
- `raw_report`

Each source type is defined by:

- canonical fields
- required fields
- synonym dictionary for header suggestion
- validation rules
- apply semantics
- `supports_apply` flag

The source-type registry lives in [`apps/api/app/modules/mapping/service.py`](/Users/sergeyselyuk/Documents/shaytanmagamax-dab5018f/apps/api/app/modules/mapping/service.py).

## Lifecycle

1. `POST /api/uploads/files`
2. original file is stored through the object storage abstraction
3. `UploadBatch` + `UploadFile` are created
4. parse job extracts headers and preview rows
5. source type is detected or respected from UI input
6. mapping suggestions are generated
7. file moves to one of:
   - `mapping_required`
   - `validating`
   - `ready_to_apply` for `raw_report`
8. validation persists `UploadedRowIssue` rows and bridges them into `QualityIssue`
9. file moves to:
   - `issues_found`
   - `ready_to_apply`
   - `failed`
10. apply writes normalized rows into operational tables
11. analytics refresh materializes parquet + DuckDB outputs
12. final state becomes:
   - `applied`
   - `applied_with_warnings`
   - `failed`

## Status Model

- `uploaded`
- `parsing`
- `mapping_required`
- `validating`
- `issues_found`
- `ready_to_apply`
- `applying`
- `applied`
- `applied_with_warnings`
- `failed`

Status transitions are recorded into `UploadBatch.status_payload.history`. Job execution trail is stored in `JobRun`.

## Lineage

For every upload the system persists:

- original filename
- source type and detected source type
- uploader id
- upload timestamp
- checksum
- file size and mime type
- storage key
- parsing version
- normalization version
- selected mapping template id
- preview headers and sample rows
- validation summary
- row counts
- apply counts
- duplicate upload linkage
- job history

## Apply Semantics

- `sales`: upsert by `client_id + sku_id + period_month`
- `stock`: append snapshot history by row
- `diy_clients`: upsert client policy
- `category_structure`: rebuild hierarchy nodes incrementally and attach SKU categories
- `inbound`: upsert by `external_ref`
- `raw_report`: storage-only for now, no operational apply

## Extension Points

To add a new report type:

1. extend the source-type spec registry
2. add validation rules in [`validation.py`](/Users/sergeyselyuk/Documents/shaytanmagamax-dab5018f/apps/api/app/modules/uploads/validation.py)
3. add apply logic in [`service.py`](/Users/sergeyselyuk/Documents/shaytanmagamax-dab5018f/apps/api/app/modules/uploads/service.py)
4. expose canonical fields in the frontend service layer if needed
