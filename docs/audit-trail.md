# Audit Trail

## Purpose

Critical product actions are persisted into `SystemEvent` and exposed through `/api/admin/audit-events`.

Audit is not just log output. Each event is queryable later and linked to request context.

## Event shape

Each audit record includes:

- actor user id
- action
- target type
- target id
- status
- request id
- optional trace id
- timestamp
- context payload

## Actions currently recorded

- `auth.login`
- `auth.permission_denied`
- `uploads.file_uploaded`
- `uploads.batch_uploaded`
- `uploads.mapping_suggested`
- `uploads.mapping_saved`
- `uploads.batch_mapping_saved`
- `uploads.validated`
- `uploads.applied`
- `uploads.batch_applied`
- `mapping.template_created`
- `mapping.template_updated`
- `mapping.template_applied`
- `mapping.sku_alias_created`
- `mapping.client_alias_created`
- `reserve.run_created`
- `assistant.session_created`
- `assistant.session_updated`
- `assistant.message_posted`
- `assistant.query`
- `exports.generate`
- `exports.download`
- `admin.user_role_changed`
- `admin.job_retry`

## Operational usage

Use audit events to answer:

- who uploaded or applied a file
- who changed a mapping template
- who recalculated reserve and with what scope
- who downloaded an export
- why an action was denied

## Notes

- audit payloads intentionally keep business context lightweight but useful
- request ids make it possible to correlate UI errors, API logs, and audit records
- sensitive secrets are not persisted in audit payloads
