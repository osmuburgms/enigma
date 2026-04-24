#include <WiFi.h>
#include <WebServer.h>
#include <EEPROM.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>
#include <SPI.h>
#include <MFRC522.h>
#include <Adafruit_NeoPixel.h>

// ========= LED RGB =========
#define LED_PIN 8
#define NUM_LEDS 1
Adafruit_NeoPixel pixel(NUM_LEDS, LED_PIN, NEO_GRB + NEO_KHZ800);

enum EstadoLED {
  WIFI_CONECTANDO,
  WIFI_OK,
  MQTT_CONECTANDO,
  MQTT_OK,
  MODO_AP
};

EstadoLED estadoLED = WIFI_CONECTANDO;
unsigned long lastBlink = 0;
bool ledState = false;

// ========= EEPROM =========
#define EEPROM_SIZE 512
#define ADDR_SSID 0
#define ADDR_PASS 100
#define ADDR_MQTT 200

// ========= AP =========
WebServer server(80);
bool modoAP = false;

// ========= RFID =========
#define SS_1 3
#define SS_2 4
#define SS_3 18
#define SS_4 6
#define SS_5 15
#define RST_PIN 2

MFRC522 lectores[5] = {
  MFRC522(SS_1, RST_PIN),
  MFRC522(SS_2, RST_PIN),
  MFRC522(SS_3, RST_PIN),
  MFRC522(SS_4, RST_PIN),
  MFRC522(SS_5, RST_PIN)
};

// ========= MQTT =========
WiFiClient espClient;
PubSubClient client(espClient);

String mqtt_server = "";
const int mqtt_port = 1883;
const char* mqtt_topic = "guardian/sensores/rfid";

// ========= SERIAL =========
HardwareSerial SerialExt(1);

// ========= TIMERS =========
unsigned long lastMQTTAttempt = 0;
unsigned long lastReadTime[5] = {0,0,0,0,0};

const unsigned long MQTT_INTERVAL = 3000;
const unsigned long RFID_COOLDOWN = 800;

// ========= LED =========
void actualizarLED() {
  unsigned long now = millis();

  switch (estadoLED) {

    case WIFI_CONECTANDO:
      if (now - lastBlink > 500) {
        lastBlink = now;
        ledState = !ledState;
        pixel.setPixelColor(0, ledState ? pixel.Color(255, 150, 0) : 0);
        pixel.show();
      }
      break;

    case WIFI_OK:
      pixel.setPixelColor(0, pixel.Color(0, 0, 255));
      pixel.show();
      break;

    case MQTT_CONECTANDO:
      if (now - lastBlink > 500) {
        lastBlink = now;
        ledState = !ledState;
        pixel.setPixelColor(0, ledState ? pixel.Color(0, 0, 255) : 0);
        pixel.show();
      }
      break;

    case MQTT_OK:
      pixel.setPixelColor(0, pixel.Color(0, 255, 0));
      pixel.show();
      break;

    case MODO_AP:
      pixel.setPixelColor(0, pixel.Color(255, 0, 0));
      pixel.show();
      break;
  }
}

// ========= EEPROM =========
String leerEEPROM(int addr) {
  String value = "";
  for (int i = 0; i < 100; i++) {
    char c = EEPROM.read(addr + i);
    if (c == '\0') break;
    value += c;
  }
  return value;
}

void escribirEEPROM(int addr, String data) {
  for (int i = 0; i < data.length(); i++) {
    EEPROM.write(addr + i, data[i]);
  }
  EEPROM.write(addr + data.length(), '\0');
  EEPROM.commit();
}

// ========= JSON SERIAL (SIMULACIÓN) =========
void procesarJSONSerial(String input) {

  StaticJsonDocument<200> doc;
  DeserializationError error = deserializeJson(doc, input);

  if (error) return;

  if (!doc.containsKey("tag") || !doc.containsKey("esp") || !doc.containsKey("sensor")) {
    return;
  }

  char buffer[200];
  serializeJson(doc, buffer);

  Serial.println("📥 JSON recibido:");
  Serial.println(buffer);

  SerialExt.println("📥 JSON recibido:");
  SerialExt.println(buffer);

  if (client.connected()) {
    client.publish(mqtt_topic, buffer);
    Serial.println("📡 Enviado a MQTT");
  } else {
    Serial.println("⚠️ MQTT no conectado");
  }
}

// ========= COMANDOS =========
void procesarComando(String input) {
  input.trim();

  if (input.startsWith("MQTT:")) {
    String nuevaIP = input.substring(5);
    nuevaIP.trim();

    escribirEEPROM(ADDR_MQTT, nuevaIP);

    mqtt_server = nuevaIP;
    client.setServer(mqtt_server.c_str(), mqtt_port);
    client.disconnect();

    Serial.println("🔄 Nueva IP MQTT aplicada");
    SerialExt.println("🔄 Nueva IP MQTT aplicada");
  }
}

