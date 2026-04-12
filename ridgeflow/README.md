# RidgeFlow

RidgeFlow is a standalone V1 platform for AI-native roofing material takeoffs and project workflow management.

It is built as its own codebase and database, separate from the existing ConTech app in this workspace.

## What V1 includes

- Roofing-focused project intake
- PDF blueprint upload tracking
- Native PDF blueprint analysis pipeline
- Generated material assemblies for key roof systems
- Project dashboard and pipeline stages
- Task board for estimator and PM handoff
- Team chat by project
- Historical storage for projects, takeoffs, tasks, and activity

## Supported V1 roof systems

- Architectural shingles
- TPO
- EPDM
- Standing seam metal
- PVC
- Modified bitumen

## Tech stack

- Flask
- SQLite for local V1 storage
- Waitress for production serving
- Server-rendered HTML with lightweight JavaScript

## Run locally

```powershell
cd ridgeflow
..\.venv\Scripts\python.exe app.py
```

Then open `http://127.0.0.1:5051`.

If you prefer to use the production-style server:

```powershell
cd ridgeflow
..\.venv\Scripts\python.exe serve.py
```

## Database

RidgeFlow stores its data in its own local database:

- `ridgeflow\instance\ridgeflow.sqlite3`

Blueprint uploads are stored under:

- `ridgeflow\instance\uploads\blueprints\`

## Notes on the AI takeoff engine

This V1 codebase now includes:

- native PDF parsing for text-based blueprints
- rasterization workers for page image generation
- OCR workers for image-based text extraction
- vision-worker hooks for model-assisted sheet interpretation
- takeoff generation from stored blueprint analysis

RidgeFlow is ready for local PDF processing today, with optional model-backed vision analysis when an OpenAI API key is configured.

## Native blueprint pipeline in this codebase

Uploaded blueprint PDFs are now analyzed automatically by RidgeFlow's native parser layer.

The current pipeline can:

- detect page count from PDF structure
- extract readable text from text-based PDFs and many simple content streams
- classify likely roof-sheet labels
- detect roofing system keywords
- extract measurement hints such as roof area, perimeter, ridge, valley, eave, and waste
- compare newer blueprint versions against the prior set and flag material scope changes
- rank review priorities using estimator corrections and approved takeoff history
- store analysis history in the RidgeFlow database
- generate takeoff inputs directly from the latest stored blueprint analysis when enough signals are present

Current limitation:

- scanned image-only PDFs still need OCR or a vision model, which is the next planned layer

## Raster, OCR, and vision workers

RidgeFlow now includes a queued worker pipeline for blueprint enhancement:

1. Rasterize PDF pages into images
2. Run OCR on rendered pages
3. Run vision analysis on rendered pages
4. Consolidate worker outputs back into RidgeFlow blueprint analysis

### Worker commands

Queue a blueprint for worker processing:

```powershell
cd ridgeflow
..\.venv\Scripts\python.exe -m flask --app app.py queue-blueprint-workers 3
```

Run the worker once:

```powershell
cd ridgeflow
..\.venv\Scripts\python.exe -m flask --app app.py run-worker --once
```

Run several jobs:

```powershell
cd ridgeflow
..\.venv\Scripts\python.exe -m flask --app app.py run-worker --max-jobs 10
```

### Backends

Rasterization backends:

- `pdftoppm` if Poppler is installed and on PATH
- `magick` if ImageMagick is installed and on PATH

OCR backends:

- `tesseract` if Tesseract is installed and on PATH

Vision backends:

- `openai` when `OPENAI_API_KEY` is set

For local tests, RidgeFlow also includes mock backends.

### Recommended environment variables

- `RASTERIZER_BACKEND=auto`
- `PDFTOPPM_COMMAND=pdftoppm`
- `MAGICK_COMMAND=magick`
- `OCR_BACKEND=auto`
- `VISION_BACKEND=auto`
- `TESSERACT_COMMAND=tesseract`
- `OPENAI_VISION_MODEL=gpt-4.1`
- `OPENAI_VISION_DETAIL=high`

### Windows installation notes

For a local Windows setup, RidgeFlow works best with:

- Poppler for `pdftoppm`
- Tesseract OCR
- ImageMagick as an optional rasterizer fallback

If a tool is installed outside your shell PATH, you can pin the exact executable in `.env`:

```dotenv
RASTERIZER_BACKEND=pdftoppm
PDFTOPPM_COMMAND=C:\full\path\to\pdftoppm.exe
OCR_BACKEND=tesseract
TESSERACT_COMMAND=C:\full\path\to\tesseract.exe
VISION_BACKEND=auto
```

### Storage

Rendered page images are stored under:

- `ridgeflow\instance\uploads\blueprint-pages\`

## Key files

- `app.py` - local entry point
- `serve.py` - Waitress entry point
- `ridgeflow/__init__.py` - app factory
- `ridgeflow/db.py` - database setup and CLI
- `ridgeflow/schema.sql` - isolated database schema
- `ridgeflow/services/takeoff.py` - native takeoff generation logic
- `ridgeflow/routes/web.py` - dashboard and workflow routes
- `ridgeflow/routes/api.py` - JSON endpoints
- `docs/v1-product-blueprint.md` - product and architecture guide
