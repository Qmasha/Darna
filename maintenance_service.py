"""Predictive maintenance: transparent heuristic risk score from asset age and time since last service."""
from datetime import date, timedelta

SERVICE_INTERVAL_MONTHS = {"Camera": 6, "Smart Lock": 6, "HVAC": 4, "Plumbing": 12, "Electrical": 12, "Network": 12}
ISSUES = {"Camera": "Lens/sensor degradation or connectivity loss", "Smart Lock": "Motor wear or battery failure",
          "HVAC": "Compressor or filter failure", "Plumbing": "Leak or pipe corrosion",
          "Electrical": "Wiring fault or breaker failure", "Network": "Hardware failure or firmware issues"}
RECS = {"Critical": "Schedule service immediately.", "High": "Book maintenance within 2 weeks.",
        "Medium": "Plan maintenance this quarter.", "Low": "No action needed; continue routine checks."}


def _d(v):
    try:
        return date.fromisoformat(str(v)[:10]) if v else None
    except ValueError:
        return None


def _months(a, b):
    return max(0.0, (b - a).days / 30.4)


def predict(asset, today=None, battery=None):
    today = today or date.today()
    inst = _d(asset["installation_date"])
    last = _d(asset["last_maintenance_date"]) or inst
    life = asset["expected_lifespan_months"] or 60
    interval = SERVICE_INTERVAL_MONTHS.get(asset["asset_type"], 6)
    age_ratio = min(1.0, _months(inst, today) / life) if inst else 0.3
    overdue = min(1.0, (_months(last, today) / interval) / 2) if last else 0.5
    score = 0.55 * age_ratio + 0.45 * overdue
    issue = ISSUES.get(asset["asset_type"], "General wear and tear")
    if battery is not None and battery < 20:
        score, issue = min(1.0, score + 0.3), "Low battery - lock may stop responding"
    risk = "Critical" if score >= 0.8 else "High" if score >= 0.6 else "Medium" if score >= 0.35 else "Low"
    fail = today + timedelta(days=int((1 - score) * life * 0.5 * 30.4))
    conf = round(0.5 + 0.1 * bool(inst) + 0.1 * bool(asset["last_maintenance_date"]) + 0.1 * bool(asset["expected_lifespan_months"]), 2)
    return issue, risk, fail.isoformat(), RECS[risk], conf


def run_predictions(conn):
    conn.execute("DELETE FROM maintenance_predictions")
    batteries = {r["name"]: r["battery"] for r in conn.execute("SELECT name, battery FROM locks")}
    count = 0
    for a in conn.execute("SELECT * FROM maintenance_assets").fetchall():
        issue, risk, fail, rec, conf = predict(a, battery=batteries.get(a["asset_name"]))
        conn.execute("INSERT INTO maintenance_predictions (asset_id, predicted_issue, risk_level, "
                     "predicted_failure_date, recommendation, model_confidence) VALUES (?,?,?,?,?,?)",
                     (a["id"], issue, risk, fail, rec, conf))
        count += 1
        if risk in ("High", "Critical"):
            conn.execute("INSERT INTO activities (title, description) VALUES (?,?)",
                         ("Predictive Maintenance", f"{risk} risk: {a['asset_name']} - {issue}"))
    return count
