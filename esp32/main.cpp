#include <Arduino.h>           // Arduino library default by PlatformIO
#include <EEPROM.h>            // EEPROM library default by PlatformIO
#include <WiFi.h>              // WiFi library default by PlatformIO
#include <SPI.h>               // SPI driver default by PlatformIO
#include <MFRC522.h>           // MFRC522 library by miguelbalboa <GithubComunnity>
#include <PubSubClient.h>      // PubSubClient library by Nick O'leary

//=====================================================
// CONFIGURACION
//=====================================================

const uint8_t ESP_ID = 1; // ID -> {1, 2, 3, 4, 5}
const uint8_t NUM_READERS = 5;

// Chip Select de cada RC522
const uint8_t RFID_SS[NUM_READERS] = {
  13, 15, 33, 25, 5
};

// Reset independiente para cada RC522
const uint8_t RFID_RST[NUM_READERS] = {
  14, 4, 32, 26, 27
};

const uint8_t LED_PIN = 2;

//=====================================================
// WIFI Y MQTT
//=====================================================

const char *ssid = "ssid_name";
const char *password = "ssid_password"; // si la red es abierta no importa este parametro
const bool wifiRequiresPassword = false; // true -> red cerrada, false -> red abierta

WiFiClient espClient;
PubSubClient client(espClient);

IPAddress mqttServerIp(192, 168, 88, 2); // IP por default si no hay datos en EEPROM
const int mqtt_port = 1883;
const char *mqtt_topic = "guardian/sensores/rfid";

const uint8_t EEPROM_SIZE = 16;
const uint8_t EEPROM_MAGIC = 0xA5;
const int EEPROM_MAGIC_ADDR = 0;
const int EEPROM_BROKER_ADDR = 1;

unsigned long lastWifiAttempt = 0;
unsigned long lastMqttAttempt = 0;
String serial0Buffer;

//=====================================================
// OBJETOS RFID
//=====================================================

MFRC522 readers[NUM_READERS] = {
  MFRC522(RFID_SS[0], RFID_RST[0]),
  MFRC522(RFID_SS[1], RFID_RST[1]),
  MFRC522(RFID_SS[2], RFID_RST[2]),
  MFRC522(RFID_SS[3], RFID_RST[3]),
  MFRC522(RFID_SS[4], RFID_RST[4])
};

//=====================================================
// VARIABLES
//=====================================================

bool cardPresent[NUM_READERS] = {
  false, false, false, false, false
};

String lastUid[NUM_READERS] = {
  "", "", "", "", ""
};

//=====================================================
// UTILIDADES
//=====================================================

String uidToString(MFRC522 &reader)
{
  String uidStr;

  for (byte i = 0; i < reader.uid.size; i++)
  {
    if (reader.uid.uidByte[i] < 0x10)
    {
      uidStr += "0";
    }

    uidStr += String(reader.uid.uidByte[i], HEX);

    if (i < reader.uid.size - 1)
    {
      uidStr += " ";
    }
  }

  uidStr.toUpperCase();

  return uidStr;
}

bool isPrintableIpChar(char value)
{
  return (value >= '0' && value <= '9') || value == '.';
}

String extractIpFromText(const String &text)
{
  String candidate;

  for (unsigned int i = 0; i < text.length(); i++)
  {
    char ch = text.charAt(i);

    if (isdigit(ch) || ch == '.')
    {
      candidate += ch;
    }
    else if (candidate.length() > 0 && (ch == ' ' || ch == '\t' || ch == '\r' || ch == '\n' || ch == '"' || ch == '\'' || ch == ',' || ch == ';'))
    {
      break;
    }
  }

  return candidate;
}

