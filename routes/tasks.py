from datetime import datetime, timezone

from flask import Blueprint, abort, g, jsonify, request

from api_helpers import get_owned, json_list
from models import IGNORED, RECURRENCES, Course, Task, db
from recurrence import next_due_at
from security import authenticate

bp = Blueprint("tasks", __name__, url_prefix="/tasks")
bp.before_request(authenticate)  # every task route requires a session


def _parse_title(value):
    if not isinstance(value, str) or not value.strip():
        abort(400, "title must be a non-empty string.")
    return value.strip()


def _parse_description(value):
    if not isinstance(value, str):
        abort(400, "description must be a string.")
    return value


def _parse_due_at(value):
    """Accepts null or an ISO 8601 datetime. Datetimes without a timezone are taken as UTC."""
    if value is None:
        return None
    try:
        due_at = datetime.fromisoformat(value)
    except (TypeError, ValueError):
        abort(400, "due_at must be an ISO 8601 datetime or null.")
    return due_at if due_at.tzinfo else due_at.replace(tzinfo=timezone.utc)


def _parse_completed(value):
    if not isinstance(value, bool):
        abort(400, "completed must be a boolean.")
    return value


def _parse_recurrence(value):
    if value not in RECURRENCES:
        abort(400, f"recurrence must be one of {', '.join(RECURRENCES)}.")
    return value


def _parse_course_id(value):
    """Accepts null or the id of one of the user's own courses."""
    if value is not None:
        get_owned(Course, [value])
    return value


# Fields the client may set. Canvas-sourced links are set only by sync.
FIELD_PARSERS = {
    "title": _parse_title,
    "description": _parse_description,
    "due_at": _parse_due_at,
    "completed": _parse_completed,
    "recurrence": _parse_recurrence,
    "course_id": _parse_course_id,
}


def _apply_fields(task, data):
    for field, parse in FIELD_PARSERS.items():
        if field in data:
            setattr(task, field, parse(data[field]))

    if task.recurrence != "none" and task.due_at is None:
        abort(400, "A repeating task needs a due_at.")
    # Completing a repeating task rolls it forward instead of finishing it.
    if task.completed and task.recurrence != "none":
        task.due_at = next_due_at(task.due_at, task.recurrence)
        task.completed = False


@bp.get("")
def list_tasks():
    """All of the user's tasks, optionally filtered by ?course_id=<id> or ?course_id=none."""
    query = db.select(Task).where(Task.user_id == g.user.id)
    course_id = request.args.get("course_id")
    if course_id == "none":
        query = query.where(Task.course_id.is_(None))
    elif course_id is not None:
        if not course_id.isdigit():
            abort(400, "course_id must be an integer or 'none'.")
        query = query.where(Task.course_id == int(course_id))

    tasks = db.session.scalars(query.order_by(Task.due_at.asc().nulls_last(), Task.id))
    return jsonify([task.to_dict() for task in tasks])


@bp.post("")
def create_tasks():
    """Body: [{title, description?, due_at?, completed?, recurrence?, course_id?}, ...]"""
    tasks = []
    for data in json_list():
        if "title" not in data:
            abort(400, "title is required.")
        task = Task(user_id=g.user.id, description="", completed=False, recurrence="none")
        _apply_fields(task, data)
        tasks.append(task)

    db.session.add_all(tasks)
    db.session.commit()
    return jsonify([task.to_dict() for task in tasks]), 201


@bp.patch("")
def update_tasks():
    """Body: [{id, ...fields to change}, ...]"""
    items = json_list()
    tasks = get_owned(Task, [item.get("id") for item in items])
    for item in items:
        _apply_fields(tasks[item["id"]], item)

    db.session.commit()
    return jsonify([tasks[item["id"]].to_dict() for item in items])


@bp.delete("")
def delete_tasks():
    """Body: {ids: [...]}. Deleting a Canvas task ignores its assignment so sync won't re-offer it."""
    body = request.get_json(silent=True)
    ids = body.get("ids") if isinstance(body, dict) else None
    if not isinstance(ids, list):
        abort(400, "Request body must be {\"ids\": [...]}.")

    for task in get_owned(Task, ids).values():
        if task.assignment:
            task.assignment.status = IGNORED
        db.session.delete(task)

    db.session.commit()
    return "", 204
