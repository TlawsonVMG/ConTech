# ConTech App Architecture

## Current stack

- Frontend: plain HTML, CSS, and JavaScript
- Backend: Flask
- Database: SQLite
- Dev workflow: VS Code + Python virtual environment

## Why this stack

Node and npm were not available in the current environment, but Python and pip were. This scaffold keeps ConTech easy to run locally right now while still giving us a clean path to expand into a larger application.

## Current repo layout

- `app.py`
  Flask entry point for local development.
- `contech/__init__.py`
  App factory and configuration.
- `contech/db.py`
  SQLite connection handling and database bootstrap command.
- `contech/schema.sql`
  Phase-one schema foundation.
- `contech/seed.py`
  Demo branch, customer, operations, and accounting seed data.
- `contech/routes/web.py`
  Serves the current frontend files.
- `contech/routes/api.py`
  JSON endpoints for health and bootstrap data.
- `contech/services/bootstrap.py`
  Builds the frontend payload from seeded database records.
- `index.html`, `styles.css`, `app.js`
  Current ConTech frontend shell and interaction layer.

## Phase-one domain support

The scaffold now accounts for:

- Single-branch operations
- Residential and commercial customers
- Sales pipeline and quote flow
- Jobs and dispatch records
- Inventory and purchasing queue
- Full-bookkeeping foundation with ledger tables and journal entry tables
- Payroll runs, employees, bank accounts, cards, receivables, and vendor payables

## Recommended next build steps

1. Replace the seeded bootstrap-only API with real CRUD endpoints for customers, leads, opportunities, quotes, jobs, and invoices.
2. Add authentication and role-based access for sales, dispatch, inventory, and accounting users.
3. Break the current single-page frontend into module-specific screens and forms.
4. Add migrations instead of full schema resets for database evolution.
5. Decide whether phase two stays in server-rendered Python or moves to a dedicated frontend app once a Node toolchain is available.
