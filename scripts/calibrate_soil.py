"""
Soil sensor calibration helper — walks you through recording the raw
ADC values in dry air and fully submerged, then prints the two
constants to paste into firmware/sensor_node/sensor_node.ino.

What it expects:
    - The ESP32 is plugged in via USB and running firmware/test_soil/.
    - That sketch prints lines like "Soil raw ADC: 3412 (...)" every
      500 ms at 115200 baud.

How to run:
    python -m pip install pyserial          # one-time, if not installed
    python scripts/calibrate_soil.py        # lists available ports
    python scripts/calibrate_soil.py --port /dev/cu.usbserial-0001

On macOS the ESP32 typically shows up as /dev/cu.usbserial-XXXX or
/dev/cu.SLAB_USBtoUART depending on which USB-serial chip the dev
board uses. Run the script with no arguments to see the full list.
"""
import argparse
import re
import statistics
import sys
import time
from pathlib import Path

try:
    import serial
    import serial.tools.list_ports
except ImportError:
    print("pyserial is not installed. Install it first:")
    print("    python -m pip install pyserial")
    sys.exit(1)

BAUD = 115200
SAMPLES_PER_PHASE = 50
ADC_LINE_RE = re.compile(r"Soil raw ADC:\s*(-?\d+)")


def list_ports() -> None:
    ports = list(serial.tools.list_ports.comports())
    if not ports:
        print("No serial devices detected. Is the ESP32 plugged in?")
        return
    print("Detected serial ports:")
    for p in ports:
        print(f"  {p.device}   ({p.description})")
    print("\nRerun with --port <one of the above>.")


def collect(ser: "serial.Serial", n: int, label: str) -> int:
    """Read n valid ADC lines and return the rounded mean."""
    values: list[int] = []
    print(f"\n[{label}] collecting {n} samples...")
    deadline = time.time() + 60  # give the ESP32 at most a minute
    while len(values) < n and time.time() < deadline:
        raw = ser.readline().decode("utf-8", errors="ignore").strip()
        match = ADC_LINE_RE.search(raw)
        if not match:
            continue
        val = int(match.group(1))
        values.append(val)
        # Live progress in-place
        print(f"  sample {len(values):2d}/{n}   ADC = {val}", end="\r")
    print()  # newline after progress
    if len(values) < n:
        print(f"  WARNING: only got {len(values)}/{n} samples — check the ESP32 is running test_soil.ino at 115200 baud.")
        if not values:
            raise SystemExit("No samples collected; aborting.")
    mean = round(statistics.mean(values))
    stdev = round(statistics.stdev(values)) if len(values) > 1 else 0
    lo, hi = min(values), max(values)
    print(f"  [{label}] mean={mean}  stdev={stdev}  range={lo}–{hi}")
    return mean


def patch_firmware(air: int, water: int) -> None:
    """Offer to edit the AIR_VALUE / WATER_VALUE in sensor_node.ino."""
    ino = Path(__file__).resolve().parent.parent / "firmware" / "sensor_node" / "sensor_node.ino"
    if not ino.exists():
        print(f"(can't find {ino} to auto-patch — paste the values manually)")
        return

    answer = input(f"\nPatch {ino} with these values? [y/N] ").strip().lower()
    if answer != "y":
        return

    src = ino.read_text()
    new = re.sub(r"const int AIR_VALUE\s*=\s*\d+;", f"const int AIR_VALUE   = {air};", src)
    new = re.sub(r"const int WATER_VALUE\s*=\s*\d+;", f"const int WATER_VALUE = {water};", new)
    if new == src:
        print("Couldn't find the AIR_VALUE/WATER_VALUE lines — paste manually.")
        return
    ino.write_text(new)
    print(f"Updated {ino}")


def main() -> None:
    p = argparse.ArgumentParser(description="Calibrate the capacitive soil moisture sensor.")
    p.add_argument("--port", help="Serial port (e.g. /dev/cu.usbserial-0001). Omit to list ports.")
    p.add_argument("--samples", type=int, default=SAMPLES_PER_PHASE,
                   help=f"samples per phase (default {SAMPLES_PER_PHASE})")
    args = p.parse_args()

    if not args.port:
        list_ports()
        return

    print(f"Opening {args.port} @ {BAUD} baud...")
    try:
        ser = serial.Serial(args.port, BAUD, timeout=2)
    except serial.SerialException as exc:
        raise SystemExit(f"Couldn't open {args.port}: {exc}")

    # Give the ESP32 a moment to reset after opening the port.
    time.sleep(2)
    ser.reset_input_buffer()

    try:
        input("Step 1/2 — hold the sensor in DRY AIR (don't touch the probe), then press Enter.")
        air = collect(ser, args.samples, "AIR")

        input("\nStep 2/2 — submerge ONLY the bare probe in water (keep the PCB dry), then press Enter.")
        water = collect(ser, args.samples, "WATER")
    finally:
        ser.close()

    if air <= water:
        print("\nWARNING: air reading is not higher than water reading.")
        print("Capacitive sensors normally read HIGHER in dry air. Double-check wiring / phase order.")

    print("\n" + "=" * 55)
    print("Paste these into firmware/sensor_node/sensor_node.ino:")
    print("=" * 55)
    print(f"const int AIR_VALUE   = {air};   // dry-air reading")
    print(f"const int WATER_VALUE = {water};   // submerged reading")
    print("=" * 55)

    patch_firmware(air, water)
    print("\nDone. Reflash sensor_node.ino to use the new calibration.")


if __name__ == "__main__":
    main()
