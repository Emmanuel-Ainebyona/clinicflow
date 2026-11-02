# ClinicFlow

> Clinic appointment scheduling & patient records

A clinic management application with conflict-free scheduling and strict object-level access control: patients see only their own data, doctors only their own appointments, notes and prescriptions.

**Problem solved:** Clinics need to schedule without double booking while keeping patient records private, and need to know who accessed what.

## Features
- Booking with clinic-hours, future-date and duration rules; double booking of a doctor or a patient is rejected by the application and by database triggers
- Self-registered users become patients automatically and can book and cancel their own appointments
- Visit notes readable only by the authoring doctor and admins; prescriptions visible to the treating doctor and the patient
- Every read of a patient record or visit note is written to the audit log
- Roles: admin, doctor, receptionist, patient (default)
- Role-aware dashboard

## Roles
admin: all. doctor: own appointments, patients they treat, own notes/prescriptions. receptionist: patients and bookings. patient: own record, bookings and prescriptions.

## Technology stack
| Layer | Technology |
|---|---|
| Frontend | Vanilla JavaScript single-page app (no build step), responsive CSS, accessible dialogs/forms |
| Backend | Python 3.12, Flask 3, PyJWT, scrypt password hashing (standard library) |
| Database | SQLite (WAL-safe, foreign keys on) with versioned SQL migrations |
| Ops | Docker, Docker Compose, GitHub Actions CI, gunicorn |

> **Design note:** the stack was chosen so the project runs from a clean checkout with two dependencies and no build step. The data layer is plain SQL with explicit transactions, so porting to PostgreSQL is mostly a matter of dialect changes in `migrations/` and `app/core.py` (see *Limitations*).

## Architecture
```
Browser (frontend/*.js) --JSON/HTTPS--> Flask app (app/)
   config.js defines screens           core.py: auth, RBAC, validation, generic CRUD Resource, audit, security headers
   ui.js renders tables/forms          __init__.py: this project's resources, business rules, endpoints
                                       SQLite via migrations/*.sql (000_base = users, audit; 001 = domain schema)
```

## Quick start
```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env            # optional in development (a random SECRET_KEY is generated per process)
python manage.py migrate        # applies migrations (also applied automatically on startup)
python manage.py seed           # loads clearly-labelled demo data
python manage.py run            # http://127.0.0.1:8000
```
Demo accounts (admin@demo.test, doctor@demo.test, doctor2@demo.test, reception@demo.test, patient@demo.test) all use the local-only password `Demo-Pass-2026!`. **Never use demo credentials or demo data in production.**

New users can also register on the sign-in screen. Password recovery by e-mail is not implemented (no mail service); admins reset passwords from the Users screen.

## Environment variables
See `.env.example`. Key ones: `APP_ENV` (`production` enforces `SECRET_KEY` of 32+ chars and adds HSTS), `SECRET_KEY`, `DATABASE_PATH`, `TOKEN_TTL_SECONDS`, `CORS_ORIGINS`, `RATELIMIT_ENABLED`, `RATELIMIT_LOGIN`.

## Database
Migrations live in `migrations/` and are applied in filename order, tracked in `schema_migrations`. Seed data: `python manage.py seed` (idempotent: skipped if users exist). Integrity is enforced by primary/foreign keys, CHECK constraints, unique and partial indexes and triggers.

## Testing
```bash
python -m unittest discover -s tests -t . -v     # backend unit + API integration + security tests
for f in frontend/*.js; do node --check "$f"; done  # frontend syntax check
python manage.py seed && python manage.py run &      # then:
python scripts/smoke.py http://127.0.0.1:8000        # live HTTP smoke test
```
**Result of the last run in the authoring environment:** Ran 39 tests in 15.031s OK  (39 tests; 39 PASS).
Full per-test results: see `docs/TEST_REPORT.md`.

**Not covered:** browser-level UI tests (the frontend was only syntax-checked, never exercised in a real browser), dependency vulnerability scanning (`pip-audit` runs in CI), Docker image build, and load/accessibility testing. Screenshots are not included because none could be captured honestly.

