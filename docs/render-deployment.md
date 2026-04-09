# Render Deployment

This project includes a `render.yaml` Blueprint for an invite-only ConTech pilot.

## What Render Will Create

- Web service: `contech`
- PostgreSQL database: `contech-db`
- Persistent disk for field/job-document uploads: `/var/data`
- Health check: `/api/ready`
- Generated production `SECRET_KEY`
- Prompted first-admin password through `BOOTSTRAP_ADMIN_PASSWORD`

## Dashboard Steps

1. Push this repository to GitHub.
2. In Render, choose **New > Blueprint**.
3. Select the GitHub repository that contains ConTech.
4. Render should detect `render.yaml`.
5. When prompted for `BOOTSTRAP_ADMIN_PASSWORD`, enter a strong password for the first ConTech admin account.
6. Let Render create the web service and PostgreSQL database.
7. After deployment finishes, open the Render service URL and verify `/api/ready`.
8. Sign in with:

   ```text
   Username: admin
   Password: the BOOTSTRAP_ADMIN_PASSWORD value you entered in Render
   ```

## Important Notes

- `SEED_DEMO_DATA` is set to `false` for Render, so public pilot deployments do not expose demo users.
- The first deploy uses `python -m flask --app wsgi ensure-db`, which initializes only an empty database and refuses to overwrite an existing partial schema.
- Render uses the database's internal connection string for `DATABASE_URL`.
- External PostgreSQL access is disabled in the Blueprint with `ipAllowList: []`.
- Uploaded field documents are stored on the persistent disk under `/var/data/uploads/job-documents`.

## Post-Deploy Checks

Run these from Render Shell or locally against the deployed service where appropriate:

```powershell
python -m flask --app wsgi check-db
```

Then open:

- `/api/ready`
- `/login`
- `/pilot-feedback`
- `/feedback/inbox`

Do not invite testers until `/api/ready` returns `ready`.
