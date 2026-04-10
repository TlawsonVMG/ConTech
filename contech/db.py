import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import unquote, urlparse

import click
from flask import current_app, g
from werkzeug.security import generate_password_hash

from .seed import seed_demo_data

SCHEMA_VERSION = "2026.04.10.customer-invites"

try:
    import psycopg
    from psycopg.rows import dict_row
except ImportError:  # pragma: no cover - exercised only when PostgreSQL support is not installed.
    psycopg = None
    dict_row = None


TABLE_COPY_ORDER = [
    "branches",
    "users",
    "customers",
    "customer_contacts",
    "customer_portal_users",
    "portal_messages",
    "auth_attempts",
    "feedback_submissions",
    "leads",
    "opportunities",
    "quotes",
    "jobs",
    "deliveries",
    "change_orders",
    "change_order_versions",
    "job_documents",
    "vendors",
    "inventory_items",
    "job_materials",
    "purchase_requests",
    "job_cost_entries",
    "invoices",
    "bank_accounts",
    "invoice_payments",
    "company_cards",
    "employees",
    "payroll_runs",
    "ledger_accounts",
    "journal_entries",
    "journal_entry_lines",
    "tasks",
    "activity_feed",
    "email_messages",
    "calendar_events",
    "report_months",
]

REQUIRED_COLUMNS = {
    "quotes": {
        "opportunity_id",
        "issue_date",
        "expiration_date",
        "estimated_cost",
        "target_margin_pct",
        "deposit_required",
        "deposit_received",
        "signed_date",
    },
    "jobs": {"opportunity_id", "quote_id"},
    "invoices": {
        "quote_id",
        "change_order_id",
        "issued_date",
        "billing_type",
        "application_number",
        "billing_period_start",
        "billing_period_end",
        "retainage_pct",
        "retainage_held",
    },
    "job_materials": {"job_id", "inventory_item_id", "requested_qty", "reserved_qty", "shortage_qty", "status", "notes"},
    "job_cost_entries": {"job_id", "cost_code", "source_type", "total_cost", "status", "notes"},
    "change_orders": {
        "job_id",
        "customer_id",
        "change_number",
        "status",
        "amount",
        "cost_impact",
        "schedule_days",
        "is_billable",
    },
    "change_order_versions": {"change_order_id", "version_number", "changed_at", "changed_by", "snapshot_json"},
    "job_documents": {
        "job_id",
        "customer_id",
        "record_type",
        "file_reference",
        "stored_file_name",
        "original_filename",
        "captured_at",
        "status",
        "notes",
    },
    "purchase_requests": {
        "job_id",
        "job_material_id",
        "inventory_item_id",
        "requested_qty",
        "ordered_qty",
        "received_qty",
        "eta_date",
        "status",
        "owner_name",
        "needed_by",
        "vendor_notes",
    },
    "tasks": {"reminder_at", "details"},
    "activity_feed": {"activity_type", "owner_name"},
    "auth_attempts": {"username", "ip_address", "attempted_at", "was_success"},
    "feedback_submissions": {"submitter_name", "submitter_email", "summary", "details", "status"},
    "email_messages": {"direction", "contact_email", "integration_status"},
    "calendar_events": {"event_type", "starts_at", "integration_status"},
    "customer_contacts": {"customer_id", "full_name", "role_label", "is_primary"},
    "customers": {"company_name", "company_address", "company_logo_filename", "company_profile_updated_at"},
    "customer_portal_users": {
        "customer_id",
        "email",
        "password_hash",
        "full_name",
        "is_active",
        "role_label",
        "phone",
        "invite_token_hash",
        "invite_status",
        "invite_sent_at",
        "invite_expires_at",
        "invite_accepted_at",
        "profile_completed_at",
    },
    "portal_messages": {"customer_id", "portal_user_id", "subject", "message_body", "status"},
    "invoice_payments": {"invoice_id", "payment_date", "payment_amount", "payment_method", "posted_by"},
}


def _validate_identifier(identifier):
    if not identifier or not identifier.replace("_", "").isalnum():
        raise ValueError(f"Unsafe SQL identifier: {identifier!r}")
    return identifier


