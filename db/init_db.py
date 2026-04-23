"""
Initialize (or upgrade) the HydroSense SQLite database.

Idempotent: safe to run repeatedly. Creates tables if missing and
inserts the default Ust-Kamenogorsk node row if no nodes exist yet.
"""
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "hydrosense.db"
SCHEMA_PATH = Path(__file__).with_name("schema.sql")

DEFAULT_NODE = {
    "node_id": "node_01",
    "name": "Ust-Kamenogorsk pilot",
    "latitude": 49.93,
    "longitude": 82.58,
    "oblast": "East Kazakhstan",
    "deployment_date": None,        # filled in when actually deployed
    "status": "pending",
    "air_value": 3400,              # placeholder until real calibration
    "water_value": 1500,
    "notes": "MVP prototype node — single sensor for proof-of-concept demo.",
}


def init() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(DB_PATH) as conn:
        with open(SCHEMA_PATH, "r") as f:
            conn.executescript(f.read())

        cur = conn.execute("SELECT COUNT(*) FROM nodes")
        if cur.fetchone()[0] == 0:
            cols = ",".join(DEFAULT_NODE.keys())
            placeholders = ",".join("?" * len(DEFAULT_NODE))
            conn.execute(
                f"INSERT INTO nodes ({cols}) VALUES ({placeholders})",
                tuple(DEFAULT_NODE.values()),
            )
            print(f"Inserted default node row: {DEFAULT_NODE['node_id']}")

        n_nodes = conn.execute("SELECT COUNT(*) FROM nodes").fetchone()[0]
        n_reads = conn.execute("SELECT COUNT(*) FROM readings").fetchone()[0]
        n_alerts = conn.execute("SELECT COUNT(*) FROM alerts").fetchone()[0]

    print(f"DB ready at {DB_PATH}")
    print(f"  nodes:    {n_nodes}")
    print(f"  readings: {n_reads}")
    print(f"  alerts:   {n_alerts}")


if __name__ == "__main__":
    init()
