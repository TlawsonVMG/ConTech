FIELD_PRIORITY_META = {
    "roof_system_suggestion": {"label": "Roof System"},
    "roof_area_squares": {"label": "Roof Area"},
    "roof_area_sqft": {"label": "Area Sq Ft"},
    "perimeter_feet": {"label": "Perimeter"},
    "ridge_feet": {"label": "Ridge"},
    "valley_feet": {"label": "Valley"},
    "eave_feet": {"label": "Eave"},
    "waste_pct": {"label": "Waste"},
    "drains_count": {"label": "Drains"},
    "penetrations_count": {"label": "Penetrations"},
    "parapet_feet": {"label": "Parapet"},
    "scale_text": {"label": "Detected Scale"},
    "flashing_types": {"label": "Flashing Types"},
}

RANKABLE_FIELDS = tuple(FIELD_PRIORITY_META.keys())


def _field_label(field_name):
    return FIELD_PRIORITY_META.get(field_name, {}).get("label", field_name.replace("_", " ").title())


def _roof_system_correction_counts(db, roof_system):
    rows = db.execute(
        """
        SELECT afc.field_name, COUNT(*) AS count
        FROM analysis_field_corrections afc
        JOIN blueprints b ON b.id = afc.blueprint_id
        JOIN projects p ON p.id = b.project_id
        WHERE p.roof_system = ?
        GROUP BY afc.field_name
        """,
        (roof_system,),
    ).fetchall()
    return {row["field_name"]: row["count"] for row in rows}


def _global_correction_counts(db):
    rows = db.execute(
        """
        SELECT field_name, COUNT(*) AS count
        FROM analysis_field_corrections
        GROUP BY field_name
        """
    ).fetchall()
    return {row["field_name"]: row["count"] for row in rows}


def _approved_takeoff_count(db, roof_system):
    row = db.execute(
        """
        SELECT COUNT(*) AS count
        FROM takeoff_runs
        WHERE system_type = ? AND status = 'Approved'
        """,
        (roof_system,),
    ).fetchone()
    return row["count"] if row else 0


def build_feedback_profile(db, roof_system):
    roof_system_corrections = _roof_system_correction_counts(db, roof_system)
    global_corrections = _global_correction_counts(db)
    approved_takeoffs = _approved_takeoff_count(db, roof_system)
    top_fields = sorted(
        roof_system_corrections.items(),
        key=lambda item: (-item[1], _field_label(item[0])),
    )
    return {
        "roof_system": roof_system,
        "approved_takeoffs": approved_takeoffs,
        "roof_system_corrections": roof_system_corrections,
        "global_corrections": global_corrections,
        "total_corrections": sum(roof_system_corrections.values()),
        "top_fields": [
            {
                "field_name": field_name,
                "label": _field_label(field_name),
                "count": count,
            }
            for field_name, count in top_fields[:4]
        ],
    }


def _revision_changed_fields(revision_compare):
    changed = set()
    if not revision_compare:
        return changed
    for field_name, metric in (revision_compare.get("metric_deltas") or {}).items():
        if metric.get("delta_value") not in (None, 0):
            changed.add(field_name)
    flashing_changes = (revision_compare.get("list_changes") or {}).get("flashing_types") or {}
    if flashing_changes.get("added") or flashing_changes.get("removed"):
        changed.add("flashing_types")
    for flag in revision_compare.get("review_flags") or []:
        if "Roof system changed" in flag:
            changed.add("roof_system_suggestion")
    return changed


def _missing_value(value):
    return value in (None, "", [])


def rank_feedback_priorities(db, roof_system, analysis, revision_compare=None, limit=5, feedback_profile=None):
    if not analysis:
        return []

    profile = feedback_profile or build_feedback_profile(db, roof_system)
    effective_data = analysis.get("effective_structured_data") or analysis.get("structured_data") or {}
    field_confidence = analysis.get("effective_field_confidence") or analysis.get("field_confidence") or {}
    changed_fields = _revision_changed_fields(revision_compare)
    ranked = []

    for field_name in RANKABLE_FIELDS:
        if field_name == "roof_system_suggestion":
            value = analysis.get("effective_roof_system_suggestion") or analysis.get("roof_system_suggestion")
        else:
            value = effective_data.get(field_name)

        confidence = float(field_confidence.get(field_name, 0.0))
        missing = _missing_value(value)
        system_corrections = profile["roof_system_corrections"].get(field_name, 0)
        global_corrections = profile["global_corrections"].get(field_name, 0)
        approved_takeoffs = max(1, profile["approved_takeoffs"])
        correction_rate = system_corrections / max(1, system_corrections + approved_takeoffs)

        score = 0.0
        reasons = []

        if missing:
            score += 0.38
            reasons.append("Missing from current AI analysis")

        low_confidence = max(0.0, 0.9 - confidence)
        if low_confidence > 0:
            score += low_confidence * 0.55
            if confidence < 0.7:
                reasons.append("Low AI confidence")

        if field_name in changed_fields:
            score += 0.24
            reasons.append("Changed from the prior blueprint revision")

        if system_corrections:
            score += min(0.34, (system_corrections * 0.12) + (correction_rate * 0.2))
            reasons.append(f"Frequently corrected on {roof_system} jobs")
        elif global_corrections >= 2:
            score += min(0.14, global_corrections * 0.03)
            reasons.append("Historically corrected across prior jobs")

        if (
            not missing
            and confidence >= 0.9
            and system_corrections == 0
            and field_name not in changed_fields
            and profile["approved_takeoffs"] >= 2
        ):
            score -= 0.08

        if score <= 0.09:
            continue

        band = "high" if score >= 0.72 else "medium" if score >= 0.42 else "low"
        ranked.append(
            {
                "field_name": field_name,
                "label": _field_label(field_name),
                "score": round(score, 2),
                "confidence": confidence,
                "band": band,
                "reasons": reasons[:3],
                "system_corrections": system_corrections,
            }
        )

    ranked.sort(key=lambda item: (-item["score"], item["label"]))
    return ranked[:limit]
