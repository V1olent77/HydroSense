"""
HydroSense backend — minimal Flask API the ESP32 posts readings to,
and the Streamlit dashboard pulls them from.

Run locally:
    python db/init_db.py        # one-time, creates data/hydrosense.db
    python api.py               # serves on 0.0.0.0:5001 by default
                                # (macOS uses 5000 for AirPlay Receiver)

Expose to the ESP32 (which is on a different network):
    ngrok http 5001             # gives you a public https URL to paste
                                # into firmware/sensor_node/sensor_node.ino

Override the port with:  PORT=8080 python api.py

Endpoints
---------
POST /api/data       Receive one reading from a node (ESP32 calls this)
GET  /api/recent     Recent readings for the dashboard
GET  /api/nodes      Registered sensor nodes
GET  /api/alerts     Alert history
GET  /api/health     Health check
"""
import os
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

from flask import Flask, jsonify, request

ROOT = Path(__file__).resolve().parent
DB_PATH = ROOT / "data" / "hydrosense.db"
PORT = int(os.environ.get("PORT", 5001))

app = Flask(__name__)

# Required fields the ESP32 sends. soil_raw + rssi are optional.
REQUIRED_FIELDS = {
    "node_id", "soil_moisture", "temperature_bmp",
    "temperature_dht", "humidity", "pressure",
}


def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


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
            # Reject readings from unknown nodes — keeps the schema honest.
            row = conn.execute(
                "SELECT 1 FROM nodes WHERE node_id = ?", (payload["node_id"],)
            ).fetchone()
            if not row:
                return jsonify({"error": f"unknown node_id {payload['node_id']!r}"}), 400

            conn.execute(
                """
                INSERT INTO readings
                    (node_id, timestamp, soil_moisture, soil_raw,
                     temperature_bmp, temperature_dht, humidity, pressure, rssi)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    payload["node_id"],
                    timestamp,
                    payload["soil_moisture"],
                    payload.get("soil_raw"),
                    payload["temperature_bmp"],
                    payload["temperature_dht"],
                    payload["humidity"],
                    payload["pressure"],
                    payload.get("rssi"),
                ),
            )
            row_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        return jsonify({"status": "ok", "id": row_id, "timestamp": timestamp}), 201
    except sqlite3.Error as exc:
        return jsonify({"error": f"db error: {exc}"}), 500


# ---------------------------------------------------------------- GETs
@app.route("/api/recent", methods=["GET"])
def recent():
    """Most recent readings — used by the Sensor Data dashboard page.

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
            SELECT timestamp, soil_moisture, soil_raw,
                   temperature_bmp, temperature_dht,
                   humidity, pressure, rssi
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