// ========= SERIAL =========
void manejarSeriales() {

  if (Serial.available()) {
    String input = Serial.readStringUntil('\n');
    input.trim();

    if (input.startsWith("MQTT:")) {
      procesarComando(input);
    } else if (input.startsWith("{")) {
      procesarJSONSerial(input);
    }
  }

  if (SerialExt.available()) {
    String input = SerialExt.readStringUntil('\n');
    input.trim();

    if (input.startsWith("MQTT:")) {
      procesarComando(input);
    }
  }
}

// ========= WEB =========
void handleRoot() {
  String html = "<html><body>";
  html += "<h2>Config ESP32 RFID</h2>";
  html += "<form method='POST' action='/save'>";
  html += "SSID: <input name='ssid'><br>";
  html += "Password: <input name='pass'><br>";
  html += "MQTT IP: <input name='mqtt'><br>";
  html += "<input type='submit'>";
  html += "</form></body></html>";

  server.send(200, "text/html", html);
}

void handleSave() {
  escribirEEPROM(ADDR_SSID, server.arg("ssid"));
  escribirEEPROM(ADDR_PASS, server.arg("pass"));
  escribirEEPROM(ADDR_MQTT, server.arg("mqtt"));

  delay(1000);
  ESP.restart();
}

// ========= AP =========
void iniciarAP() {
  WiFi.mode(WIFI_AP);
  WiFi.softAP("ESP32-RFID-SETUP", "12345678");

  server.on("/", handleRoot);
  server.on("/save", handleSave);
  server.begin();

  modoAP = true;
  estadoLED = MODO_AP;
}

// ========= WIFI =========
bool conectarWiFi() {
  String ssid = leerEEPROM(ADDR_SSID);
  String pass = leerEEPROM(ADDR_PASS);

  if (ssid == "") return false;

  estadoLED = WIFI_CONECTANDO;

  WiFi.mode(WIFI_STA);
  WiFi.begin(ssid.c_str(), pass.c_str());

  unsigned long start = millis();

  while (WiFi.status() != WL_CONNECTED && millis() - start < 15000) {
    actualizarLED();
    delay(50);
  }

  if (WiFi.status() == WL_CONNECTED) {
    estadoLED = WIFI_OK;
    return true;
  }

  return false;
}

// ========= MQTT =========
void manejarMQTT() {

  if (client.connected()) {
    estadoLED = MQTT_OK;
    return;
  }

  estadoLED = MQTT_CONECTANDO;

  if (millis() - lastMQTTAttempt < MQTT_INTERVAL) return;

  lastMQTTAttempt = millis();

  if (client.connect("ESP32C6_Client")) {
    estadoLED = MQTT_OK;
  }
}

// ========= UID =========
String uidToString(MFRC522::Uid *uid) {
  String uidStr = "";

  for (byte i = 0; i < uid->size; i++) {
    if (uid->uidByte[i] < 0x10) uidStr += "0";
    uidStr += String(uid->uidByte[i], HEX);
    if (i < uid->size - 1) uidStr += " ";
  }

  uidStr.toUpperCase();
  return uidStr;
}

// ========= SETUP =========
void setup() {
  Serial.begin(115200);
  SerialExt.begin(115200, SERIAL_8N1, 17, 16);

  EEPROM.begin(EEPROM_SIZE);
  SPI.begin();

  pixel.begin();
  pixel.clear();
  pixel.show();

  for (int i = 0; i < 5; i++) {
    lectores[i].PCD_Init();
  }

  if (!conectarWiFi()) {
    iniciarAP();
    return;
  }

  mqtt_server = leerEEPROM(ADDR_MQTT);
  client.setServer(mqtt_server.c_str(), mqtt_port);
}

// ========= LOOP =========
void loop() {

  manejarSeriales();
  actualizarLED();

  if (modoAP) {
    server.handleClient();
    return;
  }

  manejarMQTT();
  client.loop();

  unsigned long now = millis();

  for (int i = 0; i < 5; i++) {

    if (now - lastReadTime[i] < RFID_COOLDOWN) continue;

    if (!lectores[i].PICC_IsNewCardPresent()) continue;
    if (!lectores[i].PICC_ReadCardSerial()) continue;

    lastReadTime[i] = now;

    String uid = uidToString(&lectores[i].uid);

    StaticJsonDocument<128> doc;
    doc["tag"] = uid;
    doc["esp"] = 1;
    doc["sensor"] = i + 1;

    char buffer[128];
    serializeJson(doc, buffer);

    if (client.connected()) {
      client.publish(mqtt_topic, buffer);
    }

    Serial.println(buffer);
    SerialExt.println(buffer);

    lectores[i].PICC_HaltA();
  }
}