def _utc_timestamp():
    return datetime.now(UTC).replace(tzinfo=None, microsecond=0).isoformat(sep=" ")


def _split_sql_statements(script):
    statements = []
    current = []
    in_single_quote = False
    in_double_quote = False

    for char in script:
        if char == "'" and not in_double_quote:
            in_single_quote = not in_single_quote
        elif char == '"' and not in_single_quote:
            in_double_quote = not in_double_quote

        if char == ";" and not in_single_quote and not in_double_quote:
            statement = "".join(current).strip()
            if statement:
                statements.append(statement)
            current = []
            continue

        current.append(char)

    trailing = "".join(current).strip()
    if trailing:
        statements.append(trailing)

    return statements


def _sqlite_path_from_url(database_url):
    parsed = urlparse(database_url)
    if parsed.scheme != "sqlite":
        raise RuntimeError(f"Unsupported DATABASE_URL scheme: {parsed.scheme}")
    path = unquote(parsed.path or "")
    if parsed.netloc and parsed.netloc != "localhost":
        path = f"//{parsed.netloc}{path}"
    return path or ":memory:"


class CursorWrapper:
    def __init__(self, cursor):
        self._cursor = cursor

    @property
    def lastrowid(self):
        return getattr(self._cursor, "lastrowid", None)

    def fetchone(self):
        return self._cursor.fetchone()

    def fetchall(self):
        return self._cursor.fetchall()

    def __iter__(self):
        return iter(self._cursor)

    def __getattr__(self, name):
        return getattr(self._cursor, name)


class DatabaseConnection:
    def __init__(self, connection, engine):
        self._connection = connection
        self.engine = engine

    @property
    def is_postgresql(self):
        return self.engine == "postgresql"

    def _prepare_query(self, query):
        if self.is_postgresql:
            return query.replace("?", "%s")
        return query

    def execute(self, query, params=()):
        cursor = self._connection.cursor()
        cursor.execute(self._prepare_query(query), tuple(params or ()))
        return CursorWrapper(cursor)

    def executemany(self, query, seq_of_params):
        cursor = self._connection.cursor()
        cursor.executemany(self._prepare_query(query), [tuple(params or ()) for params in seq_of_params])
        return CursorWrapper(cursor)

    def executescript(self, script):
        if not self.is_postgresql:
            self._connection.executescript(script)
            return None

        cursor = self._connection.cursor()
        for statement in _split_sql_statements(script):
            cursor.execute(statement)
        return CursorWrapper(cursor)

    def insert(self, query, params=(), returning_column="id"):
        statement = query.strip().rstrip(";")
        if self.is_postgresql:
            if "returning " not in statement.lower():
                statement = f"{statement} RETURNING {returning_column}"
            row = self.execute(statement, params).fetchone()
            return row[returning_column]

        return self.execute(statement, params).lastrowid

    def table_exists(self, table_name):
        table_name = _validate_identifier(table_name)
        if self.is_postgresql:
            row = self.execute(
                """
                SELECT EXISTS (
                    SELECT 1
                    FROM information_schema.tables
                    WHERE table_schema = current_schema()
                      AND table_name = ?
                ) AS exists
                """,
                (table_name,),
            ).fetchone()
            return bool(row["exists"])

        row = self.execute(
            "SELECT COUNT(*) AS count FROM sqlite_master WHERE type = 'table' AND name = ?",
            (table_name,),
        ).fetchone()
        return row["count"] > 0

    def table_columns(self, table_name):
        table_name = _validate_identifier(table_name)
        if self.is_postgresql:
            rows = self.execute(
                """
                SELECT column_name AS name
                FROM information_schema.columns
                WHERE table_schema = current_schema()
                  AND table_name = ?
                """,
                (table_name,),
            ).fetchall()
            return {row["name"] for row in rows}

        rows = self.execute(f"PRAGMA table_info({table_name})").fetchall()
        return {row["name"] for row in rows}

    def reset_identity_sequence(self, table_name, column_name="id"):
        if not self.is_postgresql:
            return

        table_name = _validate_identifier(table_name)
        column_name = _validate_identifier(column_name)
        sequence_row = self.execute(
            "SELECT pg_get_serial_sequence(?, ?) AS sequence_name",
            (table_name, column_name),
        ).fetchone()
        sequence_name = sequence_row["sequence_name"] if sequence_row else None
        if not sequence_name:
            return

        max_row = self.execute(
            f"SELECT COALESCE(MAX({column_name}), 0) AS max_value FROM {table_name}"
        ).fetchone()
        max_value = int(max_row["max_value"])
        seed_value = max_value if max_value > 0 else 1
        self.execute(
            "SELECT setval(CAST(? AS regclass), ?, ?)",
            (sequence_name, seed_value, max_value > 0),
        )

    def commit(self):
        self._connection.commit()

    def rollback(self):
        self._connection.rollback()

    def close(self):
        self._connection.close()


