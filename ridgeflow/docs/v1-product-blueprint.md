# RidgeFlow V1 Product Blueprint

Date: April 11, 2026

## Product aim

RidgeFlow is an AI-native roofing takeoff and project workflow platform designed to turn blueprint PDFs into reviewable material plans, then carry those plans through estimator review, procurement, and production handoff.

## V1 positioning

RidgeFlow is a standalone product.

It is not a plugin and it is not tied to an existing CRM or local database.

V1 is focused on:

1. Roofing takeoffs only
2. Blueprint PDF intake
3. Estimator review before approval
4. Project workflow from intake through approved takeoff
5. Shared team coordination around each job

## Core V1 workflows

### 1. Project intake

- Create a new project
- Assign estimator
- Set bid date and due date
- Choose primary roof system
- Track job status from intake to close

### 2. Blueprint ingestion

- Upload one or more PDF plan sets
- Store blueprint metadata
- Track version labels and phase labels
- Keep files attached to the project record

### 3. AI-native takeoff

- Select a blueprint
- Choose roof system
- Feed extracted geometry into the native takeoff engine
- Generate material assemblies and quantities
- Save confidence and review status
- Approve the takeoff after estimator review

### 4. Project workflow

- Manage tasks by status
- Track blockers and due dates
- Keep activity history by project
- Hand off from estimating to operations cleanly

### 5. Team communication

- Project-level message feed
- Fast coordination between estimator, PM, and operations
- Shared context anchored to the project itself

## Target users

### Estimator

- Uploads blueprints
- Runs AI takeoffs
- Reviews generated material lists
- Approves final takeoff package

### Project manager

- Monitors approved takeoffs
- Creates follow-up tasks
- Tracks blockers and procurement readiness

### Operations coordinator

- Reviews scope readiness
- Uses approved quantities during ordering and scheduling

## V1 domain model

### Team

- Owns users and projects

### User

- Estimator, project manager, operations, admin

### Project

- Job-level record
- Client, address, dates, status, roof system

### Blueprint

- PDF document metadata
- Version, phase, pages, upload state

### Takeoff run

- AI/native calculation event
- Linked to one blueprint
- Stores status, confidence, geometry, summary, and approval metadata

### Takeoff item

- Generated material line
- Category, material name, quantity, vendor hint, notes

### Task

- Workflow action owned by a team member
- Status, priority, due date

### Project message

- Chat message scoped to a project

### Project activity

- Immutable audit-style event log

## Architecture

### Frontend

- Server-rendered Flask templates
- Lightweight JavaScript for filtering and small UX enhancements
- Clean minimal UI optimized for estimators and PMs

### Backend

- Flask app factory
- Web routes for workflow pages
- JSON API routes for future SPA/mobile expansion
- Service layer for takeoff logic

### Data

- SQLite for local V1
- Separate database file under the RidgeFlow instance folder
- Easy upgrade path to PostgreSQL later

### Storage

- Local file storage for blueprint PDFs in V1
- Clear upload folder separation

## Native AI engine roadmap

The current codebase implements the product shell and the takeoff generation service.

The next layer for true automated blueprint understanding should add:

1. PDF ingestion and page rasterization
2. OCR and sheet classification
3. Roof plane and detail detection
4. Measurement extraction
5. Assembly selection by roof system
6. Confidence scoring and review prompts
7. Revision comparison across blueprint versions

## V1 status model

### Project status

- Intake
- Blueprint Review
- AI Processing
- Estimator Review
- Approved
- Ordered
- In Production
- Closed

### Takeoff status

- Queued
- Processing
- Review Required
- Approved

### Task status

- todo
- in_progress
- blocked
- done

## Folder structure

```text
ridgeflow/
  app.py
  serve.py
  requirements.txt
  docs/
  tests/
  ridgeflow/
    __init__.py
    db.py
    schema.sql
    seed.py
    routes/
    services/
    static/
    templates/
```

## Recommended next build phases

### Phase 1.1

- Add user authentication
- Add organization settings
- Add revision compare for plan sets

### Phase 1.2

- Integrate PDF vision pipeline
- Add async background workers
- Add review comments directly on takeoff items

### Phase 1.3

- Material supplier integrations
- Purchase order generation
- Cost benchmarking against historical jobs
