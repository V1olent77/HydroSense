"""Prediction comparison: satellite-only vs satellite + sensor composite."""
from pathlib import Path
import sys

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from utils.data_loader import (
    load_monthly_indices,
    load_sensor_csv,
    match_sensor_oblast,
)
from utils.prediction import satellite_only, satellite_plus_sensor

st.set_page_config(page_title="Prediction — HydroSense", layout="wide")
st.title("Satellite-only vs satellite + sensor")
st.caption(
    "Composite drought index (0–100). The right card adds ground-truth soil "
    "moisture + evapotranspiration pressure from the ESP32 node."
)

indices = load_monthly_indices()
sensor = load_sensor_csv()

if indices is None:
    st.warning("Run `python time_series.py` — no satellite indices available.")
    st.stop()

# Select the oblast that contains the sensor (default) or let the user override.
sensor_oblast = match_sensor_oblast(indices)
oblasts = sorted(indices["oblast"].unique())
default_idx = oblasts.index(sensor_oblast) if sensor_oblast in oblasts else 0
oblast = st.selectbox("Oblast (satellite context)", oblasts, index=default_idx)

sat_row = indices[indices["oblast"] == oblast].sort_values("date").iloc[-1]
sat_payload = {
    "spi": sat_row["spi"],
    "vhi": sat_row["vhi"],
    "temp_anomaly": sat_row["temp_anomaly"],
}
sat_score = satellite_only(sat_payload)

sensor_score = None
if sensor is not None:
    latest_sensor = sensor.iloc[-1].to_dict()
    sensor_score = satellite_plus_sensor(sat_payload, latest_sensor)

# --- Headline cards ----------------------------------------------------
c1, c2, c3 = st.columns(3)
c1.metric("Satellite-only risk", f"{sat_score:.1f} / 100")
if sensor_score is not None:
    delta = sensor_score - sat_score
    c2.metric("Satellite + sensor risk", f"{sensor_score:.1f} / 100",
              delta=f"{delta:+.1f}", delta_color="inverse")
    c3.metric("Ground correction", f"{delta:+.1f}",
              help="Positive = sensors detect worse drought than satellite suggests.")
else:
    c2.info("Upload sensor data on the Sensor Data page to enable the comparison.")

# --- Explanation -------------------------------------------------------
st.subheader("What changes with ground data?")
if sensor_score is None:
    st.write(
        "Without sensor readings, the platform can only estimate drought from "
        "satellite indices — a macro-scale view that averages across kilometers "
        "and misses root-depth conditions."
    )
else:
    if delta >= 5:
        st.warning(
            "The sensor detects **higher** drought risk than satellite data alone. "
            "Root-depth soil moisture is depleting faster than the surface estimate "
            "suggests — an early warning that would be invisible from space."
        )
    elif delta <= -5:
        st.success(
            "The sensor reports **lower** drought risk than satellite data alone. "
            "Irrigation or local precipitation is buffering root-depth moisture "
            "even while the surface reads dry."
        )
    else:
        st.info("Ground and satellite agree closely — conditions are uniform at this site.")

# --- Component breakdown ----------------------------------------------
st.subheader("Component scores")
bd_col1, bd_col2 = st.columns(2)
with bd_col1:
    st.markdown("**Satellite-only composite**")
    st.write({
        "SPI (precip z-score)": round(float(sat_row["spi"]), 2),
        "VHI (vegetation 0–100)": round(float(sat_row["vhi"]), 1),
        "Temp anomaly (z-score)": round(float(sat_row["temp_anomaly"]), 2),
        "→ composite": round(sat_score, 1),
    })
with bd_col2:
    st.markdown("**Sensor add-ons**")
    if sensor is not None:
        st.write({
            "Soil moisture (%)": round(float(latest_sensor.get("soil_moisture", float("nan"))), 1),
            "Temp BMP (°C)": round(float(latest_sensor.get("temperature_bmp", float("nan"))), 1),
            "Humidity (%)": round(float(latest_sensor.get("humidity", float("nan"))), 1),
            "→ composite": round(sensor_score, 1),
        })
    else:
        st.caption("No sensor data loaded.")

st.caption(
    f"Satellite context from {sat_row['date'].strftime('%b %Y')} · oblast: {oblast}."
)