def _connect_database(database_url=None, database_path=None):
    if database_url:
        parsed = urlparse(database_url)
        if parsed.scheme in {"postgresql", "postgres"}:
            if psycopg is None:
                raise RuntimeError("PostgreSQL support requires psycopg. Install dependencies from requirements.txt first.")
            return DatabaseConnection(psycopg.connect(database_url, row_factory=dict_row), "postgresql")
        if parsed.scheme == "sqlite":
            database_path = _sqlite_path_from_url(database_url)
        else:
            raise RuntimeError(f"Unsupported DATABASE_URL scheme: {parsed.scheme}")

    connection = sqlite3.connect(
        str(database_path),
        detect_types=sqlite3.PARSE_DECLTYPES,
    )
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return DatabaseConnection(connection, "sqlite")


def _schema_path_for(db):
    if db.is_postgresql:
        return Path(current_app.root_path) / "schema.postgresql.sql"
    return Path(current_app.root_path) / "schema.sql"


def _reseed_identity_sequences(db):
    if not db.is_postgresql:
        return
    for table_name in TABLE_COPY_ORDER:
        db.reset_identity_sequence(table_name)


def seed_bootstrap_admin(db):
    bootstrap_password = current_app.config.get("BOOTSTRAP_ADMIN_PASSWORD")
    if not bootstrap_password:
        return False

    branch_count = db.execute("SELECT COUNT(*) AS count FROM branches").fetchone()["count"]
    if branch_count == 0:
        db.execute(
            """
            INSERT INTO branches (id, name, code, address, city, state, postal_code)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                1,
                current_app.config.get("BOOTSTRAP_BRANCH_NAME", "ConTech Pilot Branch"),
                current_app.config.get("BOOTSTRAP_BRANCH_CODE", "MAIN"),
                current_app.config.get("BOOTSTRAP_BRANCH_ADDRESS", "Launch address pending"),
                current_app.config.get("BOOTSTRAP_BRANCH_CITY", "TBD"),
                current_app.config.get("BOOTSTRAP_BRANCH_STATE", "NA"),
                current_app.config.get("BOOTSTRAP_BRANCH_POSTAL_CODE", "00000"),
            ),
        )

    user_count = db.execute("SELECT COUNT(*) AS count FROM users").fetchone()["count"]
    if user_count > 0:
        return False

    db.execute(
        """
        INSERT INTO users (branch_id, username, password_hash, full_name, role_name, is_active)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            1,
            current_app.config.get("BOOTSTRAP_ADMIN_USERNAME", "admin").strip().lower(),
            generate_password_hash(bootstrap_password),
            current_app.config.get("BOOTSTRAP_ADMIN_FULL_NAME", "ConTech Administrator"),
            "admin",
            1,
        ),
    )
    _reseed_identity_sequences(db)
    return True


