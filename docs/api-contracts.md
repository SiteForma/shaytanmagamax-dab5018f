# API Contracts

Primary route families:

- `/api/health`
- `/api/auth`
- `/api/dashboard`
- `/api/catalog`
- `/api/clients`
- `/api/sales`
- `/api/stock`
- `/api/inbound`
- `/api/reserve`
- `/api/uploads`
- `/api/mapping`
- `/api/quality`
- `/api/assistant`

Frontend compatibility rule:

- backend schemas stay Pythonic (`snake_case`)
- `apps/web/src/services/*` maps them into the premium shell’s existing camelCase contracts
- this allows incremental replacement of mocks without rewriting pages

Error envelope:

```json
{
  "code": "invalid_credentials",
  "message": "Invalid email or password",
  "request_id": "..."
}
```
