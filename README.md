# 💡 Enigma del Einstein - Sistema Completo RFID + Web

Un juego de lógica estilo "Einstein" que integra sensores RFID reales vía ESP32C6, conexión MQTT y una interfaz web interactiva en tiempo real.

**Características:**
- Tablero 5x5 con lógica deductiva
- Interfaz web en tiempo real con Socket.IO
- Integración RFID con 5 lectores conectados a ESP32C6
- Comunicación MQTT para sensores remotos
- Actualización de IP del servidor por serial desde Raspberry Pi
- Sistema de pistas dinámicas y validación automática

---

## ⚠️ Requisitos del Sistema

### Hardware
- **Raspberry Pi 400** (o compatible con GPIO)
- **ESP32C6** con 5 lectores RFID (MFRC522)
- Cables de conexión para serial (GPIO 14 TX, GPIO 15 RX)
- Broker MQTT (ej: Mosquitto) en la red o localhost

### Software
- Python 3.7+
- pip y virtualenv
- Navegador web moderno (Chrome, Firefox, etc.)

---

## ☰ Estructura del Proyecto

```
enigma/
├── ESP32-C6/
│   ├── enigma.ino                # ESP32-C6 source code
│   ├── esp32_apmode.ino          # ESP32-C6 AP mode source code
├── backend/
│   ├── app.py                    # Punto de entrada principal
│   ├── game_logic.py             # Lógica del juego y validación
│   ├── mqtt_handler.py           # Gestión de conexiones MQTT
│   ├── serial_transmitter.py     # Envío de IP por serial a ESP32C6
│   ├── utils/
│   │   └── database.py           # Modelo del tablero 5x5
│   ├── scenarios.json            # Escenarios predefinidos
│   ├── requirements.txt          # Dependencias Python
│   ├── test_game.py              # Script de pruebas
│   └── uid_pruebas.txt           # UIDs de prueba para sensores
├── frontend/
│   ├── index.html                # Interfaz principal
│   ├── css/
│   │   └── styles.css            # Estilos
│   ├── js/
│   │   └── app.js                # Lógica del frontend
│   └── images/                   # Imágenes usadas en el frontend
├── run.sh                        # Script de inicio
├── restart.sh                    # Script de reinicio
├── send_ip.sh                    # Script para enviar IP automáticamente
├── send_ip_manual.sh             # Script para enviar IP manualmente
├── enigma.service                # Servicio systemd (opcional)
└── README.md                     # Este archivo
```

---

## ⚙️ Instalación y Configuración

### 1. Clonar/preparar el proyecto
```bash
cd /home/pi400/enigma
```

### 2. Crear entorno virtual
```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Instalar dependencias
```bash
pip install -r backend/requirements.txt
```

### 4. Configurar Broker MQTT (opcional)
Si no tienes un broker MQTT en tu red, instala Mosquitto:

```bash
sudo apt-get install mosquitto mosquitto-clients
sudo systemctl start mosquitto
sudo systemctl enable mosquitto
```

Verifica la conexión:
```bash
mosquitto_sub -h localhost -t "guardian/#" -v
```

---

## ⏻ Cómo Iniciar el Sistema

### Opción 1: Ejecución manual
```bash
source venv/bin/activate
./run.sh
```

El servidor estará disponible en: **http://localhost:5000**

### Opción 2: Usar systemd (para autoinicios)
```bash
sudo cp enigma.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl start enigma
sudo systemctl enable enigma
```

Ver logs:
```bash
sudo journalctl -u enigma -f
```

---

## >_ Pruebas desde Terminal

### 1. Probar API REST directamente

**Obtener estado del juego:**
```bash
curl http://localhost:5000/api/game/status
```

**Obtener tablero:**
```bash
curl http://localhost:5000/api/game/board
```

**Obtener pistas:**
```bash
curl http://localhost:5000/api/game/clues
```

**Obtener logs:**
```bash
curl http://localhost:5000/api/system/logs
```

### 2. Simular lectura RFID desde terminal

#### Opción A: curl (HTTP REST)

```bash
curl -X POST http://localhost:5000/api/rfid \
  -H "Content-Type: application/json" \
  -d '{
    "tag": "AB CD EF 12",
    "esp": 1,
    "sensor": 1
  }'
