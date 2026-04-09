from datetime import UTC, datetime, timedelta
from functools import wraps
from pathlib import Path
from urllib.parse import urlparse

from flask import Blueprint, abort, current_app, flash, g, redirect, render_template, request, send_from_directory, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from ..db import get_db

bp = Blueprint("portal", __name__, url_prefix="/portal")


def _current_timestamp():
    return datetime.now(UTC).replace(tzinfo=None, microsecond=0).isoformat(sep=" ")


def _client_ip():
    forwarded_for = request.headers.get("X-Forwarded-For", "")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return request.remote_addr or "unknown"


def _is_safe_next_url(next_url):
    if not next_url:
        return False
    parsed = urlparse(next_url)
    return parsed.scheme == "" and parsed.netloc == "" and next_url.startswith("/portal")


def _fetch_portal_user(portal_user_id):
    return get_db().execute(
        """
        SELECT cpu.*, c.name AS customer_name, c.segment, c.service_address, c.primary_contact,
               c.phone AS customer_phone, c.email AS customer_email, c.trade_mix, c.status AS customer_status
        FROM customer_portal_users cpu
        JOIN customers c ON c.id = cpu.customer_id
        WHERE cpu.id = ?
        """,
        (portal_user_id,),
    ).fetchone()


def _record_login_attempt(email, ip_address, was_success):
    db = get_db()
    current_time = _current_timestamp()
    purge_before = (datetime.now(UTC).replace(tzinfo=None, microsecond=0) - timedelta(days=2)).isoformat(sep=" ")
    db.execute(
        """
        INSERT INTO auth_attempts (username, ip_address, attempted_at, was_success)
        VALUES (?, ?, ?, ?)
        """,
        (f"portal:{email or '<blank>'}", ip_address, current_time, 1 if was_success else 0),
    )
    db.execute("DELETE FROM auth_attempts WHERE attempted_at < ?", (purge_before,))


def _is_login_rate_limited(email, ip_address):
    window_start = (
        datetime.now(UTC) - timedelta(minutes=int(current_app.config.get("LOGIN_WINDOW_MINUTES", 15)))
    ).replace(tzinfo=None, microsecond=0).isoformat(sep=" ")
    attempts = get_db().execute(
        """
        SELECT COUNT(*) AS count
        FROM auth_attempts
        WHERE was_success = 0
          AND (
            username = ?
            OR ip_address = ?
          )
          AND attempted_at >= ?
        """,
        (f"portal:{email or '<blank>'}", ip_address, window_start),
    ).fetchone()["count"]
    return attempts >= int(current_app.config.get("LOGIN_MAX_FAILURES", 5))


@bp.before_app_request
def load_customer_portal_user():
    portal_user_id = session.get("customer_portal_user_id")
    g.customer_portal_user = _fetch_portal_user(portal_user_id) if portal_user_id is not None else None


@bp.app_context_processor
def inject_customer_portal_context():
    return {
        "current_customer_portal_user": g.get("customer_portal_user"),
    }


def customer_portal_login_required(view):
    @wraps(view)
    def wrapped_view(**kwargs):
        if g.get("customer_portal_user") is None:
            return redirect(url_for("portal.login", next=request.full_path if request.query_string else request.path))
        return view(**kwargs)

    return wrapped_view


@bp.get("/")
def index():
    if g.get("customer_portal_user") is not None:
        return redirect(url_for("portal.dashboard"))
    return redirect(url_for("portal.login"))


