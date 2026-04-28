"""Train a small LSTM to forecast monthly composite drought index from
the past 12 months → next 2 months for each Kazakhstan oblast.

Architecture:
  Input:  (batch, seq_len=12, features=4)   features = [ndvi, precip, soil, composite]
  LSTM:   1 layer, hidden_size=32
  Head:   Linear(32 → 2)                    output = next 2 months of composite

Training data:
  ml/build_history.py output (60 monthly samples per oblast).
  Sliding-window over each oblast's series → ~46 windows per oblast → 644 total
  samples after train/val split.

Saves:
  ml/models/lstm_v1.pt        — model weights + scaler params
  ml/models/lstm_v1_meta.json — train/val loss curves, hyper-params

Run:
  python ml/lstm_train.py
  # ~30 sec on a laptop CPU. PyTorch needed only when this runs.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import torch
import torch.nn as nn
from torch.utils.data import DataLoader, TensorDataset

ROOT = Path(__file__).resolve().parent.parent
HISTORY = ROOT / "data" / "seeds" / "oblast_history.json"
MODELS = Path(__file__).resolve().parent / "models"
MODELS.mkdir(parents=True, exist_ok=True)
CKPT = MODELS / "lstm_v1.pt"
META = MODELS / "lstm_v1_meta.json"

# Hyper-params
SEQ_LEN = 12          # past months we look at
HORIZON = 2           # months we forecast (we'll fan out 2 mo → 8 weeks linearly)
HIDDEN = 32
EPOCHS = 80
BATCH = 32
LR = 5e-3
SEED = 42
FEATURES = ["ndvi", "precipitation_mm", "soil_moisture_pct", "composite_index"]
TARGET = "composite_index"


def load_series():
    """Returns dict {oblast: list_of_dicts (sorted by month)}."""
    payload = json.loads(HISTORY.read_text())
    out = {}
    for ob, months in payload["oblasts"].items():
        out[ob] = sorted(months, key=lambda m: m["month"])
    return out


def build_windows(series):
    """Sliding windows of (SEQ_LEN, num_features) → (HORIZON,) targets.
    Returns (X, y) numpy-style tensors."""
    X, y = [], []
    for ob, months in series.items():
        if len(months) < SEQ_LEN + HORIZON:
            continue
        feat = torch.tensor(
            [[m[f] for f in FEATURES] for m in months], dtype=torch.float32
        )
        tgt = torch.tensor([m[TARGET] for m in months], dtype=torch.float32)
        for i in range(len(months) - SEQ_LEN - HORIZON + 1):
            X.append(feat[i : i + SEQ_LEN])
            y.append(tgt[i + SEQ_LEN : i + SEQ_LEN + HORIZON])
    return torch.stack(X), torch.stack(y)


def fit_scaler(X):
    """Per-feature mean/std over training set. Returns (mean, std) tensors."""
    flat = X.reshape(-1, X.shape[-1])
    mean = flat.mean(dim=0)
    std = flat.std(dim=0).clamp(min=1e-6)
    return mean, std


def normalize(X, mean, std):
    return (X - mean) / std


class DroughtLSTM(nn.Module):
    def __init__(self, n_features, hidden=HIDDEN, horizon=HORIZON):
        super().__init__()
        self.lstm = nn.LSTM(n_features, hidden, batch_first=True)
        self.head = nn.Linear(hidden, horizon)

    def forward(self, x):
        out, _ = self.lstm(x)
        return self.head(out[:, -1, :])  # last timestep → horizon outputs


def train():
    torch.manual_seed(SEED)
    series = load_series()
    X, y = build_windows(series)
    print(f"Total windows: {X.shape[0]}, X={tuple(X.shape)}, y={tuple(y.shape)}")

    # 80/20 split (stratification not needed — synthetic, ~uniform)
    n_train = int(0.8 * X.shape[0])
    perm = torch.randperm(X.shape[0])
    X, y = X[perm], y[perm]
    X_tr, y_tr = X[:n_train], y[:n_train]
    X_va, y_va = X[n_train:], y[n_train:]

    mean, std = fit_scaler(X_tr)
    X_tr = normalize(X_tr, mean, std)
    X_va = normalize(X_va, mean, std)

    train_loader = DataLoader(
        TensorDataset(X_tr, y_tr), batch_size=BATCH, shuffle=True
    )

    model = DroughtLSTM(len(FEATURES))
    opt = torch.optim.Adam(model.parameters(), lr=LR)
    crit = nn.MSELoss()

    history = []
    for epoch in range(1, EPOCHS + 1):
        model.train()
        tr_loss = 0.0
        for xb, yb in train_loader:
            opt.zero_grad()
            pred = model(xb)
            loss = crit(pred, yb)
            loss.backward()
            opt.step()
            tr_loss += loss.item() * xb.shape[0]
        tr_loss /= len(train_loader.dataset)

        model.eval()
        with torch.no_grad():
            va_pred = model(X_va)
            va_loss = crit(va_pred, y_va).item()
            va_mae = (va_pred - y_va).abs().mean().item()

        history.append({"epoch": epoch, "train_mse": tr_loss,
                        "val_mse": va_loss, "val_mae": va_mae})

        if epoch == 1 or epoch % 10 == 0 or epoch == EPOCHS:
            print(f"  epoch {epoch:3d}  train_mse={tr_loss:.4f}  "
                  f"val_mse={va_loss:.4f}  val_mae={va_mae:.4f}")

    # Save state + scaler params + hyper-params (everything needed to predict).
    torch.save({
        "state_dict": model.state_dict(),
        "scaler_mean": mean.tolist(),
        "scaler_std": std.tolist(),
        "features": FEATURES,
        "seq_len": SEQ_LEN,
        "horizon": HORIZON,
        "hidden": HIDDEN,
    }, CKPT)
    print(f"Saved model checkpoint → {CKPT}")

    # Persist training metadata
    META.write_text(json.dumps({
        "model_version": "lstm_v1",
        "trained_on": "ml/build_history.py synthetic v1 (seed=42)",
        "n_windows": int(X.shape[0]),
        "n_train": int(n_train),
        "n_val": int(X.shape[0] - n_train),
        "epochs": EPOCHS,
        "final_val_mae": history[-1]["val_mae"],
        "final_val_mse": history[-1]["val_mse"],
        "history": history,
    }, indent=2))
    print(f"Saved training meta → {META}")


if __name__ == "__main__":
    train()