```

**Parámetros:**
- `tag`: UID del tag RFID (formato hexadecimal con espacios)
- `esp`: ID de la ESP32 (1-5 típicamente)
- `sensor`: Número del sensor RFID (1-5)

#### Opción B: test_game.py (Directo)

Desde dentro de la carpeta `backend` con el **entorno virtual activo**:

```bash
cd backend
python3 test_game.py place <fila> <columna> "<UID>"
```

**Ejemplo:**
```bash
python3 test_game.py place 1 1 "AB CD EF 12"
```

Este método coloca el tag directamente en el tablero sin necesidad de estar conectado a MQTT.

### 3. Reiniciar partida
```bash
curl -X POST http://localhost:5000/api/game/reset
```

### 4. Script de prueba automatizada

```bash
cd backend
python3 test_game.py
```

Este script simula múltiples lecturas RFID y verifica la lógica del juego.

---

## ⏏ Envío de IP por Serial a ESP32C6

### Conexión física Raspberry Pi ↔ ESP32C6

```
 Raspberry Pi 400            ESP32C6
──────────────────         ─────────
Pin 8  (GPIO14)   ───────>  RX (17)
Pin 10 (GPIO15)   <───────  TX (16)
Pin 6  (GND)      ───────>  GND
Pin 1 (3V3)       ───────>  3V3
```

**Verificar conexión:**
```bash
ls -l /dev/serial0
# O también: ls -l /dev/ttyAMA0
```

### Envío de IP Automático

**Con detección automática de IP:**
```bash
source venv/bin/activate
sudo python3 backend/serial_transmitter.py
```

**Con IP específica:**
```bash
sudo python3 backend/serial_transmitter.py 192.168.43.10
```

**Con puerto serial personalizado:**
```bash
sudo python3 backend/serial_transmitter.py 192.168.43.10 /dev/ttyUSB0
```

### Formato de mensaje
El script envía el siguiente formato que la ESP32C6 espera:
```
MQTT:192.168.43.10
```

La ESP32C6 procesa este comando y actualiza la dirección del servidor MQTT en su EEPROM.

### Automatizar envío al iniciar
Agrega al final de `~/.bashrc` o crea un script:
```bash
# Enviar IP al iniciar el backend
sudo python3 /home/pi400/enigma/backend/serial_transmitter.py
```

---

## ⓘ Scripts de Utilidad

El proyecto incluye 3 scripts `.sh` en la carpeta raíz para facilitar operaciones comunes:

### 1. `restart.sh` - Reiniciar servicio Enigma

Reinicia el servicio systemd de Enigma:

```bash
./restart.sh
```

**Equivalente manual:**
```bash
sudo systemctl restart enigma.service
```

**Casos de uso:**
- Recargar cambios en el código
- Resolver problemas de conexión
- Actualizar configuración

---

### 2. `send_ip.sh` - Enviar IP automática del servidor

Envía automáticamente la IP actual del servidor Raspberry Pi a la ESP32C6 por serial. Activa el entorno virtual y ejecuta `serial_transmitter.py`:

```bash
./send_ip.sh
```

**Equivalente manual:**
```bash
source venv/bin/activate
cd backend
sudo python3 serial_transmitter.py
```

**Casos de uso:**
- Sincronizar IP después de cambios de red
- Automatizar en scripts de inicio
- Ejecutar periódicamente vía cron

---

### 3. `send_ip_manual.sh` - Enviar IP específica

Envía una IP específica (como argumento) a la ESP32C6 por serial:

```bash
./send_ip_manual.sh 192.168.1.100
./send_ip_manual.sh 192.168.43.10
```

**Equivalente manual:**
```bash
source venv/bin/activate
cd backend
sudo python3 serial_transmitter.py 192.168.1.100
```

**Casos de uso:**
- Cambiar manualmente la IP del servidor MQTT
- Probar conectividad con direcciones específicas
- Configuración post-instalación

---

## ⛁ Integración MQTT

### Tópicos suscritos por el backend

| Tópico | Descripción |
|--------|-------------|
| `guardian/sensores/rfid` | Datos de lectores RFID (5 sensores) |
| `guardian/system/open` | Control remoto de apertura |
| `guardian/game/reset` | Reiniciar partida |
| `guardian/game/status` | Solicitar estado actual |

### Tópicos publicados por el backend

| Tópico | Descripción |
|--------|-------------|
| `guardian/system/log` | Mensajes de log del sistema |
| `guardian/game/state` | Estado completo del tablero |
| `guardian/game/completed` | Notificación de fin de juego |
| `guardian/game/status/response` | Respuesta a solicitud de estado |

### Mensaje RFID esperado (desde ESP32C6)

```json
{
  "tag": "AB CD EF 12",
  "esp": 1,
  "sensor": 1
}
```

### Prueba de conexión MQTT

**Terminal 1 - Suscribirse a todos los mensajes:**
```bash
mosquitto_sub -h localhost -t "guardian/#" -v
```

**Terminal 2 - Publicar un UID de prueba:**
```bash
mosquitto_pub -h localhost -t "guardian/sensores/rfid" \
  -m '{"tag": "12 34 56 78", "esp": 1, "sensor": 1}'
