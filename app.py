import os

try:
    # Local development only: python-dotenv isn't installed on Render,
    # where the environment variables come from the dashboard.
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

import requests
from flask import Flask, jsonify
from flask_cors import CORS
from werkzeug.exceptions import HTTPException

from models import db
from routes import auth, canvas, tasks


def _database_url():
    # Render hands out postgresql:// URLs; SQLAlchemy needs to be told to use psycopg 3.
    return os.environ["DATABASE_URL"].replace("postgresql://", "postgresql+psycopg://", 1)


def _allowed_origins():
    # Scheme + host only, e.g. https://<username>.github.io. Unset means no cross-origin access.
    frontend_url = os.environ.get("FRONTEND_URL")
    return [frontend_url.rstrip("/")] if frontend_url else []


app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = _database_url()
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_pre_ping": True,  # Render closes idle connections
    # Return timestamptz values in UTC so responses and recurrence math don't depend on the DB's TimeZone.
    "connect_args": {"options": "-c timezone=UTC"},
}
CORS(app, origins=_allowed_origins())

db.init_app(app)
app.register_blueprint(auth.bp)
app.register_blueprint(tasks.bp)
app.register_blueprint(canvas.bp)

# Free Render services have no shell or pre-deploy step, so tables are created at startup.
with app.app_context():
    db.create_all()


@app.errorhandler(HTTPException)
def http_error(error):
    """Return every abort() as JSON so the frontend can read the message."""
    return jsonify(error=error.description), error.code


@app.errorhandler(requests.RequestException)
def canvas_unavailable(_error):
    return jsonify(error="Could not reach Canvas. Please try again later."), 502

@app.get("/")
def home():
    return "The Canvas To-Do app is running!"

@app.get("/health")
def health():
    return jsonify(status="ok")


if __name__ == "__main__":
    # Local development only. Render runs the app with gunicorn instead.
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port, debug=True)
