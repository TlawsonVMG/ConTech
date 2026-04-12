import json
from datetime import datetime

from .pdf_pipeline import get_latest_blueprint_analysis


METRIC_FIELDS = (
    ("roof_area_squares", "Roof Area", "squares", 0.05, 3.0),
    ("perimeter_feet", "Perimeter", "lf", 0.04, 20.0),
    ("ridge_feet", "Ridge", "lf", 0.08, 8.0),
    ("valley_feet", "Valley", "lf", 0.1, 6.0),
    ("eave_feet", "Eave", "lf", 0.06, 10.0),
    ("waste_pct", "Waste", "%", 0.1, 1.0),
    ("drains_count", "Drains", "count", 0.0, 1.0),
    ("penetrations_count", "Penetrations", "count", 0.0, 1.0),
    ("parapet_feet", "Parapet", "lf", 0.08, 10.0),
)


def _now():
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def _json_load(value, default):
    if not value:
        return default
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return default


def _format_delta(field_meta, delta_value):
    _field_name, label, unit, _pct_threshold, _abs_threshold = field_meta
    if delta_value is None:
        return f"{label} unchanged"
    if unit == "count":
        return f"{label} {delta_value:+.0f}"
    if unit == "%":
        return f"{label} {delta_value:+.1f}%"
    if unit == "squares":
        return f"{label} {delta_value:+.1f} squares"
    return f"{label} {delta_value:+.1f} {unit}"


def _safe_percent_delta(base_value, candidate_value):
    if base_value in (None, 0):
        return None
    return (float(candidate_value) - float(base_value)) / float(base_value)


def _compare_metric(field_meta, base_value, candidate_value):
    field_name, label, unit, pct_threshold, abs_threshold = field_meta
    if base_value is None and candidate_value is None:
        return None

    delta_value = None
    delta_pct = None
    material_change = False

    if base_value is None or candidate_value is None:
        material_change = True
    else:
        delta_value = round(float(candidate_value) - float(base_value), 2)
        delta_pct = _safe_percent_delta(base_value, candidate_value)
        if unit == "count":
            material_change = abs(delta_value) >= abs_threshold
        else:
            material_change = abs(delta_value) >= abs_threshold or (
                delta_pct is not None and abs(delta_pct) >= pct_threshold
            )

    return {
        "field_name": field_name,
        "label": label,
        "unit": unit,
        "base_value": base_value,
        "candidate_value": candidate_value,
        "delta_value": delta_value,
        "delta_pct": round(delta_pct, 4) if delta_pct is not None else None,
        "material_change": material_change,
        "display": _format_delta(field_meta, delta_value),
    }


def _compare_lists(base_values, candidate_values):
    base_set = {str(item).strip() for item in (base_values or []) if str(item).strip()}
    candidate_set = {str(item).strip() for item in (candidate_values or []) if str(item).strip()}
    return {
        "added": sorted(candidate_set - base_set),
        "removed": sorted(base_set - candidate_set),
        "unchanged": sorted(base_set & candidate_set),
    }


def _compare_page_roles(base_summary, candidate_summary):
    roles = set(base_summary or {}) | set(candidate_summary or {})
    changes = {}
    for role_name in sorted(roles):
        base_value = int((base_summary or {}).get(role_name, 0) or 0)
        candidate_value = int((candidate_summary or {}).get(role_name, 0) or 0)
        if base_value == 0 and candidate_value == 0:
            continue
        changes[role_name] = {
            "base_count": base_value,
            "candidate_count": candidate_value,
            "delta": candidate_value - base_value,
        }
    return changes


