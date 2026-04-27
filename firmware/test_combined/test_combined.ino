// Bring-up sketch: ESP32 + capacitive soil moisture + DS18B20. No WiFi, no HTTP.
// Prints both sensors to Serial every 2 seconds.
//
// Wiring:
//   ESP32 3.3V   -> red breadboard rail (+)
//   ESP32 GND    -> blue breadboard rail (-)
//   Soil VCC     -> red rail (+3.3V)
//   Soil GND     -> blue rail (GND)
//   Soil AOUT    -> ESP32 GPIO34
//   DS18B20 VCC  -> red rail (+3.3V)
//   DS18B20 GND  -> blue rail (GND)
//   DS18B20 DATA -> ESP32 GPIO5
//   DS18B20 DATA <-> 4.7 kOhm resistor <-> +3.3V  (skip if your DS18B20 module already has it)
//
// Libraries: OneWire, DallasTemperature.

#include <OneWire.h>
#include <DallasTemperature.h>

#define SOIL_PIN     34
#define ONE_WIRE_PIN 5

// Calibration placeholders — overwrite after running scripts/calibrate_soil.py
const int AIR_VALUE   = 3400;
const int WATER_VALUE = 1500;

OneWire oneWire(ONE_WIRE_PIN);
DallasTemperature ds18b20(&oneWire);

bool dsOk = false;

void setup() {
  Serial.begin(115200);
  delay(500);
  Serial.println("\n=== ESP32 Soil + DS18B20 test ===");

  ds18b20.begin();
  int dsCount = ds18b20.getDeviceCount();
  if (dsCount > 0) {
    Serial.printf("DS18B20 OK — %d sensor(s) on bus\n", dsCount);
    dsOk = true;
  } else {
    Serial.println("DS18B20 NOT FOUND. Check DATA=GPIO5 and 4.7k pull-up to 3.3V.");
  }

  Serial.println("Reading every 2 seconds...\n");
}

void loop() {
  Serial.println("---- Reading ----");

  // Soil moisture
  int raw = analogRead(SOIL_PIN);
  int pct = constrain(map(raw, AIR_VALUE, WATER_VALUE, 0, 100), 0, 100);
  Serial.printf("Soil    raw: %4d   moisture: %d%%\n", raw, pct);

  // DS18B20
  if (dsOk) {
    ds18b20.requestTemperatures();
    float t = ds18b20.getTempCByIndex(0);
    if (t == DEVICE_DISCONNECTED_C) {
      Serial.println("DS18B20 NO RESPONSE this cycle.");
    } else {
      Serial.printf("DS18B20 soil temp: %.2f C\n", t);
    }
  } else {
    Serial.println("DS18B20 (not initialized, skipping)");
  }

  Serial.println();
  delay(2000);
}
