import os
import time
from datetime import datetime

import ee
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

# === CONFIG ===========================================================
PROJECT = os.environ.get("GEE_PROJECT")
START = "2015-01-01"
END = "2024-12-31"
OUT_DIR = "/Users/alanmusahitov/Desktop/sft stuff/data/processed"
CSV_PATH = os.path.join(OUT_DIR, "monthly_indices.csv")
PNG_PATH = os.path.join(OUT_DIR, "drought_time_series.png")
SCALE = 5000  # metres — regional aggregation resolution

# === INIT GEE =========================================================
if not PROJECT:
    raise SystemExit(
        "Set GEE_PROJECT to your Earth Engine Cloud project id, e.g.:\n"
        "  export GEE_PROJECT=your-project-id"
    )
ee.Initialize(project=PROJECT)

# === AOI: Kazakhstan oblasts (GAUL level-1) ===========================
oblasts = ee.FeatureCollection("FAO/GAUL/2015/level1").filter(
    ee.Filter.eq("ADM0_NAME", "Kazakhstan")
)

# === MONTHLY DATE LIST ================================================
def month_starts(start: str, end: str) -> list[str]:
    out = []
    d = datetime.strptime(start, "%Y-%m-%d").replace(day=1)
    last = datetime.strptime(end, "%Y-%m-%d")
    while d <= last:
        out.append(d.strftime("%Y-%m-%d"))
        d = d.replace(year=d.year + (d.month // 12), month=(d.month % 12) + 1)
    return out

months = month_starts(START, END)
print(f"Pulling {len(months)} months × {oblasts.size().getInfo()} oblasts ({START} → {END})")

# === DATASETS =========================================================
NDVI = ee.ImageCollection("MODIS/061/MOD13A2").select("NDVI")
PRECIP = ee.ImageCollection("UCSB-CHG/CHIRPS/DAILY").select("precipitation")
TEMP = ee.ImageCollection("ECMWF/ERA5_LAND/MONTHLY_AGGR").select("temperature_2m")


def monthly_by_oblast(coll: ee.ImageCollection, band: str, agg: str) -> list:
    """One feature per (month, oblast) with the regional mean of `band`.

    Issues one getInfo() per month so we don't trip GEE's
    "too many concurrent aggregations" rate limit. ~120 calls per
    dataset; the small per-call latency is fine and far more reliable
    than a single huge server-side reduction.
    """
    all_features = []
    total = len(months)
    for i, start_str in enumerate(months, 1):
        start = ee.Date(start_str)
        end = start.advance(1, "month")
        sub = coll.filterDate(start, end)
        img = sub.sum() if agg == "sum" else sub.mean()
        reduced = img.reduceRegions(
            collection=oblasts,
            reducer=ee.Reducer.mean(),
            scale=SCALE,
        ).select(["ADM1_NAME", "mean"], retainGeometry=False)

        # Retry once on the same 429 / transient GEE hiccups.
        for attempt in range(3):
            try:
                month_feats = reduced.getInfo()["features"]
                break
            except ee.EEException as exc:
                if attempt == 2:
                    raise
                wait = 5 * (attempt + 1)
                print(f"  [{start_str}] retrying in {wait}s after: {exc}")
                time.sleep(wait)

        for f in month_feats:
            f["properties"]["date"] = start_str
        all_features.extend(month_feats)

        if i % 12 == 0 or i == total:
            print(f"   {i:3d}/{total} months  ({start_str[:7]})")
    return all_features


print("→ NDVI (MODIS)")
ndvi_feats = monthly_by_oblast(NDVI, "NDVI", "mean")
print("→ Precipitation (CHIRPS)")
precip_feats = monthly_by_oblast(PRECIP, "precipitation", "sum")
print("→ Temperature (ERA5)")
temp_feats = monthly_by_oblast(TEMP, "temperature_2m", "mean")


def to_df(feats: list, col: str) -> pd.DataFrame:
    rows = [(f["properties"]["date"], f["properties"]["ADM1_NAME"], f["properties"].get("mean"))
            for f in feats]
    df = pd.DataFrame(rows, columns=["date", "oblast", col])
    df["date"] = pd.to_datetime(df["date"])
    return df


df = (
    to_df(ndvi_feats, "ndvi_raw")
    .merge(to_df(precip_feats, "precip_mm"), on=["date", "oblast"])
    .merge(to_df(temp_feats, "temp_k"), on=["date", "oblast"])
    .sort_values(["oblast", "date"])
    .reset_index(drop=True)
)

# MODIS NDVI is scaled by 10_000; ERA5 temperature is in Kelvin.
df["ndvi"] = df["ndvi_raw"] / 10_000.0
df["temp_c"] = df["temp_k"] - 273.15

# === DROUGHT INDICES (computed per oblast) ============================
# VHI: NDVI rescaled 0–100 within each oblast's own 10-year range.
def vhi(s: pd.Series) -> pd.Series:
    lo, hi = s.min(), s.max()
    return (s - lo) / (hi - lo) * 100 if hi > lo else s * 0

df["vhi"] = df.groupby("oblast")["ndvi"].transform(vhi)

# SPI / temp anomaly: z-score each calendar month against that oblast's
# own climatology, so seasonal cycles and regional means don't dominate.
df["month_num"] = df["date"].dt.month
df["spi"] = df.groupby(["oblast", "month_num"])["precip_mm"].transform(
    lambda s: (s - s.mean()) / s.std() if s.std() > 0 else s * 0
)
df["temp_anomaly"] = df.groupby(["oblast", "month_num"])["temp_c"].transform(
    lambda s: (s - s.mean()) / s.std() if s.std() > 0 else s * 0
)

df["drought_risk"] = (
    (100 - df["vhi"]) * 0.4
    + (-df["spi"] * 20).clip(0, 100) * 0.4
    + (df["temp_anomaly"] * 10).clip(0, 100) * 0.2
).clip(0, 100)

df = df.drop(columns=["month_num", "ndvi_raw", "temp_k"])
os.makedirs(OUT_DIR, exist_ok=True)
df.to_csv(CSV_PATH, index=False)
print(f"\nSaved {len(df):,} rows ({df['oblast'].nunique()} oblasts × {df['date'].nunique()} months) → {CSV_PATH}")

# === PLOT: national mean + per-oblast drought risk ====================
national = df.groupby("date")[["ndvi", "precip_mm", "temp_c", "drought_risk"]].mean().reset_index()

plt.style.use("dark_background")
fig, axes = plt.subplots(4, 1, figsize=(14, 11), sharex=True, facecolor="#0f0f0f")

axes[0].plot(national["date"], national["ndvi"], color="#a6d96a")
axes[0].set_ylabel("NDVI", color="white")
axes[0].set_title(
    f"Kazakhstan monthly drought indicators ({START[:4]}–{END[:4]}) — historical assessment",
    color="white", fontsize=14, fontweight="bold", pad=12,
)

axes[1].plot(national["date"], national["precip_mm"], color="#74add1")
axes[1].set_ylabel("Precip (mm)", color="white")

axes[2].plot(national["date"], national["temp_c"], color="#fdae61")
axes[2].set_ylabel("Temp (°C)", color="white")

# Faint per-oblast lines + bold national mean for the risk panel.
for name, sub in df.groupby("oblast"):
    axes[3].plot(sub["date"], sub["drought_risk"], color="#d7191c", alpha=0.12, linewidth=0.8)
axes[3].plot(national["date"], national["drought_risk"], color="#d7191c", linewidth=2, label="National mean")
axes[3].set_ylabel("Drought risk", color="white")
axes[3].set_ylim(0, 100)
axes[3].axhspan(75, 100, alpha=0.1, color="#d7191c")
axes[3].legend(loc="upper left", facecolor="#0f0f0f", edgecolor="#333333", labelcolor="white")

for ax in axes:
    ax.set_facecolor("#0f0f0f")
    ax.tick_params(colors="#888888")
    ax.grid(alpha=0.15)
    for s in ax.spines.values():
        s.set_edgecolor("#333333")

axes[-1].xaxis.set_major_locator(mdates.YearLocator())
axes[-1].xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
fig.text(
    0.01, 0.005,
    "Sources: MODIS NDVI · CHIRPS · ERA5 (via Google Earth Engine) — HydroSense",
    color="#666666", fontsize=8,
)

plt.tight_layout()
plt.savefig(PNG_PATH, dpi=180, bbox_inches="tight", facecolor="#0f0f0f")
print(f"Chart saved → {PNG_PATH}")
