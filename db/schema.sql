-- HydroSense SQLite schema. Apply with:  python db/init_db.py
-- (idempotent; safe to re-run)

-- nodes: one row per deployed ESP32 sensor
CREATE TABLE IF NOT EXISTS nodes (
    node_id          TEXT PRIMARY KEY,
    name             TEXT NOT NULL,
    latitude         REAL,
    longitude        REAL,
    oblast           TEXT,
    deployment_date  TEXT,                -- ISO 8601 YYYY-MM-DD
    status           TEXT DEFAULT 'active', -- active | offline | retired
    air_value        INTEGER,             -- soil sensor calibration (dry)
    water_value      INTEGER,             -- soil sensor calibration (submerged)
    notes            TEXT,
    created_at       TEXT DEFAULT (datetime('now'))
);

-- ---------------------------------------------------------------
-- readings — one row per 15-min sample from each node
-- (BMP280 / DHT22 columns dropped; only soil + DS18B20 now)
-- ---------------------------------------------------------------
CREATE TABLE IF NOT EXISTS readings (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    node_id          TEXT NOT NULL,
    timestamp        TEXT NOT NULL,       -- ISO 8601 UTC
    soil_moisture    REAL,                -- 0–100 %
    soil_raw         INTEGER,             -- raw ADC for re-calibration
    soil_temperature REAL,                -- °C, from DS18B20
    rssi             INTEGER,             -- WiFi signal strength, optional
    received_at      TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (node_id) REFERENCES nodes(node_id)
);
CREATE INDEX IF NOT EXISTS idx_readings_node_time ON readings(node_id, timestamp);

-- ---------------------------------------------------------------
-- alerts — threshold breaches surfaced on the Alerts page
-- ---------------------------------------------------------------
CREATE TABLE IF NOT EXISTS alerts (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    node_id          TEXT NOT NULL,
    timestamp        TEXT NOT NULL,
    alert_type       TEXT NOT NULL,       -- soil_low | temp_high | et_critical | composite_high
    value            REAL,                -- the metric that breached
    threshold        REAL,                -- the threshold that was crossed
    message          TEXT,
    acknowledged     INTEGER DEFAULT 0,   -- 0 = open, 1 = acknowledged
    created_at       TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (node_id) REFERENCES nodes(node_id)
);
CREATE INDEX IF NOT EXISTS idx_alerts_time ON alerts(timestamp);
