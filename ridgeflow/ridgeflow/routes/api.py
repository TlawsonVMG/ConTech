from flask import Blueprint, abort, jsonify

from ..db import get_db
from ..services.pdf_pipeline import build_takeoff_seed, get_latest_blueprint_analysis
from ..services.worker_pipeline import list_blueprint_worker_jobs, summarize_blueprint_worker_state

bp = Blueprint("api", __name__)


def _as_dicts(rows):
    return [dict(row) for row in rows]


@bp.get("/health")
def health():
    return jsonify({"status": "ok", "app": "RidgeFlow"})


@bp.get("/projects")
def projects():
    rows = get_db().execute(
        """
        SELECT p.*,
            (SELECT COUNT(*) FROM blueprints b WHERE b.project_id = p.id) AS blueprint_count,
            (SELECT COUNT(*) FROM takeoff_runs tr WHERE tr.project_id = p.id) AS takeoff_count,
            (SELECT COUNT(*) FROM tasks t WHERE t.project_id = p.id AND t.status != 'done') AS open_task_count
        FROM projects p
        ORDER BY p.updated_at DESC, p.id DESC
        """
    ).fetchall()
    return jsonify(_as_dicts(rows))


@bp.get("/projects/<int:project_id>")
def project_detail(project_id):
    db = get_db()
    project = db.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
    if project is None:
        abort(404)

    blueprints = _as_dicts(
        db.execute(
            "SELECT * FROM blueprints WHERE project_id = ? ORDER BY uploaded_at DESC, id DESC",
            (project_id,),
        ).fetchall()
    )
    for blueprint in blueprints:
        analysis = get_latest_blueprint_analysis(db, blueprint["id"])
        if analysis is not None:
            analysis["takeoff_seed"] = build_takeoff_seed(analysis, project_roof_system=project["roof_system"])
        blueprint["latest_analysis"] = analysis
        blueprint["worker_summary"] = summarize_blueprint_worker_state(db, blueprint["id"])

    payload = {
        "project": dict(project),
        "blueprints": blueprints,
        "takeoff_runs": _as_dicts(
            db.execute(
                "SELECT * FROM takeoff_runs WHERE project_id = ? ORDER BY created_at DESC, id DESC",
                (project_id,),
            ).fetchall()
        ),
        "tasks": _as_dicts(
            db.execute(
                """
                SELECT t.*, u.full_name AS owner_name
                FROM tasks t
                LEFT JOIN users u ON u.id = t.owner_user_id
                WHERE t.project_id = ?
                ORDER BY t.created_at DESC, t.id DESC
                """,
                (project_id,),
            ).fetchall()
        ),
        "messages": _as_dicts(
            db.execute(
                """
                SELECT pm.*, u.full_name, u.avatar_initials
                FROM project_messages pm
                JOIN users u ON u.id = pm.user_id
                WHERE pm.project_id = ?
                ORDER BY pm.created_at ASC, pm.id ASC
                """,
                (project_id,),
            ).fetchall()
        ),
    }
    return jsonify(payload)


@bp.get("/projects/<int:project_id>/blueprints/<int:blueprint_id>/analysis")
def blueprint_analysis(project_id, blueprint_id):
    db = get_db()
    blueprint = db.execute(
        "SELECT * FROM blueprints WHERE id = ? AND project_id = ?",
        (blueprint_id, project_id),
    ).fetchone()
    if blueprint is None:
        abort(404)

    analysis = get_latest_blueprint_analysis(db, blueprint_id)
    if analysis is None:
        return jsonify(
            {
                "blueprint": dict(blueprint),
                "analysis": None,
                "worker_summary": summarize_blueprint_worker_state(db, blueprint_id),
                "worker_jobs": list_blueprint_worker_jobs(db, blueprint_id),
            }
        )

    analysis["takeoff_seed"] = build_takeoff_seed(analysis, project_roof_system=None)
    return jsonify(
        {
            "blueprint": dict(blueprint),
            "analysis": analysis,
            "worker_summary": summarize_blueprint_worker_state(db, blueprint_id),
            "worker_jobs": list_blueprint_worker_jobs(db, blueprint_id),
        }
    )


@bp.get("/projects/<int:project_id>/takeoffs/<int:takeoff_id>")
def takeoff_detail(project_id, takeoff_id):
    db = get_db()
    takeoff = db.execute(
        "SELECT * FROM takeoff_runs WHERE id = ? AND project_id = ?",
        (takeoff_id, project_id),
    ).fetchone()
    if takeoff is None:
        abort(404)

    payload = {
        "takeoff": dict(takeoff),
        "items": _as_dicts(
            db.execute(
                "SELECT * FROM takeoff_items WHERE takeoff_run_id = ? ORDER BY sort_order, id",
                (takeoff_id,),
            ).fetchall()
        ),
    }
    return jsonify(payload)
