"""
HydroSense forecast layer — LSTM trained on monthly per-oblast indices.

Predicts drought_risk 2 months ahead (~8 weeks) from a 12-month lookback.
Reads data/processed/monthly_indices.csv produced by time_series.py.
"""
import os
from pathlib import Path

import numpy as np
import pandas as pd
import torch
from torch import nn
from torch.utils.data import DataLoader, TensorDataset
import matplotlib.pyplot as plt

# === CONFIG ===========================================================
ROOT = Path("/Users/alanmusahitov/Desktop/sft stuff")
CSV_IN = ROOT / "data" / "processed" / "monthly_indices.csv"
OUT_DIR = ROOT / "data" / "processed"
MODEL_PATH = OUT_DIR / "forecast_model.pt"
FORECAST_CSV = OUT_DIR / "forecast.csv"
EVAL_PNG = OUT_DIR / "forecast_eval.png"

LOOKBACK = 12           # months of history fed to the LSTM
HORIZON = 2             # months ahead to predict (~8 weeks)
FEATURES = ["ndvi", "precip_mm", "temp_c", "vhi", "spi", "temp_anomaly", "drought_risk"]
TARGET = "drought_risk"

TRAIN_END = "2022-12-31"
VAL_END = "2023-12-31"

HIDDEN = 64
LAYERS = 2
DROPOUT = 0.2
LR = 1e-3
EPOCHS = 80
BATCH = 128
SEED = 42

DEVICE = torch.device("cuda" if torch.cuda.is_available()
                     else "mps" if torch.backends.mps.is_available()
                     else "cpu")

# === LOAD =============================================================
if not CSV_IN.exists():
    raise SystemExit(f"Missing {CSV_IN}. Run time_series.py first.")

df = pd.read_csv(CSV_IN, parse_dates=["date"]).sort_values(["oblast", "date"]).reset_index(drop=True)
oblasts = sorted(df["oblast"].unique())
oblast_idx = {o: i for i, o in enumerate(oblasts)}
N_OBLAST = len(oblasts)
print(f"Loaded {len(df):,} rows · {N_OBLAST} oblasts · {df['date'].min().date()} → {df['date'].max().date()}")

# Fill missing satellite readings BEFORE normalizing — MODIS skips
# snow-covered pixels, so winter NDVI has gaps that would otherwise
# produce NaN losses during training.
df[FEATURES] = (
    df.groupby("oblast")[FEATURES]
      .transform(lambda s: s.interpolate(limit_direction="both"))
)
# Anything still NaN (e.g. an oblast missing an entire feature) → 0,
# which is the post-normalization mean and a safe neutral value.
df[FEATURES] = df[FEATURES].fillna(0.0)
n_nan_remaining = int(df[FEATURES].isna().sum().sum())
assert n_nan_remaining == 0, f"{n_nan_remaining} NaN values still in features"

# Normalize continuous features on the training window only to avoid leakage.
train_mask = df["date"] <= TRAIN_END
mu = df.loc[train_mask, FEATURES].mean()
sigma = df.loc[train_mask, FEATURES].std().replace(0, 1.0)
df[FEATURES] = (df[FEATURES] - mu) / sigma

# === SEQUENCE BUILDER =================================================
def build_sequences(frame: pd.DataFrame):
    """Return (X, oblast_idx, y, target_date) arrays for every valid window."""
    X, O, y, T = [], [], [], []
    for oblast, sub in frame.groupby("oblast"):
        sub = sub.sort_values("date").reset_index(drop=True)
        vals = sub[FEATURES].to_numpy(dtype=np.float32)
        dates = sub["date"].to_numpy()
        for i in range(len(sub) - LOOKBACK - HORIZON + 1):
            X.append(vals[i:i + LOOKBACK])
            y.append(vals[i + LOOKBACK + HORIZON - 1, FEATURES.index(TARGET)])
            O.append(oblast_idx[oblast])
            T.append(dates[i + LOOKBACK + HORIZON - 1])
    return (np.stack(X), np.array(O, dtype=np.int64),
            np.array(y, dtype=np.float32), np.array(T))

