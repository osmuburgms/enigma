#!/bin/bash
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"
source "$SCRIPT_DIR/venv/bin/activate"
cd "$SCRIPT_DIR/backend"
sudo python3 serial_transmitter.py
