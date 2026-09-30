from datetime import datetime

from cryptography.fernet import InvalidToken
from flask import Blueprint, abort, g, jsonify

from api_helpers import get_owned, json_list
from canvas_client import CanvasAuthError, CanvasClient
from models import IGNORED, KEPT, PENDING, Assignment, Course, Task, db
from security import authenticate, decrypt_pat

bp = Blueprint("canvas", __name__, url_prefix="/canvas")
bp.before_request(authenticate)  # every Canvas route requires a session


@bp.errorhandler(CanvasAuthError)
def canvas_token_required(_error):
    """
    The stored PAT is missing, unreadable, or was rejected (expired/revoked) by Canvas.
    Drop it and ask the frontend to collect a new one.

    Returns 403, not 401, on purpose: the session token is still valid. A 401 would
    look like "session expired, log in again" to the frontend, while this 403 with
    error="canvas_token_required" means "prompt the user for a new PAT".
    """
    db.session.rollback()
    g.user.encrypted_pat = None
    db.session.commit()
    return jsonify(
        error="canvas_token_required",
        message="Your Canvas token is missing, expired or revoked. Please submit a new one.",
    ), 403


def _canvas_client():
    if g.user.encrypted_pat is None:
        raise CanvasAuthError()
    try:
        return CanvasClient(decrypt_pat(g.user.encrypted_pat))
    except InvalidToken:  # ENCRYPTION_KEY changed, so the stored PAT is unreadable
        raise CanvasAuthError()


def _parse_canvas_time(value):
    return datetime.fromisoformat(value) if value else None


def _sync_courses(canvas_courses):
    """Records new courses as pending, refreshes names, and returns this term's courses."""
    known = {course.canvas_course_id: course for course in g.user.courses}
    synced = []
    for data in canvas_courses:
        course = known.get(data["id"])
        if course is None:
            course = Course(canvas_course_id=data["id"], status=PENDING)
            g.user.courses.append(course)
        course.name = data["name"].strip()
        synced.append(course)
    return synced


def _sync_assignments(course, canvas_assignments, known):
    """Records new assignments as pending and refreshes Canvas-sourced fields."""
    for data in canvas_assignments:
        assignment = known.get(data["id"])
        if assignment is None:
            assignment = Assignment(canvas_assignment_id=data["id"], status=PENDING)
            g.user.assignments.append(assignment)
        assignment.course = course
        assignment.name = data["name"]
        assignment.due_at = _parse_canvas_time(data.get("due_at"))
        assignment.html_url = data["html_url"]

        # Imported tasks follow Canvas's due date and course; user edits to
        # title and description are left alone. (The link is read from the assignment.)
        if assignment.task:
            assignment.task.due_at = assignment.due_at
            assignment.task.course = course


def _task_from(assignment):
    return Task(
        user_id=g.user.id,
        title=assignment.name,
        description="",
        due_at=assignment.due_at,
        completed=False,
        recurrence="none",
        course=assignment.course,
        assignment=assignment,
    )


def _apply_decisions(model):
    """Body: [{id, status: "kept" | "ignored"}, ...]. Returns the updated rows."""
    items = json_list()
    rows = get_owned(model, [item.get("id") for item in items])
    for item in items:
        if item.get("status") not in (KEPT, IGNORED):
            abort(400, f"status must be '{KEPT}' or '{IGNORED}'.")
        rows[item["id"]].status = item["status"]
    return list(rows.values())


@bp.post("/sync")
def sync():
    """
    Pulls this term's courses, then the assignments of every kept course.
    Returns everything still waiting on a keep/ignore decision.
    """
    client = _canvas_client()
    known_assignments = {a.canvas_assignment_id: a for a in g.user.assignments}
    for course in _sync_courses(client.get_active_courses()):
        if course.status == KEPT:
            assignments = client.get_assignments(course.canvas_course_id)
            _sync_assignments(course, assignments, known_assignments)
    db.session.commit()

    return jsonify(
        pending_courses=[c.to_dict() for c in g.user.courses if c.status == PENDING],
        pending_assignments=[
            a.to_dict()
            for a in g.user.assignments
            if a.status == PENDING and a.course.status == KEPT
        ],
    )


@bp.get("/courses")
def list_courses():
    return jsonify([course.to_dict() for course in g.user.courses])


@bp.get("/assignments")
def list_assignments():
    return jsonify([assignment.to_dict() for assignment in g.user.assignments])


@bp.patch("/courses")
def decide_courses():
    """Keep or ignore courses. Assignments of newly kept courses appear on the next sync."""
    courses = _apply_decisions(Course)
    db.session.commit()
    return jsonify([course.to_dict() for course in courses])


@bp.patch("/assignments")
def decide_assignments():
    """Keep or ignore assignments. Keeping one creates its task right away."""
    assignments = _apply_decisions(Assignment)
    for assignment in assignments:
        if assignment.status == KEPT and assignment.task is None:
            db.session.add(_task_from(assignment))
    db.session.commit()
    return jsonify([assignment.to_dict() for assignment in assignments])
