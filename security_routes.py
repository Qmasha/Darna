from datetime import date
from flask import Blueprint, jsonify, request
import network_service as ns
import maintenance_service as ms

bp = Blueprint("security", __name__)
STAFF = ("Property Manager", "Security Staff")
MANAGER = ("Property Manager",)
ALL = ("Property Manager", "Security Staff", "Resident")


def register_security_routes(app, get_db, role_required):
    def rows(sql, args=()):
        c = get_db()
        try:
            return [dict(r) for r in c.execute(sql, args).fetchall()]
        finally:
            c.close()

    def write(fn):
        c = get_db()
        try:
            out = fn(c)
            c.commit()
            return out
        finally:
            c.close()

    @bp.route("/api/network/devices")
    @role_required(*STAFF)
    def devices():
        return jsonify(rows("SELECT *, last_seen >= datetime('now','-15 minutes') AS online "
                            "FROM network_devices ORDER BY last_seen DESC"))

    @bp.route("/api/network/alerts")
    @role_required(*STAFF)
    def alerts():
        return jsonify(rows("SELECT a.*, d.device_name FROM security_alerts a LEFT JOIN network_devices d "
                            "ON d.id=a.device_id ORDER BY (a.status='Open') DESC, a.id DESC LIMIT 100"))

    @bp.route("/api/network/scan", methods=["POST"])
    @role_required(*STAFF)
    def scan():
        data = request.get_json(silent=True) or {}
        observed = ns.demo_scan() if data.get("demo") else data.get("devices")
        if not isinstance(observed, list):
            return jsonify({"error": "Provide a 'devices' list or set demo=true."}), 400
        seen, new = write(lambda c: ns.process_scan(c, observed))
        return jsonify({"devices_seen": seen, "new_alerts": new})

    @bp.route("/api/network/devices/<int:did>/trust", methods=["POST"])
    @role_required(*MANAGER)
    def trust(did):
        def f(c):
            cur = c.execute("UPDATE network_devices SET status='Trusted' WHERE id=?", (did,))
            if cur.rowcount:
                c.execute("UPDATE security_alerts SET status='Resolved', resolved_at=CURRENT_TIMESTAMP "
                          "WHERE device_id=? AND alert_type IN ('Unknown Device','IP/MAC Conflict') AND status='Open'", (did,))
            return cur.rowcount
        return (jsonify({"message": "Device trusted"}) if write(f) else (jsonify({"error": "Device not found"}), 404))

    @bp.route("/api/network/alerts/<int:aid>/resolve", methods=["POST"])
    @role_required(*STAFF)
    def resolve(aid):
        n = write(lambda c: c.execute("UPDATE security_alerts SET status='Resolved', resolved_at=CURRENT_TIMESTAMP "
                                      "WHERE id=?", (aid,)).rowcount)
        return jsonify({"message": "Resolved"}) if n else (jsonify({"error": "Alert not found"}), 404)

    @bp.route("/api/maintenance/predictions")
    @role_required(*ALL)
    def predictions():
        return jsonify(rows("""SELECT p.*, a.asset_name, a.asset_type, a.location, a.last_maintenance_date
            FROM maintenance_predictions p JOIN maintenance_assets a ON a.id=p.asset_id
            ORDER BY CASE p.risk_level WHEN 'Critical' THEN 0 WHEN 'High' THEN 1 WHEN 'Medium' THEN 2 ELSE 3 END,
            p.predicted_failure_date"""))

    @bp.route("/api/maintenance/assets", methods=["GET", "POST"])
    @role_required(*ALL)
    def assets():
        if request.method == "GET":
            return jsonify(rows("SELECT * FROM maintenance_assets ORDER BY asset_name"))
        if session_role() not in MANAGER:
            return jsonify({"error": "Permission denied"}), 403
        d = request.get_json(silent=True) or {}
        name, typ, loc = (str(d.get(k, "")).strip() for k in ("asset_name", "asset_type", "location"))
        if not name or not typ or not loc:
            return jsonify({"error": "Name, type and location are required"}), 400
        life = d.get("expected_lifespan_months")
        write(lambda c: c.execute(
            "INSERT INTO maintenance_assets (asset_name, asset_type, location, installation_date, "
            "last_maintenance_date, expected_lifespan_months) VALUES (?,?,?,?,?,?)",
            (name, typ, loc, d.get("installation_date") or None, d.get("last_maintenance_date") or None,
             int(life) if str(life or "").isdigit() else None)))
        return jsonify({"message": "Asset added"}), 201

    @bp.route("/api/maintenance/predict", methods=["POST"])
    @role_required(*MANAGER)
    def predict_all():
        return jsonify({"assets_analysed": write(ms.run_predictions)})

    @bp.route("/api/maintenance/assets/<int:aid>/serviced", methods=["POST"])
    @role_required(*MANAGER)
    def serviced(aid):
        n = write(lambda c: c.execute("UPDATE maintenance_assets SET last_maintenance_date=? WHERE id=?",
                                      (date.today().isoformat(), aid)).rowcount)
        return jsonify({"message": "Maintenance recorded"}) if n else (jsonify({"error": "Asset not found"}), 404)

    @bp.route("/api/facial/events")
    @role_required(*STAFF)
    def face_events():
        return jsonify(rows("""SELECT e.id, e.event_type, e.confidence, e.event_time, e.notes, p.full_name, c.name AS camera
            FROM access_events e LEFT JOIN authorized_persons p ON p.id=e.person_id
            LEFT JOIN cameras c ON c.id=e.camera_id ORDER BY e.id DESC LIMIT 50"""))

    app.register_blueprint(bp)


def session_role():
    from flask import session
    return session.get("user_role")
