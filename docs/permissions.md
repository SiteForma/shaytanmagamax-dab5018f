# Permissions

## Model

`Shaytan Machine` uses a role plus capability model.

Seeded roles:

- `admin`
- `operator`
- `analyst`
- `viewer`

Capability examples:

- `dashboard:read`
- `reserve:read`
- `reserve:run`
- `uploads:read`
- `uploads:write`
- `uploads:apply`
- `mapping:read`
- `mapping:write`
- `quality:read`
- `inbound:sync`
- `assistant:query`
- `exports:generate`
- `exports:download`
- `admin:read`
- `admin:manage-users`
- `settings:manage`

## Enforcement

Backend enforcement happens in `apps/api/app/api/dependencies.py` through `require_capability(resource, action)`.
Router-level protection is centralized in `apps/api/app/api/router.py`.

Important properties:

- frontend visibility is advisory only
- backend is the source of truth
- denied operations return a structured `permission_denied` envelope with request id
- permission denials are also written to the audit trail as `auth.permission_denied`

## Read access posture

Operational and product read surfaces are protected at the backend before the request reaches feature routers.

Protected by router-level `require_user + require_capability`:

- `dashboard` → `dashboard:read`
- `catalog` → `catalog:read`
- `clients` → `clients:read`
- `stock` → `stock:read`
- `inbound` → `inbound:read`
- `sales` → `sales:read`
- `reserve` → `reserve:read`
- `uploads` → `uploads:read`
- `mapping` → `mapping:read`
- `quality` → `quality:read`
- `assistant` → `assistant:query`

Mixed-capability surfaces keep route-level checks per endpoint:

- `inbound`
  - timeline read is covered by `inbound:read`
  - Google Sheet manual sync requires `inbound:sync`
- `exports`
  - generation routes require `exports:generate`
  - job listing/detail/download routes require `exports:download`
- `admin`
  - read diagnostics require `admin:read`
  - role mutation requires `admin:manage-users`

This split is intentional: `exports` and `admin` contain both read and stronger write-sensitive actions, so the route itself remains the source of truth for the exact capability.

## Intentionally open endpoints

The following routes remain open by design and are not product-data read surfaces:

- `POST /api/auth/login`
- `GET /api/health/live`
- `GET /api/health/ready`

`GET /api/auth/me` is authenticated but does not require a separate capability because it returns only the caller session context.

## Current role posture

`admin`

- full access via `*:*`
- manages users and settings
- can inspect and retry operational jobs

`operator`

- read access to operational surfaces
- can run reserve
- can upload, validate, apply, map, export
- can manually sync inbound Google Sheet data
- can inspect admin/operator panel but cannot change user roles

`analyst`

- read access to analytical surfaces
- can run reserve
- can upload, map, apply, export
- can manually sync inbound Google Sheet data
- no admin panel access

`viewer`

- read-only product access
- can read reserve, uploads, and mapping review surfaces
- can open assistant queries
- cannot mutate uploads, mapping, reserve, or exports
- cannot trigger inbound Google Sheet sync

## Frontend behavior

Frontend uses capability-aware navigation and guarded routes.

- unavailable sections are hidden from the sidebar
- protected routes render a calm access-denied state instead of surfacing raw `403` fetch failures
- mutation buttons are disabled when the user lacks the corresponding capability

## Extension points

- explicit deny policies per role
- per-client or per-module scoped policies
- policy-aware assistant filtering
- SCIM/SSO-backed user provisioning later
