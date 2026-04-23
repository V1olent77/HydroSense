# HydroSense firmware

ESP32 sketches for the HydroSense sensor node. Designed to be flashed in
the order below — each test isolates one component so debugging stays
sane when something doesn't work.

## One-time Arduino IDE setup

1. Install the Arduino IDE: <https://www.arduino.cc/en/software>
2. Add the ESP32 board package
   - File → Preferences → Additional Board Manager URLs
   - Add `https://raw.githubusercontent.com/espressif/arduino-esp32/gh-pages/package_esp32_index.json`
   - Tools → Board → Boards Manager → search "ESP32" → install **esp32 by Espressif**
3. Install libraries (Sketch → Include Library → Manage Libraries)
   - **Adafruit BMP280 Library**
   - **Adafruit Unified Sensor** (BMP280 dependency)
   - **DHT sensor library** by Adafruit
4. Tools → Board → **ESP32 Dev Module**
5. Plug the board in. Tools → Port → pick the new COM/tty entry that
   appeared.

If upload fails with `Failed to connect to ESP32`, hold the **BOOT**
button on the board while clicking Upload.

## Recommended bring-up order

| Order | Sketch | Purpose | What to verify |
|---|---|---|---|
| 1 | `test_serial/` | Board + IDE + cable work | Counter prints in Serial Monitor at 115200 baud |
| 2 | `test_soil/` | Capacitive soil sensor | Raw value drops when probe is touched / submerged |
| 3 | `test_bmp280/` | I²C temperature + pressure | Sane temp & ~950–1020 hPa pressure |
| 4 | `test_dht22/` | Humidity + backup temperature | Sane humidity + temp, no NaN |
| 5 | `sensor_node/` | Combined firmware that POSTs to the HydroSense backend | All four readings appear and the API receives them |

## Soil sensor calibration (REQUIRED)

Every capacitive sensor reads slightly different values. Without
calibration the percent reading is meaningless.

1. Flash `test_soil/` so the raw ADC value prints once per second.
2. Hold the dry probe in the air for ~30 s, note the average reading →
   this is `AIR_VALUE` (typically 3000–3500).
3. Submerge **only the bare probe section** (NOT the PCB!) in a glass
   of water for ~30 s, note the average → this is `WATER_VALUE`
   (typically 1300–1700).
4. Open `firmware/sensor_node/sensor_node.ino` and replace the two
   constants near the top:

   ```c
   const int AIR_VALUE   = 3400;  // ← your dry-air reading
   const int WATER_VALUE = 1500;  // ← your submerged reading
   ```

`scripts/calibrate_soil.py` automates this — point it at the COM port
that the ESP32 is on and it walks through the two measurements.

## Wiring summary (combined firmware)

```
ESP32 Dev Module
  3.3V  ──────► BMP280 VCC, Soil VCC, DHT22 VCC
  GND   ──────► BMP280 GND, Soil GND, DHT22 GND
  GPIO21 (SDA) ► BMP280 SDA
  GPIO22 (SCL) ► BMP280 SCL
  GPIO34 (ADC) ► Soil sensor AOUT
  GPIO4        ► DHT22 DATA
```

**Critical:** the BMP280 ships with separate pin headers — these MUST
be soldered before the board can plug into the breadboard. If you've
never soldered, watch one short YouTube tutorial. It's not hard.

## Configuring the combined firmware

Before flashing `sensor_node/`, edit the four constants at the top:

```c
const char* ssid      = "YOUR_WIFI_SSID";
const char* password  = "YOUR_WIFI_PASSWORD";
const char* serverURL = "http://YOUR_BACKEND_HOST:5001/api/data";
const char* nodeId    = "node_01";
```

`serverURL` options:
- **Same WiFi network** — use your laptop's local IP, e.g.
  `http://192.168.1.42:5001/api/data`. Make sure `api.py` is running.
- **Public URL** — run `ngrok http 5000` to get a public tunnel to
  your local Flask server, then paste the ngrok HTTPS URL here.
- **Cloud-hosted** — deploy `api.py` to Render/Railway and use that
  URL.

If you're deploying somewhere with no WiFi, see the SD-card fallback
section at the bottom of `/Users/alanmusahitov/Downloads/aquasight_guide.md`.

## Sanity-check checklist before field deployment

- [ ] All four test sketches print sensible values
- [ ] Soil sensor calibrated (your AIR_VALUE / WATER_VALUE in the .ino)
- [ ] Combined firmware has been running on the bench for ≥ 1 hour
      without crashing or memory issues
- [ ] At least 4 successful POSTs visible in the Flask log / dashboard
- [ ] Power bank stays on with the ESP32 connected for ≥ 2 hours
      (some banks auto-shutoff at low current draw — see guide §Power)
