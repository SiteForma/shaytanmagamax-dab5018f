# Upload Center

## Product Flow

The Upload Center now works with real backend data instead of mock upload cards.

Backend endpoints used by the UI:

- `GET /api/uploads/files`
- `POST /api/uploads/files`
- `GET /api/uploads/files/{id}`
- `GET /api/uploads/files/{id}/preview`
- `POST /api/uploads/files/{id}/validate`
- `POST /api/uploads/files/{id}/apply`

## Frontend Integration

Primary frontend files:

- [`apps/web/src/features/uploads/UploadCenterPage.tsx`](/Users/sergeyselyuk/Documents/shaytanmagamax-dab5018f/apps/web/src/features/uploads/UploadCenterPage.tsx)
- [`apps/web/src/services/upload.service.ts`](/Users/sergeyselyuk/Documents/shaytanmagamax-dab5018f/apps/web/src/services/upload.service.ts)

The screen shows:

- upload intake
- source type selector
- upload history
- selected file summary
- readiness flags
- jump into mapping
- validate/apply actions

## UX Contract

The page stays premium-shell-first:

- no replacement of shell layout
- no generic admin rewrite
- same dark MAGAMAX language
- upload lifecycle shown as product states, not raw backend noise
