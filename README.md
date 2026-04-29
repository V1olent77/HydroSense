# HydroSense

> Drought early-warning for Kazakhstan — satellite indices + LSTM forecast + ground-truth IoT sensor, on one dashboard.

Kazakhstan loses billions of tenge a year to drought. Farmers, water managers, and regional
officials often find out too late because national drought data is monthly, coarse, and
backward-looking. **HydroSense fuses three data layers** — five years of MODIS / CHIRPS / ERA5
satellite history for all 14 oblasts, an LSTM that forecasts drought risk eight weeks ahead, and
a reference ESP32 ground node deployed in Ust-Kamenogorsk — into a single dashboard that
shows both current conditions and where things are heading.

Live demo: <https://hydrosense-web.vercel.app> · API: <https://hydrosense-api.onrender.com>

---

## Quickstart

### 1. Python environment
```bash
git clone https://github.com/V1olent77/HydroSense.git
cd HydroSense
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

### 2. (Optional) Pull fresh satellite data
The repo ships with seeded JSON in `data/seeds/`, so you can skip this on a first run.
To regenerate from scratch you need a free Google Earth Engine account.
```bash
export GEE_PROJECT=your-gee-project-id
python ml/gee_pull.py
python ml/build_history.py
python ml/build_current.py
```

### 3. Train the LSTM forecast model (~30 s on a CPU)
```bash
python ml/lstm_train.py
python ml/lstm_forecast.py
```
Produces `ml/models/lstm_v1.pt` (24 KB) and `data/seeds/oblast_forecasts.json` —
8 weeks ahead × 14 oblasts = 112 forecast rows.

### 4. Run the API + frontend locally
```bash
# Terminal 1 — Flask ingestion + read API on :5001
python db/init_db.py        # one-time: create SQLite, seed oblasts
python api.py

# Terminal 2 — React landing on :5173
cd web && npm install && npm run dev
```

### 5. (Optional) Flash the ESP32 sensor node
See [`firmware/README.md`](firmware/README.md). Calibrate the soil probe with:
```bash
python scripts/calibrate_soil.py --port /dev/cu.usbserial-XXXX
```
Then point `serverURL` in `firmware/sensor_node/sensor_node.ino` at your deployed API.

---

## What's inside

| Layer              | Tool                | What it does                                              |
|--------------------|---------------------|-----------------------------------------------------------|
| Satellite history  | Google Earth Engine | MODIS NDVI, CHIRPS precip, ERA5 soil moisture — 2020–2024 |
| Composite index    | pandas / numpy      | Per-oblast NDVI + soil + precip → drought risk 0–1        |
| Forecast           | PyTorch LSTM        | 12-month lookback → 2-month horizon, fanned to 8 weeks    |
| Sensor node        | ESP32 + Arduino     | Capacitive soil probe + DS18B20 soil temp, 15-min POSTs   |
| Ingestion          | Flask + SQLite      | `/api/data` endpoint, 6 tables (nodes / readings / oblast indices / history / forecasts / alerts) |
| Frontend           | React + Tailwind    | Single-page landing with bento layout, live data strip, AI forecast card |

### Project structure
```
.
├── api.py                  # Flask read + ingestion API
├── ml/
│   ├── oblasts.py          # canonical 14-oblast registry
│   ├── gee_pull.py         # GEE → raw JSON
│   ├── build_history.py    # raw JSON → monthly per-oblast series
│   ├── build_current.py    # latest month → "current state" snapshot
│   ├── lstm_train.py       # train and save ml/models/lstm_v1.pt
│   ├── lstm_forecast.py    # produce 8-week forecast JSON
│   └── models/             # checkpoint + metadata
├── db/
│   ├── schema.sql          # nodes, readings, alerts, oblast_indices, oblast_history, oblast_forecasts
│   └── init_db.py          # idempotent DB creator + seeder
├── data/
│   └── seeds/              # oblast_indices.json, oblast_history.json, oblast_forecasts.json
├── firmware/
│   ├── sensor_node/        # production sketch
│   ├── test_soil/          # capacitive probe only
│   └── test_combined/      # soil + DS18B20 together
├── web/
│   └── src/HydroSenseLanding.jsx   # the landing page (single self-contained component)
├── scripts/
│   ├── calibrate_soil.py
│   ├── seed_demo_data.py
│   └── simulate_sensor.py
└── docs/
    └── DEPLOY_API.md       # Render deploy notes
```

---

## How it works

### 1. Composite drought index — current state

For each of the 14 oblasts and each month, the pipeline computes:

- **NDVI** — MODIS Terra MOD13Q1 surface reflectance, cloud-masked, clipped to oblast geometry, mean over the oblast.
- **Soil moisture (%)** — ERA5-Land top-layer volumetric water content, monthly mean.
- **Precipitation (mm / 30 d)** — CHIRPS satellite-gauge rainfall, 30-day rolling sum.
- **Composite index (0–1)** — weighted fusion: `0.40 · ndvi_deficit + 0.35 · soil_deficit + 0.25 · precip_deficit`. Bucketed `< 0.35 healthy`, `0.35–0.6 moderate`, `≥ 0.6 severe`.

Each deficit is normalized against that oblast's own ten-year climatology — so Mangystau's "normal" (semi-desert) and East Kazakhstan's "normal" (forest-steppe) aren't lumped together.

### 2. LSTM forecast — eight weeks ahead

Code: [`ml/lstm_train.py`](ml/lstm_train.py) and [`ml/lstm_forecast.py`](ml/lstm_forecast.py).

```
Input  : (batch, seq_len = 12, features = 4)
         features = [ndvi, precipitation_mm, soil_moisture_pct, composite_index]
