// HydroSense sensor node — ESP32 + capacitive soil moisture + BMP280 + DHT22.
// Upload via Arduino IDE (Board: "ESP32 Dev Module", baud 115200).
//
// Libraries: Adafruit BMP280, Adafruit Unified Sensor, DHT sensor library.
// Wiring: see /Users/alanmusahitov/Downloads/aquasight_guide.md §Hardware: Wiring.

#include <WiFi.h>
#include <HTTPClient.h>
#include <Wire.h>
#include <Adafruit_BMP280.h>
#include <DHT.h>

// --- Configuration ---------------------------------------------------
// NOTE: fill these in locally before flashing. Do NOT commit real credentials.
const char* ssid      = "YOUR_WIFI_SSID";
const char* password  = "YOUR_WIFI_PASSWORD";
const char* serverURL = "http://YOUR_BACKEND_HOST:5001/api/data";
const char* nodeId    = "node_01";

// --- Sensor pins -----------------------------------------------------
#define SOIL_PIN 34
#define DHT_PIN  4
#define DHT_TYPE DHT22

// --- Soil calibration (measure yours in dry air vs fully submerged) --
const int AIR_VALUE   = 3400;
const int WATER_VALUE = 1500;

// --- Reading cadence -------------------------------------------------
const unsigned long INTERVAL_MS = 900000; // 15 minutes

Adafruit_BMP280 bmp;
DHT dht(DHT_PIN, DHT_TYPE);

void setup() {
  Serial.begin(115200);
  Serial.println("HydroSense sensor node v1.0");

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

  // Try 0x76 first, then 0x77 (clone boards tie SDO high).
  if (bmp.begin(0x76)) {
    Serial.println("BMP280 initialized at 0x76");
  } else if (bmp.begin(0x77)) {
    Serial.println("BMP280 initialized at 0x77");
  } else {
    Serial.println("BMP280 not found at 0x76 OR 0x77 — check wiring (SDA=GPIO21, SCL=GPIO22, VCC=3.3V).");
  }

  dht.begin();
  Serial.println("DHT22 initialized");
  Serial.println("Setup complete.\n");
}

void loop() {
  int rawSoil = analogRead(SOIL_PIN);
  int soilPct = constrain(map(rawSoil, AIR_VALUE, WATER_VALUE, 0, 100), 0, 100);

  float bmpTemp  = bmp.readTemperature();
  float pressure = bmp.readPressure() / 100.0;
  float humidity = dht.readHumidity();
  float dhtTemp  = dht.readTemperature();

  Serial.println("---- Reading ----");
  Serial.printf("Soil: %d%%  (raw %d)\n", soilPct, rawSoil);
  Serial.printf("BMP temp: %.2f C  Pressure: %.2f hPa\n", bmpTemp, pressure);
  Serial.printf("DHT humidity: %.2f %%  DHT temp: %.2f C\n\n", humidity, dhtTemp);

  if (WiFi.status() == WL_CONNECTED) {
    HTTPClient http;
    http.begin(serverURL);
    http.addHeader("Content-Type", "application/json");

    String payload = String("{") +
      "\"soil_moisture\":" + soilPct + "," +
      "\"temperature_bmp\":" + bmpTemp + "," +
      "\"temperature_dht\":" + dhtTemp + "," +
      "\"humidity\":" + humidity + "," +
      "\"pressure\":" + pressure + "," +
      "\"soil_raw\":" + rawSoil + "," +
      "\"node_id\":\"" + nodeId + "\"}";

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
