"""HydroSense backend. Flask API the ESP32 posts readings to and the
React landing reads from.

Run locally:
    python db/init_db.py     # one-time
    python api.py            # serves on 0.0.0.0:5001
    PORT=8080 python api.py  # override the port

Endpoints:
    POST /api/data                 Receive one reading from a sensor node
    GET  /api/latest               Single most recent reading for a node
    GET  /api/recent               Recent readings (with hours window)
    GET  /api/nodes                Registered sensor nodes
    GET  /api/alerts               Alert history
    GET  /api/stats                Headline counters for the landing
    GET  /api/health               Health check

    GET  /api/oblasts                       List all 14 oblasts + current state
    GET  /api/oblasts/<name>                One oblast: current + history + forecast
    GET  /api/oblasts/<name>/history        Monthly time series (5y)
    GET  /api/oblasts/<name>/forecast       8-week LSTM forecast
"""
import os
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

from flask import Flask, jsonify, request
from flask_cors import CORS

ROOT = Path(__file__).resolve().parent
DB_PATH = ROOT / "data" / "hydrosense.db"
PORT = int(os.environ.get("PORT", 5001))

# Allowed origins: in dev anything goes; in prod set ALLOWED_ORIGINS env var
# (comma-separated) e.g. "https://hydrosense.vercel.app,https://www.hydrosense.kz"
allowed = os.environ.get("ALLOWED_ORIGINS", "*")
origins = [o.strip() for o in allowed.split(",")] if allowed != "*" else "*"

app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": origins}})

# Required fields the ESP32 sends. soil_temperature, soil_raw, rssi are optional.
REQUIRED_FIELDS = {"node_id", "soil_moisture"}


def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def composite_drought_index(soil_moisture, soil_temperature):
    """Lightweight stand-in for the real composite index until the GEE
    pipeline writes oblast_indices. Range 0 (healthy) - 1 (severe drought).
    """
    if soil_moisture is None:
        return None
    moisture_stress = max(0.0, min(1.0, 1.0 - soil_moisture / 100.0))
    if soil_temperature is None:
        return round(moisture_stress, 2)
    # Above 25C soil temp adds stress (cap at 35C)
    temp_stress = max(0.0, min(1.0, (soil_temperature - 25.0) / 10.0))
    composite = 0.7 * moisture_stress + 0.3 * temp_stress
    return round(min(1.0, composite), 2)


