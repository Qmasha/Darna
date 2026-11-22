import os
import secrets
import sqlite3
import time
from functools import wraps
from pathlib import Path

from flask import Flask, render_template, jsonify, request, session, redirect, url_for
from werkzeug.security import generate_password_hash, check_password_hash

from facial_routes import register_facial_routes
from security_routes import register_security_routes

app = Flask(__name__)
# Set DARNA_SECRET_KEY in production; a random key means sessions reset on restart.
app.secret_key = os.environ.get("DARNA_SECRET_KEY") or secrets.token_hex(32)
app.config.update(SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Lax")

DATABASE = Path(__file__).with_name("darna.db")
FAILED_LOGINS = {}  # (ip, email) -> timestamps; simple brute-force lockout
MAX_FAILS, LOCK_SECONDS = 5, 300


def get_db():
    connection = sqlite3.connect(DATABASE)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def init_db():
    connection = get_db()
    connection.executescript(Path(__file__).with_name("schema.sql").read_text())
    connection.commit()
    connection.close()


def role_required(*allowed_roles):
    def decorator(function):
        @wraps(function)
        def wrapper(*args, **kwargs):
            if "user_id" not in session:
                return jsonify({"error": "Unauthorized"}), 401
            if session.get("user_role") not in allowed_roles:
                return jsonify({"error": "Permission denied"}), 403
            return function(*args, **kwargs)
        return wrapper
    return decorator


def create_default_user():
    connection = get_db()
    if connection.execute("SELECT id FROM users WHERE email = ?", ("admin@darna.com",)).fetchone() is None:
        connection.execute(
            "INSERT INTO users (name, email, password, role) VALUES (?, ?, ?, ?)",
            ("Darna Administrator", "admin@darna.com", generate_password_hash("Darna123!"), "Property Manager"))
        connection.commit()
    connection.close()


def _locked(key):
    now = time.time()
    FAILED_LOGINS[key] = [t for t in FAILED_LOGINS.get(key, []) if now - t < LOCK_SECONDS]
    return len(FAILED_LOGINS[key]) >= MAX_FAILS


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        key = (request.remote_addr, email)
        if _locked(key):
            return render_template("login.html", error="Too many failed attempts. Try again in 5 minutes."), 429
        connection = get_db()
        user = connection.execute("SELECT * FROM users WHERE lower(email) = ?", (email,)).fetchone()
        connection.close()
        if user and check_password_hash(user["password"], password):
            FAILED_LOGINS.pop(key, None)
            session.clear()
            session.update(user_id=user["id"], user_name=user["name"], user_role=user["role"])
            return redirect(url_for("dashboard"))
        FAILED_LOGINS.setdefault(key, []).append(time.time())
        return render_template("login.html", error="Invalid email or password."), 401
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/")
def dashboard():
    if "user_id" not in session:
        return redirect(url_for("login"))
    return render_template("dashboard.html", user_name=session["user_name"], role=session["user_role"])


@app.route("/api/dashboard")
def dashboard_data():
    if "user_id" not in session:
        return jsonify({"error": "Unauthorized"}), 401
    connection = get_db()
    q = lambda sql: [dict(r) for r in connection.execute(sql).fetchall()]
    data = {
        "cameras": q("SELECT * FROM cameras"),
        "locks": q("SELECT * FROM locks"),
        "members": q("SELECT * FROM members"),
        "activities": q("SELECT * FROM activities ORDER BY id DESC LIMIT 50"),
        "open_alerts": connection.execute("SELECT COUNT(*) FROM security_alerts WHERE status='Open'").fetchone()[0],
        "high_risk_assets": connection.execute(
            "SELECT COUNT(*) FROM maintenance_predictions WHERE risk_level IN ('High','Critical')").fetchone()[0],
    }
    connection.close()
    return jsonify(data)


@app.route("/api/locks/<int:lock_id>/toggle", methods=["POST"])
@role_required("Property Manager", "Security Staff")
def toggle_lock(lock_id):
    connection = get_db()
    lock = connection.execute("SELECT * FROM locks WHERE id = ?", (lock_id,)).fetchone()
    if lock is None:
        connection.close()
        return jsonify({"error": "Lock not found"}), 404
    new_status = 1 - lock["is_locked"]
    connection.execute("UPDATE locks SET is_locked = ? WHERE id = ?", (new_status, lock_id))
    connection.execute("INSERT INTO activities (title, description) VALUES (?, ?)",
                       (lock["name"], "Door was locked" if new_status else "Door was unlocked"))
    connection.commit()
    updated = dict(connection.execute("SELECT * FROM locks WHERE id = ?", (lock_id,)).fetchone())
    connection.close()
    return jsonify(updated)


def _camera_fields(data):
    name, location, schedule = (str(data.get(k, "")).strip() for k in ("name", "location", "schedule"))
    status = data.get("status", "Online")
    if not name or not location or not schedule:
        return None, "All fields are required"
    if status not in ("Online", "Offline"):
        return None, "Invalid camera status"
    return (name, location, status, schedule), None


@app.route("/api/cameras", methods=["POST"])
@role_required("Property Manager")
def add_camera():
    fields, error = _camera_fields(request.get_json(silent=True) or {})
    if error:
        return jsonify({"error": error}), 400
    connection = get_db()
    cursor = connection.execute("INSERT INTO cameras (name, location, status, schedule) VALUES (?, ?, ?, ?)", fields)
    connection.commit()
    camera = dict(connection.execute("SELECT * FROM cameras WHERE id = ?", (cursor.lastrowid,)).fetchone())
    connection.close()
    return jsonify(camera), 201


@app.route("/api/cameras/<int:camera_id>", methods=["PUT"])
@role_required("Property Manager")
def edit_camera(camera_id):
    fields, error = _camera_fields(request.get_json(silent=True) or {})
    if error:
        return jsonify({"error": error}), 400
    connection = get_db()
    cursor = connection.execute(
        "UPDATE cameras SET name = ?, location = ?, status = ?, schedule = ? WHERE id = ?", (*fields, camera_id))
    connection.commit()
    connection.close()
    if cursor.rowcount == 0:
        return jsonify({"error": "Camera not found"}), 404
    return jsonify({"message": "Camera updated successfully"})


@app.route("/api/cameras/<int:camera_id>", methods=["DELETE"])
@role_required("Property Manager")
def delete_camera(camera_id):
    connection = get_db()
    cursor = connection.execute("DELETE FROM cameras WHERE id = ?", (camera_id,))
    connection.commit()
    connection.close()
    if cursor.rowcount == 0:
        return jsonify({"error": "Camera not found"}), 404
    return jsonify({"message": "Camera deleted successfully"})


# Register feature modules (facial recognition, network monitoring, predictive maintenance)
register_facial_routes(app, get_db, role_required)
register_security_routes(app, get_db, role_required)

init_db()
create_default_user()

if __name__ == "__main__":
    app.run(debug=os.environ.get("FLASK_DEBUG") == "1")
