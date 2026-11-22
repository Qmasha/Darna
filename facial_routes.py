import os
import tempfile
from pathlib import Path

from flask import Blueprint, jsonify, request, session, render_template

from face_service import (
    create_face_embedding,
    save_encrypted_embedding,
    load_encrypted_embedding,
    cosine_distance
)

facial_bp = Blueprint("facial", __name__)
TEMPLATE_DIR = Path(__file__).with_name("biometric_templates")
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png"}
MATCH_THRESHOLD = float(os.environ.get("DARNA_FACE_DISTANCE_THRESHOLD", "0.30"))

def _save_upload_temporarily(upload):
    suffix = Path(upload.filename or "").suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise ValueError("Please upload a JPG or PNG image.")
    handle = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    try:
        upload.save(handle.name)
    finally:
        handle.close()
    return Path(handle.name)


def _ai_error_message(error, action):
    """Turn an unexpected failure into a message that says what is actually wrong."""
    if isinstance(error, ImportError):
        return ("AI library missing (" + str(error) + "). Run: pip install deepface tf-keras "
                "- Python 3.12 is recommended; TensorFlow may not support newer versions.")
    return f"Facial {action} failed: {type(error).__name__}: {error}"

def register_facial_routes(app, get_db, role_required):
    @facial_bp.route("/facial-recognition")
    def facial_recognition_page():
        if "user_id" not in session:
            from flask import redirect, url_for
            return redirect(url_for("login"))
        connection = get_db()
        cameras = [dict(row) for row in connection.execute(
            "SELECT id, name, location FROM cameras"
        ).fetchall()]
        connection.close()
        return render_template("facial_recognition.html", cameras=cameras)

    @facial_bp.route("/api/facial/enroll", methods=["POST"])
    @role_required("Property Manager")
    def enroll_person():
        full_name = request.form.get("full_name", "").strip()
        access_role = request.form.get("access_role", "Resident").strip()
        consent = request.form.get("consent") == "yes"
        upload = request.files.get("face_image")

        if not full_name or not upload:
            return jsonify({"error": "Name and face image are required."}), 400
        if not consent:
            return jsonify({"error": "Explicit consent is required before enrollment."}), 400

        temp_path = None
        connection = get_db()
        try:
            temp_path = _save_upload_temporarily(upload)
            embedding = create_face_embedding(temp_path)

            cursor = connection.execute(
                """INSERT INTO authorized_persons
                   (full_name, access_role, is_authorized, consent_recorded)
                   VALUES (?, ?, 1, 1)""",
                (full_name, access_role)
            )
            person_id = cursor.lastrowid
            template_path = TEMPLATE_DIR / f"person_{person_id}.enc"
            save_encrypted_embedding(embedding, template_path)

            connection.execute(
                "UPDATE authorized_persons SET biometric_template_ref = ? WHERE id = ?",
                (str(template_path), person_id)
            )
            connection.execute(
                "INSERT INTO activities (title, description) VALUES (?, ?)",
                ("Facial Recognition", f"{full_name} was enrolled with consent")
            )
            connection.commit()
            return jsonify({
                "message": "Person enrolled successfully.",
                "person_id": person_id,
                "name": full_name
            }), 201
        except ValueError as error:
            connection.rollback()
            return jsonify({"error": str(error)}), 400
        except Exception as error:
            connection.rollback()
            app.logger.exception("Facial enrollment failed")
            return jsonify({"error": _ai_error_message(error, "enrollment")}), 500
        finally:
            connection.close()
            if temp_path and temp_path.exists():
                temp_path.unlink(missing_ok=True)

    @facial_bp.route("/api/facial/identify", methods=["POST"])
    @role_required("Property Manager", "Security Staff")
    def identify_person():
        upload = request.files.get("face_image")
        camera_id = request.form.get("camera_id", type=int)
        if not upload:
            return jsonify({"error": "Please provide a face image."}), 400

        temp_path = None
        connection = get_db()
        try:
            if camera_id is not None:
                camera = connection.execute(
                    "SELECT id FROM cameras WHERE id = ?", (camera_id,)
                ).fetchone()
                if camera is None:
                    return jsonify({"error": "Camera not found."}), 404

            temp_path = _save_upload_temporarily(upload)
            probe = create_face_embedding(temp_path)

            people = connection.execute(
                """SELECT id, full_name, is_authorized, biometric_template_ref
                   FROM authorized_persons
                   WHERE consent_recorded = 1
                     AND biometric_template_ref IS NOT NULL"""
            ).fetchall()

            best_person = None
            best_distance = 1.0

            for person in people:
                template_path = Path(person["biometric_template_ref"])
                if not template_path.is_file():
                    continue
                try:
                    stored_embedding = load_encrypted_embedding(template_path)
                    distance = cosine_distance(probe, stored_embedding)
                except Exception:
                    app.logger.exception("Could not read an enrolled biometric template")
                    continue

                if distance < best_distance:
                    best_distance = distance
                    best_person = person

            matched = best_person is not None and best_distance <= MATCH_THRESHOLD

            if matched and int(best_person["is_authorized"]) == 1:
                event_type = "authorized"
                person_id = best_person["id"]
                person_name = best_person["full_name"]
                message = f"Possible authorized match: {person_name}"
            elif matched:
                event_type = "unauthorized"
                person_id = best_person["id"]
                person_name = best_person["full_name"]
                message = f"Recognized person is not authorized: {person_name}"
            else:
                event_type = "unrecognized"
                person_id = None
                person_name = None
                message = "No enrolled face matched."

            similarity_score = max(0.0, min(1.0, 1.0 - best_distance))
            connection.execute(
                """INSERT INTO access_events
                   (person_id, camera_id, event_type, confidence, notes)
                   VALUES (?, ?, ?, ?, ?)""",
                (person_id, camera_id, event_type, similarity_score, message)
            )
            connection.execute(
                "INSERT INTO activities (title, description) VALUES (?, ?)",
                ("Facial Recognition", message)
            )
            connection.commit()

            return jsonify({
                "event_type": event_type,
                "person_name": person_name,
                "similarity": round(similarity_score, 4),
                "message": message,
                "manual_review_required": True
            })
        except ValueError as error:
            connection.rollback()
            return jsonify({"error": str(error)}), 400
        except Exception as error:
            connection.rollback()
            app.logger.exception("Facial identification failed")
            return jsonify({"error": _ai_error_message(error, "identification")}), 500
        finally:
            connection.close()
            if temp_path and temp_path.exists():
                temp_path.unlink(missing_ok=True)

    app.register_blueprint(facial_bp)