# ---------------------------------------------------------------- POST
@app.route("/api/data", methods=["POST"])
def ingest():
    """ESP32 posts JSON here every 15 minutes."""
    if not DB_PATH.exists():
        return jsonify({"error": "database not initialized — run db/init_db.py"}), 500

    payload = request.get_json(silent=True) or {}
    missing = REQUIRED_FIELDS - payload.keys()
    if missing:
        return jsonify({"error": f"missing fields: {sorted(missing)}"}), 400

    timestamp = payload.get("timestamp") or utc_now_iso()

    try:
        with db() as conn:
            row = conn.execute(
                "SELECT 1 FROM nodes WHERE node_id = ?", (payload["node_id"],)
            ).fetchone()
            if not row:
                return jsonify({"error": f"unknown node_id {payload['node_id']!r}"}), 400

            conn.execute(
                """
                INSERT INTO readings
                    (node_id, timestamp, soil_moisture, soil_raw,
                     soil_temperature, rssi)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    payload["node_id"],
                    timestamp,
                    payload["soil_moisture"],
                    payload.get("soil_raw"),
                    payload.get("soil_temperature"),
                    payload.get("rssi"),
                ),
            )
            row_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        return jsonify({"status": "ok", "id": row_id, "timestamp": timestamp}), 201
    except sqlite3.Error as exc:
        return jsonify({"error": f"db error: {exc}"}), 500


# ---------------------------------------------------------------- GETs
@app.route("/api/latest", methods=["GET"])
def latest():
    """Single most recent reading for a node. Used by the live cards on
    the React landing — minimal payload, easy to render."""
    node_id = request.args.get("node_id", "node_01")
    with db() as conn:
        node = conn.execute(
            "SELECT node_id, name, latitude, longitude, oblast, status "
            "FROM nodes WHERE node_id = ?",
            (node_id,),
        ).fetchone()
        if not node:
            return jsonify({"error": f"unknown node_id {node_id!r}"}), 404

        row = conn.execute(
            """
            SELECT timestamp, soil_moisture, soil_temperature, soil_raw, rssi
            FROM readings
            WHERE node_id = ?
            ORDER BY timestamp DESC
            LIMIT 1
            """,
            (node_id,),
        ).fetchone()

    if not row:
        return jsonify({"node": dict(node), "reading": None})

    reading = dict(row)
    reading["drought_index"] = composite_drought_index(
        reading.get("soil_moisture"), reading.get("soil_temperature")
    )
    return jsonify({"node": dict(node), "reading": reading})


@app.route("/api/recent", methods=["GET"])
def recent():
    """Recent readings — used for charts and history.

    Query params:
        node_id  default 'node_01'
        hours    default 24, max 720 (~30 d)
    """
    node_id = request.args.get("node_id", "node_01")
    try:
        hours = min(int(request.args.get("hours", 24)), 720)
    except ValueError:
        return jsonify({"error": "hours must be an integer"}), 400

    cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
    with db() as conn:
        rows = conn.execute(
            """
            SELECT timestamp, soil_moisture, soil_raw, soil_temperature, rssi
            FROM readings
            WHERE node_id = ? AND timestamp >= ?
            ORDER BY timestamp ASC
            """,
            (node_id, cutoff),
        ).fetchall()
    return jsonify({"node_id": node_id, "count": len(rows),
                    "readings": [dict(r) for r in rows]})


@app.route("/api/nodes", methods=["GET"])
def list_nodes():
    with db() as conn:
        rows = conn.execute(
            "SELECT * FROM nodes ORDER BY created_at"
        ).fetchall()
    return jsonify({"nodes": [dict(r) for r in rows]})


@app.route("/api/alerts", methods=["GET"])
def list_alerts():
    """Optional query: ?since=ISO_TIMESTAMP, ?include_acknowledged=1"""
    since = request.args.get("since")
    include_ack = request.args.get("include_acknowledged") == "1"
    sql = "SELECT * FROM alerts WHERE 1=1"
    params: list = []
    if since:
        sql += " AND timestamp >= ?"
        params.append(since)
    if not include_ack:
        sql += " AND acknowledged = 0"
    sql += " ORDER BY timestamp DESC LIMIT 200"
    with db() as conn:
        rows = conn.execute(sql, params).fetchall()
    return jsonify({"alerts": [dict(r) for r in rows]})


@app.route("/api/stats", methods=["GET"])
def stats():
    """Headline numbers for the landing stat-bar. Honest counts."""
    with db() as conn:
        n_nodes = conn.execute("SELECT COUNT(*) FROM nodes").fetchone()[0]
        n_readings = conn.execute("SELECT COUNT(*) FROM readings").fetchone()[0]
        n_oblasts = conn.execute("SELECT COUNT(*) FROM oblast_indices").fetchone()[0]
        n_forecasts = conn.execute("SELECT COUNT(*) FROM oblast_forecasts").fetchone()[0]
    return jsonify({
        "nodes": n_nodes,
        "readings": n_readings,
        "oblasts_tracked": n_oblasts,
        "forecasts_active": n_forecasts,
        "data_sources": 6,
        "regions_total": 14,
    })


# ---------------------------------------------------------------- OBLASTS
@app.route("/api/oblasts", methods=["GET"])
def list_oblasts():
    """All 14 oblasts with current composite drought index. Used by the
    SatelliteCard heatmap on the landing."""
    with db() as conn:
        rows = conn.execute(
            "SELECT * FROM oblast_indices ORDER BY composite_index DESC"
        ).fetchall()
    return jsonify({
        "count": len(rows),
        "oblasts": [dict(r) for r in rows],
    })


@app.route("/api/oblasts/<name>", methods=["GET"])
def oblast_detail(name):
    """One oblast bundle: current + last 12mo history + full LSTM forecast."""
    with db() as conn:
        current = conn.execute(
            "SELECT * FROM oblast_indices WHERE oblast = ? COLLATE NOCASE",
            (name,),
        ).fetchone()
        if not current:
            return jsonify({"error": f"unknown oblast {name!r}"}), 404

        history = conn.execute(
            "SELECT month, ndvi, precipitation_mm, soil_moisture_pct, composite_index "
            "FROM oblast_history WHERE oblast = ? COLLATE NOCASE "
            "ORDER BY month DESC LIMIT 12",
            (name,),
        ).fetchall()

        forecast = conn.execute(
            "SELECT week_offset, forecast_date, composite_index, "
            "       confidence_lower, confidence_upper, model_version "
            "FROM oblast_forecasts WHERE oblast = ? COLLATE NOCASE "
            "ORDER BY week_offset ASC",
            (name,),
        ).fetchall()

    return jsonify({
        "current":  dict(current),
        "history":  [dict(r) for r in reversed(history)],   # oldest→newest
        "forecast": [dict(r) for r in forecast],
    })


@app.route("/api/oblasts/<name>/history", methods=["GET"])
def oblast_history_route(name):
    """Full monthly history (5y default). Optional ?months=N."""
    try:
        months = min(int(request.args.get("months", 60)), 240)
    except ValueError:
        return jsonify({"error": "months must be an integer"}), 400
    with db() as conn:
        rows = conn.execute(
            "SELECT month, ndvi, precipitation_mm, soil_moisture_pct, composite_index "
            "FROM oblast_history WHERE oblast = ? COLLATE NOCASE "
            "ORDER BY month DESC LIMIT ?",
            (name, months),
        ).fetchall()
    if not rows:
        return jsonify({"error": f"no history for oblast {name!r}"}), 404
    return jsonify({
        "oblast": name,
        "count": len(rows),
        "history": [dict(r) for r in reversed(rows)],
    })


@app.route("/api/oblasts/<name>/forecast", methods=["GET"])
def oblast_forecast_route(name):
    """8-week LSTM forecast for one oblast. Used by AIModelCard."""
    with db() as conn:
        rows = conn.execute(
            "SELECT week_offset, forecast_date, composite_index, "
            "       confidence_lower, confidence_upper, model_version, generated_at "
            "FROM oblast_forecasts WHERE oblast = ? COLLATE NOCASE "
            "ORDER BY week_offset ASC",
            (name,),
        ).fetchall()
    if not rows:
        return jsonify({"error": f"no forecast for oblast {name!r}"}), 404
    return jsonify({
        "oblast": name,
        "horizon_weeks": len(rows),
        "model_version": rows[0]["model_version"],
        "generated_at": rows[0]["generated_at"],
        "forecast": [dict(r) for r in rows],
    })


@app.route("/api/health", methods=["GET"])
def health():
    ok = DB_PATH.exists()
    return jsonify({
        "status": "ok" if ok else "db_missing",
        "db_path": str(DB_PATH),
        "time": utc_now_iso(),
    }), (200 if ok else 503)


if __name__ == "__main__":
    if not DB_PATH.exists():
        print(f"WARNING: {DB_PATH} doesn't exist yet — run `python db/init_db.py` first.")
    app.run(host="0.0.0.0", port=PORT, debug=True)