def compare_blueprint_analyses(base_blueprint, compared_blueprint, base_analysis, compared_analysis):
    if base_blueprint is None:
        return {
            "status": "No Prior Revision",
            "summary": "This is the first blueprint version stored for the project.",
            "metric_deltas": {},
            "list_changes": {},
            "page_role_changes": {},
            "review_flags": [],
        }

    if base_analysis is None or compared_analysis is None:
        return {
            "status": "Pending",
            "summary": "Revision compare is waiting on completed blueprint analyses.",
            "metric_deltas": {},
            "list_changes": {},
            "page_role_changes": {},
            "review_flags": ["Run analysis on both blueprint versions to compare revisions."],
        }

    base_data = base_analysis.get("effective_structured_data") or base_analysis.get("structured_data") or {}
    compared_data = compared_analysis.get("effective_structured_data") or compared_analysis.get("structured_data") or {}
    metric_deltas = {}
    changed_metric_displays = []
    review_flags = []

    for field_meta in METRIC_FIELDS:
        field_name = field_meta[0]
        metric = _compare_metric(field_meta, base_data.get(field_name), compared_data.get(field_name))
        if metric is None:
            continue
        metric_deltas[field_name] = metric
        if metric["delta_value"] not in (None, 0):
            changed_metric_displays.append(metric["display"])
        if metric["material_change"]:
            review_flags.append(f"Review {metric['label'].lower()} delta between revisions.")

    base_system = base_analysis.get("effective_roof_system_suggestion") or base_analysis.get("roof_system_suggestion")
    compared_system = compared_analysis.get("effective_roof_system_suggestion") or compared_analysis.get("roof_system_suggestion")
    if base_system and compared_system and base_system != compared_system:
        review_flags.append(f"Roof system changed from {base_system} to {compared_system}.")

    list_changes = {
        "flashing_types": _compare_lists(base_data.get("flashing_types"), compared_data.get("flashing_types")),
    }
    if list_changes["flashing_types"]["added"] or list_changes["flashing_types"]["removed"]:
        review_flags.append("Review flashing and edge-condition changes between plan revisions.")

    page_role_changes = _compare_page_roles(
        base_analysis.get("page_role_summary"),
        compared_analysis.get("page_role_summary"),
    )
    if compared_analysis.get("confidence", 0.0) + 0.12 < base_analysis.get("confidence", 0.0):
        review_flags.append("AI confidence dropped on the newer revision.")

    unique_flags = []
    seen = set()
    for flag in review_flags:
        if flag not in seen:
            seen.add(flag)
            unique_flags.append(flag)

    if unique_flags:
        status = "Review Required"
    elif changed_metric_displays or list_changes["flashing_types"]["added"] or list_changes["flashing_types"]["removed"]:
        status = "Changed"
    else:
        status = "No Material Change"

    summary_parts = [
        f"Compared {compared_blueprint['version_label']} to {base_blueprint['version_label']}",
    ]
    if changed_metric_displays:
        summary_parts.append(", ".join(changed_metric_displays[:3]))
    if list_changes["flashing_types"]["added"]:
        summary_parts.append(f"added {', '.join(list_changes['flashing_types']['added'][:3])}")
    if list_changes["flashing_types"]["removed"]:
        summary_parts.append(f"removed {', '.join(list_changes['flashing_types']['removed'][:3])}")
    if unique_flags:
        summary_parts.append(f"{len(unique_flags)} review flag(s)")
    if len(summary_parts) == 1:
        summary_parts.append("no material changes detected")

    return {
        "status": status,
        "summary": "; ".join(summary_parts) + ".",
        "metric_deltas": metric_deltas,
        "list_changes": list_changes,
        "page_role_changes": page_role_changes,
        "review_flags": unique_flags,
    }


def _previous_blueprint(db, project_id, blueprint_id):
    current = db.execute(
        "SELECT id, uploaded_at FROM blueprints WHERE id = ? AND project_id = ?",
        (blueprint_id, project_id),
    ).fetchone()
    if current is None:
        return None
    return db.execute(
        """
        SELECT *
        FROM blueprints
        WHERE project_id = ?
          AND (uploaded_at < ? OR (uploaded_at = ? AND id < ?))
        ORDER BY uploaded_at DESC, id DESC
        LIMIT 1
        """,
        (project_id, current["uploaded_at"], current["uploaded_at"], current["id"]),
    ).fetchone()


def _next_blueprint(db, project_id, blueprint_id):
    current = db.execute(
        "SELECT id, uploaded_at FROM blueprints WHERE id = ? AND project_id = ?",
        (blueprint_id, project_id),
    ).fetchone()
    if current is None:
        return None
    return db.execute(
        """
        SELECT *
        FROM blueprints
        WHERE project_id = ?
          AND (uploaded_at > ? OR (uploaded_at = ? AND id > ?))
        ORDER BY uploaded_at ASC, id ASC
        LIMIT 1
        """,
        (project_id, current["uploaded_at"], current["uploaded_at"], current["id"]),
    ).fetchone()


