"""Generate 5 years of monthly per-oblast history.

Each oblast gets 60 monthly samples with:
  * realistic seasonality (peak NDVI in May-June, dry winters)
  * year-on-year drift (2022 was wetter than 2024 in KZ historically)
  * per-oblast climate baseline from ml/oblasts.py
  * Gaussian noise for realism

Output: data/seeds/oblast_history.json — committed to repo, loaded
into the oblast_history DB table by db/init_db.py.

In production this script is REPLACED by ml/gee_pull.py which fetches
real MODIS NDVI + CHIRPS precip + ERA5-Land soil moisture from Google
Earth Engine. Until GEE credentials are wired up, this synthetic
history is what the LSTM trains on.
"""
from __future__ import annotations

import json
import math
import random
from datetime import date, timedelta
from pathlib import Path

from oblasts import OBLASTS, severity_label

ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "data" / "seeds" / "oblast_history.json"

# 5 years × 12 months = 60 samples per oblast.
YEARS = 5
END_MONTH = date(2026, 4, 1)   # last sample month

# Year-on-year drought severity multiplier (>1 = drier than baseline).
# Loosely based on KZ drought history: 2021 normal, 2022 wet, 2023 dry,
# 2024 very dry, 2025 mixed, 2026 trending dry again.
YEAR_DROUGHT_MULT = {
    2021: 1.05,
    2022: 0.85,   # wetter
    2023: 1.18,   # dry
    2024: 1.30,   # very dry
    2025: 1.10,
    2026: 1.20,   # current trend
}


def month_iter():
    """Yield (year, month) tuples from oldest to most recent."""
    end = END_MONTH
    months = YEARS * 12
    start = date(end.year - YEARS, end.month, 1)
    cur = start
    for _ in range(months):
        yield cur.year, cur.month
        # Advance one month
        if cur.month == 12:
            cur = date(cur.year + 1, 1, 1)
        else:
            cur = date(cur.year, cur.month + 1, 1)


def synth_month(baseline_row, year: int, month: int, rng: random.Random):
    """Return a single-month sample for one oblast."""
    name, lat, lon, ndvi_b, precip_b, soil_b, comp_b, _ = baseline_row

    # Seasonal NDVI: peaks in May-June (month 5-6), trough in Jan-Feb.
    season_ndvi = 0.5 + 0.5 * math.cos(2 * math.pi * (month - 6) / 12)
    ndvi = ndvi_b * (0.45 + 0.85 * season_ndvi) + rng.gauss(0, 0.03)
    ndvi = max(0.05, min(0.85, ndvi))

    # Seasonal precipitation: wet spring, dry summer in continental KZ.
    # Strongest April-May, weakest July-Aug, second peak October.
    season_pr = 0.55 + 0.55 * math.cos(2 * math.pi * (month - 4) / 12)
    drought_mult = YEAR_DROUGHT_MULT.get(year, 1.0)
    precip = precip_b * season_pr / drought_mult + rng.gauss(0, 3.0)
    precip = max(0.5, precip)

    # Soil moisture lags precipitation slightly.
    season_soil = 0.6 + 0.4 * math.cos(2 * math.pi * (month - 5) / 12)
    soil = soil_b * season_soil / drought_mult + rng.gauss(0, 1.5)
    soil = max(2.0, min(60.0, soil))

    # Composite drought index (0 healthy, 1 severe). Empirical mix.
    moisture_stress = 1.0 - soil / 60.0
    veg_stress = 1.0 - ndvi / 0.7
    precip_stress = max(0.0, 1.0 - precip / 50.0)
    composite = max(
        0.0,
        min(
            1.0,
            0.4 * moisture_stress
            + 0.35 * veg_stress
            + 0.25 * precip_stress,
        ),
    )

    return {
        "month": f"{year:04d}-{month:02d}",
        "ndvi": round(ndvi, 3),
        "precipitation_mm": round(precip, 1),
        "soil_moisture_pct": round(soil, 1),
        "composite_index": round(composite, 3),
        "severity": severity_label(composite),
    }


def build():
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    rng = random.Random(42)  # deterministic seed → reproducible LSTM training
    out = {}

    for row in OBLASTS:
        name = row[0]
        history = [synth_month(row, y, m, rng) for y, m in month_iter()]
        out[name] = history

    # Convenience meta block so consumers don't have to scan keys.
    payload = {
        "_meta": {
            "generated_with": "ml/build_history.py (synthetic, deterministic seed=42)",
            "year_range": [
                next(iter(out.values()))[0]["month"][:4],
                next(iter(out.values()))[-1]["month"][:4],
            ],
            "samples_per_oblast": YEARS * 12,
            "oblasts": list(out.keys()),
            "note": "Replace with output of ml/gee_pull.py once GEE creds are wired in.",
        },
        "oblasts": out,
    }

    OUTPUT.write_text(json.dumps(payload, indent=2))
    n = sum(len(v) for v in out.values())
    print(f"Wrote {n} monthly samples across {len(out)} oblasts → {OUTPUT}")


if __name__ == "__main__":
    build()
