# HydroSense

> Drought early-warning for Kazakhstan — satellite indices + ML forecast + ground-truth IoT sensor, on one dashboard.

Kazakhstan loses billions of tenge a year to drought. Farmers, water managers, and regional
officials often find out too late because national drought data is monthly, coarse, and
backward-looking. **HydroSense fuses three data layers** — 10 years of MODIS/CHIRPS/ERA5
satellite history, an LSTM that forecasts drought risk 2 months ahead for all 16 oblasts, and
a live ESP32 sensor node deployed in Ust-Kamenogorsk — into a single Streamlit dashboard that
shows both current conditions and where things are heading.

---

## Architecture

```
   ┌─────────────────────┐         ┌──────────────────────┐
   │  Google Earth       │         │  ESP32 sensor node   │
   │  Engine             │         │  (Ust-Kamenogorsk)   │
   │  MODIS NDVI         │         │  soil · temp · rh ·  │
   │  CHIRPS precip      │         │  pressure            │
   │  ERA5 temp          │         └──────────┬───────────┘
   └──────────┬──────────┘                    │ Wi-Fi POST
              │ monthly aggregates            │ every 15 min
              ▼                               ▼
   ┌─────────────────────┐         ┌──────────────────────┐
   │  time_series.py     │         │  api.py (Flask)      │
   │  → monthly_indices  │         │  → hydrosense.db      │
   │    .csv             │         │    (SQLite)          │
   └──────────┬──────────┘         └──────────┬───────────┘
              │                               │
              ▼                               │
   ┌─────────────────────┐                    │
   │  forecast.py        │                    │
   │  LSTM (PyTorch)     │                    │
   │  12mo → 2mo horizon │                    │
   │  → forecast.csv     │                    │
   └──────────┬──────────┘                    │
              │                               │
              └───────────────┬───────────────┘
                              ▼
                 ┌─────────────────────────┐
                 │  Streamlit dashboard    │
                 │  5 pages · multipage    │
                 └─────────────────────────┘
```

---

## Quickstart

### 1. Python environment
```bash
git clone https://github.com/V1olent77/HydroSense.git
cd HydroSense
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Pull 10 years of satellite data (one-time, ~20 min)
Requires a free Google Earth Engine account — sign up at <https://earthengine.google.com/>.
```bash
export GEE_PROJECT=your-gee-project-id
python time_series.py
```
Produces `data/processed/monthly_indices.csv` — 1,920 rows (16 oblasts × 120 months).

### 3. Train the forecast model (~3 min on Apple Silicon)
```bash
python forecast.py
```
Produces `data/processed/forecast_model.pt`, `forecast.csv`, and an eval chart.
Expected test-set accuracy: **RMSE ≈ 6.7, MAE ≈ 5.2** on the 0–100 risk scale.

### 4. Run the sensor API + dashboard
```bash
# Terminal 1 — ingestion API on :5001
python db/init_db.py        # one-time: create SQLite schema
python api.py

# Terminal 2 — dashboard on :8501
streamlit run app/app.py

# (optional) Terminal 3 — populate with 7 days of simulated readings
python scripts/simulate_sensor.py
```

### 5. (Optional) Flash the ESP32
See [`firmware/README.md`](firmware/README.md) for per-sensor test sketches and the
production `sensor_node.ino`. Calibrate the soil probe with:
```bash
python scripts/calibrate_soil.py --port /dev/cu.usbserial-XXXX
```
Deploy the API publicly so the field ESP32 can reach it — see
[`docs/DEPLOY_API.md`](docs/DEPLOY_API.md) (ngrok or Render).

---

## What's inside

| Layer              | Tool                | What it does                                         |
|--------------------|---------------------|------------------------------------------------------|
| Satellite history  | Google Earth Engine | MODIS NDVI, CHIRPS precip, ERA5 temp — 2015–2024     |
| Composite index    | pandas / numpy      | Per-oblast VHI + SPI + temp-anomaly → drought risk   |
| Forecast           | PyTorch LSTM        | 12-month lookback → 2-month horizon, per oblast      |
| Sensor node        | ESP32 + Arduino     | Capacitive soil + BMP280 + DHT22, 15-min POSTs       |
| Ingestion          | Flask + SQLite      | `/api/data` endpoint, 3 tables (nodes/readings/alerts) |
| Dashboard          | Streamlit + Folium  | 5-page multipage app with Plotly charts              |

### Project structure
```
.
├── time_series.py          # GEE pipeline: satellite → monthly_indices.csv
├── forecast.py             # LSTM training + evaluation
├── api.py                  # Flask ingestion API (POST /api/data)
├── app/
│   ├── app.py              # Streamlit entry point
│   └── pages/
│       ├── 1_Regional_Map.py
│       ├── 2_Sensor_Data.py
│       ├── 3_Prediction.py
│       ├── 4_Forecast.py
│       └── 5_Alerts.py
├── db/
│   ├── schema.sql          # nodes, readings, alerts
│   └── init_db.py          # idempotent DB creator
├── firmware/
│   ├── sensor_node/        # production sketch (all 3 sensors)
│   ├── test_serial/        # bare ESP32 heartbeat
│   ├── test_soil/          # capacitive probe only
│   ├── test_bmp280/        # I2C temp/pressure
│   └── test_dht22/         # humidity
├── scripts/
│   ├── calibrate_soil.py   # interactive AIR/WATER calibration helper
│   └── simulate_sensor.py  # 7-day synthetic data generator
├── docs/
│   └── DEPLOY_API.md       # ngrok + Render deploy paths
└── data/
    ├── raw/                # local .tif files
    └── processed/          # monthly_indices.csv, forecast.csv, model.pt
