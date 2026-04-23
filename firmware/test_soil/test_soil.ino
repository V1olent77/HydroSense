// Test 2 of 4 — capacitive soil moisture sensor only.
//
// Wiring:
//   Sensor VCC  → ESP32 3.3V   (NOT 5V — the ADC reads 0–3.3V natively)
//   Sensor GND  → ESP32 GND
//   Sensor AOUT → ESP32 GPIO34
//
// What you should see:
//   - In dry air the raw value sits near 3000–3500 (depends on the unit)
//   - Wrap your fingers around the probe — value should drop noticeably
//   - Submerge the bare probe (NOT the PCB!) in water — value drops to ~1300–1700
//
// Record the dry-air value as AIR_VALUE and the submerged value as
// WATER_VALUE in firmware/sensor_node/sensor_node.ino so the percent
// reading is calibrated to YOUR specific sensor.
//
// Tip: scripts/calibrate_soil.py automates this measurement loop.

#define SOIL_PIN 34

void setup() {
  Serial.begin(115200);
  delay(500);
  Serial.println("HydroSense test_soil — reads GPIO34 every 500 ms");
  Serial.println("Lower number = more moisture. Record dry vs water values.");
}

void loop() {
  int raw = analogRead(SOIL_PIN);
  Serial.printf("Soil raw ADC: %4d   (~%.2f V)\n", raw, raw * 3.3 / 4095.0);
  delay(500);
}
