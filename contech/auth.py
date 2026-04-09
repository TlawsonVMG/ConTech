from datetime import UTC, datetime, timedelta
from functools import wraps
from urllib.parse import urlparse

from flask import (
    Blueprint,
    abort,
    current_app,
    flash,
    g,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from werkzeug.security import check_password_hash

from .db import get_db

bp = Blueprint("auth", __name__)


def _fetch_user(user_id):
    return get_db().execute(
        """
        SELECT id, branch_id, username, full_name, role_name, is_active
        FROM users
        WHERE id = ?
        """,
        (user_id,),
    ).fetchone()


def _client_ip():
    forwarded_for = request.headers.get("X-Forwarded-For", "")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return request.remote_addr or "unknown"


def _record_login_attempt(username, ip_address, was_success):
    db = get_db()
    current_time = datetime.now(UTC).replace(tzinfo=None, microsecond=0)
    attempted_at = current_time.isoformat(sep=" ")
    purge_before = (current_time - timedelta(days=2)).isoformat(sep=" ")
    db.execute(
        """
        INSERT INTO auth_attempts (username, ip_address, attempted_at, was_success)
        VALUES (?, ?, ?, ?)
        """,
        (username or "<blank>", ip_address, attempted_at, 1 if was_success else 0),
    )
    db.execute(
        """
        DELETE FROM auth_attempts
        WHERE attempted_at < ?
        """,
        (purge_before,),
    )


def _is_login_rate_limited(username, ip_address):
    window_start = (
        datetime.now(UTC) - timedelta(minutes=int(current_app.config.get("LOGIN_WINDOW_MINUTES", 15)))
    ).replace(microsecond=0).isoformat(sep=" ")
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
        (
            username or "<blank>",
            ip_address,
            window_start,
        ),
    ).fetchone()["count"]
    return attempts >= int(current_app.config.get("LOGIN_MAX_FAILURES", 5))


def _is_safe_next_url(next_url):
    if not next_url:
        return False
    parsed = urlparse(next_url)
    return parsed.scheme == "" and parsed.netloc == "" and next_url.startswith("/")


@bp.before_app_request
def load_logged_in_user():
    user_id = session.get("user_id")
    g.user = _fetch_user(user_id) if user_id is not None else None


@bp.app_context_processor
def inject_auth_context():
    return {
        "current_user": g.get("user"),
    }


def login_required(view):
    @wraps(view)
    def wrapped_view(**kwargs):
        if g.get("user") is None:
            return redirect(url_for("auth.login", next=request.full_path if request.query_string else request.path))
        return view(**kwargs)

    return wrapped_view


def roles_required(*roles):
    def decorator(view):
        @login_required
        @wraps(view)
        def wrapped_view(**kwargs):
            if g.user["role_name"] not in roles:
                abort(403)
            return view(**kwargs)

        return wrapped_view

    return decorator


@bp.route("/login", methods=("GET", "POST"))
def login():
    if g.get("user") is not None:
        return redirect(url_for("crm.dashboard"))

    if request.method == "POST":
        username = request.form.get("username", "").strip().lower()
        password = request.form.get("password", "")
        ip_address = _client_ip()

        if _is_login_rate_limited(username, ip_address):
            flash("Too many failed sign-in attempts. Please wait a few minutes and try again.", "error")
            return render_template("auth/login.html")

        user = get_db().execute(
            """
            SELECT id, username, password_hash, full_name, role_name, is_active
            FROM users
            WHERE username = ?
            """,
            (username,),
        ).fetchone()

        error = None
        if user is None:
            error = "No account matched that username."
        elif not user["is_active"]:
            error = "That account is inactive."
        elif not check_password_hash(user["password_hash"], password):
            error = "Password was incorrect."

        if error is None:
            session.clear()
            session.permanent = True
            session["user_id"] = user["id"]
            _record_login_attempt(username, ip_address, True)
            get_db().commit()
            flash(f"Welcome back, {user['full_name']}.", "success")
            next_url = request.args.get("next")
            return redirect(next_url if _is_safe_next_url(next_url) else url_for("crm.dashboard"))

        _record_login_attempt(username, ip_address, False)
        get_db().commit()
        flash(error, "error")

    return render_template("auth/login.html")


@bp.post("/logout")
@login_required
def logout():
    session.clear()
    flash("You have been signed out.", "success")
    return redirect(url_for("auth.login"))
