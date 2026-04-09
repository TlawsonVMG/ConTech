import secrets
from datetime import timedelta

from flask import abort, current_app, request, session
from markupsafe import Markup


UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


def generate_csrf_token():
    token = session.get("_csrf_token")
    if token is None:
        token = secrets.token_urlsafe(32)
        session["_csrf_token"] = token
    return token


def csrf_input():
    token = generate_csrf_token()
    return Markup(f'<input type="hidden" name="csrf_token" value="{token}" />')


def _csrf_is_enabled():
    return current_app.config.get("CSRF_ENABLED", True) and not current_app.config.get("TESTING", False)


def _verify_csrf():
    if request.method not in UNSAFE_METHODS or not _csrf_is_enabled():
        return

    token = request.form.get("csrf_token") or request.headers.get("X-CSRFToken")
    if not token or token != session.get("_csrf_token"):
        abort(400, description="CSRF validation failed.")


def init_app(app):
    app.config.setdefault("CSRF_ENABLED", True)
    app.config.setdefault("SESSION_COOKIE_HTTPONLY", True)
    app.config.setdefault("SESSION_COOKIE_SAMESITE", "Lax")
    app.config.setdefault("PERMANENT_SESSION_LIFETIME", timedelta(hours=8))

    @app.before_request
    def enforce_csrf():
        _verify_csrf()

    @app.context_processor
    def inject_csrf():
        return {
            "csrf_token": generate_csrf_token,
            "csrf_input": csrf_input,
        }
