"""Optional: add demo maintenance assets, then run predictions. Usage: python seed_demo.py"""
import sqlite3
from app import DATABASE, init_db
import maintenance_service as ms

init_db()
c = sqlite3.connect(DATABASE); c.row_factory = sqlite3.Row
if not c.execute("SELECT 1 FROM maintenance_assets").fetchone():
    c.executemany("INSERT INTO maintenance_assets (asset_name, asset_type, location, installation_date, "
                  "last_maintenance_date, expected_lifespan_months) VALUES (?,?,?,?,?,?)", [
        ("Main Entrance Camera", "Camera", "Entrance", "2022-01-15", "2026-01-10", 60),
        ("Rooftop HVAC Unit", "HVAC", "Roof", "2019-06-01", "2025-03-01", 120),
        ("Basement Pipes", "Plumbing", "Basement", "2015-09-01", "2024-02-01", 240),
        ("Front Door Lock", "Smart Lock", "Entrance", "2024-05-01", "2026-06-01", 48),
        ("Main Breaker Panel", "Electrical", "Utility room", "2018-02-01", "2023-11-01", 180)])
    c.commit()
ms.run_predictions(c); c.commit(); c.close()
print("Demo assets and predictions created.")
