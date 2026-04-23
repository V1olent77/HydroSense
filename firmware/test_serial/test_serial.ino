// Heartbeat sketch. Confirms the board + IDE + cable work before any sensors are wired.
// Tools > Board: ESP32 Dev Module. Serial Monitor baud: 115200.

void setup() {
  Serial.begin(115200);
  delay(500);
  Serial.println("\nHello from ESP32 — HydroSense test_serial");
}

void loop() {
  static unsigned long counter = 0;
  Serial.printf("Tick #%lu  uptime %.1fs\n", counter++, millis() / 1000.0);
  delay(1000);
}
