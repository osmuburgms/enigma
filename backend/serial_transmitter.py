import socket
import sys

try:
    import serial
    from serial.serialutil import SerialException
except ImportError:
    serial = None
    SerialException = Exception

DEFAULT_SERIAL_PORT = "/dev/serial0"
DEFAULT_BAUDRATE = 115200
DEFAULT_TIMEOUT = 2


def get_local_ip():
    """Obtiene la IP local de la Raspberry Pi conectada a la red."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("8.8.8.8", 80))
            return sock.getsockname()[0]
    except Exception:
        return None


class SerialIPTransmitter:
    """Envía la dirección IP del broker MQTT a una ESP32 por UART en formato MQTT:IP."""

    def __init__(self, port=DEFAULT_SERIAL_PORT, baudrate=DEFAULT_BAUDRATE, timeout=DEFAULT_TIMEOUT):
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.serial_port = None

    def _open_serial(self):
        if serial is None:
            raise RuntimeError("pyserial no está instalado. Instala pyserial en el entorno de Python.")

        if self.serial_port and self.serial_port.is_open:
            return self.serial_port

        try:
            self.serial_port = serial.Serial(self.port, self.baudrate, timeout=self.timeout)
            return self.serial_port
        except SerialException as e:
            raise RuntimeError(f"No se pudo abrir el puerto serial '{self.port}': {e}")

    def send_mqtt_ip(self, broker_ip=None):
        """Envía la IP del broker MQTT en formato 'MQTT:IP' por UART."""
        broker_ip = broker_ip or get_local_ip()
        if not broker_ip:
            return False, "No se pudo determinar la IP local de la Raspberry Pi." 

        message = f"MQTT:{broker_ip}\n"

        try:
            ser = self._open_serial()
            ser.write(message.encode("utf-8"))
            ser.flush()
            return True, f"Enviado por UART: {message.strip()}"
        except Exception as e:
            return False, str(e)

    def close(self):
        if self.serial_port and self.serial_port.is_open:
            self.serial_port.close()
            self.serial_port = None


if __name__ == "__main__":
    """
    Script independiente para enviar la IP del broker MQTT a la ESP32 por serial.
    
    Uso:
        python3 serial_transmitter.py                    # Detecta la IP automáticamente
        python3 serial_transmitter.py 192.168.1.100      # Especifica la IP
        python3 serial_transmitter.py 192.168.1.100 /dev/ttyUSB0  # Con puerto serial personalizado
    """
    
    ip = None
    port = DEFAULT_SERIAL_PORT
    
    if len(sys.argv) > 1:
        ip = sys.argv[1]
    
    if len(sys.argv) > 2:
        port = sys.argv[2]
    
    transmitter = SerialIPTransmitter(port=port)
    
    try:
        success, message = transmitter.send_mqtt_ip(broker_ip=ip)
        print(message)
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        transmitter.close()
