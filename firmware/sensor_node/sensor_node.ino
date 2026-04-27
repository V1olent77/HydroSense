// HydroSense sensor node — ESP32 + capacitive soil moisture + DS18B20.
// Upload via Arduino IDE (Board: "ESP32 Dev Module", baud 115200).
//
// Libraries required (Library Manager):
//   - OneWire
//   - DallasTemperature

#include <WiFi.h>
#include <HTTPClient.h>
#include <OneWire.h>
#include <DallasTemperature.h>

// --- Configuration ---------------------------------------------------
// Fill these in locally before flashing. Do NOT commit real credentials.
const char* ssid      = "YOUR_WIFI_SSID";
const char* password  = "YOUR_WIFI_PASSWORD";
const char* serverURL = "http://YOUR_BACKEND_HOST:5001/api/data";
const char* nodeId    = "node_01";

// --- Sensor pins -----------------------------------------------------
#define SOIL_PIN     34   // analog, capacitive soil moisture AOUT
#define ONE_WIRE_PIN 5    // digital, DS18B20 DATA (needs 4.7k pull-up to 3.3V)

// --- Soil calibration (run scripts/calibrate_soil.py to dial these in)
const int AIR_VALUE   = 3400;
const int WATER_VALUE = 1500;

// --- Reading cadence -------------------------------------------------
const unsigned long INTERVAL_MS = 900000; // 15 minutes

OneWire oneWire(ONE_WIRE_PIN);
DallasTemperature ds18b20(&oneWire);

bool dsOk = false;

void setup() {
  Serial.begin(115200);
  delay(300);
  Serial.println("\nHydroSense sensor node v1.2 (soil + DS18B20)");

  WiFi.begin(ssid, password);
  Serial.print("Connecting to WiFi");
  int attempts = 0;
  while (WiFi.status() != WL_CONNECTED && attempts < 30) {
    delay(500);
    Serial.print(".");
    attempts++;
  }
  if (WiFi.status() == WL_CONNECTED) {
    Serial.println("\nWiFi connected: " + WiFi.localIP().toString());
  } else {
    Serial.println("\nWiFi FAILED — readings will still print locally.");
  }

  // DS18B20
  ds18b20.begin();
  int dsCount = ds18b20.getDeviceCount();
  if (dsCount > 0) {
    Serial.printf("DS18B20 initialized — %d sensor(s) on bus\n", dsCount);
    dsOk = true;
  } else {
    Serial.println("DS18B20 NOT FOUND — check DATA=GPIO5 and the 4.7k pull-up resistor.");
  }

  Serial.println("Setup complete.\n");
}

void loop() {
  // Reconnect WiFi if it dropped (keeps long-running sensor alive)
  if (WiFi.status() != WL_CONNECTED) {
    WiFi.reconnect();
  }

  // --- Soil moisture ---
  int rawSoil = analogRead(SOIL_PIN);
  int soilPct = constrain(map(rawSoil, AIR_VALUE, WATER_VALUE, 0, 100), 0, 100);

  // --- DS18B20: soil temperature ---
  float soilTemp = NAN;
  if (dsOk) {
    ds18b20.requestTemperatures();
    soilTemp = ds18b20.getTempCByIndex(0);
    if (soilTemp == DEVICE_DISCONNECTED_C) soilTemp = NAN;
  }

  Serial.println("---- Reading ----");
  Serial.printf("Soil:      %d%%   (raw %d)\n", soilPct, rawSoil);
  Serial.printf("Soil temp: %.2f C\n\n", soilTemp);

  if (WiFi.status() == WL_CONNECTED) {
    HTTPClient http;
    http.begin(serverURL);
    http.addHeader("Content-Type", "application/json");

    // Send NaN as null so the JSON stays valid.
    auto numOrNull = [](float v) {
      return isnan(v) ? String("null") : String(v, 2);
    };

    String payload = String("{") +
      "\"node_id\":\""        + nodeId + "\"," +
      "\"soil_moisture\":"    + soilPct + "," +
      "\"soil_raw\":"         + rawSoil + "," +
      "\"soil_temperature\":" + numOrNull(soilTemp) + "," +
      "\"rssi\":"             + WiFi.RSSI() +
      "}";

    int code = http.POST(payload);
    if (code > 0) {
      Serial.println("POST ok, server returned " + String(code));
    } else {
      Serial.println("POST failed: " + http.errorToString(code));
    }
    http.end();
  }

  delay(INTERVAL_MS);
}