bool parseBrokerIp(const String &text, IPAddress &outIp)
{
  String candidate = extractIpFromText(text);
  if (candidate.length() == 0)
  {
    return false;
  }

  int octet0 = 0;
  int octet1 = 0;
  int octet2 = 0;
  int octet3 = 0;

  if (sscanf(candidate.c_str(), "%d.%d.%d.%d", &octet0, &octet1, &octet2, &octet3) != 4)
  {
    return false;
  }

  if (octet0 < 0 || octet0 > 255 ||
      octet1 < 0 || octet1 > 255 ||
      octet2 < 0 || octet2 > 255 ||
      octet3 < 0 || octet3 > 255)
  {
    return false;
  }

  outIp = IPAddress(octet0, octet1, octet2, octet3);
  return true;
}

void publishTelemetry(const String &payload)
{
  Serial.println(payload);

  if (!client.connected())
  {
    Serial.println("MQTT: cliente no conectado; se omite publish");
    return;
  }

  bool ok = client.publish(mqtt_topic, payload.c_str());
  Serial.printf("MQTT publish -> %s (%s)\n",
                payload.c_str(),
                ok ? "ok" : "fail");
}

void saveBrokerIpToEEPROM(const IPAddress &ip)
{
  EEPROM.write(EEPROM_MAGIC_ADDR, EEPROM_MAGIC);
  EEPROM.write(EEPROM_BROKER_ADDR + 0, ip[0]);
  EEPROM.write(EEPROM_BROKER_ADDR + 1, ip[1]);
  EEPROM.write(EEPROM_BROKER_ADDR + 2, ip[2]);
  EEPROM.write(EEPROM_BROKER_ADDR + 3, ip[3]);
  EEPROM.commit();
}

bool loadBrokerIpFromEEPROM()
{
  if (EEPROM.read(EEPROM_MAGIC_ADDR) != EEPROM_MAGIC)
  {
    return false;
  }

  mqttServerIp = IPAddress(
      EEPROM.read(EEPROM_BROKER_ADDR + 0),
      EEPROM.read(EEPROM_BROKER_ADDR + 1),
      EEPROM.read(EEPROM_BROKER_ADDR + 2),
      EEPROM.read(EEPROM_BROKER_ADDR + 3));

  return true;
}

void setBrokerIp(const IPAddress &newIp)
{
  mqttServerIp = newIp;
  saveBrokerIpToEEPROM(mqttServerIp);
  client.setServer(mqttServerIp, mqtt_port);
  client.disconnect();

  if (loadBrokerIpFromEEPROM())
  {
    Serial.printf("EEPROM: broker verificado como %s\n", mqttServerIp.toString().c_str());
  }
  else
  {
    Serial.println("EEPROM: no se pudo verificar el broker guardado");
  }

  String message = "Broker MQTT actualizado a " + mqttServerIp.toString() + " y guardado en EEPROM";
  Serial.println(message);

  String payload = "{";
  payload += "\"tag\": \"broker_ip\",";
  payload += "\"esp\": " + String(ESP_ID) + ",";
  payload += "\"ip\": \"" + mqttServerIp.toString() + "\"";
  payload += "}";

  publishTelemetry(payload);
}

void processSerialLine(String line)
{
  line.trim();

  if (line.length() == 0)
  {
    return;
  }

  Serial.printf("Serial RX [UART0]: %s\n", line.c_str());

  IPAddress newIp;
  if (newIp.fromString(line) || parseBrokerIp(line, newIp))
  {
    setBrokerIp(newIp);
    return;
  }

  String message = "IP invalida recibida: " + line + " (esperado formato 192.168.1.10)";
  Serial.println(message);
}

void pollSerialCommands(String &buffer)
{
  static unsigned long lastActivity = 0;

  while (Serial.available() > 0)
  {
    char value = static_cast<char>(Serial.read());

    if (value == '\r')
    {
      continue;
    }

    if (value == '\n')
    {
      processSerialLine(buffer);
      buffer = "";
      lastActivity = 0;
      continue;
    }

    if (buffer.length() < 32 && isPrintableIpChar(value))
    {
      buffer += value;
    }
    else if (buffer.length() < 32 && value == ' ')
    {
      continue;
    }

    lastActivity = millis();
  }

  if (buffer.length() >= 7 && lastActivity > 0 && millis() - lastActivity >= 150)
  {
    processSerialLine(buffer);
    buffer = "";
    lastActivity = 0;
  }
}