## API
See `docs/API.md` (generated from the running application's routes).

## Project structure
```
.env.example
.github/workflows/ci.yml
.gitignore
CONTRIBUTING.md
Dockerfile
SECURITY.md
app/__init__.py
app/core.py
app/seed.py
docker-compose.yml
docs/API.md
frontend/config.js
frontend/index.html
frontend/styles.css
frontend/ui.js
manage.py
migrations/000_base.sql
migrations/001_clinicflow.sql
requirements-prod.txt
requirements.txt
scripts/smoke.py
tests/__init__.py
tests/base.py
tests/test_core.py
tests/test_domain.py
```

## Production build and deployment (Linux)
**Docker:** `cp .env.example .env`, set `SECRET_KEY`, then `docker compose up -d --build`. Data lives in the `appdata` volume.

**Without Docker (systemd + nginx):**
```bash
sudo useradd --system --home /srv/clinicflow clinicflow; sudo git clone <repo> /srv/clinicflow; cd /srv/clinicflow
sudo python3 -m venv .venv && sudo .venv/bin/pip install -r requirements-prod.txt
sudo -u clinicflow cp .env.example .env     # set APP_ENV=production, SECRET_KEY, DATABASE_PATH=/var/lib/clinicflow/app.db
```
`/etc/systemd/system/clinicflow.service`:
```ini
[Service]
User=clinicflow
WorkingDirectory=/srv/clinicflow
EnvironmentFile=/srv/clinicflow/.env
ExecStart=/srv/clinicflow/.venv/bin/gunicorn --bind 127.0.0.1:8000 --workers 1 --threads 8 "app:create_app()"
Restart=always
[Install]
WantedBy=multi-user.target
```
nginx site: `location / { proxy_pass http://127.0.0.1:8000; proxy_set_header Host $host; proxy_set_header X-Forwarded-For $remote_addr; proxy_set_header X-Forwarded-Proto $scheme; }`, then `sudo certbot --nginx -d your.domain` for HTTPS.
Create the first real admin by seeding nothing in production: register a user, then promote it with `sqlite3 $DATABASE_PATH "UPDATE users SET role='admin' WHERE email='you@example.com'"`.

**Development vs production:** development uses a random per-process secret and the Flask dev server; production requires `SECRET_KEY`, runs under gunicorn behind HTTPS and must not load demo seed data.

## Backup and restore
```bash
sqlite3 "$DATABASE_PATH" ".backup '/backups/clinicflow-$(date +%F).db'"   # safe while running
# restore: stop the service, then
cp /backups/clinicflow-YYYY-MM-DD.db "$DATABASE_PATH" && sudo systemctl start clinicflow
```

## Troubleshooting
| Symptom | Fix |
|---|---|
| `RuntimeError: SECRET_KEY must be set in production` | Set a 32+ character `SECRET_KEY` (see `.env.example`). |
| `Address already in use` | Another process uses the port: `PORT=8001 python manage.py run`. |
| `database is locked` | Only one process should write; run a single gunicorn worker. |
| Logged out after every restart in development | No `SECRET_KEY` set; add one to `.env`. |
| `ModuleNotFoundError: flask` | Activate the venv and `pip install -r requirements.txt`. |
| 429 responses | Rate limit hit; wait a minute or raise `RATELIMIT_LOGIN`. |

## Limitations (please read)
- Object-level authorisation is enforced in the data layer through per-resource scope filters, so out-of-scope records return 404 rather than leaking existence.
- Limitation: sensitive fields are not encrypted at rest. For real clinical data add field-level encryption or an encrypted database (e.g. SQLCipher/PostgreSQL with pgcrypto), and a compliance review.
- SQLite and an in-process rate limiter assume a single application process.
- No refresh tokens or MFA; see `SECURITY.md`.
- Tests ran against SQLite only; the PostgreSQL port has not been attempted.

## Suggested GitHub metadata
- **Description:** Clinic appointment scheduling & patient records (Flask + SQLite, RBAC, audit log, tests, Docker, CI)
- **Topics:** healthcare scheduling appointments access-control flask sqlite rbac audit-log portfolio
- **Suggested commits:** feat: patients with object-level scoping; feat: appointment booking with overlap protection; feat: visit notes and prescriptions; feat: audit of record reads; test: permission matrix and race tests; chore: docker, CI, docs

## License
No license has been selected. Add a `LICENSE` file of your choice (for example MIT) before publishing if you want others to reuse the code.
