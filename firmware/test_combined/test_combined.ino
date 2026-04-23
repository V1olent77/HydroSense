// Bring-up sketch: ESP32 + BMP280 + DHT22. No WiFi, no HTTP.
// Prints both sensors to Serial every 2 seconds.
//
// Wiring:
//   ESP32 3.3V  -> BMP280 VCC, DHT22 VCC
//   ESP32 GND   -> BMP280 GND, DHT22 GND
//   ESP32 GPIO21 (SDA) -> BMP280 SDA
//   ESP32 GPIO22 (SCL) -> BMP280 SCL
//   ESP32 GPIO4        -> DHT22 DATA
//
// Libraries: Adafruit BMP280, Adafruit Unified Sensor, DHT sensor library.

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

  // 0x76 is the usual address; 0x77 is used by boards that tie SDO high.
  if (bmp.begin(0x76)) {
    Serial.println("BMP280 initialized at 0x76");
    bmpOk = true;
  } else if (bmp.begin(0x77)) {
    Serial.println("BMP280 initialized at 0x77");
    bmpOk = true;
  } else {
    Serial.println("BMP280 NOT FOUND. Check SDA=GPIO21, SCL=GPIO22, VCC=3.3V.");
  }

  dht.begin();
  Serial.println("DHT22 pin configured on GPIO4");
  Serial.println("Reading every 2 seconds...\n");
}

void loop() {
  Serial.println("---- Reading ----");

  if (bmpOk) {
    float bmpTemp  = bmp.readTemperature();
    float pressure = bmp.readPressure() / 100.0;
    Serial.printf("BMP280  temp: %.2f C   pressure: %.2f hPa\n",
                  bmpTemp, pressure);
  } else {
    Serial.println("BMP280  (not initialized, skipping)");
  }

  float humidity = dht.readHumidity();
  float dhtTemp  = dht.readTemperature();
  if (isnan(humidity) || isnan(dhtTemp)) {
    Serial.println("DHT22   NO RESPONSE. Check VCC=3.3V, DATA=GPIO4.");
  } else {
    Serial.printf("DHT22   humidity: %.1f %%   temp: %.2f C\n",
                  humidity, dhtTemp);
  }

  Serial.println();
  delay(2000);
}
