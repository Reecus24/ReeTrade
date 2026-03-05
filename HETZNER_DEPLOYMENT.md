# ReeTrade Terminal - Hetzner Deployment Anleitung

## Übersicht
Diese Anleitung zeigt, wie Sie den Trading Bot auf einem Hetzner VPS für 24/7 Betrieb deployen.

**Geschätzte Kosten:** ~4-5€/Monat (CX11 Server)
**Geschätzte Zeit:** 30-45 Minuten

---

## Schritt 1: Hetzner Account & Server erstellen

### 1.1 Account erstellen
1. Gehen Sie zu [https://www.hetzner.com/cloud](https://www.hetzner.com/cloud)
2. Erstellen Sie einen Account
3. Fügen Sie eine Zahlungsmethode hinzu

### 1.2 Server erstellen
1. Klicken Sie auf **"Add Server"**
2. Wählen Sie:
   - **Location:** Falkenstein oder Nürnberg (Deutschland)
   - **Image:** Ubuntu 22.04
   - **Type:** CX11 (2 vCPU, 2 GB RAM, 20 GB SSD) - ~4€/Monat
   - **SSH Key:** Fügen Sie Ihren SSH Key hinzu (oder nutzen Sie Passwort)
3. Klicken Sie **"Create & Buy Now"**
4. Notieren Sie die **IP-Adresse** des Servers

---

## Schritt 2: Mit Server verbinden

### Windows (PowerShell oder PuTTY):
```bash
ssh root@IHRE_SERVER_IP
```

### Mac/Linux:
```bash
ssh root@IHRE_SERVER_IP
```

---

## Schritt 3: Server vorbereiten

Kopieren Sie diese Befehle und führen Sie sie aus:

```bash
# System updaten
apt update && apt upgrade -y

# Benötigte Pakete installieren
apt install -y git python3 python3-pip python3-venv nodejs npm nginx certbot python3-certbot-nginx

# MongoDB installieren
curl -fsSL https://pgp.mongodb.com/server-7.0.asc | gpg -o /usr/share/keyrings/mongodb-server-7.0.gpg --dearmor
echo "deb [ signed-by=/usr/share/keyrings/mongodb-server-7.0.gpg ] https://repo.mongodb.org/apt/ubuntu jammy/mongodb-org/7.0 multiverse" | tee /etc/apt/sources.list.d/mongodb-org-7.0.list
apt update
apt install -y mongodb-org

# MongoDB starten
systemctl start mongod
systemctl enable mongod

# App-Verzeichnis erstellen
mkdir -p /opt/reetrade
cd /opt/reetrade
```

---

## Schritt 4: Code hochladen

### Option A: Von GitHub (empfohlen)
```bash
cd /opt/reetrade
git clone https://github.com/IHR_USERNAME/IHR_REPO.git .
```

### Option B: Manuell per SCP
Von Ihrem lokalen Computer:
```bash
scp -r /pfad/zu/app/* root@IHRE_SERVER_IP:/opt/reetrade/
```

---

## Schritt 5: Backend einrichten

```bash
cd /opt/reetrade/backend

# Python Virtual Environment erstellen
python3 -m venv venv
source venv/bin/activate

# Dependencies installieren
pip install --upgrade pip
pip install -r requirements.txt

# .env Datei erstellen
cat > .env << 'EOF'
MONGO_URL=mongodb://localhost:27017
DB_NAME=reetrade_db
JWT_SECRET=IHR_GEHEIMER_JWT_KEY_HIER_AENDERN
ENCRYPTION_KEY=IHR_ENCRYPTION_KEY_HIER_GENERIEREN
EOF

# Encryption Key generieren (kopieren und in .env einfügen)
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

---

## Schritt 6: Frontend bauen

```bash
cd /opt/reetrade/frontend

# Dependencies installieren
npm install

# .env für Production erstellen
cat > .env << 'EOF'
REACT_APP_BACKEND_URL=https://IHRE_DOMAIN.de
EOF

# Frontend bauen
npm run build
```

---

## Schritt 7: Systemd Services erstellen

### Backend Service:
```bash
cat > /etc/systemd/system/reetrade-backend.service << 'EOF'
[Unit]
Description=ReeTrade Backend API
After=network.target mongod.service

[Service]
Type=simple
User=root
WorkingDirectory=/opt/reetrade/backend
Environment=PATH=/opt/reetrade/backend/venv/bin
ExecStart=/opt/reetrade/backend/venv/bin/uvicorn server:app --host 0.0.0.0 --port 8001
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF
```

### Worker Service (für 24/7 Trading):
```bash
cat > /etc/systemd/system/reetrade-worker.service << 'EOF'
[Unit]
Description=ReeTrade Trading Worker
After=network.target mongod.service reetrade-backend.service

[Service]
Type=simple
User=root
WorkingDirectory=/opt/reetrade/backend
Environment=PATH=/opt/reetrade/backend/venv/bin
ExecStart=/opt/reetrade/backend/venv/bin/python -c "import asyncio; from worker import MultiUserTradingWorker; w = MultiUserTradingWorker(); asyncio.run(w.start())"
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF
```

### Services aktivieren:
```bash
systemctl daemon-reload
systemctl enable reetrade-backend
systemctl enable reetrade-worker
systemctl start reetrade-backend
systemctl start reetrade-worker
```

---

## Schritt 8: Nginx als Reverse Proxy

```bash
cat > /etc/nginx/sites-available/reetrade << 'EOF'
server {
    listen 80;
    server_name IHRE_DOMAIN.de;  # Oder Server-IP

    # Frontend (statische Dateien)
    location / {
        root /opt/reetrade/frontend/build;
        try_files $uri $uri/ /index.html;
    }

    # Backend API
    location /api {
        proxy_pass http://127.0.0.1:8001;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_cache_bypass $http_upgrade;
        proxy_read_timeout 300s;
    }
}
EOF

# Aktivieren
ln -s /etc/nginx/sites-available/reetrade /etc/nginx/sites-enabled/
rm /etc/nginx/sites-enabled/default
nginx -t
systemctl restart nginx
```

---

## Schritt 9: SSL Zertifikat (optional aber empfohlen)

Wenn Sie eine Domain haben:
```bash
certbot --nginx -d IHRE_DOMAIN.de
```

---

## Schritt 10: Firewall einrichten

```bash
ufw allow 22    # SSH
ufw allow 80    # HTTP
ufw allow 443   # HTTPS
ufw enable
```

---

## Nützliche Befehle

### Status prüfen:
```bash
systemctl status reetrade-backend
systemctl status reetrade-worker
systemctl status mongod
```

### Logs anzeigen:
```bash
# Backend Logs
journalctl -u reetrade-backend -f

# Worker Logs (Trading Bot)
journalctl -u reetrade-worker -f

# Letzte 100 Zeilen
journalctl -u reetrade-worker -n 100
```

### Neustart:
```bash
systemctl restart reetrade-backend
systemctl restart reetrade-worker
```

### Stoppen:
```bash
systemctl stop reetrade-worker   # Stoppt Trading
systemctl stop reetrade-backend  # Stoppt API
```

---

## Troubleshooting

### MongoDB startet nicht:
```bash
systemctl status mongod
journalctl -u mongod -n 50
```

### Backend Error:
```bash
cd /opt/reetrade/backend
source venv/bin/activate
python server.py  # Manuell starten um Fehler zu sehen
```

### Worker Error:
```bash
cd /opt/reetrade/backend
source venv/bin/activate
python -c "from worker import MultiUserTradingWorker; import asyncio; w = MultiUserTradingWorker(); asyncio.run(w.start())"
```

---

## Updates deployen

```bash
cd /opt/reetrade

# Neuen Code holen
git pull

# Backend neu starten
systemctl restart reetrade-backend
systemctl restart reetrade-worker

# Bei Frontend-Änderungen:
cd frontend
npm install
npm run build
```

---

## Kosten-Übersicht

| Komponente | Kosten/Monat |
|------------|--------------|
| Hetzner CX11 | ~4€ |
| Domain (optional) | ~1€ |
| **Gesamt** | **~5€/Monat** |

---

## Sicherheits-Tipps

1. **Ändern Sie alle Secrets** in den .env Dateien
2. **Nutzen Sie SSH Keys** statt Passwörter
3. **Halten Sie das System aktuell:** `apt update && apt upgrade`
4. **Backups:** MongoDB Daten regelmäßig sichern

---

Bei Fragen: Die Logs sind Ihr bester Freund! 🔍
