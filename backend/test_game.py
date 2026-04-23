#!/usr/bin/env python3
"""
Script de prueba para simular sensores RFID

Permite probar el sistema sin necesidad de ESP32 reales
Úsalo así:
    python test_game.py place <row> <col> <uid>
    python test_game.py status
    python test_game.py reset
"""

import paho.mqtt.client as mqtt
import json
import sys
import time

class TestClient:
    def __init__(self, broker="localhost", port=1883):
        self.broker = broker
        self.port = port
        # Usar callback_api_version para compatibilidad con paho-mqtt v2.0+
        self.client = mqtt.Client(
            client_id="enigma_test_client",
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2
        )
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        self.connected = False

    def on_connect(self, client, userdata, flags, rc, properties=None):
        if rc == 0:
            print(f"✓ Conectado a {self.broker}:{self.port}")
            self.connected = True
        else:
            print(f"✗ Error de conexión, código: {rc}")

    def on_message(self, client, userdata, msg, properties=None):
        try:
            payload = msg.payload.decode()
            print(f"\n← [{msg.topic}]")
            try:
                data = json.loads(payload)
                print(json.dumps(data, indent=2, ensure_ascii=False))
            except:
                print(payload)
        except Exception as e:
            print(f"Error procesando mensaje: {e}")

    def connect(self):
        try:
            self.client.connect(self.broker, self.port, 60)
            self.client.subscribe("guardian/game/state", qos=1)
            self.client.subscribe("guardian/system/log", qos=1)
            self.client.subscribe("guardian/game/completed", qos=1)
            self.client.subscribe("guardian/game/status/response", qos=1)
            self.client.loop_start()
            time.sleep(1)
            return True
        except Exception as e:
            print(f"✗ Error conectando: {e}")
            return False

    def place_rfid(self, row, col, uid):
        """Simula la detección de un RFID"""
        if not self.connected:
            print("✗ No conectado a MQTT")
            return

        payload = {
            "tag": uid,
            "esp": col,
            "sensor": row
        }

        print(f"→ Colocando tarjeta {uid} en posición ({row}, {col})")
        self.client.publish("guardian/sensores/rfid", json.dumps(payload))
        time.sleep(0.5)

    def request_status(self):
        """Solicita el estado del juego"""
        if not self.connected:
            print("✗ No conectado a MQTT")
            return

        print("→ Solicitando estado del juego...")
        self.client.publish("guardian/game/status", "")
        time.sleep(0.5)

    def reset_game(self):
        """Reinicia el juego"""
        if not self.connected:
            print("✗ No conectado a MQTT")
            return

        print("→ Reiniciando juego...")
        self.client.publish("guardian/game/reset", "")
        time.sleep(0.5)

    def disconnect(self):
        self.client.loop_stop()
        self.client.disconnect()

def show_usage():
    print("""
Uso: python test_game.py <comando> [argumentos]

Comandos:
  place <fila> <col> <uid>  - Colocar tarjeta en posición
  status                     - Obtener estado del juego
  reset                      - Reiniciar el juego
  test                       - Ejecutar prueba automática

Ejemplos:
  python test_game.py place 1 1 "AB CD EF 01"
  python test_game.py status
  python test_game.py reset
  python test_game.py test
    """)

def run_test_suite(client):
    """Ejecuta una serie de pruebas automáticas"""
    print("\n" + "="*50)
    print("PRUEBA AUTOMÁTICA")
    print("="*50 + "\n")

    # Verificar UIDs disponibles
    uids = {
        "color": ["AB CD EF 01", "AB CD EF 02", "AB CD EF 03", "AB CD EF 04", "AB CD EF 05"],
        "nacionalidad": ["0A AB 58 BF", "43 FF DC 06", "E9 A1 11 4D", "50 2B D0 A6", "A0 77 93 5E"],
        "mascota": ["22 33 44 55", "22 33 44 56", "22 33 44 57", "22 33 44 58", "22 33 44 59"],
        "comida": ["33 44 55 66", "33 44 55 67", "33 44 55 68", "33 44 55 69", "33 44 55 70"],
        "dulces": ["44 55 66 77", "44 55 66 78", "44 55 66 79", "44 55 66 80", "44 55 66 81"],
    }

    # Test 1: Colocar tarjetas válidas
    print("\n[TEST 1] Colocando tarjetas válidas...")
    test_moves = [
        (1, 1, uids["color"][0]),
        (1, 2, uids["nacionalidad"][0]),
        (2, 1, uids["mascota"][0]),
        (2, 2, uids["comida"][0]),
        (3, 3, uids["dulces"][0]),
    ]

    for row, col, uid in test_moves:
        print(f"  Colocando en ({row}, {col}): {uid}")
        client.place_rfid(row, col, uid)
        time.sleep(1)

    # Test 2: Mover tag a nueva posición (debe permitirlo)
    print("\n[TEST 2] Moviendo tag a nueva posición (debe permitirlo)...")
    client.place_rfid(1, 3, uids["color"][0])  # Mover color[0] de (1,1) a (1,3)
    time.sleep(1)

    # Test 3: Intentar duplicado de atributo en fila (debe fallar)
    print("\n[TEST 3] Intentando colocar mismo atributo en fila (debe fallar)...")
    client.place_rfid(1, 4, uids["color"][1])  # Intentar colocar otro color en fila 1
    time.sleep(1)

    # Test 4: Mover tag a otra fila (debe permitirlo)
    print("\n[TEST 4] Moviendo tag a otra fila (debe permitirlo)...")
    client.place_rfid(2, 2, uids["color"][0])  # Mover color[0] de (1,3) a (2,2)
    time.sleep(1)

    # Test 5: Reiniciar
    print("\n[TEST 5] Reiniciando juego...")
    client.reset_game()
    time.sleep(1)

    print("\n" + "="*50)
    print("PRUEBA COMPLETADA")
    print("="*50 + "\n")

if __name__ == "__main__":
    client = TestClient()

    if not client.connect():
        sys.exit(1)

    try:
        if len(sys.argv) < 2:
            show_usage()
        elif sys.argv[1] == "place" and len(sys.argv) == 5:
            row = int(sys.argv[2])
            col = int(sys.argv[3])
            uid = sys.argv[4]
            client.place_rfid(row, col, uid)
            time.sleep(2)
        elif sys.argv[1] == "status":
            client.request_status()
            time.sleep(2)
        elif sys.argv[1] == "reset":
            client.reset_game()
            time.sleep(2)
        elif sys.argv[1] == "test":
            run_test_suite(client)
        else:
            show_usage()
    finally:
        client.disconnect()