def _create_customer_portal_users_table(db):
    if db.table_exists("customer_portal_users"):
        return

    if db.is_postgresql:
        db.execute(
            """
            CREATE TABLE customer_portal_users (
                id INTEGER GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
                branch_id INTEGER NOT NULL REFERENCES branches (id),
                customer_id INTEGER NOT NULL REFERENCES customers (id),
                email TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                full_name TEXT NOT NULL,
                role_label TEXT,
                phone TEXT,
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                last_login_at TEXT,
                invite_token_hash TEXT,
                invite_status TEXT NOT NULL DEFAULT 'accepted',
                invite_sent_at TEXT,
                invite_expires_at TEXT,
                invite_accepted_at TEXT,
                profile_completed_at TEXT
            )
            """
        )
    else:
        db.execute(
            """
            CREATE TABLE customer_portal_users (
                id INTEGER PRIMARY KEY,
                branch_id INTEGER NOT NULL REFERENCES branches (id),
                customer_id INTEGER NOT NULL REFERENCES customers (id),
                email TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                full_name TEXT NOT NULL,
                role_label TEXT,
                phone TEXT,
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                last_login_at TEXT,
                invite_token_hash TEXT,
                invite_status TEXT NOT NULL DEFAULT 'accepted',
                invite_sent_at TEXT,
                invite_expires_at TEXT,
                invite_accepted_at TEXT,
                profile_completed_at TEXT
            )
            """
        )


def _create_portal_messages_table(db):
    if db.table_exists("portal_messages"):
        return

    if db.is_postgresql:
        db.execute(
            """
            CREATE TABLE portal_messages (
                id INTEGER GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
                branch_id INTEGER NOT NULL REFERENCES branches (id),
                customer_id INTEGER NOT NULL REFERENCES customers (id),
                portal_user_id INTEGER REFERENCES customer_portal_users (id),
                submitted_at TEXT NOT NULL,
                subject TEXT NOT NULL,
                message_body TEXT NOT NULL,
                status TEXT NOT NULL,
                internal_notes TEXT,
                reviewed_at TEXT,
                reviewed_by TEXT
            )
            """
        )
    else:
        db.execute(
            """
            CREATE TABLE portal_messages (
                id INTEGER PRIMARY KEY,
                branch_id INTEGER NOT NULL REFERENCES branches (id),
                customer_id INTEGER NOT NULL REFERENCES customers (id),
                portal_user_id INTEGER REFERENCES customer_portal_users (id),
                submitted_at TEXT NOT NULL,
                subject TEXT NOT NULL,
                message_body TEXT NOT NULL,
                status TEXT NOT NULL,
                internal_notes TEXT,
                reviewed_at TEXT,
                reviewed_by TEXT
            )
            """
        )


def _add_column_if_missing(db, table_name, column_name, column_definition):
    table_name = _validate_identifier(table_name)
    column_name = _validate_identifier(column_name)
    if column_name in db.table_columns(table_name):
        return
    db.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_definition}")


def _migrate_customer_profile_columns(db):
    if not db.table_exists("customers"):
        return

    _add_column_if_missing(db, "customers", "company_name", "TEXT")
    _add_column_if_missing(db, "customers", "company_address", "TEXT")
    _add_column_if_missing(db, "customers", "company_logo_filename", "TEXT")
    _add_column_if_missing(db, "customers", "company_profile_updated_at", "TEXT")


def _migrate_customer_portal_user_columns(db):
    if not db.table_exists("customer_portal_users"):
        return

    _add_column_if_missing(db, "customer_portal_users", "role_label", "TEXT")
    _add_column_if_missing(db, "customer_portal_users", "phone", "TEXT")
    _add_column_if_missing(db, "customer_portal_users", "invite_token_hash", "TEXT")
    _add_column_if_missing(db, "customer_portal_users", "invite_status", "TEXT NOT NULL DEFAULT 'accepted'")
    _add_column_if_missing(db, "customer_portal_users", "invite_sent_at", "TEXT")
    _add_column_if_missing(db, "customer_portal_users", "invite_expires_at", "TEXT")
    _add_column_if_missing(db, "customer_portal_users", "invite_accepted_at", "TEXT")
    _add_column_if_missing(db, "customer_portal_users", "profile_completed_at", "TEXT")


def apply_non_destructive_migrations(db):
    if not db.table_exists("branches") or not db.table_exists("customers"):
        return

    _migrate_customer_profile_columns(db)
    _create_customer_portal_users_table(db)
    _migrate_customer_portal_user_columns(db)
    _create_portal_messages_table(db)
    record_schema_version(db, version="2026.04.10.customer-invites", notes="Customer invite and profile columns added")