@bp.route("/login", methods=("GET", "POST"))
def login():
    if g.get("customer_portal_user") is not None:
        return redirect(url_for("portal.dashboard"))

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        ip_address = _client_ip()

        if _is_login_rate_limited(email, ip_address):
            flash("Too many failed sign-in attempts. Please wait a few minutes and try again.", "error")
            return render_template("portal/login.html")

        portal_user = get_db().execute(
            """
            SELECT id, email, password_hash, full_name, is_active
            FROM customer_portal_users
            WHERE email = ?
            """,
            (email,),
        ).fetchone()

        error = None
        if portal_user is None:
            error = "Email or password was incorrect."
        elif not portal_user["is_active"]:
            error = "Email or password was incorrect."
        elif not check_password_hash(portal_user["password_hash"], password):
            error = "Email or password was incorrect."

        if error is None:
            session.clear()
            session.permanent = True
            session["customer_portal_user_id"] = portal_user["id"]
            db = get_db()
            _record_login_attempt(email, ip_address, True)
            db.execute("UPDATE customer_portal_users SET last_login_at = ? WHERE id = ?", (_current_timestamp(), portal_user["id"]))
            db.commit()
            flash(f"Welcome, {portal_user['full_name']}.", "success")
            next_url = request.args.get("next")
            return redirect(next_url if _is_safe_next_url(next_url) else url_for("portal.dashboard"))

        _record_login_attempt(email, ip_address, False)
        get_db().commit()
        flash(error, "error")

    return render_template("portal/login.html")


@bp.post("/logout")
@customer_portal_login_required
def logout():
    session.clear()
    flash("You have been signed out of the customer portal.", "success")
    return redirect(url_for("portal.login"))


def _portal_dashboard_payload(customer_id):
    db = get_db()
    customer = db.execute("SELECT * FROM customers WHERE id = ?", (customer_id,)).fetchone()
    contacts = db.execute(
        """
        SELECT full_name, role_label, phone, email, is_primary
        FROM customer_contacts
        WHERE customer_id = ?
        ORDER BY is_primary DESC, full_name
        """,
        (customer_id,),
    ).fetchall()
    quotes = db.execute(
        """
        SELECT id, quote_number, option_name, description, status, amount, issue_date, expiration_date
        FROM quotes
        WHERE customer_id = ?
        ORDER BY id DESC
        """,
        (customer_id,),
    ).fetchall()
    jobs = db.execute(
        """
        SELECT id, name, scope, status, scheduled_start, crew_name, committed_revenue
        FROM jobs
        WHERE customer_id = ?
        ORDER BY scheduled_start DESC, id DESC
        """,
        (customer_id,),
    ).fetchall()
    deliveries = db.execute(
        """
        SELECT d.route_name, d.truck_name, d.eta, d.status, d.notes, j.name AS job_name
        FROM deliveries d
        JOIN jobs j ON j.id = d.job_id
        WHERE j.customer_id = ?
        ORDER BY d.eta DESC
        """,
        (customer_id,),
    ).fetchall()
    invoices = db.execute(
        """
        SELECT invoice_number, billing_type, application_number, status, amount, issued_date, due_date,
               retainage_held, remaining_balance
        FROM invoices
        WHERE customer_id = ?
        ORDER BY due_date DESC, id DESC
        """,
        (customer_id,),
    ).fetchall()
    documents = db.execute(
        """
        SELECT jd.id, jd.record_type, jd.title, jd.original_filename, jd.file_reference, jd.captured_at,
               jd.status, j.name AS job_name
        FROM job_documents jd
        JOIN jobs j ON j.id = jd.job_id
        WHERE jd.customer_id = ?
        ORDER BY jd.captured_at DESC, jd.id DESC
        LIMIT 12
        """,
        (customer_id,),
    ).fetchall()
    messages = db.execute(
        """
        SELECT id, submitted_at, subject, message_body, status, reviewed_at, reviewed_by
        FROM portal_messages
        WHERE customer_id = ?
        ORDER BY submitted_at DESC, id DESC
        LIMIT 10
        """,
        (customer_id,),
    ).fetchall()
    summary = {
        "quotes": db.execute("SELECT COUNT(*) AS count FROM quotes WHERE customer_id = ?", (customer_id,)).fetchone()["count"],
        "jobs": db.execute("SELECT COUNT(*) AS count FROM jobs WHERE customer_id = ?", (customer_id,)).fetchone()["count"],
        "invoices": db.execute("SELECT COUNT(*) AS count FROM invoices WHERE customer_id = ?", (customer_id,)).fetchone()["count"],
        "open_balance": db.execute(
            "SELECT COALESCE(SUM(remaining_balance), 0) AS total FROM invoices WHERE customer_id = ?",
            (customer_id,),
        ).fetchone()["total"],
    }
    return {
        "customer": customer,
        "contacts": contacts,
        "quotes": quotes,
        "jobs": jobs,
        "deliveries": deliveries,
        "invoices": invoices,
        "documents": documents,
        "messages": messages,
        "summary": summary,
    }


