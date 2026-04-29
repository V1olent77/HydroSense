// HydroSense sensor node v1.3 — ESP32 + capacitive soil moisture + DS18B20.
// HTTPS-capable, with POST retry and Render free-tier wake ping.
//
// Upload via Arduino IDE (Board: "ESP32 Dev Module", baud 115200).
//
// Libraries required (Library Manager):
//   - OneWire
//   - DallasTemperature

#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <HTTPClient.h>
#include <OneWire.h>
#include <DallasTemperature.h>

// --- Configuration ---------------------------------------------------
// SECURITY: do NOT commit real Wi-Fi creds to a public repo. Replace
// these with placeholders before pushing to GitHub.
const char* ssid      = "iPhone";
const char* password  = "Alan2009";
const char* serverURL = "https://hydrosense-api.onrender.com/api/data";
const char* healthURL = "https://hydrosense-api.onrender.com/api/health";
const char* nodeId    = "node_01";

// --- Sensor pins -----------------------------------------------------
#define SOIL_PIN     34   // analog, capacitive soil moisture AOUT
#define ONE_WIRE_PIN 5    // digital, DS18B20 DATA (needs 4.7k pull-up to 3.3V)

// --- Soil calibration (run scripts/calibrate_soil.py to dial these in)
const int AIR_VALUE   = 3400;
const int WATER_VALUE = 1500;

// --- Cadence + retry -------------------------------------------------
const unsigned long INTERVAL_MS     = 900000; // 15 minutes between readings
const int           MAX_POST_RETRIES = 3;
const unsigned long RETRY_DELAY_MS   = 4000;  // 4 s between POST attempts
const unsigned long HTTP_TIMEOUT_MS  = 15000; // give Render time to wake

OneWire oneWire(ONE_WIRE_PIN);
DallasTemperature ds18b20(&oneWire);

bool dsOk = false;

// --- WiFi connect helper --------------------------------------------
bool connectWiFi() {
  if (WiFi.status() == WL_CONNECTED) return true;
  Serial.print("Connecting to Wi-Fi");
  WiFi.begin(ssid, password);
  int attempts = 0;
  while (WiFi.status() != WL_CONNECTED && attempts < 40) {
    delay(500);
    Serial.print(".");
    attempts++;
  }
  if (WiFi.status() == WL_CONNECTED) {
    Serial.println("\nWi-Fi OK: " + WiFi.localIP().toString() +
                   "  RSSI " + String(WiFi.RSSI()) + " dBm");
    return true;
  }
  Serial.println("\nWi-Fi FAILED after 20 s.");
  return false;
}

// --- Wake Render free-tier with a quick GET -------------------------
// Render sleeps an inactive instance after ~15 min. The first POST
// after sleep can take 30-60 s while the dyno starts. Pinging
// /api/health first lets the wake-up cost a cheap GET instead of
// burning all our POST retries.
void wakeRender(WiFiClientSecure& client) {
  HTTPClient http;
  http.setTimeout(HTTP_TIMEOUT_MS);
  http.begin(client, healthURL);
  int code = http.GET();
  Serial.printf("Wake ping  /api/health -> %d\n", code);
  http.end();
}

// --- Send one reading, returning HTTP code (<=0 = failure) ----------
int sendReading(WiFiClientSecure& client, const String& payload) {
  HTTPClient http;
  http.setTimeout(HTTP_TIMEOUT_MS);
  http.begin(client, serverURL);
  http.addHeader("Content-Type", "application/json");
  int code = http.POST(payload);
  if (code > 0) {
    Serial.printf("POST -> %d  %s\n", code, http.getString().c_str());
  } else {
    Serial.printf("POST -> FAIL  %s\n", http.errorToString(code).c_str());
  }
  http.end();
  return code;
}

void setup() {
  Serial.begin(115200);
  delay(300);
  Serial.println("\nHydroSense sensor node v1.3 (HTTPS + retry)");

  connectWiFi();

  ds18b20.begin();
  int dsCount = ds18b20.getDeviceCount();
  if (dsCount > 0) {
    Serial.printf("DS18B20 initialized - %d sensor(s) on bus\n", dsCount);
    dsOk = true;
  } else {
    Serial.println("DS18B20 NOT FOUND - check DATA=GPIO5 + 4.7k pull-up.");
  }

  Serial.println("Setup complete.\n");
}

void loop() {
  // Make sure Wi-Fi is up. If it dropped (e.g. iPhone hotspot slept),
  // back off 30 s and try again — don't burn the loop on dead Wi-Fi.
  if (!connectWiFi()) {
    delay(30000);
    return;
  }

  // --- Soil moisture ---
  int rawSoil = analogRead(SOIL_PIN);
  int soilPct = constrain(map(rawSoil, AIR_VALUE, WATER_VALUE, 0, 100), 0, 100);

  // --- DS18B20 soil temperature ---
  float soilTemp = NAN;
  if (dsOk) {
    ds18b20.requestTemperatures();
    soilTemp = ds18b20.getTempCByIndex(0);
    if (soilTemp == DEVICE_DISCONNECTED_C) soilTemp = NAN;
  }

  Serial.println("---- Reading ----");
  Serial.printf("Soil:      %d%%   (raw %d)\n", soilPct, rawSoil);
  Serial.printf("Soil temp: %.2f C\n", soilTemp);

  // --- Build JSON ---
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

  // --- HTTPS client ---
  // Render uses a Let's Encrypt cert. Verifying it on-device would
  // require shipping the CA bundle in flash; for an open-source field
  // demo we accept any cert (`setInsecure`). Traffic is still
  // encrypted in transit, just not authenticated.
  WiFiClientSecure client;
  client.setInsecure();

  // Warm Render up, then POST with up to 3 retries.
  wakeRender(client);

  int lastCode = 0;
  for (int attempt = 1; attempt <= MAX_POST_RETRIES; attempt++) {
    Serial.printf("POST attempt %d/%d ...\n", attempt, MAX_POST_RETRIES);
    lastCode = sendReading(client, payload);
    if (lastCode >= 200 && lastCode < 300) break;
    if (attempt < MAX_POST_RETRIES) delay(RETRY_DELAY_MS);
  }
  Serial.printf("Final result: %d\n\n", lastCode);

  delay(INTERVAL_MS);
}
