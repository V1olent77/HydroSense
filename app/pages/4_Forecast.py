"""LSTM forecast page — 2-month-ahead drought risk per oblast.

Reads data/processed/forecast.csv produced by forecast.py. Includes honest
caveats: ~2000 training windows, single-site validation.
"""
from pathlib import Path
import sys

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from utils.data_loader import load_forecast

st.set_page_config(page_title="Forecast — HydroSense", layout="wide")
st.title("LSTM drought forecast — 2 months ahead")
st.caption(
    "Experimental AI layer. PyTorch LSTM · 12-month lookback · per-oblast. "
    "Consumes `forecast.csv` from forecast.py."
)

forecast = load_forecast()
if forecast is None:
    st.warning("Run `python forecast.py` to train the model and produce `forecast.csv`.")
    st.stop()

oblasts = sorted(forecast["oblast"].unique())
oblast = st.selectbox("Oblast", ["All (national mean)"] + oblasts)

if oblast == "All (national mean)":
    view = forecast.groupby("date", as_index=False)[
        ["predicted_risk", "actual_risk", "lower_95", "upper_95"]
    ].mean()
else:
    view = forecast[forecast["oblast"] == oblast].sort_values("date")

# --- Accuracy metrics --------------------------------------------------
residuals = (view["predicted_risk"] - view["actual_risk"]).dropna()
rmse = float(np.sqrt(np.mean(residuals ** 2))) if not residuals.empty else float("nan")
mae = float(np.mean(np.abs(residuals))) if not residuals.empty else float("nan")

c1, c2, c3 = st.columns(3)
c1.metric("Test-set RMSE", f"{rmse:.2f}")
c2.metric("Test-set MAE", f"{mae:.2f}")
c3.metric("Windows", f"{len(view):,}")

# --- Chart -------------------------------------------------------------
fig = go.Figure()
fig.add_traces([
    go.Scatter(x=view["date"], y=view["upper_95"],
               line=dict(width=0), showlegend=False, hoverinfo="skip"),
    go.Scatter(x=view["date"], y=view["lower_95"],
               line=dict(width=0), fill="tonexty", fillcolor="rgba(215,25,28,0.18)",
               name="95% band"),
    go.Scatter(x=view["date"], y=view["actual_risk"],
               line=dict(color="#ffffff", width=2), name="Actual"),
    go.Scatter(x=view["date"], y=view["predicted_risk"],
               line=dict(color="#d7191c", width=2, dash="dash"),
               name="Predicted (+2 mo)"),
])
fig.update_layout(
    template="plotly_dark",
    height=460,
    yaxis=dict(title="Drought risk (0–100)", range=[0, 100]),
    margin=dict(l=10, r=10, t=30, b=10),
)
st.plotly_chart(fig, use_container_width=True)

# --- Leaderboard of next-window predictions ---------------------------
st.subheader("Latest predictions — by oblast")
latest_date = forecast["date"].max()
latest = (
    forecast[forecast["date"] == latest_date]
    .sort_values("predicted_risk", ascending=False)
    .round(1)
    .reset_index(drop=True)
)
st.caption(f"Next window: {pd.to_datetime(latest_date).strftime('%B %Y')}")
st.dataframe(
    latest[["oblast", "predicted_risk", "actual_risk", "lower_95", "upper_95"]],
    use_container_width=True,
)

with st.expander("Honest caveats"):
    st.markdown(
        """
- Trained on ~2,000 monthly windows (2015–2022) · validated on 2023 · tested on 2024.
- No field validation beyond the single ESP32 node — a 50-node network would let us
  calibrate and improve the model.
- RMSE/MAE above are on held-out 2024 windows; real-world drift may differ.
- The LSTM is the forward-looking layer. For current conditions, trust the composite
  index on the Regional Map and Prediction Comparison pages.
"""
    )
