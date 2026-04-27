"""Fill the readings table with 7 days of plausible-looking data for the
default node, so the React landing has something to display before a real
ESP32 is wired up.

Run:  python scripts/seed_demo_data.py
Wipe + reseed: python scripts/seed_demo_data.py --reset

Pattern:
  * sample every 15 minutes (96 / day) -> 7 * 96 = 672 rows
  * soil moisture: ~45 % baseline, drifting down 1.5 %/day with diurnal
    bumps, with one irrigation spike on day 3
  * soil temperature: diurnal sine 18-26 C, slightly damped vs air
"""
from __future__ import annotations

import argparse
import math
import random
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "hydrosense.db"

NODE_ID = "node_01"
DAYS = 7
INTERVAL_MIN = 15
SAMPLES = DAYS * 24 * 60 // INTERVAL_MIN


def synth_reading(t: datetime, day_index: int):
    """Return a realistic (soil_moisture, soil_raw, soil_temperature) tuple."""
    hour = t.hour + t.minute / 60

    # Soil moisture: linear dry-down, diurnal jitter, one irrigation event.
    base = 48.0 - day_index * 1.5
    diurnal = -1.5 * math.sin((hour - 6) / 24 * 2 * math.pi)
    irrigation_bump = 18.0 if (day_index == 3 and 5 <= hour <= 6) else 0.0
    noise = random.gauss(0, 0.6)
    soil_moisture = max(5.0, min(85.0, base + diurnal + irrigation_bump + noise))

    # Raw ADC inverse-mapped from moisture (3400 dry, 1500 wet).
    soil_raw = int(3400 - (soil_moisture / 100.0) * (3400 - 1500))

    # Soil temp lags air by ~2h, range 18-26 C, plus light noise.
    soil_temperature = (
        22.0
        + 4.0 * math.sin((hour - 14) / 24 * 2 * math.pi)
        + random.gauss(0, 0.3)
    )

    rssi = random.randint(-72, -55)
    return round(soil_moisture, 1), soil_raw, round(soil_temperature, 2), rssi


def seed(reset: bool = False) -> None:
    if not DB_PATH.exists():
        raise SystemExit(
            f"DB not found at {DB_PATH}. Run `python db/init_db.py` first."
        )

    with sqlite3.connect(DB_PATH) as conn:
        if reset:
            conn.execute("DELETE FROM readings WHERE node_id = ?", (NODE_ID,))
            print(f"Wiped existing readings for {NODE_ID}.")

        # Skip if already seeded (idempotent unless --reset).
        existing = conn.execute(
            "SELECT COUNT(*) FROM readings WHERE node_id = ?", (NODE_ID,)
        ).fetchone()[0]
        if existing and not reset:
            print(f"Already have {existing} readings for {NODE_ID} — skipping. Use --reset to wipe.")
            return

        # Make sure node exists.
        if not conn.execute(
            "SELECT 1 FROM nodes WHERE node_id = ?", (NODE_ID,)
        ).fetchone():
            raise SystemExit(
                f"Node {NODE_ID} not found. Run `python db/init_db.py` first."
            )

        end = datetime.now(timezone.utc).replace(second=0, microsecond=0)
        # Round to the previous quarter hour for clean intervals.
        end = end.replace(minute=(end.minute // 15) * 15)
        start = end - timedelta(days=DAYS)

        rows = []
        for i in range(SAMPLES):
            t = start + timedelta(minutes=i * INTERVAL_MIN)
            day_index = (t - start).days
            sm, sr, st, rssi = synth_reading(t, day_index)
            rows.append((NODE_ID, t.isoformat(), sm, sr, st, rssi))

        conn.executemany(
            "INSERT INTO readings (node_id, timestamp, soil_moisture, soil_raw, "
            "soil_temperature, rssi) VALUES (?, ?, ?, ?, ?, ?)",
            rows,
        )
        print(f"Seeded {len(rows)} readings for {NODE_ID} "
              f"({start.isoformat()} → {end.isoformat()}).")

        # Drop a sample alert too, so the alerts page isn't empty.
        conn.execute("DELETE FROM alerts WHERE node_id = ?", (NODE_ID,))
        conn.execute(
            "INSERT INTO alerts (node_id, timestamp, alert_type, value, threshold, message) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (NODE_ID, (end - timedelta(hours=18)).isoformat(),
             "soil_low", 22.0, 25.0,
             "Soil moisture dipped below 25% threshold for >2h."),
        )

    print("Done.")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Seed HydroSense demo readings.")
    p.add_argument("--reset", action="store_true", help="Wipe existing rows first.")
    args = p.parse_args()
    seed(reset=args.reset)
