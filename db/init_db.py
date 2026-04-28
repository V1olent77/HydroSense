"""Initialize the HydroSense SQLite database.

Idempotent: creates tables if missing, inserts the default
Ust-Kamenogorsk node row if no nodes exist, and loads the committed
oblast JSON seeds (current state + history + LSTM forecasts) into the
DB on every cold start.

The JSONs live at:
  data/seeds/oblast_indices.json
  data/seeds/oblast_history.json
  data/seeds/oblast_forecasts.json

They are produced offline by:
  ml/build_history.py  → synthetic 5y history (or ml/gee_pull.py for real)
  ml/build_current.py  → snapshot of latest month
  ml/lstm_forecast.py  → 8-week LSTM predictions

This means Render's ephemeral disk is fine — we re-seed everything from
JSON each time the service boots.
"""
import json
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "hydrosense.db"
SCHEMA_PATH = Path(__file__).with_name("schema.sql")
SEEDS = ROOT / "data" / "seeds"

DEFAULT_NODE = {
    "node_id": "node_01",
    "name": "Ust-Kamenogorsk pilot",
    "latitude": 49.93,
    "longitude": 82.58,
    "oblast": "East Kazakhstan",
    "deployment_date": None,
    "status": "pending",
    "air_value": 3400,
    "water_value": 1500,
    "notes": "MVP prototype node.",
}


def load_oblast_indices(conn):
    path = SEEDS / "oblast_indices.json"
    if not path.exists():
        print(f"  ! no {path.name}, skipping current-state seed")
        return 0
    rows = json.loads(path.read_text())
    conn.executemany(
        """INSERT OR REPLACE INTO oblast_indices
           (oblast, latitude, longitude, ndvi, precipitation_mm,
            soil_moisture_pct, composite_index, severity, updated_at)
           VALUES (:oblast, :latitude, :longitude, :ndvi, :precipitation_mm,
                   :soil_moisture_pct, :composite_index, :severity, :updated_at)""",
        rows,
    )
    return len(rows)


def load_oblast_history(conn):
    path = SEEDS / "oblast_history.json"
    if not path.exists():
        print(f"  ! no {path.name}, skipping history seed")
        return 0
    payload = json.loads(path.read_text())
    rows = []
    for oblast, months in payload["oblasts"].items():
        for m in months:
            rows.append({"oblast": oblast, **m})
    conn.executemany(
        """INSERT OR REPLACE INTO oblast_history
           (oblast, month, ndvi, precipitation_mm, soil_moisture_pct, composite_index)
           VALUES (:oblast, :month, :ndvi, :precipitation_mm,
                   :soil_moisture_pct, :composite_index)""",
        rows,
    )
    return len(rows)


def load_oblast_forecasts(conn):
    path = SEEDS / "oblast_forecasts.json"
    if not path.exists():
        print(f"  ! no {path.name}, skipping forecast seed")
        return 0
    payload = json.loads(path.read_text())
    model_version = payload["_meta"]["model_version"]
    generated_at = payload["_meta"]["generated_at"]
    # Wipe any older forecasts of this model — we always replace.
    conn.execute("DELETE FROM oblast_forecasts WHERE model_version = ?", (model_version,))
    rows = []
    for oblast, weeks in payload["forecasts"].items():
        for w in weeks:
            rows.append({
                "oblast": oblast,
                "model_version": model_version,
                "generated_at": generated_at,
                **w,
            })
    conn.executemany(
        """INSERT INTO oblast_forecasts
           (oblast, week_offset, forecast_date, composite_index,
            confidence_lower, confidence_upper, model_version, generated_at)
           VALUES (:oblast, :week_offset, :forecast_date, :composite_index,
                   :confidence_lower, :confidence_upper, :model_version, :generated_at)""",
        rows,
    )
    return len(rows)


def init() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(DB_PATH) as conn:
        with open(SCHEMA_PATH, "r") as f:
            conn.executescript(f.read())

        # Forward-only migration: ensure soil_temperature exists on legacy DBs.
        existing_cols = {row[1] for row in conn.execute("PRAGMA table_info(readings)")}
        if "soil_temperature" not in existing_cols:
            conn.execute("ALTER TABLE readings ADD COLUMN soil_temperature REAL")
            print("Migrated readings: added soil_temperature column")

        # ---- nodes -----------------------------------------------------
        cur = conn.execute("SELECT COUNT(*) FROM nodes")
        if cur.fetchone()[0] == 0:
            cols = ",".join(DEFAULT_NODE.keys())
            placeholders = ",".join("?" * len(DEFAULT_NODE))
            conn.execute(
                f"INSERT INTO nodes ({cols}) VALUES ({placeholders})",
                tuple(DEFAULT_NODE.values()),
            )
            print(f"Inserted default node row: {DEFAULT_NODE['node_id']}")

        # ---- oblast seeds ---------------------------------------------
        n_idx = load_oblast_indices(conn)
        n_hist = load_oblast_history(conn)
        n_fcst = load_oblast_forecasts(conn)
        if n_idx:  print(f"Loaded {n_idx} oblast current-state rows")
        if n_hist: print(f"Loaded {n_hist} oblast monthly history rows")
        if n_fcst: print(f"Loaded {n_fcst} LSTM forecast rows")

        n_nodes = conn.execute("SELECT COUNT(*) FROM nodes").fetchone()[0]
        n_reads = conn.execute("SELECT COUNT(*) FROM readings").fetchone()[0]
        n_alerts = conn.execute("SELECT COUNT(*) FROM alerts").fetchone()[0]

    print(f"DB ready at {DB_PATH}")
    print(f"  nodes:           {n_nodes}")
    print(f"  readings:        {n_reads}")
    print(f"  alerts:          {n_alerts}")
    print(f"  oblast_indices:  {n_idx}")
    print(f"  oblast_history:  {n_hist}")
    print(f"  oblast_forecasts:{n_fcst}")


if __name__ == "__main__":
    init()
