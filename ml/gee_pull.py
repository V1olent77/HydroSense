"""Pull the latest month of MODIS NDVI + CHIRPS precipitation +
ERA5-Land soil moisture from Google Earth Engine, reduce per-oblast,
and write data/seeds/oblast_history.json (appending one new month) +
data/seeds/oblast_indices.json (current snapshot).

Authentication
--------------
Two ways for the GitHub Actions runner / your laptop to talk to GEE:

  1. Personal account (interactive, only on your laptop):
        earthengine authenticate
     A token gets cached in ~/.config/earthengine/credentials.

  2. Service account (recommended for automation):
        a) Create a service account on cloud.google.com → IAM → Service
           Accounts. Grant it the "Earth Engine Resource Viewer" role.
        b) Download the JSON key.
        c) Register the service account at https://signup.earthengine.google.com/
        d) On your laptop or as a GitHub secret named GEE_SERVICE_ACCOUNT_JSON,
           paste the contents of the JSON key.

Falling back to synthetic
-------------------------
If `earthengine-api` is not installed OR credentials are missing OR a
GEE call raises, this script DOES NOT FAIL the build. It logs a warning
and re-runs ml/build_history.py + ml/build_current.py instead. That way
the rest of the pipeline (LSTM training, forecast, API) keeps working
on synthetic-but-realistic data until you wire credentials in.
"""
from __future__ import annotations

import json
import logging
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HISTORY = ROOT / "data" / "seeds" / "oblast_history.json"
INDICES = ROOT / "data" / "seeds" / "oblast_indices.json"

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("gee_pull")


def authenticate_ee():
    """Returns True if Earth Engine successfully initialized."""
    try:
        import ee
    except ImportError:
        log.warning("earthengine-api not installed — install with `pip install earthengine-api`")
        return False, None

    sa_json = os.environ.get("GEE_SERVICE_ACCOUNT_JSON")
    try:
        if sa_json:
            # CI / GitHub Actions path: credentials in env var.
            with open("/tmp/gee_sa.json", "w") as f:
                f.write(sa_json)
            credentials = ee.ServiceAccountCredentials(
                email=None, key_file="/tmp/gee_sa.json"
            )
            ee.Initialize(credentials)
            log.info("GEE initialized via service account")
        else:
            # Local laptop path: cached user credentials.
            ee.Initialize()
            log.info("GEE initialized via cached user credentials")
        return True, ee
    except Exception as exc:
        log.warning(f"GEE init failed: {exc}")
        return False, None


def reduce_per_oblast(ee, image, bands, scale=5000):
    """Reduce an ee.Image to mean values per oblast and return a dict
    {oblast_name: {band: value}}.

    Uses Natural Earth admin-1 boundaries filtered to Kazakhstan. No
    additional uploads needed — Natural Earth ships with GEE.
    """
    from oblasts import OBLASTS

    fc = ee.FeatureCollection("FAO/GAUL/2015/level1") \
        .filter(ee.Filter.eq("ADM0_NAME", "Kazakhstan"))

    reduced = image.reduceRegions(
        collection=fc,
        reducer=ee.Reducer.mean(),
        scale=scale,
    ).getInfo()

    result = {}
    for feat in reduced.get("features", []):
        props = feat["properties"]
        # FAO uses ADM1_NAME — match against our canonical names.
        admin_name = props.get("ADM1_NAME", "")
        # Best-effort fuzzy match against our 14 baselines.
        match = next(
            (row[0] for row in OBLASTS
             if row[0].lower() in admin_name.lower()
             or admin_name.lower() in row[0].lower()),
            None,
        )
        if match:
            result[match] = {b: props.get(b) for b in bands}
    return result


