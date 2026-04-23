#!/bin/bash
if [ $# -eq 0 ]; then
    echo "Error: Debe proporcionar una IP como argumento"
    echo "Uso: $0 <ip>"
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"
source "$SCRIPT_DIR/venv/bin/activate"
cd "$SCRIPT_DIR/backend"

IP=$1
echo "Enviando IP: $IP"
sudo python3 serial_transmitter.py "$IP"
