import sqlite3
from pathlib import Path

import click
from flask import current_app, g


def get_db():
    database_name = current_app.config["DATABASE"]
    if database_name == ":memory:":
        if "memory_db" not in current_app.extensions:
            current_app.extensions["memory_db"] = sqlite3.connect(":memory:", check_same_thread=False)
            current_app.extensions["memory_db"].row_factory = sqlite3.Row
            current_app.extensions["memory_db"].execute("PRAGMA foreign_keys = ON")
        g.db = current_app.extensions["memory_db"]
        return g.db

    if "db" not in g:
        database_path = Path(database_name)
        database_path.parent.mkdir(parents=True, exist_ok=True)
        g.db = sqlite3.connect(database_path)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


def close_db(_error=None):
    if current_app.config["DATABASE"] == ":memory:":
        g.pop("db", None)
        return
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    db = get_db()
    with current_app.open_resource("schema.sql") as schema_file:
        db.executescript(schema_file.read().decode("utf-8"))
    db.commit()


def _table_exists(db, table_name):
    row = db.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table_name,),
    ).fetchone()
    return row is not None


def _column_names(db, table_name):
    return {row["name"] for row in db.execute(f"PRAGMA table_info({table_name})").fetchall()}


def _ensure_column(db, table_name, column_name, ddl):
    if column_name not in _column_names(db, table_name):
        db.execute(f"ALTER TABLE {table_name} ADD COLUMN {ddl}")


def ensure_schema_compatibility():
    db = get_db()
    if not _table_exists(db, "teams"):
        return

    if _table_exists(db, "blueprint_analyses"):
        _ensure_column(db, "blueprint_analyses", "page_role_summary_json", "page_role_summary_json TEXT NOT NULL DEFAULT '{}'")
        _ensure_column(db, "blueprint_analyses", "structured_data_json", "structured_data_json TEXT NOT NULL DEFAULT '{}'")
        _ensure_column(db, "blueprint_analyses", "field_confidence_json", "field_confidence_json TEXT NOT NULL DEFAULT '{}'")
        _ensure_column(db, "blueprint_analyses", "review_required_json", "review_required_json TEXT NOT NULL DEFAULT '[]'")

    db.execute(
        """
        CREATE TABLE IF NOT EXISTS analysis_field_corrections (
            id INTEGER PRIMARY KEY,
            blueprint_id INTEGER NOT NULL REFERENCES blueprints (id) ON DELETE CASCADE,
            blueprint_analysis_id INTEGER REFERENCES blueprint_analyses (id) ON DELETE CASCADE,
            field_name TEXT NOT NULL,
            field_value_text TEXT,
            field_value_number REAL,
            corrected_by_name TEXT NOT NULL,
            notes TEXT,
            created_at TEXT NOT NULL
        )
        """
    )
    db.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_analysis_field_corrections_blueprint
        ON analysis_field_corrections (blueprint_id, field_name, id DESC)
        """
    )
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS blueprint_revision_compares (
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
        )
        """
    )
    db.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_blueprint_revision_compares_compared
        ON blueprint_revision_compares (compared_blueprint_id)
        """
    )
    db.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_blueprint_revision_compares_project
        ON blueprint_revision_compares (project_id, updated_at DESC)
        """
    )
    db.commit()


def ensure_seeded():
    db = get_db()
    team_table = db.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'teams'"
    ).fetchone()

    if team_table is None:
        init_db()
    else:
        ensure_schema_compatibility()

    if current_app.config.get("SEED_DEMO_DATA"):
        user_count = db.execute("SELECT COUNT(*) AS count FROM users").fetchone()["count"]
        if user_count == 0:
            from .seed import seed_demo_data

            seed_demo_data(db)


@click.command("init-db")
def init_db_command():
    init_db()
    if current_app.config.get("SEED_DEMO_DATA"):
        from .seed import seed_demo_data

        seed_demo_data(get_db())
    click.echo("Initialized the RidgeFlow database.")


def init_app(app):
    app.teardown_appcontext(close_db)
    app.cli.add_command(init_db_command)
    from .services.worker_pipeline import queue_blueprint_workers_command, run_worker_command

    app.cli.add_command(run_worker_command)
    app.cli.add_command(queue_blueprint_workers_command)