def _schema_is_current(db):
    apply_non_destructive_migrations(db)
    for table_name in TABLE_COPY_ORDER:
        if not db.table_exists(table_name):
            return False

    for table_name, required_columns in REQUIRED_COLUMNS.items():
        if not required_columns.issubset(db.table_columns(table_name)):
            return False

    return True


def _has_any_contech_tables(db):
    return any(db.table_exists(table_name) for table_name in [*TABLE_COPY_ORDER, "schema_migrations"])


def _ensure_schema_migrations_table(db):
    if db.table_exists("schema_migrations"):
        return

    if db.is_postgresql:
        db.execute(
            """
            CREATE TABLE schema_migrations (
                id INTEGER GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
                version TEXT NOT NULL UNIQUE,
                applied_at TEXT NOT NULL,
                notes TEXT NOT NULL
            )
            """
        )
    else:
        db.execute(
            """
            CREATE TABLE schema_migrations (
                id INTEGER PRIMARY KEY,
                version TEXT NOT NULL UNIQUE,
                applied_at TEXT NOT NULL,
                notes TEXT NOT NULL
            )
            """
        )


def record_schema_version(db, version=SCHEMA_VERSION, notes="Baseline schema applied"):
    _ensure_schema_migrations_table(db)
    existing = db.execute("SELECT id FROM schema_migrations WHERE version = ?", (version,)).fetchone()
    if existing:
        return

    db.execute(
        """
        INSERT INTO schema_migrations (version, applied_at, notes)
        VALUES (?, ?, ?)
        """,
        (version, _utc_timestamp(), notes),
    )


def get_schema_status(db=None):
    db = db or get_db()
    schema_current = _schema_is_current(db)
    schema_version = None
    applied_at = None

    if schema_current:
        _ensure_schema_migrations_table(db)
        record_schema_version(db, notes="Schema version verified")
        row = db.execute(
            """
            SELECT version, applied_at
            FROM schema_migrations
            ORDER BY applied_at DESC, id DESC
            LIMIT 1
            """
        ).fetchone()
        if row:
            schema_version = row["version"]
            applied_at = row["applied_at"]
        db.commit()

    return {
        "engine": db.engine,
        "schema_current": schema_current,
        "schema_version": schema_version,
        "applied_at": applied_at,
    }


def get_db():
    if "db" not in g:
        database_url = current_app.config.get("DATABASE_URL")
        database_path = current_app.config.get("DATABASE")
        g.db = _connect_database(database_url=database_url, database_path=database_path)

    return g.db


def close_db(_error=None):
    db = g.pop("db", None)

    if db is not None:
        db.close()


def init_db(seed_demo_data_enabled=None, db_connection=None):
    db = db_connection or get_db()
    schema_path = _schema_path_for(db)
    db.executescript(schema_path.read_text(encoding="utf-8"))
    should_seed = current_app.config.get("SEED_DEMO_DATA", False) if seed_demo_data_enabled is None else seed_demo_data_enabled
    if should_seed:
        seed_demo_data(db)
        _reseed_identity_sequences(db)
    else:
        seed_bootstrap_admin(db)
    record_schema_version(db)
    db.commit()


def ensure_seeded():
    db = get_db()

    if not _schema_is_current(db):
        if not current_app.config.get("AUTO_INIT_DB", True):
            raise RuntimeError("Database schema is missing or outdated. Run the database initialization step before starting ConTech.")
        init_db()
        return

    record_schema_version(db, notes="Schema version verified")

    row = db.execute("SELECT COUNT(*) AS count FROM branches").fetchone()

    if row["count"] == 0 and current_app.config.get("SEED_DEMO_DATA", False):
        seed_demo_data(db)
        _reseed_identity_sequences(db)
    elif row["count"] == 0:
        seed_bootstrap_admin(db)
    db.commit()