LSTM   : 1 layer, hidden_size = 32
Head   : Linear(32 → 2)
Output : next 2 months of composite_index
```

**Training data.** `ml/build_history.py` produces 60 months of synthetic-but-realistic
history per oblast (climate baselines from `ml/oblasts.py`, monthly seasonal modulation, gaussian noise). Sliding 12-month windows over each oblast's series yield ~46 training windows per oblast → 644 total samples after a strict time-based train / validation split.

**Hyper-parameters.** 80 epochs · batch 32 · Adam @ lr 5 × 10⁻³ · MSE loss · seed 42.
Inputs are z-scored (per-feature mean / std stored alongside the checkpoint).
Trains in roughly 30 seconds on a laptop CPU; the saved checkpoint is 24 KB.

**From 2 months → 8 weeks.** The head emits two monthly steps; we linearly interpolate between *now*, month + 1, and month + 2 to get eight weekly points. Each weekly point gets a 95 % confidence band whose half-width is `validation_mae × 1.96`, so the band visibly widens with horizon.

**Inference.** `ml/lstm_forecast.py` runs offline (e.g. via daily GitHub Actions cron), loads the checkpoint, walks every oblast's last 12 months, and writes `data/seeds/oblast_forecasts.json` — 112 rows, committed back to the repo. Render then re-seeds the SQLite DB on next deploy. The Flask API serves the result through `GET /api/oblasts/<name>/forecast`; the React `AIModelCard` renders it.

### 3. Ground-truth sensor

An ESP32 with a capacitive soil-moisture probe and a DS18B20 soil-temperature sensor sits in
Ust-Kamenogorsk and POSTs JSON every 15 minutes to `POST /api/data`. The dashboard's
`IoTSensorCard` shows the live reading, a 24-hour soil-moisture sparkline, and a delta chip
(soil-moisture change vs. 24 h ago). The point of one node is **not** wall-to-wall coverage —
it's to demonstrate validating remote-sensing estimates with in-situ measurement, the way a
production system would be scaled.

---

## Hardware BOM

Total: **~9,000 ₸** from Kaspi (Kazakhstan).

| Part                                   | Purpose                              |
|----------------------------------------|--------------------------------------|
| ESP32 DevKit v1                        | Wi-Fi microcontroller                |
| Capacitive soil moisture sensor v1.2   | Soil moisture (analog)               |
| DS18B20 (waterproof gilze)             | Soil temperature, OneWire bus        |
| 4.7 kΩ resistor                        | Pull-up for DS18B20 DATA line        |
| Breadboard, jumpers, micro-USB cable   | Wiring                               |

For a field deployment add an IP65 junction box (200 × 120 × 75 mm), 2 PG7 cable glands, a 20 000 mAh power bank with low-current mode, neutral silicone sealant, and a bit of rebar — see the field-deployment checklist in the docs.

Wiring diagram and pin assignments are in [`firmware/README.md`](firmware/README.md).

---

## Limitations & future work

- **Monthly-to-weekly fan-out** — the LSTM emits two monthly forecasts; the eight weekly points
  shown on the dashboard are linearly interpolated. Genuinely-weekly forecasts would need a
  model trained on weekly inputs (Sentinel-2 NDVI is the obvious source).
- **Synthetic history baseline** — the training history uses realistic per-oblast baselines but
  is partly synthesized. Replacing it with the full 2015-onward GEE pull is straightforward
  (`ml/gee_pull.py` is already wired) but takes ~20 minutes and a GEE quota.
- **Single sensor node** — we prove the ground-truth concept with one ESP32 in
  Ust-Kamenogorsk. Scaling to a real network needs one node per oblast minimum.
- **Free Render tier sleeps** — cold starts add ~30 s after 15 min idle. Fine for demos;
  switch to a paid tier or pin the instance with a UptimeRobot ping for production.
- **No alerting yet** — the `alerts` table exists but threshold detection isn't wired into the
  ingest path. SMS / webhook delivery is on the roadmap.
- **No river / reservoir layer** — Kazakhstan's Balkhash / Caspian / Aral basin data is
  fragmented. Integrating Kazhydromet feeds is the next obvious extension.

---

## Credits

- **Author:** [@V1olent77](https://github.com/V1olent77).
- **Coding collaborator:** Anthropic Claude (Sonnet 4.5 / 4.6) — used pair-programming-style
  for backend scaffolding, the React landing, the LSTM training loop, and the field-deployment
  documentation. Every commit was reviewed and accepted by a human.
- **Satellite data:** NASA MODIS, UCSB CHIRPS, ECMWF ERA5 (via Google Earth Engine).
- **Administrative boundaries:** FAO GAUL 2015 level-1.
- **Libraries:** PyTorch, pandas, Flask, React, Tailwind, lucide-react, earthengine-api.

---

## License

MIT.
