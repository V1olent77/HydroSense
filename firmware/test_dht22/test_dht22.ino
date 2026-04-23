// Test 4 of 4 — DHT22 (digital humidity + temperature).
//
// Wiring:
//   VCC  → 3.3V
//   GND  → GND
//   DATA → GPIO4
//   (Most DHT22 breakouts have a 10 kΩ pull-up resistor on the PCB
//    already — check for a small surface-mount resistor next to the
//    DATA pin. If yours is the bare 4-pin sensor, add a 10 kΩ between
//    VCC and DATA.)
//
// Library: "DHT sensor library" by Adafruit.
//
// Expected output: humidity 20–80 %, temperature within ~1 °C of room.
//
// Common issues:
//   - NaN readings → wiring is loose, or you're polling faster than
//     the DHT22's 2-second minimum interval.
//   - Reads work for a few seconds then stop → power instability;
//     try a different USB cable or power source.

#include <DHT.h>

#define DHT_PIN  4
#define DHT_TYPE DHT22

DHT dht(DHT_PIN, DHT_TYPE);

void setup() {
  Serial.begin(115200);
  delay(500);
  Serial.println("HydroSense test_dht22 — needs 2 s between reads");
  dht.begin();
}

void loop() {
  float humidity = dht.readHumidity();
  float temp = dht.readTemperature();

  if (isnan(humidity) || isnan(temp)) {
    Serial.println("DHT22 read failed (NaN). Check wiring / wait 2 s between reads.");
  } else {
    Serial.printf("Humidity: %.1f %%   Temp: %.1f C\n", humidity, temp);
  }
  delay(2000);
}
