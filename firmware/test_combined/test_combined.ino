// Minimal ESP32 + BMP280 + DHT22 bring-up sketch.
// No WiFi, no HTTP — just prints both sensors to Serial every 2 seconds.
// Use this to verify wiring BEFORE flashing sensor_node.ino.
//
// Wiring:
//   ESP32 3.3V  -> BMP280 VCC, DHT22 VCC
//   ESP32 GND   -> BMP280 GND, DHT22 GND
//   ESP32 GPIO21 (SDA) -> BMP280 SDA
//   ESP32 GPIO22 (SCL) -> BMP280 SCL
//   ESP32 GPIO4        -> DHT22 DATA
//
// Libraries needed (Library Manager):
//   - Adafruit BMP280 Library
//   - Adafruit Unified Sensor   (auto-installed as dependency)
//   - DHT sensor library by Adafruit

#include <Wire.h>
#include <Adafruit_BMP280.h>
#include <DHT.h>

#define DHT_PIN  4
#define DHT_TYPE DHT22

Adafruit_BMP280 bmp;
DHT dht(DHT_PIN, DHT_TYPE);

bool bmpOk = false;

void setup() {
  Serial.begin(115200);
  delay(500);
  Serial.println("\n=== ESP32 BMP280 + DHT22 test ===");

  // Try both common I2C addresses — 0x76 is the "default",
  // 0x77 is what many breakouts ship with (SDO tied high).
  if (bmp.begin(0x76)) {
    Serial.println("BMP280 initialized at 0x76");
    bmpOk = true;
  } else if (bmp.begin(0x77)) {
    Serial.println("BMP280 initialized at 0x77");
    bmpOk = true;
  } else {
    Serial.println("BMP280 NOT FOUND — check wiring:");
    Serial.println("  VCC -> ESP32 3.3V  (NOT 5V / VIN)");
    Serial.println("  GND -> ESP32 GND");
    Serial.println("  SDA -> ESP32 GPIO21");
    Serial.println("  SCL -> ESP32 GPIO22");
  }

  dht.begin();
  Serial.println("DHT22 pin configured on GPIO4");
  Serial.println("Reading every 2 seconds...\n");
}

void loop() {
  Serial.println("---- Reading ----");

  // --- BMP280 ---------------------------------------------------------
  if (bmpOk) {
    float bmpTemp  = bmp.readTemperature();
    float pressure = bmp.readPressure() / 100.0;  // Pa -> hPa
    Serial.printf("BMP280  temp: %.2f C   pressure: %.2f hPa\n",
                  bmpTemp, pressure);
  } else {
    Serial.println("BMP280  (not initialized — skip)");
  }

  // --- DHT22 ----------------------------------------------------------
  // DHT22 is slow — readings can fail; the library returns NaN if so.
  float humidity = dht.readHumidity();
  float dhtTemp  = dht.readTemperature();
  if (isnan(humidity) || isnan(dhtTemp)) {
    Serial.println("DHT22   NO RESPONSE — check wiring:");
    Serial.println("  VCC  -> ESP32 3.3V");
    Serial.println("  GND  -> ESP32 GND");
    Serial.println("  DATA -> ESP32 GPIO4  (middle pin on 4-pin module)");
  } else {
    Serial.printf("DHT22   humidity: %.1f %%   temp: %.2f C\n",
                  humidity, dhtTemp);
  }

  Serial.println();
  delay(2000);
}