bool connectWifi()
{
  if (WiFi.status() == WL_CONNECTED)
  {
    return true;
  }

  WiFi.mode(WIFI_STA);
  WiFi.setAutoReconnect(true);

  if (wifiRequiresPassword)
  {
    WiFi.begin(ssid, password);
    Serial.println("Conectando a WiFi con contraseña...");
  }
  else
  {
    WiFi.begin(ssid);
    Serial.println("Conectando a WiFi abierta...");
  }

  unsigned long start = millis();

  while (millis() - start < 15000)
  {
    wl_status_t status = WiFi.status();

    if (status == WL_CONNECTED)
    {
      Serial.printf("WiFi conectado. IP: %s\n", WiFi.localIP().toString().c_str());
      return true;
    }

    if (status == WL_CONNECT_FAILED || status == WL_NO_SSID_AVAIL)
    {
      Serial.printf("Error al conectar a WiFi. Estado: %d\n", status);
      return false;
    }

    delay(200);
  }

  Serial.println("No se pudo obtener IP del WiFi en 15 s");
  return false;
}

bool reconnectMqtt()
{
  if (WiFi.status() != WL_CONNECTED)
  {
    return false;
  }

  if (client.connected())
  {
    return true;
  }

  String clientId = "esp32-rfid-" + String(ESP_ID) + "-" + String((uint32_t)ESP.getEfuseMac(), HEX);

  Serial.printf("MQTT: intentando conectar a %s:%d con clientId %s\n",
                mqttServerIp.toString().c_str(),
                mqtt_port,
                clientId.c_str());

  bool ok = client.connect(clientId.c_str());

  if (ok)
  {
    Serial.println("MQTT: conectado al broker");
  }
  else
  {
    Serial.printf("MQTT: fallo de conexion. Estado: %d\n", client.state());
  }

  return ok;
}

//=====================================================
// PUBLICACION
//=====================================================

void publishCardState(uint8_t sensorId,
                      const String &tag,
                      bool cardState)
{
  String payload = "{";

  payload += "\"tag\": \"" + tag + "\",";
  payload += "\"esp\": " + String(ESP_ID) + ",";
  payload += "\"sensor\": " + String(sensorId + 1) + ",";
  payload += "\"card\": ";
  payload += (cardState ? "true" : "false");
  payload += "}";

  publishTelemetry(payload);
}

//=====================================================
// RESET RFID
//=====================================================

void resetReader(uint8_t index)
{
  for (uint8_t i = 0; i < NUM_READERS; i++)
  {
    digitalWrite(RFID_SS[i], HIGH);
  }

  digitalWrite(RFID_RST[index], LOW);
  delay(50);

  digitalWrite(RFID_RST[index], HIGH);
  delay(50);

  readers[index].PCD_Init();

  Serial.printf(
    "RFID %d reiniciado\n",
    index + 1
  );
}

//=====================================================
// COMPROBAR SI EL LECTOR RESPONDE
//=====================================================

bool readerAlive(uint8_t index)
{
  byte version =
      readers[index].PCD_ReadRegister(
          MFRC522::VersionReg);

  if (version == 0x91 || version == 0x92 || version == 0x88 || version == 0xB2)
  {
    return true;
  }

  Serial.printf(
      "RFID %d ERROR VersionReg=0x%02X\n",
      index + 1,
      version);

  return false;
}

//=====================================================
// LECTURA DE UN SENSOR
//=====================================================

