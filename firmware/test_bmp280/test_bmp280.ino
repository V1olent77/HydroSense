// BMP280 (I2C temperature + barometric pressure).
//
// Wiring:
//   VCC -> 3.3V
//   GND -> GND
//   SDA -> GPIO21
//   SCL -> GPIO22
//
// Libraries: Adafruit BMP280 Library, Adafruit Unified Sensor.
// Some clone boards use I2C address 0x77 instead of 0x76; sketch tries both.

#include <Wire.h>
#include <Adafruit_BMP280.h>

Adafruit_BMP280 bmp;

void setup() {
  Serial.begin(115200);
  delay(500);
  Serial.println("HydroSense test_bmp280");

  if (bmp.begin(0x76)) {
    Serial.println("BMP280 found at 0x76");
  } else if (bmp.begin(0x77)) {
    Serial.println("BMP280 found at 0x77");
  } else {
    Serial.println("ERROR: BMP280 not found at 0x76 or 0x77.");
    Serial.println("Check SDA=GPIO21, SCL=GPIO22, VCC=3.3V, GND=GND.");
    while (true) delay(1000);
  }
}

void loop() {
  float temp = bmp.readTemperature();
  float pressure_hpa = bmp.readPressure() / 100.0;
  Serial.printf("Temp: %.2f C   Pressure: %.2f hPa\n", temp, pressure_hpa);
  delay(1000);
}
