from flask import Blueprint, abort, g, jsonify, request

from canvas_client import CanvasAuthError, CanvasClient
from models import Session, User, db
from security import create_session, encrypt_pat, login_required

bp = Blueprint("auth", __name__, url_prefix="/auth")


def _find_or_create_user(canvas_user_id):
    user = db.session.scalar(db.select(User).where(User.canvas_user_id == canvas_user_id))
    if user is None:
        user = User(canvas_user_id=canvas_user_id)
        db.session.add(user)
    return user


@bp.post("/token")
def login():
    """Exchanges a Canvas PAT for a session token. The PAT is never sent back."""
    body = request.get_json(silent=True) or {}
    pat = body.get("canvas_token")
    if not isinstance(pat, str) or not pat.strip():
        abort(400, "canvas_token is required.")
    pat = pat.strip()

    try:
        profile = CanvasClient(pat).get_self()
    except CanvasAuthError:
        abort(401, "Canvas rejected this token.")

    # The user's identity comes only from Canvas, never from the request body.
    user = _find_or_create_user(profile["id"])
    user.name = profile["name"]
    user.encrypted_pat = encrypt_pat(pat)  # replaces any previously stored PAT
    token, expires_at = create_session(user)
    db.session.commit()
    return jsonify(
        session_token=token, expires_at=expires_at.isoformat(), user=user.to_dict()
    )


@bp.get("/me")
@login_required
def me():
    return jsonify(g.user.to_dict())


@bp.post("/logout")
@login_required
def logout():
    """Ends only this session. The stored PAT and all data stay."""
    db.session.delete(g.session)
    db.session.commit()
    return "", 204


@bp.delete("/canvas")
@login_required
def disconnect_canvas():
    """
    Deletes the stored PAT and every session; tasks, courses and ignore decisions stay.
    This does not revoke the PAT in Canvas; the frontend should tell the user to do that.
    """
    g.user.encrypted_pat = None
    db.session.execute(db.delete(Session).where(Session.user_id == g.user.id))
    db.session.commit()
    return "", 204


@bp.delete("/account")
@login_required
def delete_account():
    """Deletes the user and, via cascades, all of their data."""
    db.session.delete(g.user)
    db.session.commit()
    return "", 204
