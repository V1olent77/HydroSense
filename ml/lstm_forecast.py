"""Generate 8-week-ahead drought forecasts for all 14 oblasts using
the trained LSTM checkpoint.

Pipeline:
  1. Load ml/models/lstm_v1.pt (weights + scaler)
  2. For each oblast: take last SEQ_LEN months from oblast_history.json
  3. Predict next HORIZON months → linearly interpolate to 8 weekly points
  4. Estimate confidence band from training residual std (val_mae * 1.96)
  5. Write data/seeds/oblast_forecasts.json — 8 rows × 14 oblasts = 112

This script is offline (committed JSON is read by the API). Re-run via
GitHub Actions cron daily; commits + pushes the updated JSON; Render
auto-deploys.
"""
from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

import torch
import torch.nn as nn

ROOT = Path(__file__).resolve().parent.parent
HISTORY = ROOT / "data" / "seeds" / "oblast_history.json"
OUTPUT  = ROOT / "data" / "seeds" / "oblast_forecasts.json"
CKPT    = ROOT / "ml" / "models" / "lstm_v1.pt"
META    = ROOT / "ml" / "models" / "lstm_v1_meta.json"

# How many weeks of forecast to fan the 2-month LSTM output into.
WEEKS_AHEAD = 8


class DroughtLSTM(nn.Module):
    """Mirror of training architecture — kept here so the API container
    doesn't need ml/lstm_train.py."""
    def __init__(self, n_features, hidden=32, horizon=2):
        super().__init__()
        self.lstm = nn.LSTM(n_features, hidden, batch_first=True)
        self.head = nn.Linear(hidden, horizon)

    def forward(self, x):
        out, _ = self.lstm(x)
        return self.head(out[:, -1, :])


def load_model():
    blob = torch.load(CKPT, weights_only=False)
    model = DroughtLSTM(
        n_features=len(blob["features"]),
        hidden=blob["hidden"],
        horizon=blob["horizon"],
    )
    model.load_state_dict(blob["state_dict"])
    model.eval()
    mean = torch.tensor(blob["scaler_mean"])
    std = torch.tensor(blob["scaler_std"])
    return model, mean, std, blob


def predict_oblast(model, mean, std, blob, history_months):
    """Returns list of {week_offset, forecast_date, composite_index,
    confidence_lower, confidence_upper} for one oblast."""
    seq_len = blob["seq_len"]
    features = blob["features"]

    # Use last seq_len months as input
    if len(history_months) < seq_len:
        return []  # not enough history
    window = history_months[-seq_len:]
    feat = torch.tensor(
        [[m[f] for f in features] for m in window], dtype=torch.float32
    ).unsqueeze(0)  # (1, seq_len, n_features)

    feat = (feat - mean) / std
    with torch.no_grad():
        pred = model(feat).squeeze(0).tolist()  # 2 monthly composite values

    # Linear-interpolate the 2-month forecast to 8 weekly points.
    # Month 1 = end of week 4, Month 2 = end of week 8.
    last_known = window[-1]["composite_index"]
    week_to_value = []
    for w in range(1, WEEKS_AHEAD + 1):
        if w <= 4:
            # interpolate between last_known and pred[0]
            t = w / 4
            v = last_known * (1 - t) + pred[0] * t
        else:
            t = (w - 4) / 4
            v = pred[0] * (1 - t) + pred[1] * t
        week_to_value.append(round(max(0.0, min(1.0, v)), 3))

    # Confidence band from training val_mae × 1.96 (95% Gaussian).
    meta = json.loads(META.read_text())
    sigma = meta["final_val_mae"] * 1.96

    today = date.today()
    out = []
    for w, v in enumerate(week_to_value, start=1):
        # Forecast widens slightly with horizon (linear ramp).
        w_sigma = sigma * (1 + 0.1 * (w - 1))
        out.append({
            "week_offset": w,
            "forecast_date": (today + timedelta(weeks=w)).isoformat(),
            "composite_index": v,
            "confidence_lower": round(max(0.0, v - w_sigma), 3),
            "confidence_upper": round(min(1.0, v + w_sigma), 3),
        })
    return out


def main():
    payload = json.loads(HISTORY.read_text())
    history = payload["oblasts"]

    model, mean, std, blob = load_model()
    print(f"Loaded model lstm_v1 ({len(blob['features'])} features, "
          f"seq_len={blob['seq_len']}, horizon={blob['horizon']})")

    out = {}
    for oblast, months in history.items():
        forecast = predict_oblast(model, mean, std, blob, sorted(months, key=lambda m: m["month"]))
        if forecast:
            out[oblast] = forecast

    payload_out = {
        "_meta": {
            "model_version": "lstm_v1",
            "weeks_ahead": WEEKS_AHEAD,
            "generated_at": date.today().isoformat(),
            "n_oblasts": len(out),
        },
        "forecasts": out,
    }
    OUTPUT.write_text(json.dumps(payload_out, indent=2))
    print(f"Wrote {WEEKS_AHEAD * len(out)} forecast points → {OUTPUT}")


if __name__ == "__main__":
    main()
