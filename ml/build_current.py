"""Take the most recent month from oblast_history.json and write it as
the 'current state' snapshot for the oblast_indices DB table.

In production this is a tiny one-liner that runs after gee_pull.py;
for now it just slices history.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HISTORY = ROOT / "data" / "seeds" / "oblast_history.json"
OUTPUT  = ROOT / "data" / "seeds" / "oblast_indices.json"


def main():
    payload = json.loads(HISTORY.read_text())
    history = payload["oblasts"]

    # Reuse oblast metadata (lat/lon) from ml/oblasts.py
    import sys
    sys.path.insert(0, str(Path(__file__).parent))
    from oblasts import OBLAST_DICTS, severity_label

    meta_by_name = {d["oblast"]: d for d in OBLAST_DICTS}
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()

    out = []
    for name, months in history.items():
        last = months[-1]
        meta = meta_by_name[name]
        out.append({
            "oblast": name,
            "latitude": meta["latitude"],
            "longitude": meta["longitude"],
            "ndvi": last["ndvi"],
            "precipitation_mm": last["precipitation_mm"],
            "soil_moisture_pct": last["soil_moisture_pct"],
            "composite_index": last["composite_index"],
            "severity": severity_label(last["composite_index"]),
            "updated_at": now,
        })

    OUTPUT.write_text(json.dumps(out, indent=2))
    print(f"Wrote {len(out)} current-state snapshots → {OUTPUT}")


if __name__ == "__main__":
    main()
