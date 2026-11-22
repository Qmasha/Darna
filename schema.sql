CREATE TABLE IF NOT EXISTS cameras (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            location TEXT NOT NULL,
            status TEXT NOT NULL,
            schedule TEXT NOT NULL
        );
CREATE TABLE IF NOT EXISTS locks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            is_locked INTEGER NOT NULL,
            battery INTEGER NOT NULL
        );
CREATE TABLE IF NOT EXISTS members (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            initial TEXT NOT NULL
        );
CREATE TABLE IF NOT EXISTS activities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT NOT NULL
        );
CREATE TABLE IF NOT EXISTS authorized_persons (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    full_name TEXT NOT NULL,
    access_role TEXT NOT NULL,
    is_authorized INTEGER NOT NULL DEFAULT 1 CHECK (is_authorized IN (0, 1)),
    consent_recorded INTEGER NOT NULL DEFAULT 0 CHECK (consent_recorded IN (0, 1)),
    biometric_template_ref TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS access_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    person_id INTEGER,
    camera_id INTEGER,
    event_type TEXT NOT NULL CHECK (event_type IN ('authorized', 'unauthorized', 'unrecognized')),
    confidence REAL CHECK (confidence IS NULL OR (confidence >= 0 AND confidence <= 1)),
    event_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    notes TEXT,
    FOREIGN KEY (person_id) REFERENCES authorized_persons(id) ON DELETE SET NULL,
    FOREIGN KEY (camera_id) REFERENCES cameras(id) ON DELETE SET NULL
);
CREATE TABLE IF NOT EXISTS network_devices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    device_name TEXT NOT NULL,
    ip_address TEXT,
    mac_address TEXT,
    device_type TEXT,
    status TEXT NOT NULL DEFAULT 'Unknown',
    first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS security_alerts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id INTEGER,
    alert_type TEXT NOT NULL,
    severity TEXT NOT NULL CHECK (severity IN ('Low', 'Medium', 'High', 'Critical')),
    description TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'Open',
    detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    resolved_at TIMESTAMP,
    FOREIGN KEY (device_id) REFERENCES network_devices(id) ON DELETE SET NULL
);
CREATE TABLE IF NOT EXISTS maintenance_assets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    asset_name TEXT NOT NULL,
    asset_type TEXT NOT NULL,
    location TEXT NOT NULL,
    installation_date DATE,
    last_maintenance_date DATE,
    expected_lifespan_months INTEGER,
    status TEXT NOT NULL DEFAULT 'Operational'
);
CREATE TABLE IF NOT EXISTS maintenance_predictions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    asset_id INTEGER NOT NULL,
    predicted_issue TEXT NOT NULL,
    risk_level TEXT NOT NULL CHECK (risk_level IN ('Low', 'Medium', 'High', 'Critical')),
    predicted_failure_date DATE,
    recommendation TEXT,
    model_confidence REAL CHECK (model_confidence IS NULL OR (model_confidence >= 0 AND model_confidence <= 1)),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (asset_id) REFERENCES maintenance_assets(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_access_events_time ON access_events(event_time);
CREATE INDEX IF NOT EXISTS idx_security_alerts_detected ON security_alerts(detected_at);
CREATE INDEX IF NOT EXISTS idx_maintenance_predictions_asset ON maintenance_predictions(asset_id);