```

---

## 🌐 API REST Completa

### Estado del Juego
```bash
GET /api/game/status
```
**Respuesta:** JSON con estado completo (tablero, pistas, etc.)

### Obtener Tablero
```bash
GET /api/game/board
```
**Respuesta:** Solo la matriz 5x5 del tablero

### Obtener Pistas
```bash
GET /api/game/clues
```
**Respuesta:** Lista de pistas disponibles

### Reiniciar Juego
```bash
POST /api/game/reset
```
**Respuesta:** Nuevo estado del juego

### Simular RFID
```bash
POST /api/rfid
Content-Type: application/json

{
  "tag": "AB CD EF 12",
  "esp": 1,
  "sensor": 1
}
```
**Respuesta:** Resultado de la operación y nuevo estado

### Obtener Logs
```bash
GET /api/system/logs
```
**Respuesta:** Últimos 50 logs del backend

---

## </> Frontend - Interfaz Web

La interfaz está disponible en **http://localhost:5000** y muestra:

- **Estado del Juego**: Nombre y progreso actual
- **Tablero 5x5**: Valores colocados con colores distintivos
- **Pistas**: Con indicadores de estado (✓ válida, ✗ inválida)
- **Último RFID**: UID detectado más recientemente
- **Logs en Vivo**: Eventos del backend actualizados en tiempo real

La comunicación es bidireccional mediante Socket.IO para actualizaciones instantáneas.

---

## ⛔ Troubleshooting

### El backend no inicia
```bash
# Verificar errores de importación
python3 -m py_compile backend/app.py

# Ver el error completo
python3 backend/app.py
```

### No hay conexión MQTT
```bash
# Verificar que Mosquitto está corriendo
sudo systemctl status mosquitto

# Probar conexión al broker
mosquitto_pub -h 127.0.0.1 -t test -m "hola"
```

### Serial no funciona
```bash
# Verificar puerto disponible
ls -la /dev/tty*

# Verificar permisos
sudo usermod -a -G dialout $USER

# Dar permisos específicos
sudo chmod 666 /dev/serial0
```

### No se reciben UIDs de la ESP32C6
1. Verifica la conexión física entre pines
2. Confirma que el código de la ESP32C6 tiene configurado GPIO 16/17 como TX/RX
3. Prueba con `mosquitto_pub` para simular
4. Revisa los logs: `GET /api/system/logs`

### Frontend no actualiza
1. Abre consola del navegador (F12) para ver errores
2. Verifica que Socket.IO está conectado
3. Recarga la página: Ctrl+Shift+R (caché limpio)

---

## { } Estructura de Datos - Tablero

El tablero es una matriz 5x5 donde:
- Fila 0: Nombres
- Fila 1: Mascotas
- Fila 2: Bebidas
- Fila 3: Nacionalidades
- Fila 4: Dulces

Ejemplo de estado:
```json
{
  "board": [
    [1, 2, 0, 3, 4],
    [4, 0, 1, 2, 3],
    ...
  ],
  "clues": [
    "La persona con gato...",
    "El inglés bebe cerveza..."
  ],
  "tags": {
    "AB CD EF 12": {"row": 0, "col": 1},
    "12 34 56 78": {"row": 1, "col": 2}
  }
}
```

---

## 🔒 Seguridad y Consideraciones

- El broker MQTT debe estar en red privada o con autenticación
- Los UIDs de tags son identificadores únicos; regístralos en `uid_pruebas.txt`
- El puerto 5000 debe estar protegido en producción (usar nginx, firewall)
- Los logs se mantienen en memoria (últimos 200)

---

## 📞 Comandos Útiles

```bash
# Compilar verificación
python3 -m py_compile backend/*.py

# Ver servicios MQTT activos
systemctl status mosquitto

# Depuración del serial
sudo minicom -D /dev/serial0 -b 115200

# Killing procesos Python
pkill -f "python3 backend/app.py"

# Ver logs del servicio
sudo journalctl -u enigma -n 50 -f
```

---

## ✍︎ Licencia

Proyecto de investigación/educativo.

**¿Preguntas?** Revisa los logs, verifica las conexiones físicas y consulta los scripts de prueba.
