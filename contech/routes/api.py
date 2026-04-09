import os
from pathlib import Path

from flask import Blueprint, current_app, jsonify

from ..auth import login_required
from ..db import get_db, get_schema_status
from ..services.bootstrap import build_bootstrap_payload

bp = Blueprint("api", __name__)


@bp.get("/health")
def health():
    return jsonify({"status": "ok"})


@bp.get("/ready")
def ready():
    try:
        db = get_db()
        schema_status = get_schema_status(db)
        db.execute("SELECT 1 AS ok").fetchone()

        upload_path = Path(current_app.config["JOB_DOCUMENT_UPLOAD_FOLDER"])
        upload_path.mkdir(parents=True, exist_ok=True)
        uploads_writable = os.access(upload_path, os.W_OK)

        ready_status = schema_status["schema_current"] and uploads_writable
        payload = {
            "status": "ready" if ready_status else "degraded",
            "database": schema_status,
            "checks": {
                "database_connection": "ok",
                "uploads_writable": uploads_writable,
            },
        }
        return jsonify(payload), 200 if ready_status else 503
    except Exception as exc:
        return (
            jsonify(
                {
                    "status": "not_ready",
                    "checks": {
                        "database_connection": "failed",
                    },
                    "error": str(exc),
                }
            ),
            503,
        )


@bp.get("/bootstrap")
@login_required
def bootstrap():
    return jsonify(build_bootstrap_payload())
