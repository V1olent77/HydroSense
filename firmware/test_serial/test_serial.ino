// Test 1 of 4 — confirms the ESP32 board, USB cable, and Arduino IDE
// setup are working before any sensors are wired in.
//
// Steps:
//   1. Tools → Board → "ESP32 Dev Module"
//   2. Tools → Port → (the COM/tty port that appears when ESP32 is plugged in)
//   3. Upload this sketch (hold BOOT on the board if upload fails)
//   4. Tools → Serial Monitor, set baud to 115200
//   5. You should see "Hello from ESP32" and a counter ticking every second.
//
// If you see nothing or garbage characters, the most common fixes are:
//   - Wrong baud rate in Serial Monitor (must be 115200)
//   - Wrong board selected in Tools → Board
//   - USB cable is power-only (try another cable)

void setup() {
  Serial.begin(115200);
  delay(500);
  Serial.println("\nHello from ESP32 — HydroSense test_serial");
  Serial.println("If you can read this, the board + IDE + cable all work.");
}

void loop() {
  static unsigned long counter = 0;
  Serial.printf("Tick #%lu  uptime %.1fs\n", counter++, millis() / 1000.0);
  delay(1000);
}
