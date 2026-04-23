// Capacitive soil moisture sensor only.
//
// Wiring:
//   Sensor VCC  -> ESP32 3.3V   (not 5V; ADC reads 0-3.3V)
//   Sensor GND  -> ESP32 GND
//   Sensor AOUT -> ESP32 GPIO34
//
// Record the dry-air value as AIR_VALUE and the submerged value as
// WATER_VALUE in firmware/sensor_node/sensor_node.ino.
// scripts/calibrate_soil.py automates this.

#define SOIL_PIN 34

void setup() {
  Serial.begin(115200);
  delay(500);
  Serial.println("HydroSense test_soil — reads GPIO34 every 500 ms");
}

void loop() {
  int raw = analogRead(SOIL_PIN);
  Serial.printf("Soil raw ADC: %4d   (~%.2f V)\n", raw, raw * 3.3 / 4095.0);
  delay(500);
}
