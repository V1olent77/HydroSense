// DHT22 (digital humidity + temperature).
//
// Wiring:
//   VCC  -> 3.3V
//   GND  -> GND
//   DATA -> GPIO4
// Most breakouts include a 10k pull-up between VCC and DATA. If yours
// is a bare 4-pin sensor, add one.
//
// Library: "DHT sensor library" by Adafruit.
// Minimum 2 s between reads or you get NaN.

#include <DHT.h>

#define DHT_PIN  4
#define DHT_TYPE DHT22

DHT dht(DHT_PIN, DHT_TYPE);

void setup() {
  Serial.begin(115200);
  delay(500);
  Serial.println("HydroSense test_dht22");
  dht.begin();
}

void loop() {
  float humidity = dht.readHumidity();
  float temp = dht.readTemperature();

  if (isnan(humidity) || isnan(temp)) {
    Serial.println("DHT22 read failed (NaN). Check wiring, wait 2 s between reads.");
  } else {
    Serial.printf("Humidity: %.1f %%   Temp: %.1f C\n", humidity, temp);
  }
  delay(2000);
}