X_all, O_all, y_all, T_all = build_sequences(df)

# Split by the date of the *target*, not the input window.
train_cut = np.datetime64(TRAIN_END)
val_cut = np.datetime64(VAL_END)
train_ix = T_all <= train_cut
val_ix = (T_all > train_cut) & (T_all <= val_cut)
test_ix = T_all > val_cut
print(f"Windows — train {train_ix.sum()}, val {val_ix.sum()}, test {test_ix.sum()}")

# === DATASET ==========================================================
def make_loader(mask: np.ndarray, shuffle: bool) -> DataLoader:
    ds = TensorDataset(
        torch.from_numpy(X_all[mask]),
        torch.from_numpy(O_all[mask]),
        torch.from_numpy(y_all[mask]),
    )
    return DataLoader(ds, batch_size=BATCH, shuffle=shuffle)

train_loader = make_loader(train_ix, shuffle=True)
val_loader = make_loader(val_ix, shuffle=False)
test_loader = make_loader(test_ix, shuffle=False)

# === MODEL ============================================================
class DroughtLSTM(nn.Module):
    def __init__(self, n_features: int, n_oblasts: int, hidden: int, layers: int, dropout: float):
        super().__init__()
        self.embed = nn.Embedding(n_oblasts, 8)
        self.lstm = nn.LSTM(
            input_size=n_features + 8,
            hidden_size=hidden,
            num_layers=layers,
            dropout=dropout if layers > 1 else 0.0,
            batch_first=True,
        )
        self.head = nn.Sequential(
            nn.Linear(hidden, hidden // 2),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(hidden // 2, 1),
        )

    def forward(self, x: torch.Tensor, oblast: torch.Tensor) -> torch.Tensor:
        emb = self.embed(oblast).unsqueeze(1).expand(-1, x.size(1), -1)
        out, _ = self.lstm(torch.cat([x, emb], dim=-1))
        return self.head(out[:, -1, :]).squeeze(-1)


torch.manual_seed(SEED)
np.random.seed(SEED)
model = DroughtLSTM(len(FEATURES), N_OBLAST, HIDDEN, LAYERS, DROPOUT).to(DEVICE)
opt = torch.optim.Adam(model.parameters(), lr=LR)
loss_fn = nn.MSELoss()

# === TRAIN ============================================================
def run_epoch(loader: DataLoader, train: bool) -> float:
    model.train(train)
    total, n = 0.0, 0
    for xb, ob, yb in loader:
        xb, ob, yb = xb.to(DEVICE), ob.to(DEVICE), yb.to(DEVICE)
        if train:
            opt.zero_grad()
        pred = model(xb, ob)
        loss = loss_fn(pred, yb)
        if train:
            loss.backward()
            opt.step()
        total += loss.item() * xb.size(0)
        n += xb.size(0)
    return total / n

best_val, best_state, patience, bad = float("inf"), None, 12, 0
for epoch in range(1, EPOCHS + 1):
    tr = run_epoch(train_loader, train=True)
    with torch.no_grad():
        va = run_epoch(val_loader, train=False)
    if va < best_val - 1e-4:
        best_val, best_state, bad = va, {k: v.detach().cpu().clone() for k, v in model.state_dict().items()}, 0
    else:
        bad += 1
    if epoch % 5 == 0 or epoch == 1:
        print(f"epoch {epoch:3d} · train {tr:.4f} · val {va:.4f} · best {best_val:.4f}")
    if bad >= patience:
        print(f"early stop at epoch {epoch}")
        break

if best_state is None:
    raise RuntimeError(
        "Training failed: no valid checkpoint was saved (val loss never improved). "
        "Most common cause is NaN/Inf in features — check the assertion above."
    )
model.load_state_dict(best_state)
os.makedirs(OUT_DIR, exist_ok=True)
torch.save({
    "state_dict": best_state,
    "feature_mu": mu.to_dict(),
    "feature_sigma": sigma.to_dict(),
    "oblasts": oblasts,
    "features": FEATURES,
    "lookback": LOOKBACK,
    "horizon": HORIZON,
}, MODEL_PATH)
print(f"Model saved → {MODEL_PATH}")

# === EVALUATE + FORECAST ==============================================
def predict(loader: DataLoader) -> np.ndarray:
    model.eval()
    out = []
    with torch.no_grad():
        for xb, ob, _ in loader:
            out.append(model(xb.to(DEVICE), ob.to(DEVICE)).cpu().numpy())
    return np.concatenate(out)

# De-normalize predictions back to the 0–100 drought_risk scale.
target_mu, target_sigma = mu[TARGET], sigma[TARGET]
def denorm(arr: np.ndarray) -> np.ndarray:
    return arr * target_sigma + target_mu

test_pred = denorm(predict(test_loader))
test_true = denorm(y_all[test_ix])
rmse = float(np.sqrt(np.mean((test_pred - test_true) ** 2)))
mae = float(np.mean(np.abs(test_pred - test_true)))
print(f"\nTest set ({test_ix.sum()} windows) — RMSE {rmse:.2f} · MAE {mae:.2f} (drought_risk 0–100)")

# Residual std gives a simple uncertainty band for the dashboard.
val_pred = denorm(predict(val_loader))
val_true = denorm(y_all[val_ix])
resid_std = float(np.std(val_pred - val_true))

forecast_df = pd.DataFrame({
    "date": T_all[test_ix],
    "oblast": [oblasts[i] for i in O_all[test_ix]],
    "predicted_risk": test_pred,
    "actual_risk": test_true,
    "lower_95": test_pred - 1.96 * resid_std,
    "upper_95": test_pred + 1.96 * resid_std,
})
forecast_df.to_csv(FORECAST_CSV, index=False)
print(f"Forecasts saved → {FORECAST_CSV}")

# === PLOT =============================================================
plt.style.use("dark_background")
fig, axes = plt.subplots(2, 1, figsize=(14, 8), facecolor="#0f0f0f")

# National mean: actual vs predicted on the test window.
nat = forecast_df.groupby("date")[["predicted_risk", "actual_risk", "lower_95", "upper_95"]].mean().reset_index()
axes[0].fill_between(nat["date"], nat["lower_95"], nat["upper_95"], color="#d7191c", alpha=0.15, label="95% band")
axes[0].plot(nat["date"], nat["actual_risk"], color="white", linewidth=2, label="Actual")
axes[0].plot(nat["date"], nat["predicted_risk"], color="#d7191c", linewidth=2, linestyle="--", label="Predicted (+2mo)")
axes[0].set_title(
    f"HydroSense forecast — national mean drought risk · test 2024 · RMSE {rmse:.1f} · MAE {mae:.1f}",
    color="white", fontsize=14, fontweight="bold", pad=12,
)
axes[0].set_ylabel("Drought risk", color="white")
axes[0].set_ylim(0, 100)
axes[0].legend(loc="upper left", facecolor="#0f0f0f", edgecolor="#333333", labelcolor="white")

# Scatter of predicted vs actual across all test windows.
axes[1].scatter(forecast_df["actual_risk"], forecast_df["predicted_risk"],
                s=12, alpha=0.5, color="#d7191c", edgecolors="none")
lim = [0, 100]
axes[1].plot(lim, lim, color="#888888", linestyle="--", linewidth=1)
axes[1].set_xlim(lim); axes[1].set_ylim(lim)
axes[1].set_xlabel("Actual risk", color="white")
axes[1].set_ylabel("Predicted risk", color="white")
axes[1].set_title("Per-oblast predictions vs ground truth", color="white", fontsize=12)

for ax in axes:
    ax.set_facecolor("#0f0f0f")
    ax.tick_params(colors="#888888")
    ax.grid(alpha=0.15)
    for s in ax.spines.values():
        s.set_edgecolor("#333333")

fig.text(0.01, 0.005,
         "LSTM · 12-mo lookback · 2-mo horizon · trained 2015–2022 · HydroSense",
         color="#666666", fontsize=8)

plt.tight_layout()
plt.savefig(EVAL_PNG, dpi=180, bbox_inches="tight", facecolor="#0f0f0f")
print(f"Eval chart saved → {EVAL_PNG}")
