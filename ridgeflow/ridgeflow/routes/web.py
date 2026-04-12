from datetime import datetime
from pathlib import Path
from uuid import uuid4

from flask import Blueprint, abort, current_app, flash, redirect, render_template, request, send_from_directory, url_for
from werkzeug.utils import secure_filename

from ..db import get_db
from ..services.feedback_ranking import build_feedback_profile, rank_feedback_priorities
from ..services.pdf_pipeline import (
    CORRECTABLE_ANALYSIS_FIELDS,
    NUMERIC_STRUCTURED_FIELDS,
    analyze_blueprint_file,
    build_takeoff_seed,
    get_latest_blueprint_analysis,
    record_analysis_corrections,
    record_blueprint_analysis,
)
from ..services.revision_compare import get_blueprint_revision_compare, refresh_related_revision_compares
from ..services.takeoff import SUPPORTED_SYSTEMS, create_takeoff_run, default_waste_pct
from ..services.worker_pipeline import enqueue_blueprint_worker_pipeline, summarize_blueprint_worker_state

bp = Blueprint("web", __name__)

PROJECT_STATUSES = (
    "Intake",
    "Blueprint Review",
    "AI Processing",
    "Estimator Review",
    "Approved",
    "Ordered",
    "In Production",
    "Closed",
)
PROJECT_TYPES = ("Bid", "Budget", "Production Support")
TASK_STATUSES = ("todo", "in_progress", "blocked", "done")
TASK_PRIORITIES = ("low", "medium", "high")
ANALYSIS_FIELD_META = (
    ("roof_system_suggestion", "Roof System"),
    ("roof_area_squares", "Roof Area"),
    ("roof_area_sqft", "Area Sq Ft"),
    ("perimeter_feet", "Perimeter"),
    ("ridge_feet", "Ridge"),
    ("valley_feet", "Valley"),
    ("eave_feet", "Eave"),
    ("waste_pct", "Waste"),
    ("drains_count", "Drains"),
    ("penetrations_count", "Penetrations"),
    ("parapet_feet", "Parapet"),
    ("scale_text", "Detected Scale"),
    ("flashing_types", "Flashing Types"),
)


def _now():
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def _parse_optional_int(value):
    value = (value or "").strip()
    if not value:
        return None
    try:
        return int(value)
    except ValueError:
        return None


def _parse_optional_float(value):
    value = (value or "").strip()
    if not value:
        return 0.0
    try:
        return float(value)
    except ValueError:
        return None


def _format_analysis_value(field_name, value):
    if value in (None, "", []):
        return "Not detected"
    if isinstance(value, list):
        return ", ".join(str(item) for item in value)
    if field_name == "roof_area_squares":
        return f"{float(value):,.1f} squares"
    if field_name == "roof_area_sqft":
        return f"{float(value):,.0f} sq ft"
    if field_name in {"perimeter_feet", "ridge_feet", "valley_feet", "eave_feet", "parapet_feet"}:
        return f"{float(value):,.1f} lf"
    if field_name == "waste_pct":
        return f"{float(value):,.1f}%"
    if field_name in {"drains_count", "penetrations_count"}:
        return f"{int(float(value))}"
    return str(value)


def _analysis_field_rows(analysis):
    if not analysis:
        return []
    effective_data = analysis.get("effective_structured_data") or analysis.get("structured_data") or {}
    field_confidence = analysis.get("effective_field_confidence") or analysis.get("field_confidence") or {}
    rows = []
    for field_name, label in ANALYSIS_FIELD_META:
        if field_name == "roof_system_suggestion":
            value = analysis.get("effective_roof_system_suggestion") or analysis.get("roof_system_suggestion")
        else:
            value = effective_data.get(field_name)
        rows.append(
            {
                "field_name": field_name,
                "label": label,
                "value_display": _format_analysis_value(field_name, value),
                "confidence": float(field_confidence.get(field_name, 0.0)),
                "is_missing": value in (None, "", []),
            }
        )
    return rows


def _blueprint_page_rows(db, blueprint_id):
    rows = db.execute(
        """
        SELECT *
        FROM blueprint_page_extractions
        WHERE blueprint_id = ?
        ORDER BY page_number ASC,
            CASE source_type WHEN 'vision' THEN 0 WHEN 'ocr' THEN 1 ELSE 2 END,
            id DESC
        """,
        (blueprint_id,),
    ).fetchall()
    selected = {}
    for row in rows:
        if row["page_number"] not in selected:
            selected[row["page_number"]] = dict(row)
    return [selected[key] for key in sorted(selected)][:10]


