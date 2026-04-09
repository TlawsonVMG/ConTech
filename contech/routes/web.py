from pathlib import Path

from flask import Blueprint, current_app, send_from_directory

from ..auth import login_required

bp = Blueprint("web", __name__)


def _project_root():
    return Path(current_app.root_path).parent


@bp.get("/prototype")
@login_required
def prototype():
    return send_from_directory(_project_root(), "index.html")


@bp.get("/styles.css")
def styles():
    return send_from_directory(_project_root(), "styles.css")


@bp.get("/app.js")
def app_js():
    return send_from_directory(_project_root(), "app.js")
