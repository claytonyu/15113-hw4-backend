from flask import abort, g, request

from models import db


def json_list():
    """Returns the request body, which bulk endpoints require to be a JSON list of objects."""
    body = request.get_json(silent=True)
    if not isinstance(body, list) or not all(isinstance(item, dict) for item in body):
        abort(400, "Request body must be a JSON list of objects.")
    return body


def get_owned(model, ids):
    """
    Loads the current user's rows with these ids as {id: row}.
    Aborts with 404 if any id is missing or belongs to someone else, so bulk
    requests are all-or-nothing and never touch another user's data.
    """
    if not all(type(i) is int for i in ids):
        abort(400, "Every id must be an integer.")
    rows = db.session.scalars(
        db.select(model).where(model.user_id == g.user.id, model.id.in_(ids))
    ).all()
    if len(rows) != len(set(ids)):
        abort(404, f"One or more {model.__tablename__} were not found.")
    return {row.id: row for row in rows}