def _revision_compare_metric_rows(revision_compare):
    if not revision_compare:
        return []
    rows = []
    for field_name, payload in (revision_compare.get("metric_deltas") or {}).items():
        if payload.get("delta_value") in (None, 0):
            continue
        rows.append(
            {
                "field_name": field_name,
                "label": payload.get("label", field_name.replace("_", " ").title()),
                "display": payload.get("display", ""),
                "material_change": bool(payload.get("material_change")),
            }
        )
    return rows[:6]


def _project_or_404(project_id):
    project = get_db().execute(
        """
        SELECT p.*,
            (SELECT COUNT(*) FROM blueprints b WHERE b.project_id = p.id) AS blueprint_count,
            (SELECT COUNT(*) FROM takeoff_runs tr WHERE tr.project_id = p.id) AS takeoff_count,
            (SELECT COUNT(*) FROM tasks t WHERE t.project_id = p.id AND t.status != 'done') AS open_task_count
        FROM projects p
        WHERE p.id = ?
        """,
        (project_id,),
    ).fetchone()
    if project is None:
        abort(404)
    return project


def _blueprint_or_404(project_id, blueprint_id):
    blueprint = get_db().execute(
        "SELECT * FROM blueprints WHERE id = ? AND project_id = ?",
        (blueprint_id, project_id),
    ).fetchone()
    if blueprint is None:
        abort(404)
    return blueprint


def _team_members():
    return get_db().execute(
        "SELECT id, full_name, role_name, avatar_initials FROM users WHERE is_active = 1 ORDER BY full_name"
    ).fetchall()


