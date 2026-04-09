from datetime import datetime

from flask import Blueprint, flash, g, redirect, render_template, request, url_for

from ..auth import roles_required
from ..db import get_db

bp = Blueprint("feedback", __name__)

FEEDBACK_STATUSES = ("new", "in_review", "closed")


def _feedback_form_data(form):
    return {
        "submitter_name": form.get("submitter_name", "").strip(),
        "submitter_email": form.get("submitter_email", "").strip(),
        "company_name": form.get("company_name", "").strip(),
        "role_label": form.get("role_label", "").strip(),
        "page_url": form.get("page_url", "").strip(),
        "summary": form.get("summary", "").strip(),
        "details": form.get("details", "").strip(),
        "rating": form.get("rating", "").strip(),
    }


def _validate_feedback_form(data):
    errors = []
    if not data["submitter_name"]:
        errors.append("Your name is required.")
    if not data["submitter_email"]:
        errors.append("Your email is required.")
    if not data["summary"]:
        errors.append("A short summary is required.")
    if not data["details"]:
        errors.append("Please tell us what worked or what felt rough.")
    if data["rating"]:
        try:
            rating_value = int(data["rating"])
        except ValueError:
            errors.append("Rating must be a whole number between 1 and 5.")
        else:
            if rating_value < 1 or rating_value > 5:
                errors.append("Rating must be between 1 and 5.")
    return errors


@bp.route("/pilot-feedback", methods=("GET", "POST"))
def public_feedback():
    data = _feedback_form_data(request.form) if request.method == "POST" else {
        "submitter_name": "",
        "submitter_email": "",
        "company_name": "",
        "role_label": "",
        "page_url": "",
        "summary": "",
        "details": "",
        "rating": "",
    }
    submitted = False

    if request.method == "POST":
        errors = _validate_feedback_form(data)
        if not errors:
            rating_value = int(data["rating"]) if data["rating"] else None
            db = get_db()
            db.execute(
                """
                INSERT INTO feedback_submissions (
                    submitted_at, submitter_name, submitter_email, company_name, role_label,
                    page_url, summary, details, rating, status, internal_notes, reviewed_at, reviewed_by
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    datetime.now().strftime("%Y-%m-%d %H:%M"),
                    data["submitter_name"],
                    data["submitter_email"],
                    data["company_name"],
                    data["role_label"],
                    data["page_url"],
                    data["summary"],
                    data["details"],
                    rating_value,
                    "new",
                    "",
                    None,
                    None,
                ),
            )
            db.commit()
            submitted = True
            data = {
                "submitter_name": "",
                "submitter_email": "",
                "company_name": "",
                "role_label": "",
                "page_url": "",
                "summary": "",
                "details": "",
                "rating": "",
            }
        else:
            for error in errors:
                flash(error, "error")

    return render_template("feedback/public.html", feedback=data, submitted=submitted)


@bp.get("/feedback/inbox")
@roles_required("admin", "sales", "dispatch", "inventory", "accounting")
def feedback_inbox():
    status = request.args.get("status", "").strip()
    params = []
    sql = """
        SELECT *
        FROM feedback_submissions
    """
    if status:
        sql += " WHERE status = ?"
        params.append(status)
    sql += " ORDER BY submitted_at DESC, id DESC"
    submissions = get_db().execute(sql, params).fetchall()
    summary = {
        "new": get_db().execute("SELECT COUNT(*) AS count FROM feedback_submissions WHERE status = 'new'").fetchone()["count"],
        "in_review": get_db().execute(
            "SELECT COUNT(*) AS count FROM feedback_submissions WHERE status = 'in_review'"
        ).fetchone()["count"],
        "closed": get_db().execute("SELECT COUNT(*) AS count FROM feedback_submissions WHERE status = 'closed'").fetchone()["count"],
    }
    return render_template(
        "feedback/inbox.html",
        submissions=submissions,
        status_options=FEEDBACK_STATUSES,
        selected_status=status,
        summary=summary,
    )


@bp.post("/feedback/<int:submission_id>/status")
@roles_required("admin", "sales", "dispatch", "inventory", "accounting")
def feedback_update_status(submission_id):
    submission = get_db().execute(
        "SELECT id FROM feedback_submissions WHERE id = ?",
        (submission_id,),
    ).fetchone()
    if submission is None:
        return redirect(url_for("feedback.feedback_inbox"))

    status = request.form.get("status", "new").strip()
    internal_notes = request.form.get("internal_notes", "").strip()
    if status not in FEEDBACK_STATUSES:
        flash("Feedback status is invalid.", "error")
        return redirect(url_for("feedback.feedback_inbox"))

    db = get_db()
    db.execute(
        """
        UPDATE feedback_submissions
        SET status = ?, internal_notes = ?, reviewed_at = ?, reviewed_by = ?
        WHERE id = ?
        """,
        (
            status,
            internal_notes,
            datetime.now().strftime("%Y-%m-%d %H:%M"),
            g.user["full_name"] if g.get("user") else "System",
            submission_id,
        ),
    )
    db.commit()
    flash("Feedback status updated.", "success")
    return redirect(url_for("feedback.feedback_inbox"))
