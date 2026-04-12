import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask

from . import db
from .routes.api import bp as api_bp
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
        "RIDGEFLOW_ENV",
        "SECRET_KEY",
        "DATABASE",
        "UPLOAD_FOLDER",
        "BLUEPRINT_UPLOAD_FOLDER",
        "BLUEPRINT_PAGE_IMAGE_FOLDER",
        "DEFAULT_AI_MODEL",
        "RASTERIZER_BACKEND",
        "PDFTOPPM_COMMAND",
        "MAGICK_COMMAND",
        "OCR_BACKEND",
        "VISION_BACKEND",
        "TESSERACT_COMMAND",
        "OPENAI_VISION_MODEL",
        "OPENAI_VISION_DETAIL",
    )
    bool_keys = ("AUTO_INIT_DB", "SEED_DEMO_DATA")
    int_keys = ("RASTERIZER_DPI", "WORKER_POLL_SECONDS")

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
    return any(arg in {"init-db"} for arg in sys.argv)


def create_app(test_config=None):
    load_dotenv()
    app = Flask(__name__, instance_relative_config=True)

    app.config.from_mapping(
        RIDGEFLOW_ENV="development",
        SECRET_KEY="ridgeflow-dev",
        DATABASE=str(Path(app.instance_path) / "ridgeflow.sqlite3"),
        UPLOAD_FOLDER=str(Path(app.instance_path) / "uploads"),
        BLUEPRINT_UPLOAD_FOLDER=str(Path(app.instance_path) / "uploads" / "blueprints"),
        BLUEPRINT_PAGE_IMAGE_FOLDER=str(Path(app.instance_path) / "uploads" / "blueprint-pages"),
        MAX_CONTENT_LENGTH=64 * 1024 * 1024,
        AUTO_INIT_DB=True,
        SEED_DEMO_DATA=True,
        DEFAULT_AI_MODEL="Blueprint Vision v1",
        RASTERIZER_BACKEND="auto",
        PDFTOPPM_COMMAND="pdftoppm",
        MAGICK_COMMAND="magick",
        OCR_BACKEND="auto",
        VISION_BACKEND="auto",
        TESSERACT_COMMAND="tesseract",
        OPENAI_VISION_MODEL="gpt-4.1",
        OPENAI_VISION_DETAIL="high",
        RASTERIZER_DPI=144,
        WORKER_POLL_SECONDS=5,
    )

    if test_config is not None:
        app.config.update(test_config)
    else:
        _load_config_from_env(app)

    Path(app.instance_path).mkdir(parents=True, exist_ok=True)
    Path(app.config["UPLOAD_FOLDER"]).mkdir(parents=True, exist_ok=True)
    Path(app.config["BLUEPRINT_UPLOAD_FOLDER"]).mkdir(parents=True, exist_ok=True)
    Path(app.config["BLUEPRINT_PAGE_IMAGE_FOLDER"]).mkdir(parents=True, exist_ok=True)

    @app.template_filter("currency")
    def currency_filter(value):
        try:
            return f"${float(value):,.0f}"
        except (TypeError, ValueError):
            return value

    @app.template_filter("decimal")
    def decimal_filter(value):
        try:
            return f"{float(value):,.1f}"
        except (TypeError, ValueError):
            return value

    db.init_app(app)
    app.register_blueprint(web_bp)
    app.register_blueprint(api_bp, url_prefix="/api")

    if not _is_database_admin_command():
        with app.app_context():
            db.ensure_seeded()

    return app
