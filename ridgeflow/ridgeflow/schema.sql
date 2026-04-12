PRAGMA foreign_keys = OFF;

DROP TABLE IF EXISTS project_activity;
DROP TABLE IF EXISTS project_messages;
DROP TABLE IF EXISTS tasks;
DROP TABLE IF EXISTS takeoff_items;
DROP TABLE IF EXISTS takeoff_runs;
DROP TABLE IF EXISTS worker_jobs;
DROP TABLE IF EXISTS blueprint_page_extractions;
DROP TABLE IF EXISTS blueprint_page_renders;
DROP TABLE IF EXISTS analysis_field_corrections;
DROP TABLE IF EXISTS blueprint_revision_compares;
DROP TABLE IF EXISTS blueprint_analyses;
DROP TABLE IF EXISTS blueprints;
DROP TABLE IF EXISTS projects;
DROP TABLE IF EXISTS users;
DROP TABLE IF EXISTS teams;

PRAGMA foreign_keys = ON;

CREATE TABLE teams (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    slug TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL
);

CREATE TABLE users (
    id INTEGER PRIMARY KEY,
    team_id INTEGER NOT NULL REFERENCES teams (id),
    full_name TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    role_name TEXT NOT NULL,
    avatar_initials TEXT NOT NULL,
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL
);

