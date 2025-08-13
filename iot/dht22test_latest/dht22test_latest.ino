#include <WiFi.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>
#include <DHT.h>;
#define DHTPIN 4     // what pin we're connected to
#define DHTTYPE DHT22   // DHT 22  (AM2302)
DHT dht(DHTPIN, DHTTYPE); 
float hum;  //Stores humidity value
float temp;

const char* WIFI_SSID = "UST_INFINITY_LAB";
const char* WIFI_PASSWORD = "infilabs@u5t";

const char* MQTT_HOST = "test.mosquitto.org";
const uint16_t MQTT_PORT = 1883;

const char* TOPIC_PUB_ENV = "smartcity/env"; 
const char* TOPIC_SUB_CTRL = "smartcity/control/streetlights";
const char* TOPIC_PUB_ACK = "smartcity/ack/streetlights";

WiFiClient espClient;
PubSubClient client(espClient);

#define LED_PIN 2
String DEVICE_ID;
unsigned long lastPub = 0;

void controlLED(String cmd){
cmd.trim(); cmd.toUpperCase();
if (cmd == "ON") {
  digitalWrite(LED_PIN, HIGH); // active LOW
} else if (cmd == "OFF") {
  digitalWrite(LED_PIN, LOW);
}
}

void publishAck(const char* cmd, const char* status, const char* reason = nullptr){
StaticJsonDocument<200> doc;
doc["id"] = DEVICE_ID;
doc["cmd"] = cmd;
doc["status"] = status;
if (reason) doc["reason"] = reason;

char buf[200];
size_t n = serializeJson(doc, buf, sizeof(buf));
client.publish(TOPIC_PUB_ACK, buf, n);
}

void handleJsonCommand(const String& jsonStr) {
StaticJsonDocument<256> doc;
DeserializationError err = deserializeJson (doc, jsonStr);
if (err) {
publishAck("UNKNOWN", "ERROR", "Bad JSON");
return;
}

const char* id = doc["id"] | "";
const char* cmd = doc["cmd"] | "";
// Only act if addressed to me or to ALL
if (strlen(id) == 0 || strlen(cmd) == 0){
publishAck("UNKNOWN", "ERROR", "Missing fields");
return;
}
if (DEVICE_ID.equals (id) || String(id) == "ALL") {
controlLED(String(cmd));
publishAck(cmd, "OK");
} else {
  publishAck("UNKNOWN", "ERROR", "MISSING FIELDS");
  return;
}
}


void mqttCallback(char* topic, byte* payload, unsigned int length) {

String msg;
msg.reserve(length);
for (unsigned int i = 0; i < length; i++) msg += (char)payload[i];

Serial.printf("[MQTT] %s => %s\n", topic, msg.c_str());
// Accept both JSON and raw ON/OFF for convenience
if (msg.startsWith("{")) 
{
  handleJsonCommand(msg);
} else 
{
// raw ON/OFF broadcasts act only if topic is targeted to ALL devices
// (optional rule). Here we just accept them unconditionally:
  controlLED(msg);
  publishAck(msg.c_str(), "OK");
}
}


void ensureWiFi() {
if (WiFi.status() == WL_CONNECTED) return;
Serial.printf("Connecting to WiFi %s...In", WIFI_SSID);

WiFi.mode (WIFI_STA);
WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

while (WiFi.status() != WL_CONNECTED) {
delay(500); Serial.print(" ."); 
}
Serial.printf("\nWiFi connected, IP: %s\n", WiFi.localIP().toString().c_str());
}

void ensureMQTT() {
while (!client.connected()) {

Serial.print("Connecting to MQTT...");
String clientId = DEVICE_ID + "-" + String((uint32_t)millis(), HEX);

if (client.connect(clientId.c_str())) {
Serial.println("connected"); 
client.subscribe(TOPIC_SUB_CTRL);
Serial.printf("Subscribed: %s\n", TOPIC_SUB_CTRL);
}else {
Serial.printf("failed, rc=%d. Retrying in 2s\n", client.state());
delay(2000);
}
}
}

void setup(){
Serial.begin(115200);
dht.begin();
pinMode(LED_PIN, OUTPUT);
digitalWrite(LED_PIN, HIGH); // OFF initially

// Build DEVICE_ID from MAC
uint64_t mac = ESP.getEfuseMac();
char macStr[13];
snprintf(macStr, sizeof(macStr), "%012llx", mac);

DEVICE_ID = "ESP32-";
DEVICE_ID += macStr;

Serial.printf("DEVICE_ID: %s\n", DEVICE_ID.c_str());

ensureWiFi();
client.setServer(MQTT_HOST, MQTT_PORT); 
client.setCallback(mqttCallback);
ensureMQTT();
}

void loop() {
  hum = dht.readHumidity();
  temp= dht.readTemperature();
if (WiFi.status() != WL_CONNECTED) ensureWiFi();
if (!client.connected()) ensureMQTT(); 
client.loop();
//Publish fake env data periodically
unsigned long now = millis();
if (now - lastPub > 2000) {

lastPub = now;
StaticJsonDocument<128> d;
d["id"] = DEVICE_ID;
d["temp"] = temp;
d["hum"] = hum;
d["ts"] = now;
char buf[128];
size_t n = serializeJson(d, buf, sizeof(buf));
client.publish(TOPIC_PUB_ENV, buf, n);
Serial.printf("Published %s: %s\n", TOPIC_PUB_ENV, buf);
}
}