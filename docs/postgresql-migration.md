# PostgreSQL Migration Notes

ConTech can now run on either SQLite or PostgreSQL.

## What Changed

- `DATABASE_URL` now switches the app into PostgreSQL mode automatically.
- `flask --app wsgi init-db` now creates a PostgreSQL schema when `DATABASE_URL` points to PostgreSQL.
- `flask --app wsgi migrate-to-postgres` copies the current SQLite data set into PostgreSQL.
- Seed/demo inserts now reseed PostgreSQL identity sequences so new records continue incrementing correctly.

## Recommended Cutover Order

1. Back up the current SQLite file and `instance/uploads/job-documents/`.
2. Create the PostgreSQL database and credentials.
3. Set `DATABASE_URL` in `.env` or the server environment.
4. Run:

   ```powershell
   flask --app wsgi migrate-to-postgres --source-sqlite instance\contech.sqlite3 --target-url "postgresql://contech:password@host:5432/contech"
   ```

5. Copy the uploaded job-document files to the target server's persistent `instance/uploads/job-documents/` directory.
6. Start ConTech with `python serve.py`.
7. Smoke-test login, Customer 360, quotes, jobs, dispatch, purchasing, invoices, and document downloads.

## Current Scope

This migration layer is designed to keep the existing raw-SQL app working with PostgreSQL without a full ORM rewrite.

What is covered now:

- app-level PostgreSQL connections
- PostgreSQL schema initialization
- SQLite-to-PostgreSQL data copy command
- database-agnostic login throttling and workboard date logic

What should still follow before a broader production launch:

- migration files/versioning beyond the current baseline schema
- PostgreSQL-backed integration tests in CI
- database backup/restore drills
- connection pooling and secrets management on the live host
