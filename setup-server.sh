#!/bin/bash
# ReeTrade - Schnelles Setup Script für Hetzner/Ubuntu Server
# Führen Sie aus mit: curl -sSL https://raw.githubusercontent.com/IHR_REPO/setup.sh | bash

set -e

echo "=========================================="
echo "  ReeTrade Terminal - Server Setup"
echo "=========================================="

# Farben
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

print_status() { echo -e "${GREEN}[✓]${NC} $1"; }
print_warning() { echo -e "${YELLOW}[!]${NC} $1"; }
print_error() { echo -e "${RED}[✗]${NC} $1"; }

# System Update
print_status "System wird aktualisiert..."
apt update && apt upgrade -y

# Pakete installieren
print_status "Pakete werden installiert..."
apt install -y git python3 python3-pip python3-venv nodejs npm nginx ufw

# MongoDB installieren
print_status "MongoDB wird installiert..."
if ! command -v mongod &> /dev/null; then
    curl -fsSL https://pgp.mongodb.com/server-7.0.asc | gpg -o /usr/share/keyrings/mongodb-server-7.0.gpg --dearmor
    echo "deb [ signed-by=/usr/share/keyrings/mongodb-server-7.0.gpg ] https://repo.mongodb.org/apt/ubuntu jammy/mongodb-org/7.0 multiverse" | tee /etc/apt/sources.list.d/mongodb-org-7.0.list
    apt update
    apt install -y mongodb-org
fi

systemctl start mongod
systemctl enable mongod
print_status "MongoDB läuft!"

# App Verzeichnis
print_status "App-Verzeichnis wird erstellt..."
mkdir -p /opt/reetrade
cd /opt/reetrade

echo ""
print_warning "Nächste Schritte:"
echo "1. Code hochladen: scp -r /pfad/zu/app/* root@SERVER_IP:/opt/reetrade/"
echo "2. Backend einrichten: cd /opt/reetrade/backend && python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt"
echo "3. .env Dateien konfigurieren"
echo "4. Services starten (siehe HETZNER_DEPLOYMENT.md)"
echo ""
print_status "Basis-Setup abgeschlossen!"