def _log_activity(project_id, actor_name, event_type, event_text):
    get_db().execute(
        """
        INSERT INTO project_activity (project_id, actor_name, event_type, event_text, created_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (project_id, actor_name, event_type, event_text, _now()),
    )


def _update_project(project_id, status=None):
    if status:
        get_db().execute(
            "UPDATE projects SET status = ?, updated_at = ? WHERE id = ?",
            (status, _now(), project_id),
        )
        return
    get_db().execute(
        "UPDATE projects SET updated_at = ? WHERE id = ?",
        (_now(), project_id),
    )


def _blueprint_cards(project, blueprints):
    db = get_db()
    cards = []
    default_seed = None
    feedback_profile = build_feedback_profile(db, project["roof_system"])
    for blueprint in blueprints:
        analysis = get_latest_blueprint_analysis(db, blueprint["id"])
        takeoff_seed = build_takeoff_seed(analysis, project_roof_system=project["roof_system"]) if analysis else None
        revision_compare = get_blueprint_revision_compare(db, blueprint["id"])
        cards.append(
            {
                "blueprint": blueprint,
                "analysis": analysis,
                "takeoff_seed": takeoff_seed,
                "analysis_field_rows": _analysis_field_rows(analysis),
                "page_rows": _blueprint_page_rows(db, blueprint["id"]),
                "revision_compare": revision_compare,
                "revision_metric_rows": _revision_compare_metric_rows(revision_compare),
                "feedback_priorities": rank_feedback_priorities(
                    db,
                    project["roof_system"],
                    analysis,
                    revision_compare=revision_compare,
                    feedback_profile=feedback_profile,
                ),
                "worker_summary": summarize_blueprint_worker_state(db, blueprint["id"]),
            }
        )
        if default_seed is None and takeoff_seed and takeoff_seed["can_generate"]:
            default_seed = {**takeoff_seed, "blueprint_id": blueprint["id"]}

    if default_seed is None:
        default_seed = {
            "system_type": project["roof_system"],
            "roof_area_squares": None,
            "waste_pct": default_waste_pct(project["roof_system"]),
            "perimeter_feet": 0,
            "ridge_feet": 0,
            "valley_feet": 0,
            "eave_feet": 0,
            "can_generate": False,
            "missing_fields": [],
            "blueprint_id": None,
        }

    return cards, default_seed, feedback_profile


@bp.get("/")
def dashboard():
    db = get_db()
    metrics = {
        "active_projects": db.execute(
            "SELECT COUNT(*) AS count FROM projects WHERE status != 'Closed'"
        ).fetchone()["count"],
        "review_takeoffs": db.execute(
            "SELECT COUNT(*) AS count FROM takeoff_runs WHERE status != 'Approved'"
        ).fetchone()["count"],
        "open_tasks": db.execute(
            "SELECT COUNT(*) AS count FROM tasks WHERE status != 'done'"
        ).fetchone()["count"],
        "blueprint_sets": db.execute("SELECT COUNT(*) AS count FROM blueprints").fetchone()["count"],
    }

    projects = db.execute(
        """
        SELECT p.*,
            (SELECT COUNT(*) FROM blueprints b WHERE b.project_id = p.id) AS blueprint_count,
            (SELECT COUNT(*) FROM takeoff_runs tr WHERE tr.project_id = p.id) AS takeoff_count,
            (SELECT COUNT(*) FROM tasks t WHERE t.project_id = p.id AND t.status != 'done') AS open_task_count
        FROM projects p
        ORDER BY p.updated_at DESC, p.id DESC
        LIMIT 6
        """
    ).fetchall()

    tasks = db.execute(
        """
        SELECT t.*, p.name AS project_name, u.full_name AS owner_name
        FROM tasks t
        LEFT JOIN projects p ON p.id = t.project_id
        LEFT JOIN users u ON u.id = t.owner_user_id
        WHERE t.status != 'done'
        ORDER BY CASE t.priority WHEN 'high' THEN 0 WHEN 'medium' THEN 1 ELSE 2 END, t.due_date
        LIMIT 6
        """
    ).fetchall()

    messages = db.execute(
        """
        SELECT pm.*, u.full_name, u.avatar_initials, p.name AS project_name
        FROM project_messages pm
        JOIN users u ON u.id = pm.user_id
        JOIN projects p ON p.id = pm.project_id
        ORDER BY pm.created_at DESC, pm.id DESC
        LIMIT 6
        """
    ).fetchall()

    recent_takeoffs = db.execute(
        """
        SELECT tr.*, p.name AS project_name, b.original_filename
        FROM takeoff_runs tr
        JOIN projects p ON p.id = tr.project_id
        JOIN blueprints b ON b.id = tr.blueprint_id
        ORDER BY tr.created_at DESC, tr.id DESC
        LIMIT 5
        """
    ).fetchall()

    return render_template(
        "dashboard.html",
        metrics=metrics,
        projects=projects,
        tasks=tasks,
        messages=messages,
        recent_takeoffs=recent_takeoffs,
        supported_systems=SUPPORTED_SYSTEMS,
    )


@bp.get("/projects")
def project_index():
    projects = get_db().execute(
        """
        SELECT p.*,
            (SELECT COUNT(*) FROM blueprints b WHERE b.project_id = p.id) AS blueprint_count,
            (SELECT COUNT(*) FROM takeoff_runs tr WHERE tr.project_id = p.id) AS takeoff_count,
            (SELECT COUNT(*) FROM tasks t WHERE t.project_id = p.id AND t.status != 'done') AS open_task_count
        FROM projects p
        ORDER BY p.updated_at DESC, p.id DESC
        """
    ).fetchall()
    return render_template("projects/index.html", projects=projects)


@bp.route("/projects/new", methods=("GET", "POST"))
def project_create():
    members = _team_members()
    if request.method == "POST":
        db = get_db()
        name = request.form.get("name", "").strip()
        client_name = request.form.get("client_name", "").strip()
        project_type = request.form.get("project_type", "Bid").strip()
        roof_system = request.form.get("roof_system", "Architectural Shingles").strip()
        address = request.form.get("address", "").strip()
        estimator_name = request.form.get("estimator_name", "").strip()
        bid_date = request.form.get("bid_date", "").strip() or None
        due_date = request.form.get("due_date", "").strip() or None
        notes = request.form.get("notes", "").strip()

        errors = []
        if not name:
            errors.append("Project name is required.")
        if not client_name:
            errors.append("Client name is required.")
        if project_type not in PROJECT_TYPES:
            errors.append("Choose a valid project type.")
        if roof_system not in SUPPORTED_SYSTEMS:
            errors.append("Choose a supported roof system.")
        if not address:
            errors.append("Project address is required.")
        if not estimator_name:
            errors.append("Assign an estimator.")

        if errors:
            for error in errors:
                flash(error, "error")
            return render_template(
                "projects/form.html",
                members=members,
                project_statuses=PROJECT_STATUSES,
                project_types=PROJECT_TYPES,
                supported_systems=SUPPORTED_SYSTEMS,
                form=request.form,
            )

        project_id = db.execute(
            """
            INSERT INTO projects (
                team_id, name, client_name, project_type, roof_system, address, status,
                estimator_name, bid_date, due_date, notes, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                1,
                name,
                client_name,
                project_type,
                roof_system,
                address,
                "Intake",
                estimator_name,
                bid_date,
                due_date,
                notes,
                _now(),
                _now(),
            ),
        ).lastrowid
        _log_activity(project_id, estimator_name, "project_created", f"Created project for {client_name}.")
        db.commit()
        flash("Project created.", "success")
        return redirect(url_for("web.project_detail", project_id=project_id))

    return render_template(
        "projects/form.html",
        members=members,
        project_statuses=PROJECT_STATUSES,
        project_types=PROJECT_TYPES,
        supported_systems=SUPPORTED_SYSTEMS,
        form={},
    )


