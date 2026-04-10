from datetime import UTC, datetime, timedelta
from functools import wraps
from pathlib import Path
from urllib.parse import urlparse
from uuid import uuid4

from flask import Blueprint, abort, current_app, flash, g, redirect, render_template, request, send_from_directory, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

from ..db import get_db
from ..invites import hash_invite_token

bp = Blueprint("portal", __name__, url_prefix="/portal")
CUSTOMER_LOGO_UPLOAD_EXTENSIONS = (".jpg", ".jpeg", ".png", ".webp", ".gif")


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


def _timestamp_is_expired(value):
    if not value:
        return True
    try:
        return datetime.fromisoformat(value) < datetime.now()
    except ValueError:
        return True


def _profile_form_data(form):
    return {
        "full_name": form.get("full_name", "").strip(),
        "email": form.get("email", "").strip().lower(),
        "role_label": form.get("role_label", "").strip(),
        "phone": form.get("phone", "").strip(),
        "company_name": form.get("company_name", "").strip(),
        "company_address": form.get("company_address", "").strip(),
        "password": form.get("password", ""),
        "confirm_password": form.get("confirm_password", ""),
    }


def _validate_profile_form(data, require_password=False, portal_user_id=None):
    errors = []
    if not data["full_name"]:
        errors.append("Your name is required.")
    if not data["email"] or "@" not in data["email"]:
        errors.append("A valid email address is required.")
    if not data["company_name"]:
        errors.append("Company or customer name is required for quote headers.")
    if not data["company_address"]:
        errors.append("Company or billing address is required for quote headers.")
    if require_password and len(data["password"]) < 10:
        errors.append("Password must be at least 10 characters.")
    if require_password and data["password"] != data["confirm_password"]:
        errors.append("Password confirmation did not match.")
    if data["email"]:
        query = "SELECT id FROM customer_portal_users WHERE email = ?"
        params = [data["email"]]
        if portal_user_id is not None:
            query += " AND id != ?"
            params.append(portal_user_id)
        existing = get_db().execute(query, params).fetchone()
        if existing:
            errors.append("That email is already tied to another customer portal user.")
    return errors


def _save_customer_logo(upload):
    if upload is None or not upload.filename:
        return None, None

    filename = secure_filename(upload.filename)
    extension = Path(filename).suffix.lower()
    if extension not in CUSTOMER_LOGO_UPLOAD_EXTENSIONS:
        return None, "Logo must be a JPG, PNG, WEBP, or GIF image."

    stored_file_name = f"{uuid4().hex}{extension}"
    upload_dir = Path(current_app.config["CUSTOMER_LOGO_UPLOAD_FOLDER"])
    upload_dir.mkdir(parents=True, exist_ok=True)
    upload.save(upload_dir / stored_file_name)
    return stored_file_name, None


def _fetch_invite(token):
    return get_db().execute(
        """
        SELECT cpu.*, c.name AS customer_name, c.company_name, c.company_address,
               c.company_logo_filename
        FROM customer_portal_users cpu
        JOIN customers c ON c.id = cpu.customer_id
        WHERE cpu.invite_token_hash = ? AND cpu.invite_status = ?
        """,
        (hash_invite_token(token), "pending"),
    ).fetchone()


