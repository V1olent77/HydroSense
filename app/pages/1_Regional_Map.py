"""National drought map — per-oblast composite + historical PNG + sensor pin."""
from pathlib import Path
import sys

import folium
import pandas as pd
import plotly.express as px
import streamlit as st
from streamlit_folium import st_folium

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from utils.data_loader import MAP_PNG, SENSOR_LAT, SENSOR_LON, load_monthly_indices
from utils.prediction import satellite_only

st.set_page_config(page_title="Regional Map — HydroSense", layout="wide")
st.title("Regional drought map")
st.caption("Historical composite assessment + latest per-oblast drought scores.")

indices = load_monthly_indices()

# --- Historical composite PNG ------------------------------------------
if MAP_PNG.exists():
    st.subheader("Historical drought risk — Kazakhstan")
    st.image(str(MAP_PNG), use_container_width=True,
             caption="Composite of VHI + SPI + temperature anomaly (process_data.py output)")
else:
    st.info(f"`{MAP_PNG.name}` not found. Run `python process_data.py` to generate it.")

# --- Latest per-oblast scores ------------------------------------------
st.subheader("Current composite score by oblast")
if indices is None:
    st.warning("`monthly_indices.csv` not found. Run `python time_series.py` to populate per-oblast history.")
else:
    latest_date = indices["date"].max()
    latest = indices[indices["date"] == latest_date].copy()
    latest["composite"] = latest.apply(
        lambda r: satellite_only({
            "spi": r["spi"],
            "vhi": r["vhi"],
            "temp_anomaly": r["temp_anomaly"],
        }),
        axis=1,
    )
    latest = latest.sort_values("composite", ascending=False)
    st.caption(f"Snapshot for **{pd.to_datetime(latest_date).strftime('%B %Y')}** "
               f"· {len(latest)} oblasts · higher score = worse drought")

    fig = px.bar(
        latest,
        x="composite",
        y="oblast",
        orientation="h",
        color="composite",
        color_continuous_scale="Reds",
        range_color=(0, 100),
        labels={"composite": "Drought score (0–100)", "oblast": ""},
        height=480,
    )
    fig.update_layout(template="plotly_dark", margin=dict(l=10, r=10, t=10, b=10))
    st.plotly_chart(fig, use_container_width=True)

    with st.expander("Raw per-oblast table"):
        st.dataframe(
            latest[["oblast", "composite", "vhi", "spi", "temp_anomaly", "drought_risk"]]
            .reset_index(drop=True).round(2),
            use_container_width=True,
        )

# --- Sensor location map -----------------------------------------------
st.subheader("Sensor deployment site")
st.caption(f"ESP32 ground-truth node — Ust-Kamenogorsk ({SENSOR_LAT}°N, {SENSOR_LON}°E)")
m = folium.Map(location=[SENSOR_LAT, SENSOR_LON], zoom_start=9, tiles="CartoDB dark_matter")
folium.Marker(
    [SENSOR_LAT, SENSOR_LON],
    popup="HydroSense Node 01 — Irtysh basin",
    icon=folium.Icon(color="red", icon="tint", prefix="fa"),
).add_to(m)
st_folium(m, width=None, height=420, returned_objects=[])