```

---

## How it works

**1. Composite drought index (assessment — current state).**
For each oblast and each month, `time_series.py` computes:
- **VHI** — NDVI rescaled 0–100 inside that oblast's own 10-year range.
- **SPI** — z-score of CHIRPS rainfall against the oblast's own climatology for that calendar month.
- **temp_anomaly** — z-score of ERA5 temperature, same way.
- **drought_risk** = `0.4·(100−VHI) + 0.4·clip(−SPI·20, 0, 100) + 0.2·clip(temp_anomaly·10, 0, 100)`, clipped 0–100.

Why per-oblast climatologies? Mangystau's "normal" is dry; East Kazakhstan's "normal" is wet.
Comparing each region against *itself* instead of a national baseline is what makes the index
meaningful.

**2. LSTM forecast (prediction — 2 months ahead).**
`forecast.py` trains a 2-layer LSTM (hidden 64, dropout 0.2) on 12-month input windows and
predicts `drought_risk` 2 months later. An oblast embedding lets the single model learn
region-specific patterns. Trained on 2015–2022, validated on 2023, tested on 2024 — a strict
time-based split so the model never sees the future. A 95 % uncertainty band comes from the
residual std on the validation set.

**3. Ground-truth sensor.**
An ESP32 in Ust-Kamenogorsk POSTs soil moisture, air temp/pressure, and humidity every
15 min. The dashboard overlays this point observation on the satellite layer — demonstrating
the concept of *validating remote sensing with ground truth*, which is how this kind of system
would actually be scaled.

---

## Hardware BOM

Total: **~11,700 ₸** from Kaspi (Kazakhstan).

| Part                                   | Purpose                 |
|----------------------------------------|-------------------------|
| ESP32 DevKit v1                        | Wi-Fi microcontroller   |
| Capacitive soil moisture sensor v1.2   | Soil moisture (analog)  |
| BMP280                                 | Temperature + pressure  |
| DHT22                                  | Humidity + temperature  |
| Breadboard, jumpers, micro-USB cable   | Wiring                  |

Wiring diagram and pin assignments are in [`firmware/README.md`](firmware/README.md).

---

## Limitations & future work

- **Monthly resolution** — the forecast is 2 months ahead at monthly granularity. Finer
  temporal resolution would need daily MODIS/Sentinel fusion.
- **Single sensor node** — we prove the ground-truth concept with one ESP32. A real
  deployment would need a network of nodes per oblast.
- **Free Render tier sleeps** — cold starts add ~30 s after 15 min idle. Fine for demos;
  switch to a paid tier or Railway/Fly.io for production.
- **No river/reservoir data** — Kazakhstan's Balkhash / Caspian / Aral basin data is
  fragmented. Integrating Kazhydromet feeds is the next obvious extension.

---

## Credits

- **HydroSense team** — Samsung Solve for Tomorrow Kazakhstan, 2026.
- Satellite data: NASA MODIS, UCSB CHIRPS, ECMWF ERA5 (via Google Earth Engine).
- Administrative boundaries: FAO GAUL 2015 level-1.
- Libraries: PyTorch, pandas, Streamlit, Flask, Plotly, Folium, earthengine-api.

---

## License

MIT.
