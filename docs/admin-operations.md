# Admin Operations

## Admin surface

The frontend admin/operator workspace lives at `/admin`.

Current panels:

- freshness and backlog KPIs
- environment/health summary
- users and roles
- background jobs
- export jobs
- audit trail
- operational warnings and deployment posture hints

## API surface

- `GET /api/admin/users`
- `PATCH /api/admin/users/{id}/role`
- `GET /api/admin/audit-events`
- `GET /api/admin/jobs`
- `GET /api/admin/jobs/{id}`
- `POST /api/admin/jobs/{id}/retry`
- `GET /api/admin/system/freshness`
- `GET /api/admin/system/health-details`

## Intended users

`admin`

- full operator visibility
- role changes
- job retries

`operator`

- visibility into jobs, freshness, exports, and audit
- safe retries through admin read scope
- no user-role management

## Safe retry policy

Current retry support is intentionally conservative.

Supported retry targets:

- `validate_upload`
- `apply_upload`
- `refresh_analytics`
- `generate_export`

Retries are blocked for unsupported or unsafe job types.