@bp.get("/projects/<int:project_id>")
def project_detail(project_id):
    db = get_db()
    project = _project_or_404(project_id)
    blueprints = db.execute(
        "SELECT * FROM blueprints WHERE project_id = ? ORDER BY uploaded_at DESC, id DESC",
        (project_id,),
    ).fetchall()
    blueprint_cards, default_takeoff_seed, feedback_profile = _blueprint_cards(project, blueprints)
    takeoff_runs = db.execute(
        "SELECT * FROM takeoff_runs WHERE project_id = ? ORDER BY created_at DESC, id DESC",
        (project_id,),
    ).fetchall()

    selected_takeoff = None
    takeoff_id = request.args.get("takeoff_id", type=int)
    if takeoff_runs:
        selected_takeoff = next((row for row in takeoff_runs if row["id"] == takeoff_id), takeoff_runs[0])

    takeoff_items = []
    selected_takeoff_revision_compare = None
    selected_takeoff_feedback_priorities = []
    if selected_takeoff is not None:
        takeoff_items = db.execute(
            "SELECT * FROM takeoff_items WHERE takeoff_run_id = ? ORDER BY sort_order, id",
            (selected_takeoff["id"],),
        ).fetchall()
        selected_takeoff_revision_compare = get_blueprint_revision_compare(db, selected_takeoff["blueprint_id"])
        selected_takeoff_feedback_priorities = rank_feedback_priorities(
            db,
            project["roof_system"],
            get_latest_blueprint_analysis(db, selected_takeoff["blueprint_id"]),
            revision_compare=selected_takeoff_revision_compare,
            feedback_profile=feedback_profile,
        )

    tasks = db.execute(
        """
        SELECT t.*, u.full_name AS owner_name, u.avatar_initials
        FROM tasks t
        LEFT JOIN users u ON u.id = t.owner_user_id
        WHERE t.project_id = ?
        ORDER BY CASE t.priority WHEN 'high' THEN 0 WHEN 'medium' THEN 1 ELSE 2 END, t.created_at DESC
        """,
        (project_id,),
    ).fetchall()
    grouped_tasks = {status: [] for status in TASK_STATUSES}
    for task in tasks:
        grouped_tasks[task["status"]].append(task)

    messages = db.execute(
        """
        SELECT pm.*, u.full_name, u.avatar_initials, u.role_name
        FROM project_messages pm
        JOIN users u ON u.id = pm.user_id
        WHERE pm.project_id = ?
        ORDER BY pm.created_at ASC, pm.id ASC
        """,
        (project_id,),
    ).fetchall()
    activity = db.execute(
        """
        SELECT *
        FROM project_activity
        WHERE project_id = ?
        ORDER BY created_at DESC, id DESC
        LIMIT 12
        """,
        (project_id,),
    ).fetchall()

    return render_template(
        "projects/workspace.html",
        project=project,
        blueprints=blueprints,
        blueprint_cards=blueprint_cards,
        default_takeoff_seed=default_takeoff_seed,
        takeoff_runs=takeoff_runs,
        selected_takeoff=selected_takeoff,
        takeoff_items=takeoff_items,
        selected_takeoff_revision_compare=selected_takeoff_revision_compare,
        selected_takeoff_feedback_priorities=selected_takeoff_feedback_priorities,
        feedback_profile=feedback_profile,
        tasks=tasks,
        grouped_tasks=grouped_tasks,
        messages=messages,
        activity=activity,
        members=_team_members(),
        task_statuses=TASK_STATUSES,
        task_priorities=TASK_PRIORITIES,
        supported_systems=SUPPORTED_SYSTEMS,
    )


