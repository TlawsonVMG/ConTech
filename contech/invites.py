import hashlib
import secrets


def generate_invite_token():
    return secrets.token_urlsafe(32)


def hash_invite_token(token):
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
