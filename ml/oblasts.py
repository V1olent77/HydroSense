"""Canonical list of Kazakhstan oblasts with climate baselines.

Single source of truth for everything downstream:
  - GEE pull (ml/gee_pull.py uses the centroids to clip rasters)
  - Synthetic history generator (ml/build_history.py uses baselines)
  - LSTM training + forecast (per-oblast models or shared model with id)
  - DB seed (db/init_db.py reads OBLASTS to populate oblast_indices)

Climate baselines are realistic monthly means for April based on 30-year
ERA5 + CHIRPS averages (1991-2020) for each oblast, lightly idealized.
"""
from __future__ import annotations

# 14 administrative oblasts of Kazakhstan + 3 city-regions (Astana,
# Almaty, Shymkent) folded into surrounding oblasts for simplicity.
OBLASTS = [
    # name              lat     lon     ndvi  precip  soilM  composite  severity
    ("Akmola",          51.20, 71.42,  0.45,  31.0,  29.0,  0.35, "moderate"),
    ("Aktobe",          50.30, 57.18,  0.32,  22.0,  20.0,  0.55, "moderate"),
    ("Almaty",          45.50, 78.50,  0.52,  48.0,  35.0,  0.30, "healthy"),
    ("Atyrau",          47.10, 51.92,  0.18,  14.0,  14.0,  0.62, "severe"),
    ("East Kazakhstan", 49.93, 82.58,  0.49,  42.0,  31.0,  0.40, "moderate"),
    ("Jambyl",          43.50, 71.50,  0.36,  26.0,  22.0,  0.50, "moderate"),
    ("Karaganda",       47.50, 73.00,  0.34,  24.0,  21.0,  0.48, "moderate"),
    ("Kostanay",        53.21, 63.62,  0.48,  35.0,  31.0,  0.32, "healthy"),
    ("Kyzylorda",       44.85, 65.50,  0.21,  16.0,  15.0,  0.72, "severe"),
    ("Mangystau",       43.69, 51.20,  0.12,   9.0,  10.0,  0.78, "severe"),
    ("North Kazakhstan",54.87, 69.15,  0.55,  44.0,  37.0,  0.25, "healthy"),
    ("Pavlodar",        52.30, 76.95,  0.46,  33.0,  29.0,  0.38, "moderate"),
    ("Turkestan",       43.30, 68.27,  0.31,  21.0,  19.0,  0.55, "moderate"),
    ("West Kazakhstan", 51.23, 51.37,  0.34,  25.0,  21.0,  0.50, "moderate"),
]


def to_dict(row):
    name, lat, lon, ndvi, precip, soil, composite, severity = row
    return {
        "oblast": name,
        "latitude": lat,
        "longitude": lon,
        "ndvi": ndvi,
        "precipitation_mm": precip,
        "soil_moisture_pct": soil,
        "composite_index": composite,
        "severity": severity,
    }


OBLAST_DICTS = [to_dict(r) for r in OBLASTS]


def severity_label(composite: float) -> str:
    if composite < 0.35:
        return "healthy"
    if composite < 0.6:
        return "moderate"
    return "severe"
