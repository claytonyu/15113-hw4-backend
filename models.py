from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

# Course and assignment import decisions.
PENDING = "pending"  # seen on Canvas, user hasn't decided yet
KEPT = "kept"
IGNORED = "ignored"

RECURRENCES = ("none", "daily", "weekly", "monthly")


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    # Always taken from Canvas's /users/self response, never from client input.
    canvas_user_id = db.Column(db.BigInteger, unique=True, nullable=False)
    name = db.Column(db.String, nullable=False)
    # Fernet-encrypted PAT. None after disconnecting or when Canvas rejects it.
    encrypted_pat = db.Column(db.Text, nullable=True)

    # Deleting a user deletes all of their data (DELETE /auth/account).
    sessions = db.relationship("Session", back_populates="user", cascade="all, delete-orphan")
    tasks = db.relationship("Task", cascade="all, delete-orphan")
    assignments = db.relationship("Assignment", cascade="all, delete-orphan")
    courses = db.relationship("Course", cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "canvas_user_id": self.canvas_user_id,
            "name": self.name,
            "canvas_connected": self.encrypted_pat is not None,
        }


class Session(db.Model):
    __tablename__ = "sessions"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    # SHA-256 hex digest; the raw token is only ever held by the client.
    token_hash = db.Column(db.String(64), unique=True, nullable=False)
    expires_at = db.Column(db.DateTime(timezone=True), nullable=False)

    user = db.relationship("User", back_populates="sessions")


class Course(db.Model):
    __tablename__ = "courses"
    __table_args__ = (db.UniqueConstraint("user_id", "canvas_course_id"),)

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    canvas_course_id = db.Column(db.BigInteger, nullable=False)
    name = db.Column(db.String, nullable=False)
    status = db.Column(db.String, nullable=False, default=PENDING)

    def to_dict(self):
        return {"id": self.id, "name": self.name, "status": self.status}


class Assignment(db.Model):
    __tablename__ = "assignments"
    __table_args__ = (db.UniqueConstraint("user_id", "canvas_assignment_id"),)

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    course_id = db.Column(db.Integer, db.ForeignKey("courses.id"), nullable=False)
    canvas_assignment_id = db.Column(db.BigInteger, nullable=False)
    name = db.Column(db.String, nullable=False)
    due_at = db.Column(db.DateTime(timezone=True), nullable=True)
    html_url = db.Column(db.String, nullable=False)
    status = db.Column(db.String, nullable=False, default=PENDING)

    course = db.relationship("Course")
    task = db.relationship("Task", back_populates="assignment", uselist=False)

    def to_dict(self):
        return {
            "id": self.id,
            "course_id": self.course_id,
            "name": self.name,
            "due_at": self.due_at.isoformat() if self.due_at else None,
            "html_url": self.html_url,
            "status": self.status,
        }


class Task(db.Model):
    __tablename__ = "tasks"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    title = db.Column(db.String, nullable=False)
    description = db.Column(db.Text, nullable=False, default="")
    due_at = db.Column(db.DateTime(timezone=True), nullable=True)
    completed = db.Column(db.Boolean, nullable=False, default=False)
    recurrence = db.Column(db.String, nullable=False, default="none")
    # Set for Canvas-imported tasks, and optionally for manual ones.
    course_id = db.Column(db.Integer, db.ForeignKey("courses.id"), nullable=True)
    # Set only for Canvas-imported tasks.
    assignment_id = db.Column(
        db.Integer, db.ForeignKey("assignments.id"), unique=True, nullable=True
    )

    course = db.relationship("Course")
    assignment = db.relationship("Assignment", back_populates="task")

    def to_dict(self):
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "due_at": self.due_at.isoformat() if self.due_at else None,
            "completed": self.completed,
            "recurrence": self.recurrence,
            "course_id": self.course_id,
            "html_url": self.assignment.html_url if self.assignment else None,
        }
