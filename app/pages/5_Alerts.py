"""Threshold-based alerts — flag oblasts (and the sensor node) that cross a risk line."""
from pathlib import Path
import sys

import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from utils.data_loader import load_forecast, load_monthly_indices, load_sensor_csv
from utils.prediction import satellite_only

st.set_page_config(page_title="Alerts — HydroSense", layout="wide")
st.title("Drought alerts")
st.caption("Configurable thresholds across satellite composite, LSTM forecast, and the sensor node.")

# --- Controls ----------------------------------------------------------
t1, t2, t3 = st.columns(3)
with t1:
    composite_threshold = st.slider("Composite risk ≥", 0, 100, 60, help="Triggers per oblast on the latest satellite month.")
with t2:
    forecast_threshold = st.slider("Forecast risk ≥", 0, 100, 65, help="Triggers per oblast on the LSTM's next window.")
with t3:
    soil_threshold = st.slider("Soil moisture ≤", 0, 100, 25, help="Triggers when the sensor node drops below this %.")

indices = load_monthly_indices()
forecast = load_forecast()
sensor = load_sensor_csv()

triggered = []

# --- Composite alerts --------------------------------------------------
st.subheader("Current composite (satellite-only)")
if indices is None:
    st.info("Monthly indices not yet built — run `time_series.py`.")
else:
    latest_date = indices["date"].max()
    latest = indices[indices["date"] == latest_date].copy()
    latest["composite"] = latest.apply(
        lambda r: satellite_only({
            "spi": r["spi"], "vhi": r["vhi"], "temp_anomaly": r["temp_anomaly"],
        }),
        axis=1,
    )
    hot = latest[latest["composite"] >= composite_threshold].sort_values("composite", ascending=False)
    if hot.empty:
        st.success(f"No oblast crosses composite {composite_threshold} for {latest_date:%b %Y}.")
    else:
        st.error(f"{len(hot)} oblast(s) above composite threshold:")
        st.dataframe(hot[["oblast", "composite", "vhi", "spi"]].round(2).reset_index(drop=True),
                     use_container_width=True)
        for _, r in hot.iterrows():
            triggered.append(("Composite", r["oblast"], float(r["composite"])))

# --- Forecast alerts ---------------------------------------------------
st.subheader("LSTM forecast — next window")
if forecast is None:
    st.info("Forecast not yet built — run `forecast.py`.")
else:
    latest_date = forecast["date"].max()
    latest_f = forecast[forecast["date"] == latest_date].copy()
    hot = latest_f[latest_f["predicted_risk"] >= forecast_threshold].sort_values("predicted_risk", ascending=False)
    if hot.empty:
        st.success(f"No oblast crosses forecast {forecast_threshold} for {latest_date:%b %Y}.")
    else:
        st.error(f"{len(hot)} oblast(s) above forecast threshold:")
        st.dataframe(hot[["oblast", "predicted_risk", "lower_95", "upper_95"]].round(1).reset_index(drop=True),
                     use_container_width=True)
        for _, r in hot.iterrows():
            triggered.append(("Forecast +2mo", r["oblast"], float(r["predicted_risk"])))

# --- Sensor alerts -----------------------------------------------------
st.subheader("ESP32 sensor node")
if sensor is None or "soil_moisture" not in sensor.columns:
    st.info("No sensor data loaded.")
else:
    latest = sensor.iloc[-1]
    soil = float(latest["soil_moisture"])
    col1, col2 = st.columns(2)
    col1.metric("Latest soil moisture", f"{soil:.1f} %")
    col2.metric("Threshold", f"≤ {soil_threshold} %")
    if soil <= soil_threshold:
        st.error(
            f"Sensor below threshold at {latest['timestamp']:%Y-%m-%d %H:%M}. "
            "Root-depth moisture is in the drought stress zone."
        )
        triggered.append(("Sensor", "Node 01 (Ust-Kamenogorsk)", soil))
    else:
        st.success("Sensor reads above threshold.")

# --- Unified trigger summary ------------------------------------------
if triggered:
    st.subheader("Active alerts")
    st.dataframe(
        pd.DataFrame(triggered, columns=["Source", "Region", "Value"]).round(1),
        use_container_width=True,
    )