def refresh_blueprint_revision_compare(db, project_id, blueprint_id):
    compared_blueprint = db.execute(
        "SELECT * FROM blueprints WHERE id = ? AND project_id = ?",
        (blueprint_id, project_id),
    ).fetchone()
    if compared_blueprint is None:
        return None

    base_blueprint = _previous_blueprint(db, project_id, blueprint_id)
    if base_blueprint is None:
        db.execute("DELETE FROM blueprint_revision_compares WHERE compared_blueprint_id = ?", (blueprint_id,))
        return None

    base_analysis = get_latest_blueprint_analysis(db, base_blueprint["id"])
    compared_analysis = get_latest_blueprint_analysis(db, compared_blueprint["id"])
    comparison = compare_blueprint_analyses(base_blueprint, compared_blueprint, base_analysis, compared_analysis)
    timestamp = _now()
    existing = db.execute(
        "SELECT id FROM blueprint_revision_compares WHERE compared_blueprint_id = ?",
        (blueprint_id,),
    ).fetchone()

    payload = (
        project_id,
        base_blueprint["id"],
        compared_blueprint["id"],
        base_analysis["id"] if base_analysis else None,
        compared_analysis["id"] if compared_analysis else None,
        comparison["status"],
        comparison["summary"],
        json.dumps(comparison["metric_deltas"]),
        json.dumps(comparison["list_changes"]),
        json.dumps(comparison["page_role_changes"]),
        json.dumps(comparison["review_flags"]),
        timestamp,
    )

    if existing is None:
        db.execute(
            """
            INSERT INTO blueprint_revision_compares (
                project_id, base_blueprint_id, compared_blueprint_id, base_analysis_id,
                compared_analysis_id, status, summary, metric_deltas_json, list_changes_json,
                page_role_changes_json, review_flags_json, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (*payload, timestamp),
        )
    else:
        db.execute(
            """
            UPDATE blueprint_revision_compares
            SET project_id = ?, base_blueprint_id = ?, compared_blueprint_id = ?,
                base_analysis_id = ?, compared_analysis_id = ?, status = ?, summary = ?,
                metric_deltas_json = ?, list_changes_json = ?, page_role_changes_json = ?,
                review_flags_json = ?, updated_at = ?
            WHERE compared_blueprint_id = ?
            """,
            (*payload, blueprint_id),
        )
    return get_blueprint_revision_compare(db, blueprint_id)


def refresh_related_revision_compares(db, project_id, blueprint_id):
    results = []
    current = refresh_blueprint_revision_compare(db, project_id, blueprint_id)
    if current is not None:
        results.append(current)
    next_blueprint = _next_blueprint(db, project_id, blueprint_id)
    if next_blueprint is not None:
        next_compare = refresh_blueprint_revision_compare(db, project_id, next_blueprint["id"])
        if next_compare is not None:
            results.append(next_compare)
    return results


def get_blueprint_revision_compare(db, blueprint_id):
    row = db.execute(
        """
        SELECT rc.*,
            base.original_filename AS base_original_filename,
            base.version_label AS base_version_label,
            compared.original_filename AS compared_original_filename,
            compared.version_label AS compared_version_label
        FROM blueprint_revision_compares rc
        LEFT JOIN blueprints base ON base.id = rc.base_blueprint_id
        LEFT JOIN blueprints compared ON compared.id = rc.compared_blueprint_id
        WHERE rc.compared_blueprint_id = ?
        """,
        (blueprint_id,),
    ).fetchone()
    if row is None:
        return None
    payload = dict(row)
    payload["metric_deltas"] = _json_load(payload.get("metric_deltas_json"), {})
    payload["list_changes"] = _json_load(payload.get("list_changes_json"), {})
    payload["page_role_changes"] = _json_load(payload.get("page_role_changes_json"), {})
    payload["review_flags"] = _json_load(payload.get("review_flags_json"), [])
    return payload
