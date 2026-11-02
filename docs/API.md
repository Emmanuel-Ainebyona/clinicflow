# API reference

Base path `/api`. Responses: `{"data": ...}` (+ `"meta": {page, per_page, total, pages}` for lists) or `{"error": {"code", "message", "details"?}}`.
Authenticate with `Authorization: Bearer <token>` from `POST /api/auth/login`. Public endpoints: `GET /api/health`, `POST /api/auth/register`, `POST /api/auth/login`.
List endpoints accept `q`, `page`, `per_page` (max 100), `sort`, `order=asc|desc` and resource-specific filters.

## Endpoints (generated from the running app)

| Path | Methods |
|---|---|
| `/api/appointments` | GET |
| `/api/appointments` | POST |
| `/api/appointments/Falseaid>/cancel` | POST |
| `/api/appointments/Falseaid>/status` | POST |
| `/api/appointments/Falserid>` | GET |
| `/api/audit` | GET |
| `/api/auth/login` | POST |
| `/api/auth/logout` | POST |
| `/api/auth/me` | GET |
| `/api/auth/register` | POST |
| `/api/directory` | GET |
| `/api/health` | GET |
| `/api/patients` | GET |
| `/api/patients` | POST |
| `/api/patients/Falserid>` | DELETE |
| `/api/patients/Falserid>` | GET |
| `/api/patients/Falserid>` | PATCH, PUT |
| `/api/prescriptions` | GET |
| `/api/prescriptions` | POST |
| `/api/prescriptions/Falserid>` | GET |
| `/api/stats` | GET |
| `/api/users` | GET |
| `/api/users/Falserid>` | GET |
| `/api/users/Falserid>` | PATCH, PUT |
| `/api/users/Falseuid>/reset-password` | POST |
| `/api/visit-notes` | GET |
| `/api/visit-notes` | POST |
| `/api/visit-notes/Falserid>` | GET |
| `/api/visit-notes/Falserid>` | PATCH, PUT |

## Example

```bash
TOKEN=$(curl -s localhost:8000/api/auth/login -H 'Content-Type: application/json' \
  -d '{"email":"admin@demo.test","password":"Demo-Pass-2026!"}' | python3 -c 'import sys,json;print(json.load(sys.stdin)["data"]["token"])')
curl -s localhost:8000/api/stats -H "Authorization: Bearer $TOKEN"
```
