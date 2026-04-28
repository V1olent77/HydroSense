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
-- alerts — threshold breaches
-- ---------------------------------------------------------------
CREATE TABLE IF NOT EXISTS alerts (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    node_id          TEXT NOT NULL,
    timestamp        TEXT NOT NULL,
    alert_type       TEXT NOT NULL,
    value            REAL,
    threshold        REAL,
    message          TEXT,
    acknowledged     INTEGER DEFAULT 0,
    created_at       TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (node_id) REFERENCES nodes(node_id)
);
CREATE INDEX IF NOT EXISTS idx_alerts_time ON alerts(timestamp);

-- ===============================================================
-- LEVEL 2: Satellite-derived per-oblast indices
-- Refreshed daily by GitHub Actions cron (ml/gee_pull.py).
-- ===============================================================

-- Current state per oblast (one row per oblast).
CREATE TABLE IF NOT EXISTS oblast_indices (
    oblast            TEXT PRIMARY KEY,
    latitude          REAL,
    longitude         REAL,
    ndvi              REAL,             -- 0..1, MODIS Terra MOD13Q1
    precipitation_mm  REAL,             -- 30-day cumulative, CHIRPS
    soil_moisture_pct REAL,             -- 0..100, ERA5-Land top layer
    composite_index   REAL,             -- 0 healthy → 1 severe drought
    severity          TEXT,             -- "healthy" | "moderate" | "severe"
    updated_at        TEXT
);

-- Monthly time series per oblast (used to train the LSTM).
CREATE TABLE IF NOT EXISTS oblast_history (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    oblast            TEXT NOT NULL,
    month             TEXT NOT NULL,    -- YYYY-MM
    ndvi              REAL,
    precipitation_mm  REAL,
    soil_moisture_pct REAL,
    composite_index   REAL,
    UNIQUE(oblast, month)
);
CREATE INDEX IF NOT EXISTS idx_history_oblast_month
    ON oblast_history(oblast, month);

-- ===============================================================
-- LEVEL 3: LSTM-generated 8-week forecasts
-- Pre-computed offline by ml/lstm_forecast.py and committed as JSON.
-- ===============================================================
CREATE TABLE IF NOT EXISTS oblast_forecasts (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    oblast            TEXT NOT NULL,
    week_offset       INTEGER NOT NULL, -- 1..8 weeks ahead
    forecast_date     TEXT NOT NULL,    -- ISO date the forecast targets
    composite_index   REAL,
    confidence_lower  REAL,
    confidence_upper  REAL,
    model_version     TEXT,             -- e.g. "lstm_v1"
    generated_at      TEXT,
    UNIQUE(oblast, week_offset, model_version)
);
CREATE INDEX IF NOT EXISTS idx_forecast_oblast
    ON oblast_forecasts(oblast, week_offset);