def _copy_table(source_db, target_db, table_name):
    table_name = _validate_identifier(table_name)
    if not source_db.table_exists(table_name):
        return 0

    rows = source_db.execute(f"SELECT * FROM {table_name} ORDER BY id").fetchall()
    if not rows:
        target_db.reset_identity_sequence(table_name)
        return 0

    columns = list(rows[0].keys())
    column_list = ", ".join(columns)
    placeholders = ", ".join("?" for _ in columns)
    values = [tuple(row[column] for column in columns) for row in rows]
    target_db.executemany(
        f"INSERT INTO {table_name} ({column_list}) VALUES ({placeholders})",
        values,
    )
    target_db.reset_identity_sequence(table_name)
    return len(values)


def migrate_sqlite_to_postgresql(source_sqlite_path, target_database_url, initialize_target=True):
    source_path = Path(source_sqlite_path)
    if not source_path.exists():
        raise click.ClickException(f"Source SQLite database was not found at {source_path}.")

    if not target_database_url:
        raise click.ClickException("Provide a PostgreSQL DATABASE_URL to receive migrated data.")

    source_db = _connect_database(database_path=source_path)
    target_db = _connect_database(database_url=target_database_url)

    try:
        if not target_db.is_postgresql:
            raise click.ClickException("The migration target must be a PostgreSQL DATABASE_URL.")

        if initialize_target:
            init_db(seed_demo_data_enabled=False, db_connection=target_db)

        copied_counts = {}
        for table_name in TABLE_COPY_ORDER:
            copied_counts[table_name] = _copy_table(source_db, target_db, table_name)

        target_db.commit()
        return copied_counts
    except Exception:
        target_db.rollback()
        raise
    finally:
        source_db.close()
        target_db.close()


@click.command("init-db")
@click.option("--with-demo-data", is_flag=True, default=False, help="Seed the database with demo data after initialization.")
def init_db_command(with_demo_data):
    init_db(seed_demo_data_enabled=with_demo_data)
    click.echo("Initialized the ConTech database.")


@click.command("ensure-db")
@click.option("--with-demo-data", is_flag=True, default=False, help="Seed the database if it needs first-time initialization.")
def ensure_db_command(with_demo_data):
    db = get_db()
    if not _has_any_contech_tables(db):
        init_db(seed_demo_data_enabled=with_demo_data)
        click.echo("Initialized the ConTech database.")
        return

    if not _schema_is_current(db):
        raise click.ClickException(
            "Database tables exist, but the schema is not current. Run an explicit migration before deploying."
        )

    record_schema_version(db, notes="Schema version verified")
    db.commit()
    click.echo("ConTech database is already initialized and current.")


@click.command("check-db")
def check_db_command():
    status = get_schema_status()
    db = get_db()
    customers = db.execute("SELECT COUNT(*) AS count FROM customers").fetchone()["count"]
    users = db.execute("SELECT COUNT(*) AS count FROM users").fetchone()["count"]
    click.echo(f"Database engine: {status['engine']}")
    click.echo(f"Schema current: {status['schema_current']}")
    click.echo(f"Schema version: {status['schema_version'] or 'unversioned'}")
    click.echo(f"Customers: {customers}")
    click.echo(f"Users: {users}")


@click.command("migrate-to-postgres")
@click.option(
    "--source-sqlite",
    type=click.Path(path_type=Path),
    default=None,
    help="Path to the source SQLite database. Defaults to the app's configured SQLite file.",
)
@click.option(
    "--target-url",
    envvar="DATABASE_URL",
    required=True,
    help="PostgreSQL DATABASE_URL for the destination database.",
)
@click.option(
    "--skip-init",
    is_flag=True,
    default=False,
    help="Skip recreating the PostgreSQL schema before copying data.",
)
def migrate_to_postgres_command(source_sqlite, target_url, skip_init):
    source_path = source_sqlite or Path(current_app.config["DATABASE"])
    copied_counts = migrate_sqlite_to_postgresql(source_path, target_url, initialize_target=not skip_init)
    total_rows = sum(copied_counts.values())
    click.echo(f"Migrated {total_rows} rows from SQLite into PostgreSQL.")


def init_app(app):
    app.teardown_appcontext(close_db)
    app.cli.add_command(init_db_command)
    app.cli.add_command(ensure_db_command)
    app.cli.add_command(check_db_command)
    app.cli.add_command(migrate_to_postgres_command)