CREATE TABLE projects (
    id INTEGER PRIMARY KEY,
    team_id INTEGER NOT NULL REFERENCES teams (id),
    name TEXT NOT NULL,
    client_name TEXT NOT NULL,
    project_type TEXT NOT NULL,
    roof_system TEXT NOT NULL,
    address TEXT NOT NULL,
    status TEXT NOT NULL,
    estimator_name TEXT NOT NULL,
    bid_date TEXT,
    due_date TEXT,
    notes TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE blueprints (
    id INTEGER PRIMARY KEY,
    project_id INTEGER NOT NULL REFERENCES projects (id) ON DELETE CASCADE,
    stored_filename TEXT,
    original_filename TEXT NOT NULL,
    phase_label TEXT NOT NULL,
    version_label TEXT NOT NULL,
    status TEXT NOT NULL,
    page_count INTEGER,
    file_size_bytes INTEGER,
    notes TEXT,
    analysis_status TEXT NOT NULL DEFAULT 'Pending',
    analysis_summary TEXT,
    analysis_confidence REAL NOT NULL DEFAULT 0,
    last_analyzed_at TEXT,
    uploaded_at TEXT NOT NULL
);

CREATE TABLE blueprint_analyses (
    id INTEGER PRIMARY KEY,
    blueprint_id INTEGER NOT NULL REFERENCES blueprints (id) ON DELETE CASCADE,
    status TEXT NOT NULL,
    pipeline_version TEXT NOT NULL,
    parser_name TEXT NOT NULL,
    page_count INTEGER NOT NULL DEFAULT 0,
    raw_text_length INTEGER NOT NULL DEFAULT 0,
    extracted_text_excerpt TEXT NOT NULL,
    roof_system_suggestion TEXT,
    confidence REAL NOT NULL DEFAULT 0,
    summary TEXT NOT NULL,
    sheet_labels_json TEXT NOT NULL DEFAULT '[]',
    roof_sheet_labels_json TEXT NOT NULL DEFAULT '[]',
    keyword_counts_json TEXT NOT NULL DEFAULT '{}',
    measurement_json TEXT NOT NULL DEFAULT '{}',
    page_role_summary_json TEXT NOT NULL DEFAULT '{}',
    structured_data_json TEXT NOT NULL DEFAULT '{}',
    field_confidence_json TEXT NOT NULL DEFAULT '{}',
    review_required_json TEXT NOT NULL DEFAULT '[]',
    warnings_json TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL,
    completed_at TEXT NOT NULL
);

CREATE TABLE blueprint_page_renders (
    id INTEGER PRIMARY KEY,
    blueprint_id INTEGER NOT NULL REFERENCES blueprints (id) ON DELETE CASCADE,
    page_number INTEGER NOT NULL,
    image_filename TEXT NOT NULL,
    mime_type TEXT NOT NULL,
    width_px INTEGER NOT NULL DEFAULT 0,
    height_px INTEGER NOT NULL DEFAULT 0,
    dpi INTEGER NOT NULL DEFAULT 144,
    render_backend TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE blueprint_page_extractions (
    id INTEGER PRIMARY KEY,
    blueprint_id INTEGER NOT NULL REFERENCES blueprints (id) ON DELETE CASCADE,
    page_number INTEGER NOT NULL,
    source_type TEXT NOT NULL,
    backend_name TEXT NOT NULL,
    status TEXT NOT NULL,
    text_excerpt TEXT NOT NULL,
    sheet_label TEXT,
    page_role TEXT,
    roof_system_hint TEXT,
    confidence REAL NOT NULL DEFAULT 0,
    measurement_json TEXT NOT NULL DEFAULT '{}',
    warnings_json TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL,
    completed_at TEXT NOT NULL
);

CREATE TABLE analysis_field_corrections (
    id INTEGER PRIMARY KEY,
    blueprint_id INTEGER NOT NULL REFERENCES blueprints (id) ON DELETE CASCADE,
    blueprint_analysis_id INTEGER REFERENCES blueprint_analyses (id) ON DELETE CASCADE,
    field_name TEXT NOT NULL,
    field_value_text TEXT,
    field_value_number REAL,
    corrected_by_name TEXT NOT NULL,
    notes TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE blueprint_revision_compares (
    id INTEGER PRIMARY KEY,
    project_id INTEGER NOT NULL REFERENCES projects (id) ON DELETE CASCADE,
    base_blueprint_id INTEGER REFERENCES blueprints (id) ON DELETE CASCADE,
    compared_blueprint_id INTEGER NOT NULL REFERENCES blueprints (id) ON DELETE CASCADE,
    base_analysis_id INTEGER REFERENCES blueprint_analyses (id) ON DELETE SET NULL,
    compared_analysis_id INTEGER REFERENCES blueprint_analyses (id) ON DELETE SET NULL,
    status TEXT NOT NULL,
    summary TEXT NOT NULL,
    metric_deltas_json TEXT NOT NULL DEFAULT '{}',
    list_changes_json TEXT NOT NULL DEFAULT '{}',
    page_role_changes_json TEXT NOT NULL DEFAULT '{}',
    review_flags_json TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE worker_jobs (
    id INTEGER PRIMARY KEY,
    blueprint_id INTEGER NOT NULL REFERENCES blueprints (id) ON DELETE CASCADE,
    job_type TEXT NOT NULL,
    status TEXT NOT NULL,
    payload_json TEXT NOT NULL DEFAULT '{}',
    attempts INTEGER NOT NULL DEFAULT 0,
    leased_at TEXT,
    last_error TEXT,
    created_at TEXT NOT NULL,
    completed_at TEXT
);

CREATE TABLE takeoff_runs (
    id INTEGER PRIMARY KEY,
    project_id INTEGER NOT NULL REFERENCES projects (id) ON DELETE CASCADE,
    blueprint_id INTEGER NOT NULL REFERENCES blueprints (id) ON DELETE CASCADE,
    blueprint_analysis_id INTEGER REFERENCES blueprint_analyses (id),
    status TEXT NOT NULL,
    system_type TEXT NOT NULL,
    source_mode TEXT NOT NULL,
    ai_model TEXT NOT NULL,
    confidence REAL NOT NULL DEFAULT 0,
    waste_pct REAL NOT NULL DEFAULT 0,
    roof_area_squares REAL NOT NULL DEFAULT 0,
    perimeter_feet REAL NOT NULL DEFAULT 0,
    ridge_feet REAL NOT NULL DEFAULT 0,
    valley_feet REAL NOT NULL DEFAULT 0,
    eave_feet REAL NOT NULL DEFAULT 0,
    analysis_summary TEXT NOT NULL,
    created_at TEXT NOT NULL,
    reviewed_at TEXT,
    approved_at TEXT
);

CREATE TABLE takeoff_items (
    id INTEGER PRIMARY KEY,
    takeoff_run_id INTEGER NOT NULL REFERENCES takeoff_runs (id) ON DELETE CASCADE,
    category TEXT NOT NULL,
    material_name TEXT NOT NULL,
    unit_label TEXT NOT NULL,
    quantity REAL NOT NULL,
    waste_pct REAL NOT NULL DEFAULT 0,
    vendor_hint TEXT,
    notes TEXT,
    sort_order INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE tasks (
    id INTEGER PRIMARY KEY,
    project_id INTEGER NOT NULL REFERENCES projects (id) ON DELETE CASCADE,
    owner_user_id INTEGER REFERENCES users (id),
    title TEXT NOT NULL,
    status TEXT NOT NULL,
    priority TEXT NOT NULL,
    due_date TEXT,
    notes TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE project_messages (
    id INTEGER PRIMARY KEY,
    project_id INTEGER NOT NULL REFERENCES projects (id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES users (id),
    body TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE project_activity (
    id INTEGER PRIMARY KEY,
    project_id INTEGER NOT NULL REFERENCES projects (id) ON DELETE CASCADE,
    actor_name TEXT NOT NULL,
    event_type TEXT NOT NULL,
    event_text TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE INDEX idx_projects_status ON projects (status);
CREATE INDEX idx_blueprints_project ON blueprints (project_id);
CREATE INDEX idx_blueprints_analysis_status ON blueprints (analysis_status);
CREATE INDEX idx_blueprint_analyses_blueprint ON blueprint_analyses (blueprint_id, id DESC);
CREATE INDEX idx_blueprint_page_renders_blueprint ON blueprint_page_renders (blueprint_id, page_number);
CREATE INDEX idx_blueprint_page_extractions_blueprint ON blueprint_page_extractions (blueprint_id, page_number, source_type);
CREATE INDEX idx_analysis_field_corrections_blueprint ON analysis_field_corrections (blueprint_id, field_name, id DESC);
CREATE UNIQUE INDEX idx_blueprint_revision_compares_compared ON blueprint_revision_compares (compared_blueprint_id);
CREATE INDEX idx_blueprint_revision_compares_project ON blueprint_revision_compares (project_id, updated_at DESC);
CREATE INDEX idx_worker_jobs_status ON worker_jobs (status, id);
CREATE INDEX idx_worker_jobs_blueprint ON worker_jobs (blueprint_id, id DESC);
CREATE INDEX idx_takeoff_runs_project ON takeoff_runs (project_id);
CREATE INDEX idx_tasks_project ON tasks (project_id, status);
CREATE INDEX idx_messages_project ON project_messages (project_id, created_at);
