"""Generate a synthetic 7-day stream of ESP32 sensor readings for
dashboard development before the real hardware is deployed.

Models:
  - Temperature: sinusoidal diurnal cycle + slow drift
  - Humidity: anti-correlated with temperature
  - Pressure: random walk around 1010 hPa
  - Soil moisture: depletes with heat/low humidity, bumps up on rain

Usage:
    python scripts/simulate_sensor.py
    python scripts/simulate_sensor.py --days 5 --node-id node_01 --db
"""
import argparse
import csv
import math
import random
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CSV = ROOT / "data" / "processed" / "sample_sensor.csv"
DB_PATH = ROOT / "data" / "hydrosense.db"

INTERVAL_MIN = 15           # match the firmware's reading cadence


def simulate(days: int, node_id: str, seed: int) -> list[dict]:
    rng = random.Random(seed)
    n = days * 24 * (60 // INTERVAL_MIN)
    end = datetime.now(timezone.utc).replace(microsecond=0)
    start = end - timedelta(minutes=INTERVAL_MIN * (n - 1))

    # Schedule a few rain events at random hours during the window.
    rain_hours = sorted(rng.sample(range(days * 24), k=max(1, days // 2)))

    soil = 70.0                  # starting moisture
    pressure = 1010.0
    rows = []

    for i in range(n):
        t = start + timedelta(minutes=INTERVAL_MIN * i)
        hour_of_day = t.hour + t.minute / 60.0
        hour_of_run = i * INTERVAL_MIN / 60.0

        # Temperature: 18 °C base + 8 °C diurnal swing + slow warming
        temp = (
            18.0
            + 8.0 * math.sin((hour_of_day - 8) / 24 * 2 * math.pi)
            + 0.05 * hour_of_run
            + rng.gauss(0, 0.4)
        )

        # Humidity: anti-correlates with temperature
        humidity = max(20.0, min(95.0, 70 - (temp - 18) * 2.5 + rng.gauss(0, 3)))

        # Pressure: random walk
        pressure += rng.gauss(0, 0.2)
        pressure = max(990.0, min(1030.0, pressure))

        # Evapotranspiration pressure → soil moisture loss this step
        et = max(0, (temp - 15) * 0.06 + (100 - humidity) * 0.01)
        soil -= et / (60 // INTERVAL_MIN)   # spread over the interval

        # Rain event? bumps soil moisture up
        if int(hour_of_run) in rain_hours and rng.random() < 0.3:
            soil += rng.uniform(8, 18)
            humidity = min(95.0, humidity + 15)

        soil = max(15.0, min(95.0, soil))

        # Two temperature sensors disagree slightly (~0.3 °C)
        temp_bmp = round(temp, 2)
        temp_dht = round(temp + rng.gauss(0, 0.3), 2)

        # Reverse the calibration map so soil_raw is plausible
        air_value, water_value = 3400, 1500
        soil_raw = int(air_value + (soil / 100) * (water_value - air_value))

        rows.append({
            "node_id": node_id,
            "timestamp": t.isoformat(),
            "soil_moisture": round(soil, 1),
            "soil_raw": soil_raw,
            "temperature_bmp": temp_bmp,
            "temperature_dht": temp_dht,
            "humidity": round(humidity, 1),
            "pressure": round(pressure, 1),
            "rssi": rng.randint(-78, -55),
        })
    return rows


def write_csv(rows: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    print(f"Wrote {len(rows):,} rows → {path}")


def write_db(rows: list[dict], db_path: Path) -> None:
    if not db_path.exists():
        raise SystemExit(f"{db_path} not found — run `python db/init_db.py` first")

    with sqlite3.connect(db_path) as conn:
        # Make sure the node exists (the simulator might use a non-default id).
        conn.execute(
            """INSERT OR IGNORE INTO nodes (node_id, name, status, notes)
               VALUES (?, ?, 'simulated', 'Auto-created by simulate_sensor.py')""",
            (rows[0]["node_id"], f"Simulated node {rows[0]['node_id']}"),
        )
        conn.executemany(
            """INSERT INTO readings
                 (node_id, timestamp, soil_moisture, soil_raw,
                  temperature_bmp, temperature_dht, humidity, pressure, rssi)
               VALUES
                 (:node_id, :timestamp, :soil_moisture, :soil_raw,
                  :temperature_bmp, :temperature_dht, :humidity, :pressure, :rssi)""",
            rows,
        )
    print(f"Inserted {len(rows):,} rows into {db_path}")


def main() -> None:
    p = argparse.ArgumentParser(description="Simulate ESP32 sensor readings.")
    p.add_argument("--days", type=int, default=7, help="length of the simulated stream")
    p.add_argument("--node-id", default="node_01")
    p.add_argument("--seed", type=int, default=42, help="reproducibility seed")
    p.add_argument("--csv", type=Path, default=DEFAULT_CSV, help="CSV output path")
    p.add_argument("--db", action="store_true", help="also insert into data/hydrosense.db")
    p.add_argument("--no-csv", action="store_true", help="skip CSV output")
    args = p.parse_args()

    rows = simulate(args.days, args.node_id, args.seed)
    if not args.no_csv:
        write_csv(rows, args.csv)
    if args.db:
        write_db(rows, DB_PATH)


if __name__ == "__main__":
    main()