@bp.post("/projects/<int:project_id>/blueprints")
def project_blueprint_upload(project_id):
    db = get_db()
    project = _project_or_404(project_id)
    upload = request.files.get("blueprint_file")
    if upload is None or not upload.filename:
        flash("Choose a blueprint PDF to upload.", "error")
        return redirect(url_for("web.project_detail", project_id=project_id))

    if Path(upload.filename).suffix.lower() != ".pdf":
        flash("Blueprint uploads must be PDF files.", "error")
        return redirect(url_for("web.project_detail", project_id=project_id))

    safe_name = secure_filename(upload.filename)
    stored_filename = f"{uuid4().hex}_{safe_name}"
    save_path = Path(current_app.config["BLUEPRINT_UPLOAD_FOLDER"]) / stored_filename
    upload.save(save_path)

    phase_label = request.form.get("phase_label", "Bid Set").strip() or "Bid Set"
    version_label = request.form.get("version_label", "v1").strip() or "v1"
    page_count = _parse_optional_int(request.form.get("page_count"))
    notes = request.form.get("notes", "").strip()

    blueprint_id = db.execute(
        """
        INSERT INTO blueprints (
            project_id, stored_filename, original_filename, phase_label, version_label, status,
            page_count, file_size_bytes, notes, uploaded_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            project_id,
            stored_filename,
            upload.filename,
            phase_label,
            version_label,
            "Ready for AI",
            page_count,
            save_path.stat().st_size,
            notes,
            _now(),
        ),
    ).lastrowid
    _update_project(project_id, status="Blueprint Review")
    _log_activity(project_id, project["estimator_name"], "blueprint_uploaded", f"Uploaded {upload.filename}.")

    flash_message = "Blueprint uploaded."
    flash_category = "success"
    try:
        analysis = analyze_blueprint_file(
            save_path,
            roof_system_hint=project["roof_system"],
            original_filename=upload.filename,
        )
        record_blueprint_analysis(db, blueprint_id, analysis)
        refresh_related_revision_compares(db, project_id, blueprint_id)
        _log_activity(project_id, "RidgeFlow AI", "blueprint_analyzed", f"Analyzed {upload.filename}.")
        if analysis["status"] == "Completed":
            flash_message = "Blueprint uploaded and analyzed."
        else:
            flash_message = "Blueprint uploaded, but the parser needs review because readable text was limited."
            flash_category = "error"
    except Exception:
        db.execute(
            """
            UPDATE blueprints
            SET analysis_status = ?, analysis_summary = ?, last_analyzed_at = ?
            WHERE id = ?
            """,
            (
                "Review Required",
                "Upload succeeded, but the native parser could not finish analysis.",
                _now(),
                blueprint_id,
            ),
        )
        _log_activity(project_id, "RidgeFlow AI", "blueprint_analysis_failed", f"Analysis failed for {upload.filename}.")
        flash_message = "Blueprint uploaded, but the parser could not analyze it cleanly."
        flash_category = "error"

    queue_result = enqueue_blueprint_worker_pipeline(db, blueprint_id)
    if queue_result is not None and flash_category == "success":
        flash_message += " Raster, OCR, and vision worker jobs were queued."

    db.commit()
    flash(flash_message, flash_category)
    return redirect(url_for("web.project_detail", project_id=project_id))


@bp.get("/blueprints/<path:filename>")
def blueprint_file(filename):
    return send_from_directory(current_app.config["BLUEPRINT_UPLOAD_FOLDER"], filename)


@bp.post("/projects/<int:project_id>/blueprints/<int:blueprint_id>/analyze")
def project_blueprint_analyze(project_id, blueprint_id):
    db = get_db()
    project = _project_or_404(project_id)
    blueprint = _blueprint_or_404(project_id, blueprint_id)

    if not blueprint["stored_filename"]:
        flash("This blueprint does not have a stored PDF file yet.", "error")
        return redirect(url_for("web.project_detail", project_id=project_id))

    file_path = Path(current_app.config["BLUEPRINT_UPLOAD_FOLDER"]) / blueprint["stored_filename"]
    if not file_path.exists():
        flash("The stored PDF file could not be found for this blueprint.", "error")
        return redirect(url_for("web.project_detail", project_id=project_id))

    analysis = analyze_blueprint_file(
        file_path,
        roof_system_hint=project["roof_system"],
        original_filename=blueprint["original_filename"],
    )
    record_blueprint_analysis(db, blueprint_id, analysis)
    refresh_related_revision_compares(db, project_id, blueprint_id)
    _update_project(project_id, status="Blueprint Review")
    _log_activity(project_id, "RidgeFlow AI", "blueprint_analyzed", f"Refreshed analysis for {blueprint['original_filename']}.")
    db.commit()

    flash(
        "Blueprint analysis refreshed." if analysis["status"] == "Completed" else "Blueprint analysis refreshed, but it still needs review.",
        "success" if analysis["status"] == "Completed" else "error",
    )
    return redirect(url_for("web.project_detail", project_id=project_id))


@bp.post("/projects/<int:project_id>/blueprints/<int:blueprint_id>/queue-workers")
def project_blueprint_queue_workers(project_id, blueprint_id):
    db = get_db()
    _project_or_404(project_id)
    _blueprint_or_404(project_id, blueprint_id)
    job_id = enqueue_blueprint_worker_pipeline(db, blueprint_id, reset=request.form.get("reset") == "1")
    db.commit()
    if job_id is None:
        flash("This blueprint already has worker jobs pending.", "error")
    else:
        flash("Worker pipeline queued for this blueprint.", "success")
    return redirect(url_for("web.project_detail", project_id=project_id))


@bp.post("/projects/<int:project_id>/blueprints/<int:blueprint_id>/compare-revision")
def project_blueprint_compare_revision(project_id, blueprint_id):
    db = get_db()
    _project_or_404(project_id)
    _blueprint_or_404(project_id, blueprint_id)
    revision_compare = refresh_related_revision_compares(db, project_id, blueprint_id)
    db.commit()
    if revision_compare:
        flash("Revision compare refreshed for this blueprint sequence.", "success")
    else:
        flash("No earlier blueprint version exists to compare against yet.", "error")
    return redirect(url_for("web.project_detail", project_id=project_id))


@bp.post("/projects/<int:project_id>/blueprints/<int:blueprint_id>/analysis-corrections")
def project_blueprint_analysis_corrections(project_id, blueprint_id):
    db = get_db()
    project = _project_or_404(project_id)
    blueprint = _blueprint_or_404(project_id, blueprint_id)
    analysis = get_latest_blueprint_analysis(db, blueprint_id)
    if analysis is None:
        flash("Run blueprint analysis before saving estimator corrections.", "error")
        return redirect(url_for("web.project_detail", project_id=project_id))

    corrected_by_name = request.form.get("corrected_by_name", "").strip() or project["estimator_name"]
    notes = request.form.get("notes", "").strip() or None
    correction_values = {}
    errors = []

    for field_name in CORRECTABLE_ANALYSIS_FIELDS:
        raw_value = request.form.get(field_name)
        if raw_value is None:
            continue
        raw_value = raw_value.strip()
        if not raw_value:
            continue
        if field_name in NUMERIC_STRUCTURED_FIELDS:
            try:
                correction_values[field_name] = float(raw_value)
            except ValueError:
                errors.append(f"{field_name.replace('_', ' ').title()} must be numeric.")
        elif field_name == "flashing_types":
            flashing_types = [item.strip() for item in raw_value.replace(";", ",").split(",") if item.strip()]
            if flashing_types:
                correction_values[field_name] = flashing_types
        else:
            correction_values[field_name] = raw_value

    if errors:
        for error in errors:
            flash(error, "error")
        return redirect(url_for("web.project_detail", project_id=project_id))
    if not correction_values:
        flash("Enter at least one corrected AI field before saving.", "error")
        return redirect(url_for("web.project_detail", project_id=project_id))

    saved_count = record_analysis_corrections(
        db,
        blueprint_id=blueprint_id,
        blueprint_analysis_id=analysis["id"],
        corrected_by_name=corrected_by_name,
        values=correction_values,
        notes=notes,
    )
    _update_project(project_id, status="Estimator Review")
    refresh_related_revision_compares(db, project_id, blueprint_id)
    _log_activity(
        project_id,
        corrected_by_name,
        "analysis_corrected",
        f"Saved {saved_count} estimator correction(s) for {blueprint['original_filename']}.",
    )
    db.commit()
    flash("Estimator corrections saved to the AI blueprint analysis.", "success")
    return redirect(url_for("web.project_detail", project_id=project_id))


@bp.post("/projects/<int:project_id>/blueprints/<int:blueprint_id>/takeoff-from-analysis")
def project_takeoff_from_analysis(project_id, blueprint_id):
    db = get_db()
    project = _project_or_404(project_id)
    blueprint = _blueprint_or_404(project_id, blueprint_id)
    analysis = get_latest_blueprint_analysis(db, blueprint_id)
    if analysis is None:
        flash("Run blueprint analysis before generating a takeoff from it.", "error")
        return redirect(url_for("web.project_detail", project_id=project_id))

    takeoff_seed = build_takeoff_seed(analysis, project_roof_system=project["roof_system"])
    if not takeoff_seed or not takeoff_seed["can_generate"]:
        missing = ", ".join(takeoff_seed["missing_fields"]) if takeoff_seed else "roof area"
        flash(f"The analysis is missing required takeoff inputs: {missing}.", "error")
        return redirect(url_for("web.project_detail", project_id=project_id))

    takeoff_id = create_takeoff_run(
        db=db,
        project_id=project_id,
        blueprint_id=blueprint_id,
        blueprint_analysis_id=analysis["id"],
        system_type=takeoff_seed["system_type"],
        roof_area_squares=takeoff_seed["roof_area_squares"],
        waste_pct=takeoff_seed["waste_pct"],
        perimeter_feet=takeoff_seed["perimeter_feet"],
        ridge_feet=takeoff_seed["ridge_feet"],
        valley_feet=takeoff_seed["valley_feet"],
        eave_feet=takeoff_seed["eave_feet"],
        ai_model=current_app.config["DEFAULT_AI_MODEL"],
        source_mode="blueprint-analysis",
        analysis_summary_override=f"Blueprint analysis seeded takeoff. {analysis['summary']}",
        confidence_override=takeoff_seed.get("confidence"),
    )
    _update_project(project_id, status="Estimator Review")
    _log_activity(
        project_id,
        "RidgeFlow AI",
        "takeoff_generated",
        f"Generated takeoff from blueprint analysis for {blueprint['original_filename']}.",
    )
    db.commit()
    flash("Takeoff created from blueprint analysis.", "success")
    return redirect(url_for("web.project_detail", project_id=project_id, takeoff_id=takeoff_id))


@bp.post("/projects/<int:project_id>/takeoffs")
def project_takeoff_create(project_id):
    db = get_db()
    project = _project_or_404(project_id)
    blueprint_id = _parse_optional_int(request.form.get("blueprint_id"))
    roof_system = request.form.get("system_type", "").strip()
    roof_area_squares = _parse_optional_float(request.form.get("roof_area_squares"))
    waste_pct = _parse_optional_float(request.form.get("waste_pct"))
    perimeter_feet = _parse_optional_float(request.form.get("perimeter_feet"))
    ridge_feet = _parse_optional_float(request.form.get("ridge_feet"))
    valley_feet = _parse_optional_float(request.form.get("valley_feet"))
    eave_feet = _parse_optional_float(request.form.get("eave_feet"))

    errors = []
    if blueprint_id is None:
        errors.append("Choose a blueprint for the takeoff run.")
    else:
        blueprint = db.execute(
            "SELECT id FROM blueprints WHERE id = ? AND project_id = ?",
            (blueprint_id, project_id),
        ).fetchone()
        if blueprint is None:
            errors.append("The selected blueprint does not belong to this project.")
    if roof_system not in SUPPORTED_SYSTEMS:
        errors.append("Choose a supported roof system.")
    if roof_area_squares is None or roof_area_squares <= 0:
        errors.append("Roof area in squares is required.")
    for label, value in (
        ("Waste", waste_pct),
        ("Perimeter", perimeter_feet),
        ("Ridge", ridge_feet),
        ("Valley", valley_feet),
        ("Eave", eave_feet),
    ):
        if value is None:
            errors.append(f"{label} value must be numeric.")

    if errors:
        for error in errors:
            flash(error, "error")
        return redirect(url_for("web.project_detail", project_id=project_id))

    takeoff_id = create_takeoff_run(
        db=db,
        project_id=project_id,
        blueprint_id=blueprint_id,
        system_type=roof_system,
        roof_area_squares=roof_area_squares,
        waste_pct=waste_pct,
        perimeter_feet=perimeter_feet,
        ridge_feet=ridge_feet,
        valley_feet=valley_feet,
        eave_feet=eave_feet,
        ai_model=current_app.config["DEFAULT_AI_MODEL"],
    )
    _update_project(project_id, status="Estimator Review")
    _log_activity(
        project_id,
        project["estimator_name"],
        "takeoff_generated",
        f"Generated {roof_system} takeoff from blueprint #{blueprint_id}.",
    )
    db.commit()
    flash("AI takeoff generated.", "success")
    return redirect(url_for("web.project_detail", project_id=project_id, takeoff_id=takeoff_id))


@bp.post("/projects/<int:project_id>/takeoffs/<int:takeoff_id>/approve")
def project_takeoff_approve(project_id, takeoff_id):
    db = get_db()
    project = _project_or_404(project_id)
    takeoff = db.execute(
        "SELECT * FROM takeoff_runs WHERE id = ? AND project_id = ?",
        (takeoff_id, project_id),
    ).fetchone()
    if takeoff is None:
        abort(404)

    timestamp = _now()
    db.execute(
        """
        UPDATE takeoff_runs
        SET status = 'Approved', reviewed_at = ?, approved_at = ?
        WHERE id = ?
        """,
        (timestamp, timestamp, takeoff_id),
    )
    _update_project(project_id, status="Approved")
    _log_activity(project_id, project["estimator_name"], "takeoff_approved", f"Approved takeoff #{takeoff_id}.")
    db.commit()
    flash("Takeoff approved.", "success")
    return redirect(url_for("web.project_detail", project_id=project_id, takeoff_id=takeoff_id))


@bp.post("/projects/<int:project_id>/tasks")
def project_task_create(project_id):
    db = get_db()
    _project_or_404(project_id)
    owner_user_id = _parse_optional_int(request.form.get("owner_user_id"))
    title = request.form.get("title", "").strip()
    priority = request.form.get("priority", "medium").strip()
    due_date = request.form.get("due_date", "").strip() or None
    notes = request.form.get("notes", "").strip()

    if not title:
        flash("Task title is required.", "error")
        return redirect(url_for("web.project_detail", project_id=project_id))
    if priority not in TASK_PRIORITIES:
        flash("Choose a valid task priority.", "error")
        return redirect(url_for("web.project_detail", project_id=project_id))

    db.execute(
        """
        INSERT INTO tasks (project_id, owner_user_id, title, status, priority, due_date, notes, created_at)
        VALUES (?, ?, ?, 'todo', ?, ?, ?, ?)
        """,
        (project_id, owner_user_id, title, priority, due_date, notes, _now()),
    )
    owner_name = "RidgeFlow"
    if owner_user_id:
        owner = db.execute("SELECT full_name FROM users WHERE id = ?", (owner_user_id,)).fetchone()
        if owner is not None:
            owner_name = owner["full_name"]
    _update_project(project_id)
    _log_activity(project_id, owner_name, "task_created", f"Added task: {title}.")
    db.commit()
    flash("Task added.", "success")
    return redirect(url_for("web.project_detail", project_id=project_id))


@bp.post("/projects/<int:project_id>/tasks/<int:task_id>/status")
def project_task_status_update(project_id, task_id):
    db = get_db()
    task = db.execute(
        "SELECT * FROM tasks WHERE id = ? AND project_id = ?",
        (task_id, project_id),
    ).fetchone()
    if task is None:
        abort(404)

    new_status = request.form.get("status", "").strip()
    if new_status not in TASK_STATUSES:
        flash("Choose a valid task status.", "error")
        return redirect(url_for("web.project_detail", project_id=project_id))

    db.execute("UPDATE tasks SET status = ? WHERE id = ?", (new_status, task_id))
    _update_project(project_id)
    _log_activity(project_id, "Workflow", "task_status_changed", f"Moved task '{task['title']}' to {new_status}.")
    db.commit()
    flash("Task status updated.", "success")
    return redirect(url_for("web.project_detail", project_id=project_id))


@bp.post("/projects/<int:project_id>/messages")
def project_message_create(project_id):
    db = get_db()
    _project_or_404(project_id)
    user_id = _parse_optional_int(request.form.get("user_id"))
    body = request.form.get("body", "").strip()

    if user_id is None:
        flash("Choose a team member for the message.", "error")
        return redirect(url_for("web.project_detail", project_id=project_id))
    if not body:
        flash("Message text is required.", "error")
        return redirect(url_for("web.project_detail", project_id=project_id))

    user = db.execute("SELECT full_name FROM users WHERE id = ?", (user_id,)).fetchone()
    if user is None:
        flash("Selected user was not found.", "error")
        return redirect(url_for("web.project_detail", project_id=project_id))

    db.execute(
        "INSERT INTO project_messages (project_id, user_id, body, created_at) VALUES (?, ?, ?, ?)",
        (project_id, user_id, body, _now()),
    )
    _update_project(project_id)
    _log_activity(project_id, user["full_name"], "message_posted", "Posted a project message.")
    db.commit()
    flash("Message sent.", "success")
    return redirect(url_for("web.project_detail", project_id=project_id))
