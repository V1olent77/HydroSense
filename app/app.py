"""HydroSense — Streamlit entry point.

Five pages live in ./pages/; shared helpers live in ./utils/.
Run: `streamlit run app/app.py`
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import streamlit as st

from utils.data_loader import (
    DATA_DIR,
    load_forecast,
    load_monthly_indices,
    load_sensor_csv,
)

st.set_page_config(
    page_title="HydroSense",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.title("HydroSense")
st.caption(
    "Drought-prediction platform for Kazakhstan — satellite indices · "
    "LSTM forecast · ESP32 ground-truth sensor"
)

# --- Top-line stats row -------------------------------------------------
indices = load_monthly_indices()
forecast = load_forecast()
sensor = load_sensor_csv()

c1, c2, c3, c4 = st.columns(4)
c1.metric("Oblasts covered", indices["oblast"].nunique() if indices is not None else 17)
c2.metric(
    "Monthly samples",
    f"{len(indices):,}" if indices is not None else "—",
    help="Rows in data/processed/monthly_indices.csv",
)
c3.metric(
    "Forecast windows",
    f"{len(forecast):,}" if forecast is not None else "—",
    help="Rows in data/processed/forecast.csv",
)
c4.metric(
    "Sensor readings",
    f"{len(sensor):,}" if sensor is not None else "—",
    help="Latest uploaded node data",
)

st.markdown(
    """
### Three layers of insight
1. **Regional Map** — national drought risk right now, across all 17 oblasts.
2. **Sensor Data** — live feed from the ESP32 node deployed near Ust-Kamenogorsk.
3. **Prediction Comparison** — satellite-only vs satellite+sensor. The delta is why the hardware exists.
4. **LSTM Forecast** — drought risk ~8 weeks ahead, per oblast (experimental AI layer).
5. **Alerts** — threshold triggers for high-risk regions.

---

**Built for:** Samsung Solve for Tomorrow · **Audience:** Kazakh government officials and NGOs

Navigate using the sidebar.
"""
)

# --- Data-availability diagnostics --------------------------------------
with st.expander("Data sources & pipeline status", expanded=False):
    rows = [
        ("Historical composite map (PNG)", DATA_DIR / "drought_risk_map.png"),
        ("Monthly indices per oblast", DATA_DIR / "monthly_indices.csv"),
        ("LSTM forecast outputs", DATA_DIR / "forecast.csv"),
        ("Sensor node readings", DATA_DIR / "sensor_data.csv"),
    ]
    for label, path in rows:
        present = Path(path).exists()
        st.write(f"{'OK' if present else 'missing'} — **{label}** · `{path.name}`")

    st.markdown(
        """
If monthly indices or forecasts are missing, run:
```
export GEE_PROJECT=your-gee-project-id
python time_series.py
python forecast.py
```

Sensor data arrives either via the Flask endpoint (`api.py`) or by uploading a
CSV on the Sensor Data page.
"""
    )