@bp.get("/dashboard")
@customer_portal_login_required
def dashboard():
    payload = _portal_dashboard_payload(g.customer_portal_user["customer_id"])
    return render_template("portal/dashboard.html", **payload)


@bp.post("/messages")
@customer_portal_login_required
def messages_create():
    subject = request.form.get("subject", "").strip()
    message_body = request.form.get("message_body", "").strip()
    if not subject:
        flash("Message subject is required.", "error")
        return redirect(url_for("portal.dashboard"))
    if not message_body:
        flash("Message body is required.", "error")
        return redirect(url_for("portal.dashboard"))

    db = get_db()
    db.execute(
        """
        INSERT INTO portal_messages (
            branch_id, customer_id, portal_user_id, submitted_at, subject, message_body,
            status, internal_notes, reviewed_at, reviewed_by
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            g.customer_portal_user["branch_id"],
            g.customer_portal_user["customer_id"],
            g.customer_portal_user["id"],
            _current_timestamp(),
            subject,
            message_body,
            "new",
            "",
            None,
            None,
        ),
    )
    db.execute(
        """
        INSERT INTO activity_feed (branch_id, customer_id, activity_date, activity_type, owner_name, title, details)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            g.customer_portal_user["branch_id"],
            g.customer_portal_user["customer_id"],
            _current_timestamp(),
            "Note",
            g.customer_portal_user["full_name"],
            f"Portal message: {subject}",
            message_body,
        ),
    )
    db.commit()
    flash("Message sent to the ConTech team.", "success")
    return redirect(url_for("portal.dashboard"))


@bp.route("/password", methods=("GET", "POST"))
@customer_portal_login_required
def password():
    if request.method == "POST":
        current_password = request.form.get("current_password", "")
        new_password = request.form.get("new_password", "")
        confirm_password = request.form.get("confirm_password", "")

        portal_user = get_db().execute(
            "SELECT password_hash FROM customer_portal_users WHERE id = ?",
            (g.customer_portal_user["id"],),
        ).fetchone()
        if not check_password_hash(portal_user["password_hash"], current_password):
            flash("Current password was incorrect.", "error")
        elif len(new_password) < 10:
            flash("New password must be at least 10 characters.", "error")
        elif new_password != confirm_password:
            flash("New password confirmation did not match.", "error")
        else:
            db = get_db()
            db.execute(
                "UPDATE customer_portal_users SET password_hash = ? WHERE id = ?",
                (generate_password_hash(new_password), g.customer_portal_user["id"]),
            )
            db.commit()
            flash("Password updated.", "success")
            return redirect(url_for("portal.dashboard"))

    return render_template("portal/password.html")


@bp.get("/documents/<int:document_id>/file")
@customer_portal_login_required
def document_file(document_id):
    document = get_db().execute(
        """
        SELECT id, customer_id, stored_file_name, original_filename
        FROM job_documents
        WHERE id = ? AND customer_id = ?
        """,
        (document_id, g.customer_portal_user["customer_id"]),
    ).fetchone()
    if document is None or not document["stored_file_name"]:
        abort(404)

    upload_dir = Path(current_app.config["JOB_DOCUMENT_UPLOAD_FOLDER"])
    file_path = upload_dir / document["stored_file_name"]
    if not file_path.exists():
        abort(404)

    response = send_from_directory(
        upload_dir,
        document["stored_file_name"],
        as_attachment=True,
        download_name=document["original_filename"] or document["stored_file_name"],
    )
    response.direct_passthrough = False
    return response
