"""Automated tests for Darna. Run with:  python -m unittest -v
Uses a temporary database, so your real darna.db is never touched.
Facial recognition is not tested here because it needs DeepFace and photos (see README, manual tests)."""
import tempfile
import unittest
from pathlib import Path

import app as darna


class DarnaTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        darna.DATABASE = Path(self.tmp.name) / "test.db"
        darna.init_db()
        darna.create_default_user()
        darna.FAILED_LOGINS.clear()
        darna.app.config["TESTING"] = True
        self.client = darna.app.test_client()

    def tearDown(self):
        self.tmp.cleanup()

    def login(self, password="Darna123!"):
        return self.client.post("/login", data={"email": "admin@darna.com", "password": password})

    def test_login_wrong_password_rejected(self):
        self.assertEqual(self.login("wrong").status_code, 401)

    def test_login_success_opens_dashboard(self):
        self.assertEqual(self.login().status_code, 302)
        self.assertEqual(self.client.get("/").status_code, 200)

    def test_protected_pages_require_login(self):
        self.assertEqual(self.client.get("/").status_code, 302)
        self.assertEqual(self.client.get("/api/dashboard").status_code, 401)
        self.assertEqual(self.client.get("/api/network/devices").status_code, 401)

    def test_login_lockout_after_repeated_failures(self):
        for _ in range(5):
            self.login("wrong")
        self.assertEqual(self.login("Darna123!").status_code, 429)

    def test_camera_validation_and_crud(self):
        self.login()
        self.assertEqual(self.client.post("/api/cameras", json={"name": "A"}).status_code, 400)
        created = self.client.post("/api/cameras", json={"name": "Cam", "location": "Gate", "schedule": "24/7"})
        self.assertEqual(created.status_code, 201)
        cid = created.get_json()["id"]
        bad = self.client.put(f"/api/cameras/{cid}", json={"name": "Cam", "location": "Gate", "schedule": "24/7", "status": "Broken"})
        self.assertEqual(bad.status_code, 400)
        self.assertEqual(self.client.put(f"/api/cameras/{cid}", data="not json").status_code, 400)
        self.assertEqual(self.client.delete(f"/api/cameras/{cid}").status_code, 200)
        self.assertEqual(self.client.delete(f"/api/cameras/{cid}").status_code, 404)

    def test_network_scan_detects_threats_without_duplicates(self):
        self.login()
        first = self.client.post("/api/network/scan", json={"demo": True}).get_json()
        self.assertEqual(first["devices_seen"], 4)
        self.assertGreater(first["new_alerts"], 0)
        second = self.client.post("/api/network/scan", json={"demo": True}).get_json()
        self.assertEqual(second["new_alerts"], 0)
        types = {a["alert_type"] for a in self.client.get("/api/network/alerts").get_json()}
        self.assertIn("Unknown Device", types)
        self.assertIn("Risky Port 3389", types)

    def test_network_scan_flags_ip_conflict(self):
        self.login()
        devices = [
            {"name": "A", "ip": "10.0.0.5", "mac": "aa:aa:aa:aa:aa:01", "type": "PC", "open_ports": []},
            {"name": "B", "ip": "10.0.0.5", "mac": "aa:aa:aa:aa:aa:02", "type": "PC", "open_ports": []},
        ]
        self.client.post("/api/network/scan", json={"devices": devices})
        types = {a["alert_type"] for a in self.client.get("/api/network/alerts").get_json()}
        self.assertIn("IP/MAC Conflict", types)

    def test_invalid_scan_input_rejected(self):
        self.login()
        self.assertEqual(self.client.post("/api/network/scan", json={}).status_code, 400)

    def test_maintenance_predictions_rank_old_assets_higher(self):
        self.login()
        add = lambda name, inst, last: self.client.post("/api/maintenance/assets", json={
            "asset_name": name, "asset_type": "HVAC", "location": "Roof",
            "installation_date": inst, "last_maintenance_date": last, "expected_lifespan_months": 120})
        self.assertEqual(add("Old unit", "2015-01-01", "2020-01-01").status_code, 201)
        self.assertEqual(add("New unit", "2026-06-01", "2026-10-01").status_code, 201)
        self.assertEqual(self.client.post("/api/maintenance/predict").get_json()["assets_analysed"], 2)
        preds = self.client.get("/api/maintenance/predictions").get_json()
        self.assertEqual(preds[0]["asset_name"], "Old unit")
        self.assertIn(preds[0]["risk_level"], ("High", "Critical"))
        self.assertEqual(preds[-1]["risk_level"], "Low")

    def test_repeated_predictions_do_not_spam_activity_feed(self):
        self.login()
        self.client.post("/api/maintenance/assets", json={
            "asset_name": "Old", "asset_type": "HVAC", "location": "Roof",
            "installation_date": "2015-01-01", "last_maintenance_date": "2018-01-01", "expected_lifespan_months": 120})
        self.client.post("/api/maintenance/predict")
        count = lambda: len(self.client.get("/api/dashboard").get_json()["activities"])
        before = count()
        self.client.post("/api/maintenance/predict")
        self.assertEqual(count(), before)

    def test_facial_enroll_requires_consent_and_image(self):
        self.login()
        self.assertEqual(self.client.post("/api/facial/enroll", data={"full_name": "X"}).status_code, 400)


if __name__ == "__main__":
    unittest.main()
