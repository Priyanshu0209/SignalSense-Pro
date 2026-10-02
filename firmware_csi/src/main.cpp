#include <WiFi.h>
#include <esp_wifi.h>
#include <WiFiUdp.h>

const char* ssid = "swan2";
const char* password = "swan1234";

const char* udpAddress = "192.168.1.5";
const int udpPort = 8001;

WiFiUDP udp;
WiFiUDP udp_ping;

uint8_t target_bssid[6];

void csi_cb(void *ctx, wifi_csi_info_t *data) {
  // Only process CSI from the connected AP (Router) to avoid noise from neighbors
  if (memcmp(data->mac, target_bssid, 6) != 0) {
    return;
  }

  udp.beginPacket(udpAddress, udpPort);
  
  // Header: 6 bytes MAC, 1 byte RSSI
  uint8_t header[7];
  memcpy(header, data->mac, 6);
  header[6] = (uint8_t)data->rx_ctrl.rssi;
  
  udp.write(header, 7);
  udp.write((const uint8_t*)data->buf, data->len);
  udp.endPacket(); 
}

void setup() {
  Serial.begin(115200);
  Serial.println("Starting ESP32 CSI Collector...");
  
  WiFi.mode(WIFI_STA);
  WiFi.begin(ssid, password);
  
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println("\nConnected to WiFi");
  Serial.print("IP Address: ");
  Serial.println(WiFi.localIP());
  
  // Save the router's BSSID
  uint8_t* bssid = WiFi.BSSID();
  if (bssid) {
      memcpy(target_bssid, bssid, 6);
  }
  
  // Enable CSI
  wifi_csi_config_t csi_config = {
      .lltf_en = true,
      .htltf_en = true,
      .stbc_htltf2_en = true,
      .ltf_merge_en = true,
      .channel_filter_en = true,
      .manu_scale = false,
      .shift = false,
  };
  
  esp_err_t res = esp_wifi_set_csi_config(&csi_config);
  if (res != ESP_OK) {
    Serial.println("Failed to set CSI config");
  }
  
  res = esp_wifi_set_csi_rx_cb(&csi_cb, NULL);
  if (res != ESP_OK) {
    Serial.println("Failed to set CSI callback");
  }
  
  // Enable promiscuous mode to sniff all packets on the channel
  esp_wifi_set_promiscuous(true);
  
  res = esp_wifi_set_csi(true);
  if (res != ESP_OK) {
    Serial.println("Failed to enable CSI");
  } else {
    Serial.println("CSI Enabled! Streaming to backend...");
  }
}

void loop() {
  // Send a heartbeat to force the router to send an ACK/reply
  // which will trigger the CSI callback
  udp_ping.beginPacket(udpAddress, udpPort);
  udp_ping.write((const uint8_t*)"ping", 4);
  udp_ping.endPacket();
  
  delay(100);
}
