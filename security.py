import hashlib
import os
import secrets
from datetime import datetime, timedelta, timezone
from functools import wraps

from cryptography.fernet import Fernet
from flask import abort, g, request

from models import Session, db

SESSION_LIFETIME = timedelta(days=7)


def _fernet():
    # ENCRYPTION_KEY lives only in the environment, never in the database.
    return Fernet(os.environ["ENCRYPTION_KEY"])


def encrypt_pat(pat):
    return _fernet().encrypt(pat.encode()).decode()


def decrypt_pat(encrypted_pat):
    """Raises cryptography.fernet.InvalidToken if ENCRYPTION_KEY has changed."""
    return _fernet().decrypt(encrypted_pat.encode()).decode()


def hash_token(token):
    return hashlib.sha256(token.encode()).hexdigest()


def create_session(user):
    """Adds a new session for the user. Returns (raw token, expires_at); only the hash is stored."""
    token = secrets.token_urlsafe(32)
    expires_at = datetime.now(timezone.utc) + SESSION_LIFETIME
    db.session.add(Session(user=user, token_hash=hash_token(token), expires_at=expires_at))
    return token, expires_at


def _bearer_token():
    scheme, _, token = request.headers.get("Authorization", "").partition(" ")
    return token if scheme == "Bearer" and token else None


def authenticate():
    """Loads the session from the Bearer token into g.session and g.user, or aborts with 401."""
    token = _bearer_token()
    session = token and db.session.scalar(
        db.select(Session).where(
            Session.token_hash == hash_token(token),
            Session.expires_at > datetime.now(timezone.utc),
        )
    )
    if not session:
        abort(401, "Invalid or expired session.")
    g.session = session
    g.user = session.user


def login_required(view):
    """Per-route version of authenticate(); blueprints that are fully private use before_request."""

    @wraps(view)
    def wrapper(*args, **kwargs):
        authenticate()
        return view(*args, **kwargs)

    return wrapper
