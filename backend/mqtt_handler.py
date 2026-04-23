import paho.mqtt.client as mqtt
import json
import time
import threading

class MQTTHandler:
    """Manejador MQTT para el Enigma del Einstein"""
    
    def __init__(self, broker="localhost", port=1883, app_callback=None):
        self.broker = broker
        self.port = port
        # Usar callback_api_version para compatibilidad con paho-mqtt v2.0+
        self.client = mqtt.Client(
            client_id="enigma_backend",
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2
        )
        self.app_callback = app_callback
        self.connected = False
        self.reconnect_attempts = 0
        self.max_reconnect_attempts = 10
        self.reconnect_delay = 2

        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        self.client.on_disconnect = self.on_disconnect
        self.client.on_publish = self.on_publish

    def start(self):
        """Inicia el cliente MQTT"""
        print("[MQTT] Iniciando cliente...")
        self.try_connect()
        self.client.loop_start()

    def try_connect(self):
        """Intenta conectar al broker MQTT con reintentos exponenciales"""
        while not self.connected:
            try:
                delay = min(self.reconnect_delay * (2 ** self.reconnect_attempts), 30)
                print(f"[MQTT] Intento {self.reconnect_attempts + 1} de conexión a {self.broker}:{self.port}...")
                self.client.connect(self.broker, self.port, 60)
                print("[MQTT] Conexión establecida.")
                return
            except Exception as e:
                self.reconnect_attempts += 1
                print(f"[MQTT] Error de conexión: {e}. Reintentando en {delay}s...")
                if self.reconnect_attempts >= self.max_reconnect_attempts:
                    print(f"[MQTT] Máximos reintentos alcanzados ({self.max_reconnect_attempts})")
                    raise
                time.sleep(delay)

    def on_connect(self, client, userdata, flags, rc, properties=None):
        """Callback de conexión"""
        if rc == 0:
            self.connected = True
            self.reconnect_attempts = 0
            print(f"[MQTT] Conectado exitosamente (código: {rc})")
            
            # Suscribirse a los tópicos
            topics = [
                ("guardian/sensores/rfid", 1),      # Datos de sensores RFID
                ("guardian/system/open", 0),         # Control remoto
                ("guardian/game/reset", 0),          # Reiniciar juego
                ("guardian/game/status", 0),         # Solicitar estado
            ]
            
            for topic, qos in topics:
                client.subscribe(topic, qos)
                print(f"[MQTT] Suscrito a '{topic}' (QoS={qos})")
        else:
            self.connected = False
            print(f"[MQTT] Error de conexión, código: {rc}")

    def on_disconnect(self, client, userdata, rc, properties=None):
        """Callback de desconexión"""
        self.connected = False
        if rc != 0:
            print(f"[MQTT] Desconexión inesperada, código: {rc}")
        else:
            print("[MQTT] Desconectado correctamente")
        
        print("[MQTT] Intentando reconectar...")
        self.try_connect()

    def on_message(self, client, userdata, msg, properties=None):
        """Callback para mensajes recibidos"""
        try:
            payload = msg.payload.decode('utf-8')
            print(f"[MQTT] Mensaje recibido en '{msg.topic}'")
            print(f"       Payload: {payload[:100]}..." if len(payload) > 100 else f"       Payload: {payload}")
            
            if self.app_callback:
                self.app_callback(msg.topic, payload)
        except UnicodeDecodeError as e:
            print(f"[MQTT] Error decodificando mensaje: {e}")
        except Exception as e:
            print(f"[MQTT] Error procesando mensaje: {e}")

    def on_publish(self, client, userdata, mid, reason_codes=None, properties=None):
        """Callback para confirmación de publicación"""
        print(f"[MQTT] Mensaje publicado (mid: {mid})")

    def publish(self, topic, message, qos=1, retain=False):
        """Publica un mensaje en un tópico MQTT
        
        Args:
            topic: Tópico destino
            message: Mensaje a publicar (string)
            qos: QoS level (0, 1, 2)
            retain: Si mantener el último mensaje
        """
        try:
            if not self.connected:
                print(f"[MQTT] ADVERTENCIA: No conectado. No se puede publicar en '{topic}'")
                return False
            
            info = self.client.publish(topic, message, qos=qos, retain=retain)
            if info.rc == mqtt.MQTT_ERR_SUCCESS:
                print(f"[MQTT] Publicado en '{topic}' (QoS={qos})")
                return True
            else:
                print(f"[MQTT] Error publicando en '{topic}': código {info.rc}")
                return False
        except Exception as e:
            print(f"[MQTT] Excepción publicando: {e}")
            return False

    def stop(self):
        """Detiene el cliente MQTT"""
        print("[MQTT] Deteniendo cliente...")
        self.client.loop_stop()
        self.client.disconnect()

    def is_connected(self):
        """Retorna el estado de conexión"""
        return self.connected
