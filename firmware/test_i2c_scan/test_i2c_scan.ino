// I2C bus scanner — lists every address that ACKs on the I2C bus.
// Use this to confirm the BMP280 is alive and find its actual address.
//
// Wiring reminder:
//   ESP32 3.3V    -> BMP280 VCC
//   ESP32 GND     -> BMP280 GND
//   ESP32 GPIO21  -> BMP280 SDA
//   ESP32 GPIO22  -> BMP280 SCL
//
// Expected output if the BMP280 is alive:
//   "Found device at 0x76"  (or 0x77)
//
// If the scanner finds NOTHING:
//   -> SDA/SCL swapped, VCC/GND swapped, bad solder joint, or dead chip.

#include <Wire.h>

void setup() {
  Serial.begin(115200);
  delay(500);
  Serial.println("\n=== I2C scanner ===");
  Wire.begin();   // default SDA=21, SCL=22 on ESP32
}

void loop() {
  Serial.println("\nScanning 0x01..0x7F ...");
  int found = 0;
  for (uint8_t addr = 1; addr < 127; addr++) {
    Wire.beginTransmission(addr);
    uint8_t err = Wire.endTransmission();
    if (err == 0) {
      Serial.printf("  Found device at 0x%02X\n", addr);
      found++;
    }
  }
  if (found == 0) {
    Serial.println("  No I2C devices found.");
    Serial.println("  Check: SDA=GPIO21, SCL=GPIO22, VCC=3.3V, GND=GND.");
  } else {
    Serial.printf("Done — %d device(s) found.\n", found);
  }
  delay(5000);
}
