# ConTech Launch Runbook

This runbook is for an invite-only pilot launch where ConTech is hosted with PostgreSQL and persistent upload storage.

## Preflight

Run these from the project root before inviting testers:

```powershell
.venv\Scripts\python -m unittest tests.test_auth_crm -v
.venv\Scripts\python -m flask --app wsgi check-db
.venv\Scripts\python -m flask --app wsgi routes
```

Then open:

- `/api/health`
- `/api/ready`
- `/login`
- `/portal/login`
- `/pilot-feedback`

## Backup

Create a database and job-document backup before every launch deploy:

```powershell
.venv\Scripts\python tools\backup_contech.py
```

The backup utility stores timestamped backups under `backups/`. It uses `pg_dump` for PostgreSQL and keeps the password in environment variables instead of on the process command line.

## Launch Smoke Test

After deploy or restart:

1. Confirm `/api/ready` returns `ready`.
2. Sign in as an admin account.
3. Open Customer 360 for a seeded or test account.
4. Create a test internal note and task.
5. Create one customer portal login with a temporary password.
6. Open `/portal/login` in a separate browser session and confirm that customer sees only their own quotes, jobs, deliveries, invoices, documents, contacts, and messages.
7. Send one portal message and confirm it appears on that Customer 360 record.
8. Open quotes, jobs, purchasing, dispatch, invoices, and feedback inbox.
9. Submit one `/pilot-feedback` test item from a separate browser session.
10. Confirm the feedback appears in `/feedback/inbox`.
11. Upload and download a small job-document test file if the pilot host has persistent storage mounted.

## Pilot Feedback Loop

During the first live trial, review feedback at least once per day:

- mark high-friction feedback as `in_review`
- keep internal notes short and actionable
- prioritize launch blockers over feature polish
- keep all customer-facing testers on invite-only access until auth, backup, and restore have been exercised

## Rollback

If the pilot app becomes unstable:

1. Stop the app process.
2. Keep the newest `backups/contech-*` folder untouched.
3. Revert the app code to the last known working version.
4. Restore the PostgreSQL dump to a clean database.
5. Unzip `job-document-uploads.zip` back into `instance/uploads/job-documents/`.
6. Restart the app and verify `/api/ready`.

Do not delete the broken database until the replacement has been verified.
