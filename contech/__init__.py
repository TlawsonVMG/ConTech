import os
import sys
from pathlib import Path

from flask import Flask
from dotenv import load_dotenv
from werkzeug.middleware.proxy_fix import ProxyFix

from .auth import bp as auth_bp
from . import db
from .security import init_app as init_security
from .routes.api import bp as api_bp
from .routes.crm import bp as crm_bp
from .routes.feedback import bp as feedback_bp
from .routes.web import bp as web_bp


def _env_flag(name):
    value = os.getenv(name)
    if value is None:
        return None
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name):
    value = os.getenv(name)
    if value is None or value.strip() == "":
        return None
    return int(value)


def _load_config_from_env(app):
    overrides = {}

    string_keys = (
        "CONTECH_ENV",
        "SECRET_KEY",
        "DATABASE",
        "DATABASE_URL",
        "UPLOAD_FOLDER",
        "JOB_DOCUMENT_UPLOAD_FOLDER",
        "BOOTSTRAP_ADMIN_USERNAME",
        "BOOTSTRAP_ADMIN_PASSWORD",
        "BOOTSTRAP_ADMIN_FULL_NAME",
        "BOOTSTRAP_BRANCH_NAME",
        "BOOTSTRAP_BRANCH_CODE",
        "BOOTSTRAP_BRANCH_ADDRESS",
        "BOOTSTRAP_BRANCH_CITY",
        "BOOTSTRAP_BRANCH_STATE",
        "BOOTSTRAP_BRANCH_POSTAL_CODE",
    )
    bool_keys = (
        "AUTO_INIT_DB",
        "SEED_DEMO_DATA",
        "SESSION_COOKIE_SECURE",
        "TRUST_PROXY_HEADERS",
        "CSRF_ENABLED",
    )
    int_keys = ("MAX_CONTENT_LENGTH", "LOGIN_MAX_FAILURES", "LOGIN_WINDOW_MINUTES")

    for key in string_keys:
        value = os.getenv(key)
        if value:
            overrides[key] = value

    for key in bool_keys:
        value = _env_flag(key)
        if value is not None:
            overrides[key] = value

    for key in int_keys:
        value = _env_int(key)
        if value is not None:
            overrides[key] = value

    if overrides:
        app.config.update(overrides)


def _is_database_admin_command():
    db_commands = {"init-db", "ensure-db", "migrate-to-postgres"}
    return any(arg in db_commands for arg in sys.argv)


def create_app(test_config=None):
    load_dotenv()
    app = Flask(__name__, instance_relative_config=True)
    env_name = (test_config or {}).get("CONTECH_ENV", "development")

    app.config.from_mapping(
        CONTECH_ENV=env_name,
        SECRET_KEY="dev",
        DATABASE=str(Path(app.instance_path) / "contech.sqlite3"),
        DATABASE_URL=None,
        UPLOAD_FOLDER=str(Path(app.instance_path) / "uploads"),
        JOB_DOCUMENT_UPLOAD_FOLDER=str(Path(app.instance_path) / "uploads" / "job-documents"),
        MAX_CONTENT_LENGTH=16 * 1024 * 1024,
        AUTO_INIT_DB=True,
        SEED_DEMO_DATA=True,
        SESSION_COOKIE_SECURE=False,
        TRUST_PROXY_HEADERS=False,
        CSRF_ENABLED=True,
        LOGIN_MAX_FAILURES=5,
        LOGIN_WINDOW_MINUTES=15,
        BOOTSTRAP_ADMIN_USERNAME="admin",
        BOOTSTRAP_ADMIN_PASSWORD=None,
        BOOTSTRAP_ADMIN_FULL_NAME="ConTech Administrator",
        BOOTSTRAP_BRANCH_NAME="ConTech Pilot Branch",
        BOOTSTRAP_BRANCH_CODE="MAIN",
        BOOTSTRAP_BRANCH_ADDRESS="Launch address pending",
        BOOTSTRAP_BRANCH_CITY="TBD",
        BOOTSTRAP_BRANCH_STATE="NA",
        BOOTSTRAP_BRANCH_POSTAL_CODE="00000",
    )

    if test_config is not None:
        app.config.update(test_config)
    else:
        _load_config_from_env(app)

    if app.config.get("CONTECH_ENV") == "production":
        if "AUTO_INIT_DB" not in (test_config or {}):
            app.config["AUTO_INIT_DB"] = False
        if "SEED_DEMO_DATA" not in (test_config or {}):
            app.config["SEED_DEMO_DATA"] = False
        if "SESSION_COOKIE_SECURE" not in (test_config or {}):
            app.config["SESSION_COOKIE_SECURE"] = True
        weak_secret_keys = {"dev", "local-dev-change-before-live", "replace-with-a-long-random-secret"}
        if app.config.get("SECRET_KEY") in weak_secret_keys:
            raise RuntimeError("Set a real SECRET_KEY before starting ConTech in production.")
        if not app.config.get("DATABASE_URL"):
            raise RuntimeError("Set DATABASE_URL to a PostgreSQL database before starting ConTech in production.")

    Path(app.instance_path).mkdir(parents=True, exist_ok=True)
    Path(app.config["UPLOAD_FOLDER"]).mkdir(parents=True, exist_ok=True)
    Path(app.config["JOB_DOCUMENT_UPLOAD_FOLDER"]).mkdir(parents=True, exist_ok=True)
    if app.config.get("TRUST_PROXY_HEADERS"):
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)  # type: ignore[assignment]

    @app.template_filter("currency")
    def currency_filter(value):
        try:
            return f"${float(value):,.0f}"
        except (TypeError, ValueError):
            return value

    @app.template_filter("date_label")
    def date_label_filter(value):
        if not value:
            return ""
        return value.replace("-0", "-")

    init_security(app)
    db.init_app(app)
    app.register_blueprint(auth_bp)
    app.register_blueprint(crm_bp)
    app.register_blueprint(web_bp)
    app.register_blueprint(feedback_bp)
    app.register_blueprint(api_bp, url_prefix="/api")

    if not _is_database_admin_command():
        with app.app_context():
            db.ensure_seeded()

    return app