def pull_real_gee():
    """Fetches last 30 days of MODIS NDVI, CHIRPS precip, ERA5 soil
    moisture from GEE. Returns dict of {oblast: {ndvi, precip, soil}}
    or raises on failure."""
    sys.path.insert(0, str(Path(__file__).parent))
    ok, ee = authenticate_ee()
    if not ok:
        raise RuntimeError("GEE not available")

    end = datetime.now(timezone.utc)
    start = end - timedelta(days=30)
    start_str = start.strftime("%Y-%m-%d")
    end_str = end.strftime("%Y-%m-%d")

    log.info(f"Pulling GEE data for window {start_str} → {end_str}")

    # MODIS Terra NDVI (250m, 16-day composites)
    ndvi_img = (
        ee.ImageCollection("MODIS/061/MOD13Q1")
        .filterDate(start_str, end_str)
        .select("NDVI")
        .mean()
        .multiply(0.0001)  # MODIS NDVI scale factor
        .rename("ndvi")
    )

    # CHIRPS daily precipitation
    precip_img = (
        ee.ImageCollection("UCSB-CHG/CHIRPS/DAILY")
        .filterDate(start_str, end_str)
        .select("precipitation")
        .sum()
        .rename("precipitation_mm")
    )

    # ERA5-Land monthly soil moisture, top layer
    soil_img = (
        ee.ImageCollection("ECMWF/ERA5_LAND/MONTHLY_AGGR")
        .filterDate(start_str, end_str)
        .select("volumetric_soil_water_layer_1")
        .mean()
        .multiply(100)  # m³/m³ → percent
        .rename("soil_moisture_pct")
    )

    # Stack into one image, reduce per oblast.
    stacked = ee.Image.cat([ndvi_img, precip_img, soil_img])
    return reduce_per_oblast(
        ee, stacked, ["ndvi", "precipitation_mm", "soil_moisture_pct"]
    )


def merge_into_history(new_month_data: dict, target_month: str):
    """Append a new month to oblast_history.json. Idempotent — replaces
    existing entry for that month if it exists."""
    sys.path.insert(0, str(Path(__file__).parent))
    from oblasts import severity_label

    payload = json.loads(HISTORY.read_text())
    history = payload["oblasts"]

    for oblast, vals in new_month_data.items():
        if oblast not in history:
            log.warning(f"Skipping unknown oblast in history merge: {oblast}")
            continue

        ndvi = vals.get("ndvi")
        precip = vals.get("precipitation_mm")
        soil = vals.get("soil_moisture_pct")
        if any(v is None for v in (ndvi, precip, soil)):
            log.warning(f"Incomplete data for {oblast}, skipping")
            continue

        # Recompute composite using the same formula as build_history.py
        moisture_stress = 1.0 - soil / 60.0
        veg_stress = 1.0 - ndvi / 0.7
        precip_stress = max(0.0, 1.0 - precip / 50.0)
        composite = max(0.0, min(1.0,
            0.4 * moisture_stress + 0.35 * veg_stress + 0.25 * precip_stress))

        new_entry = {
            "month": target_month,
            "ndvi": round(ndvi, 3),
            "precipitation_mm": round(precip, 1),
            "soil_moisture_pct": round(soil, 1),
            "composite_index": round(composite, 3),
            "severity": severity_label(composite),
        }

        # Replace if month already there, otherwise append.
        existing_idx = next(
            (i for i, m in enumerate(history[oblast]) if m["month"] == target_month),
            None,
        )
        if existing_idx is not None:
            history[oblast][existing_idx] = new_entry
        else:
            history[oblast].append(new_entry)

    payload["_meta"]["last_gee_pull"] = datetime.now(timezone.utc).isoformat()
    HISTORY.write_text(json.dumps(payload, indent=2))
    log.info(f"History updated for month {target_month}")


def fallback_synthetic():
    log.warning("Falling back to synthetic data (re-running build_history + build_current)")
    sys.path.insert(0, str(Path(__file__).parent))
    import build_history
    import build_current
    build_history.build()
    build_current.main()


def main():
    try:
        data = pull_real_gee()
        if not data:
            raise RuntimeError("GEE returned no data")
        target_month = datetime.now(timezone.utc).strftime("%Y-%m")
        merge_into_history(data, target_month)

        # Refresh the current-state snapshot from updated history.
        sys.path.insert(0, str(Path(__file__).parent))
        import build_current
        build_current.main()
        log.info("Real GEE pull succeeded.")
    except Exception as exc:
        log.warning(f"GEE pull failed: {exc}")
        fallback_synthetic()


if __name__ == "__main__":
    main()