def _fetch_portal_user(portal_user_id):
    return get_db().execute(
        """
        SELECT cpu.*, c.name AS customer_name, c.segment, c.service_address, c.primary_contact,
               c.phone AS customer_phone, c.email AS customer_email, c.trade_mix, c.status AS customer_status,
               c.company_name, c.company_address, c.company_logo_filename, c.company_profile_updated_at
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


@bp.route("/invite/<token>", methods=("GET", "POST"))
def invite(token):
    if g.get("customer_portal_user") is not None:
        return redirect(url_for("portal.dashboard"))

    invite_record = _fetch_invite(token)
    if invite_record is None or _timestamp_is_expired(invite_record["invite_expires_at"]):
        return render_template("portal/invite.html", invite_record=None, setup={}, token=token), 404

    setup = {
        "full_name": invite_record["full_name"],
        "email": invite_record["email"],
        "role_label": invite_record["role_label"] or "",
        "phone": invite_record["phone"] or "",
        "company_name": invite_record["company_name"] or invite_record["customer_name"],
        "company_address": invite_record["company_address"] or "",
    }

    if request.method == "POST":
        setup = _profile_form_data(request.form)
        errors = _validate_profile_form(setup, require_password=True, portal_user_id=invite_record["id"])
        logo_filename, logo_error = _save_customer_logo(request.files.get("company_logo"))
        if logo_error:
            errors.append(logo_error)

        if not errors:
            now = _current_timestamp()
            db = get_db()
            if logo_filename:
                db.execute(
                    """
                    UPDATE customers
                    SET company_name = ?, company_address = ?, company_logo_filename = ?,
                        company_profile_updated_at = ?
                    WHERE id = ?
                    """,
                    (
                        setup["company_name"],
                        setup["company_address"],
                        logo_filename,
                        now,
                        invite_record["customer_id"],
                    ),
                )
            else:
                db.execute(
                    """
                    UPDATE customers
                    SET company_name = ?, company_address = ?, company_profile_updated_at = ?
                    WHERE id = ?
                    """,
                    (
                        setup["company_name"],
                        setup["company_address"],
                        now,
                        invite_record["customer_id"],
                    ),
                )

            db.execute(
                """
                UPDATE customer_portal_users
                SET email = ?, full_name = ?, role_label = ?, phone = ?, password_hash = ?,
                    is_active = 1, invite_token_hash = NULL, invite_status = ?, invite_accepted_at = ?,
                    profile_completed_at = ?
                WHERE id = ?
                """,
                (
                    setup["email"],
                    setup["full_name"],
                    setup["role_label"],
                    setup["phone"],
                    generate_password_hash(setup["password"]),
                    "accepted",
                    now,
                    now,
                    invite_record["id"],
                ),
            )
            db.execute(
                """
                INSERT INTO activity_feed (branch_id, customer_id, activity_date, activity_type, owner_name, title, details)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    invite_record["branch_id"],
                    invite_record["customer_id"],
                    now,
                    "System",
                    setup["full_name"],
                    "Customer portal profile completed",
                    f"{setup['company_name']} profile information was added for quote headers.",
                ),
            )
            db.commit()
            session.clear()
            session.permanent = True
            session["customer_portal_user_id"] = invite_record["id"]
            flash("Your customer portal profile is ready.", "success")
            return redirect(url_for("portal.dashboard"))

        for error in errors:
            flash(error, "error")

    return render_template("portal/invite.html", invite_record=invite_record, setup=setup, token=token)


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


@bp.route("/profile", methods=("GET", "POST"))
@customer_portal_login_required
def profile():
    customer = get_db().execute("SELECT * FROM customers WHERE id = ?", (g.customer_portal_user["customer_id"],)).fetchone()
    profile_data = {
        "full_name": g.customer_portal_user["full_name"],
        "email": g.customer_portal_user["email"],
        "role_label": g.customer_portal_user["role_label"] or "",
        "phone": g.customer_portal_user["phone"] or "",
        "company_name": customer["company_name"] or customer["name"],
        "company_address": customer["company_address"] or customer["service_address"],
    }

    if request.method == "POST":
        profile_data = _profile_form_data(request.form)
        errors = _validate_profile_form(profile_data, portal_user_id=g.customer_portal_user["id"])
        logo_filename, logo_error = _save_customer_logo(request.files.get("company_logo"))
        if logo_error:
            errors.append(logo_error)

        if not errors:
            now = _current_timestamp()
            db = get_db()
            if logo_filename:
                db.execute(
                    """
                    UPDATE customers
                    SET company_name = ?, company_address = ?, company_logo_filename = ?,
                        company_profile_updated_at = ?
                    WHERE id = ?
                    """,
                    (
                        profile_data["company_name"],
                        profile_data["company_address"],
                        logo_filename,
                        now,
                        g.customer_portal_user["customer_id"],
                    ),
                )
            else:
                db.execute(
                    """
                    UPDATE customers
                    SET company_name = ?, company_address = ?, company_profile_updated_at = ?
                    WHERE id = ?
                    """,
                    (
                        profile_data["company_name"],
                        profile_data["company_address"],
                        now,
                        g.customer_portal_user["customer_id"],
                    ),
                )
            db.execute(
                """
                UPDATE customer_portal_users
                SET email = ?, full_name = ?, role_label = ?, phone = ?, profile_completed_at = COALESCE(profile_completed_at, ?)
                WHERE id = ?
                """,
                (
                    profile_data["email"],
                    profile_data["full_name"],
                    profile_data["role_label"],
                    profile_data["phone"],
                    now,
                    g.customer_portal_user["id"],
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
                    now,
                    "System",
                    profile_data["full_name"],
                    "Customer portal profile updated",
                    f"{profile_data['company_name']} quote header information was updated.",
                ),
            )
            db.commit()
            flash("Profile and quote header information updated.", "success")
            return redirect(url_for("portal.profile"))

        for error in errors:
            flash(error, "error")

    return render_template("portal/profile.html", customer=customer, profile=profile_data)


@bp.get("/company-logo")
@customer_portal_login_required
def company_logo():
    customer = get_db().execute(
        "SELECT company_logo_filename FROM customers WHERE id = ?",
        (g.customer_portal_user["customer_id"],),
    ).fetchone()
    if customer is None or not customer["company_logo_filename"]:
        abort(404)

    logo_dir = Path(current_app.config["CUSTOMER_LOGO_UPLOAD_FOLDER"])
    logo_path = logo_dir / customer["company_logo_filename"]
    if not logo_path.exists():
        abort(404)
    return send_from_directory(logo_dir, customer["company_logo_filename"])


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
