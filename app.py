import os

from flask import Flask, jsonify, request
from flask_cors import CORS

app = Flask(__name__)
# Allow cross-origin requests so a separately hosted frontend can call this API.
# Tighten this to your frontend's URL later, e.g. CORS(app, origins=["https://your-site.com"])
CORS(app)


@app.get("/")
def index():
    return jsonify(message="Hello from Flask on Render!")


@app.get("/health")
def health():
    return jsonify(status="ok")


@app.post("/echo")
def echo():
    # Returns whatever JSON body was sent, handy for testing POST requests.
    data = request.get_json(silent=True)
    if data is None:
        return jsonify(error="Request body must be JSON"), 400
    return jsonify(received=data)


if __name__ == "__main__":
    # Local development only. Render runs the app with gunicorn instead.
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port, debug=True)
