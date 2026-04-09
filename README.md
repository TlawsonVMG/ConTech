# ConTech

Base design and application scaffold for a roofing and siding CRM / lead-tracking platform.

ConTech now supports both:

- SQLite for local development and quick demos
- PostgreSQL for pilot/live deployments

## Run the Flask app locally

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python app.py
```

Then open `http://127.0.0.1:5000`.

## Public pilot / server setup

ConTech is now set up for a safer pilot, but a public deployment still needs a proper server, HTTPS, and environment variables.

The app now reads plain environment variables from the shell or a local `.env` file.

For Render, use the included `render.yaml` Blueprint and follow [docs/render-deployment.md](docs/render-deployment.md).

### Minimum production environment variables

Copy `.env.example` and set real values for:

- `CONTECH_ENV=production`
- `SECRET_KEY`
- `DATABASE_URL=postgresql://contech:password@host:5432/contech`
- `AUTO_INIT_DB=false`
- `SEED_DEMO_DATA=false`
- `SESSION_COOKIE_SECURE=true`
- `TRUST_PROXY_HEADERS=true`

### First-time database initialization on a server

For a clean production database:

```powershell
flask --app wsgi init-db
```

For a staging/demo environment with sample data:

```powershell
flask --app wsgi init-db --with-demo-data
```

### Run behind a production server

This repo now includes `serve.py`, `wsgi.py`, `Procfile`, and `Dockerfile`.

Simple production entrypoint:

```powershell
python serve.py
```

Recommended real deployment shape:

- Run `python serve.py` or `wsgi.py` behind HTTPS
- Put a reverse proxy/load balancer in front of the app
- Mount the `instance/` directory on persistent storage
- Keep `instance/uploads/job-documents/` persistent and backed up
- Do not expose demo accounts on a public server

### Move an existing SQLite app into PostgreSQL

Initialize a clean PostgreSQL database and copy the current SQLite data into it:

```powershell
flask --app wsgi migrate-to-postgres --source-sqlite instance\contech.sqlite3 --target-url "postgresql://contech:password@localhost:5432/contech"
```

Notes:

- The target database should be empty unless you pass `--skip-init`
- Copy the `instance/uploads/job-documents/` folder separately if you want field documents on the new server too
- After migration, keep `DATABASE_URL` set and ConTech will use PostgreSQL automatically

### Public feedback collection

- Public feedback form: `/pilot-feedback`
- Internal feedback inbox: `/feedback/inbox`
- Health endpoint: `/api/health`
- Readiness endpoint: `/api/ready`
- Failed login attempts are now throttled
- CSRF protection is enabled outside tests

### Operational checks and backups

Check the database connection, schema version, and seeded record counts:

```powershell
python -m flask --app wsgi check-db
```

Create a PostgreSQL/database plus upload backup:

```powershell
python tools\backup_contech.py
```

Backup artifacts are written under `backups/`, which is intentionally ignored by Git.

## Demo sign-in accounts

- Admin: `admin` / `ConTech!2026`
- Sales: `micah` / `Roofing!2026`
- Accounting: `accounting` / `Ledger!2026`

## Run the workflow tests

```powershell
.venv\Scripts\python -m unittest tests.test_auth_crm -v
```

## Field execution uploads

- Job-document uploads are stored under `instance\uploads\job-documents\`
- Change orders now keep revision history each time they are created or edited
- Uploaded field files are limited to 16 MB through the Flask app config

## Static preview mode

The frontend still works as a static prototype too:

```powershell
python -m http.server 8000
```

Then visit `http://127.0.0.1:8000`.

This is useful for GitHub Pages previews. When the app is served through Flask, it will also pull seeded data from SQLite through `/api/bootstrap`.

## Included in this foundation

- `app.py` - local Flask entry point
- `contech/` - backend package, schema, seed data, routes, and API services
- `index.html` - interactive ConTech UI shell
- `styles.css` - red and white block-style design system
- `app.js` - UI rendering with API bootstrap fallback
- `docs/research-notes.md` - product research from current contractor CRM platforms
- `docs/contech-product-blueprint.md` - architecture, workflows, entities, and confirmed phase-one scope
- `docs/postgresql-migration.md` - PostgreSQL rollout notes and migration checklist
- `docs/launch-runbook.md` - pilot launch checks, backup routine, and rollback notes
- `docs/render-deployment.md` - Render Blueprint deployment steps
- `requirements.txt` - Python dependencies