void pollReader(uint8_t index)
{
  if (!readerAlive(index))
  {
    resetReader(index);
    return;
  }

  MFRC522 &reader = readers[index];

  //=========================================
  // NO HAY TARJETA REGISTRADA
  //=========================================

  if (!cardPresent[index])
  {
    if (reader.PICC_IsNewCardPresent() &&
        reader.PICC_ReadCardSerial())
    {
      String uid = uidToString(reader);

      cardPresent[index] = true;
      lastUid[index] = uid;

      publishCardState(index, uid, true);

      reader.PICC_HaltA();
      reader.PCD_StopCrypto1();
    }

    return;
  }

  //=========================================
  // YA HABIA UNA TARJETA
  //=========================================

  byte atqa[2];
  byte atqaSize = sizeof(atqa);

  MFRC522::StatusCode status =
      reader.PICC_WakeupA(
          atqa,
          &atqaSize);

  if (status != MFRC522::STATUS_OK ||
      !reader.PICC_ReadCardSerial())
  {
    publishCardState(
        index,
        lastUid[index],
        false);

    cardPresent[index] = false;
    lastUid[index] = "";

    reader.PCD_StopCrypto1();

    return;
  }

  String uid = uidToString(reader);

  if (uid != lastUid[index])
  {
    publishCardState(
        index,
        lastUid[index],
        false);

    publishCardState(
        index,
        uid,
        true);

    lastUid[index] = uid;
  }

  reader.PICC_HaltA();
  reader.PCD_StopCrypto1();
}

//=====================================================
// SETUP
//=====================================================

void setup()
{
  pinMode(LED_PIN, OUTPUT);

  Serial.begin(115200);

  EEPROM.begin(EEPROM_SIZE);
  if (!loadBrokerIpFromEEPROM())
  {
    saveBrokerIpToEEPROM(mqttServerIp);
    Serial.printf(
        "Guardando IP del broker en EEPROM: %s\n",
        mqttServerIp.toString().c_str());
  }

  client.setServer(mqttServerIp, mqtt_port);

  delay(1000);

  SPI.begin(18, 19, 23);

  for (uint8_t i = 0; i < NUM_READERS; i++)
  {
    pinMode(RFID_SS[i], OUTPUT);
    digitalWrite(RFID_SS[i], HIGH);
  }

  for (uint8_t i = 0; i < NUM_READERS; i++)
  {
    pinMode(RFID_RST[i], OUTPUT);

    digitalWrite(
        RFID_RST[i],
        HIGH);

    delay(50);

    readers[i].PCD_Init();

    delay(50);

    byte version =
        readers[i].PCD_ReadRegister(
            MFRC522::VersionReg);

    Serial.printf(
        "RFID %d VersionReg = 0x%02X\n",
        i + 1,
        version);
  }

    if (connectWifi())
    {
      if (reconnectMqtt())
      {
        publishTelemetry(
          "{\"tag\": \"status\",\"esp\": " + String(ESP_ID) + ",\"message\": \"Sistema inicializado\"}");
      }
    }
}

//=====================================================
// LOOP
//=====================================================

void loop()
{
  static uint8_t activeReader = 0;

  static unsigned long lastBlink = 0;
  static bool ledState = false;

  if (WiFi.status() != WL_CONNECTED)
  {
    if (millis() - lastWifiAttempt >= 10000)
    {
      lastWifiAttempt = millis();
      connectWifi();
    }
  }

  if (!client.connected() && WiFi.status() == WL_CONNECTED)
  {
    if (millis() - lastMqttAttempt >= 5000)
    {
      lastMqttAttempt = millis();
      reconnectMqtt();
    }
  }

  client.loop();

  pollSerialCommands(serial0Buffer);

  pollReader(activeReader);

  activeReader++;

  if (activeReader >= NUM_READERS)
  {
    activeReader = 0;
  }

  unsigned long now = millis();

  if (now - lastBlink >= 500)
  {
    lastBlink = now;

    ledState = !ledState;

    digitalWrite(
        LED_PIN,
        ledState);
  }

  delay(5);
}
