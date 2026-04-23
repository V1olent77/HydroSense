"""Shared data loading helpers. All loaders return None if the file is absent,
so pages can render a friendly message instead of crashing."""
from pathlib import Path
from typing import Optional

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data" / "processed"

INDICES_CSV = DATA_DIR / "monthly_indices.csv"
FORECAST_CSV = DATA_DIR / "forecast.csv"
SENSOR_CSV = DATA_DIR / "sensor_data.csv"
MAP_PNG = DATA_DIR / "drought_risk_map.png"

SENSOR_LAT = 49.95
SENSOR_LON = 82.61
SENSOR_OBLAST_KEYWORDS = ("vostochno", "east kaz", "vostočno", "kazakhstanskaya")


@st.cache_data(show_spinner=False)
def load_monthly_indices() -> Optional[pd.DataFrame]:
    if not INDICES_CSV.exists():
        return None
    df = pd.read_csv(INDICES_CSV, parse_dates=["date"])
    return df.sort_values(["oblast", "date"]).reset_index(drop=True)


@st.cache_data(show_spinner=False)
def load_forecast() -> Optional[pd.DataFrame]:
    if not FORECAST_CSV.exists():
        return None
    df = pd.read_csv(FORECAST_CSV, parse_dates=["date"])
    return df.sort_values(["oblast", "date"]).reset_index(drop=True)


def load_sensor_csv(path: Path | None = None, uploaded=None) -> Optional[pd.DataFrame]:
    """Load sensor readings. Accepts a path, a Streamlit UploadedFile, or
    falls back to the default SENSOR_CSV on disk."""
    src = uploaded if uploaded is not None else (path or SENSOR_CSV)
    if isinstance(src, Path) and not src.exists():
        return None
    try:
        df = pd.read_csv(src)
    except Exception:
        return None
    if df.empty:
        return None
    # Coerce a unified timestamp column.
    for col in ("timestamp", "time", "date", "datetime"):
        if col in df.columns:
            df["timestamp"] = pd.to_datetime(df[col], errors="coerce")
            break
    else:
        df["timestamp"] = pd.to_datetime(df.index, errors="coerce")
    return df.dropna(subset=["timestamp"]).sort_values("timestamp").reset_index(drop=True)


def latest_row(df: pd.DataFrame, by: str = "date") -> Optional[pd.Series]:
    if df is None or df.empty:
        return None
    return df.sort_values(by).iloc[-1]


def match_sensor_oblast(indices: pd.DataFrame) -> Optional[str]:
    """Best-effort match for the East Kazakhstan oblast name used in GAUL."""
    if indices is None:
        return None
    names = indices["oblast"].unique()
    low = {n.lower(): n for n in names}
    for key in SENSOR_OBLAST_KEYWORDS:
        for ln, original in low.items():
            if key in ln:
                return original
    return None
