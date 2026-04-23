import json
import os
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
from flask_socketio import SocketIO
from mqtt_handler import MQTTHandler
from game_logic import GameLogic


class App:
    def __init__(self):
        self.frontend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "frontend"))
        self.flask_app = Flask(__name__, static_folder=self.frontend_dir, static_url_path="")
        CORS(self.flask_app)
        self.socketio = SocketIO(self.flask_app, cors_allowed_origins="*", async_mode="threading")

        self.mqtt = MQTTHandler(app_callback=self.on_mqtt_message)
        self.logic = None
        self.log_history = []

        self._register_routes()
        self._register_socket_events()

    def _log(self, message):
        payload = {"message": message}
        self.log_history.append(payload)
        if len(self.log_history) > 200:
            self.log_history.pop(0)
        self._emit_frontend_event("backend_log", payload)
        print(message)

    def _emit_frontend_event(self, event_name, payload):
        try:
            self.socketio.emit(event_name, payload)
        except Exception as e:
            print(f"[APP] Error enviando evento {event_name}: {e}")

    def _register_routes(self):
        @self.flask_app.route("/", defaults={"path": ""})
        @self.flask_app.route("/<path:path>")
        def serve_frontend(path):
            if path and os.path.exists(os.path.join(self.frontend_dir, path)):
                return send_from_directory(self.frontend_dir, path)
            return send_from_directory(self.frontend_dir, "index.html")

        @self.flask_app.route("/api/game/status", methods=["GET"])
        def api_game_status():
            return jsonify(self.logic.get_game_status())

        @self.flask_app.route("/api/game/board", methods=["GET"])
        def api_game_board():
            status = self.logic.get_game_status()
            return jsonify({"board": status["board"]})

        @self.flask_app.route("/api/game/clues", methods=["GET"])
        def api_game_clues():
            status = self.logic.get_game_status()
            return jsonify({"clues": status["clues"]})

        @self.flask_app.route("/api/game/reset", methods=["POST"])
        def api_game_reset():
            self._log("[APP] Reset solicitado desde frontend")
            self.logic.reset_game()
            return jsonify(self.logic.get_game_status())

        @self.flask_app.route("/api/rfid", methods=["POST"])
        def api_rfid():
            payload = request.get_json(silent=True)
            if not payload:
                return jsonify({"success": False, "message": "JSON inválido o faltante"}), 400

            uid = payload.get("tag")
            esp_id = payload.get("esp")
            sensor_id = payload.get("sensor")

            if uid is None or esp_id is None or sensor_id is None:
                return jsonify({"success": False, "message": "Se requieren tag, esp y sensor"}), 400

            self._log(f"[APP] RFID recibido desde frontend: UID={uid}, ESP={esp_id}, Sensor={sensor_id}")
            result = self.logic.process_rfid(uid, esp_id, sensor_id)
            return jsonify({"result": result, "status": self.logic.get_game_status()})

        @self.flask_app.route("/api/system/logs", methods=["GET"])
        def api_system_logs():
            return jsonify({"logs": self.log_history[-50:]})

    def _register_socket_events(self):
        @self.socketio.on("connect")
        def handle_connect():
            self._log("[APP] Frontend conectado via Socket.IO")
            self.socketio.emit("game_state", self.logic.get_game_status())

        @self.socketio.on("disconnect")
        def handle_disconnect():
            self._log("[APP] Frontend desconectado")

    def on_mqtt_message(self, topic, payload):
        self._log(f"[APP] Mensaje recibido desde MQTT {topic}: {payload}")

        if topic == "guardian/sensores/rfid":
            self._process_rfid_sensor(payload)
        elif topic == "guardian/system/open":
            self._log("[APP] Apertura manual solicitada.")
            self.mqtt.publish("guardian/system/log", "Apertura remota solicitada")
        elif topic == "guardian/game/reset":
            self._log("[APP] Reset del juego solicitado")
            self.logic.reset_game()
        elif topic == "guardian/game/status":
            self._log("[APP] Status del juego solicitado")
            status = self.logic.get_game_status()
            self.mqtt.publish(
                "guardian/game/status/response",
                json.dumps(status, indent=2, ensure_ascii=False)
            )

    def _process_rfid_sensor(self, payload):
        try:
            cleaned = payload.strip().replace("\ufeff", "")
            self._log(f"[APP] Payload limpio: {cleaned}")

            try:
                data = json.loads(cleaned)
            except json.JSONDecodeError as e:
                error_msg = f"[APP] Error decodificando JSON: {e}"
                self._log(error_msg)
                self.mqtt.publish("guardian/system/log", f"Error JSON: {str(e)}")
                return

            uid = data.get("tag")
            esp_id = data.get("esp")
            sensor_id = data.get("sensor")

            if not (uid and esp_id and sensor_id):
                self._log("[APP] Datos incompletos en payload")
                self.mqtt.publish("guardian/system/log", "Datos incompletos: tag, esp, sensor requeridos")
                return

            self._log(f"[APP] RFID válido - UID: {uid}, ESP: {esp_id}, Sensor: {sensor_id}")
            result = self.logic.process_rfid(uid, esp_id, sensor_id)
            if result["success"]:
                self._log(f"[APP] Movimiento exitoso: {result['message']}")
            else:
                self._log(f"[APP] Movimiento rechazado: {result['message']}")

        except KeyError as e:
            error_msg = f"[APP] Campo faltante en payload: {e}"
            self._log(error_msg)
            self.mqtt.publish("guardian/system/log", f"Error: campo faltante {str(e)}")
        except Exception as e:
            error_msg = f"[APP] Error inesperado: {e}"
            self._log(error_msg)
            self.mqtt.publish("guardian/system/log", f"Error inesperado: {str(e)}")

    def start(self):
        self.mqtt.start()
        self.logic = GameLogic(self.mqtt, frontend_callback=self._emit_frontend_event)
        self._log("[APP] Aplicación iniciada")
        self._log("[APP] Topics suscritos:")
        self._log("  - guardian/sensores/rfid (datos RFID de sensores)")
        self._log("  - guardian/system/open (control remoto)")
        self._log("  - guardian/game/reset (reiniciar juego)")
        self._log("  - guardian/game/status (obtener estado)")
        self._log("[APP] Topics disponibles para publicar:")
        self._log("  - guardian/system/log (mensajes del sistema)")
        self._log("  - guardian/game/state (estado del tablero)")
        self._log("  - guardian/game/completed (fin del juego)")
        self._log("  - guardian/game/status/response (respuesta de estado)")

    def run(self, host="0.0.0.0", port=5000):
        self.start()
        self._log(f"[APP] Servidor HTTP iniciado en http://{host}:{port}")
        self.socketio.run(
            self.flask_app,
            host=host,
            port=port,
            allow_unsafe_werkzeug=True
        )


if __name__ == "__main__":
    app = App()
    app.run()
