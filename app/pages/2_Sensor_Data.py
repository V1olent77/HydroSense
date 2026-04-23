"""Sensor dashboard — upload CSV or use default file, plot 4 measurements."""
from pathlib import Path
import sys

import pandas as pd
import plotly.express as px
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from utils.data_loader import SENSOR_CSV, load_sensor_csv

st.set_page_config(page_title="Sensor Data — HydroSense", layout="wide")
st.title("ESP32 sensor node — live feed")
st.caption(
    f"Ingest via Flask `api.py` → `{SENSOR_CSV.name}` OR upload a CSV from the ESP32's SD card."
)

uploaded = st.file_uploader("Upload sensor CSV", type=["csv"], accept_multiple_files=False)
df = load_sensor_csv(uploaded=uploaded) if uploaded else load_sensor_csv()

if df is None:
    st.info(
        f"No sensor data yet. Deploy the node or drop a CSV here "
        f"(expected columns: `timestamp, soil_moisture, temperature_bmp, temperature_dht, humidity, pressure`)."
    )
    st.stop()

# --- Headline metrics for the latest reading --------------------------
latest = df.iloc[-1]
c1, c2, c3, c4 = st.columns(4)
c1.metric("Soil moisture", f"{latest.get('soil_moisture', float('nan')):.1f} %")
c2.metric("Temperature (BMP)", f"{latest.get('temperature_bmp', float('nan')):.1f} °C")
c3.metric("Humidity", f"{latest.get('humidity', float('nan')):.1f} %")
c4.metric("Pressure", f"{latest.get('pressure', float('nan')):.1f} hPa")

st.caption(f"Latest reading · {latest['timestamp']:%Y-%m-%d %H:%M} · {len(df):,} total readings")

# --- Time series charts -----------------------------------------------
plots = [
    ("soil_moisture", "Soil moisture (%)", "#74c476"),
    ("temperature_bmp", "Temperature — BMP280 (°C)", "#fdae61"),
    ("humidity", "Humidity (%)", "#74add1"),
    ("pressure", "Barometric pressure (hPa)", "#c2a5cf"),
]

col_l, col_r = st.columns(2)
for i, (col, label, color) in enumerate(plots):
    target = col_l if i % 2 == 0 else col_r
    if col not in df.columns:
        target.info(f"`{col}` column missing from upload.")
        continue
    fig = px.line(df, x="timestamp", y=col, title=label)
    fig.update_traces(line=dict(color=color))
    fig.update_layout(template="plotly_dark", height=320, margin=dict(l=10, r=10, t=40, b=10))
    target.plotly_chart(fig, use_container_width=True)

# --- Cross-validation check -------------------------------------------
if {"temperature_bmp", "temperature_dht"}.issubset(df.columns):
    resid = (df["temperature_bmp"] - df["temperature_dht"]).dropna()
    if not resid.empty:
        st.caption(
            f"BMP vs DHT22 temperature agreement — mean Δ {resid.mean():+.2f} °C, "
            f"std {resid.std():.2f} °C (expected ≲ 1 °C)."
        )

with st.expander("Raw data"):
    st.dataframe(df.tail(200), use_container_width=True)
