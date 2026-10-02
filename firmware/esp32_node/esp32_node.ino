#include <WiFi.h>
#include <esp_wifi.h>
#include <ArduinoJson.h>

// ---------------------------------------------------------
// Configuration
// ---------------------------------------------------------
const char* ssid     = "swan2";
const char* password = "swan1234";

// ---------------------------------------------------------
// Global Variables
// ---------------------------------------------------------
String my_mac;

// Promiscuous callback function
void sniffer(void* buf, wifi_promiscuous_pkt_type_t type) {
  wifi_promiscuous_pkt_t *pkt = (wifi_promiscuous_pkt_t*)buf;
  int rssi = pkt->rx_ctrl.rssi;
  
  // Header length is 24 bytes for standard 802.11 MAC header
  uint8_t *payload = pkt->payload;
  
  // Extract Transmitter MAC Address (bytes 10-15 in 802.11 header)
  char macStr[18];
  snprintf(macStr, sizeof(macStr), "%02X:%02X:%02X:%02X:%02X:%02X",
           payload[10], payload[11], payload[12], payload[13], payload[14], payload[15]);

  // Ignore broadcast/multicast packets to save serial bandwidth
  if (payload[10] & 0x01) {
      return; 
  }
  
  // Optional: Ignore the ESP32's own packets if you don't want self-feedback
  // if (String(macStr) == my_mac) return;

  // Generate and send JSON over Serial
  StaticJsonDocument<128> doc;
  doc["mac_address"] = macStr;
  doc["rssi"] = rssi;
  doc["source"] = "esp32_sniffer";
  
  serializeJson(doc, Serial);
  Serial.println();
}

void setup() {
  Serial.begin(115200);
  delay(1000);

  Serial.println("\n--- SignalSense ESP32 Promiscuous Radar ---");
  Serial.print("Connecting to ");
  Serial.println(ssid);

  WiFi.mode(WIFI_STA);
  WiFi.begin(ssid, password);

  int attempts = 0;
  while (WiFi.status() != WL_CONNECTED && attempts < 20) {
    delay(500);
    Serial.print(".");
    attempts++;
  }

  if (WiFi.status() == WL_CONNECTED) {
    Serial.println("\nWi-Fi Connected!");
    my_mac = WiFi.macAddress();
    my_mac.toUpperCase();
    Serial.println("My MAC Address: " + my_mac);
    Serial.print("Listening on Channel: ");
    Serial.println(WiFi.channel());
  } else {
    Serial.println("\nFailed to connect. Sniffing on default Channel 1.");
    esp_wifi_set_channel(1, WIFI_SECOND_CHAN_NONE);
  }

  // Enable Promiscuous Mode to sniff ALL packets in the air!
  wifi_promiscuous_filter_t filter;
  filter.filter_mask = WIFI_PROMIS_FILTER_MASK_ALL; // Must include DATA packets to see connected users!
  esp_wifi_set_promiscuous_filter(&filter);
  esp_wifi_set_promiscuous(true);
  esp_wifi_set_promiscuous_rx_cb(&sniffer);
  Serial.println("Radar active! Sniffing real-time device RSSI...");
}

void loop() {
  // Everything happens asynchronously in the sniffer callback.
  // We just keep the main loop alive.
  delay(1000);
}
