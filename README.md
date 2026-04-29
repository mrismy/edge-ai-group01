# Industrial Digital Twin – Group 24
## Distribution Transformer Health Monitoring System

> CO326 Course Project – Industrial Digital Twin & Cyber-Physical Security

---

## 👥 Group Members

| Name | Student ID | Role |
|------|-----------|------|
| Member 1 | E/20/009 | Edge AI & Simulation |
| Member 2 | E/20/199 | Node-RED & RUL |
| Member 3 | E/20/339 | Infrastructure & Security |
| Member 4 | E/20/371 | Documentation & Dashboards |

## 📋 Industrial Problem

**Distribution Transformer Health Monitoring** — monitoring load current and
winding temperature to detect anomalies, predict remaining useful life, and
enable remote actuator control (circuit breaker trip/reset).

## 🏗️ System Architecture

```
Layer 1: Perception (Simulated Edge – ESP32-S3 equivalent)
    Python simulator → Current, Temperature, Anomaly Score (K-Means + Threshold)
                    → Modbus TCP registers
                    ▼
Layer 2: Transport
    MQTT (Mosquitto) + Sparkplug B topics (DBIRTH, DDATA, DDEATH, DCMD)
    Unified Namespace: spBv1.0/group24/DDATA/plant01/transformer01
                    ▼
Layer 3: Edge Logic
    Node-RED: data parsing, RUL estimation (linear regression),
              rule-based logic, state consistency monitoring
                    ▼
Layer 4: Application
    InfluxDB (historian) + Grafana (SCADA dashboards) + Node-RED Dashboard (Digital Twin UI)
    ↑ Bidirectional control via DCMD topics (Trip, Reset, What-If)
```

## 🚀 How to Run

### Prerequisites

- Docker Desktop installed and running
- Python 3.9+ with pip
- Git

### Step 1: Clone and Setup

```bash
git clone <repo-url>
cd edge-ai-group24
```

### Step 2: Create MQTT Password File

```bash
# Run the Mosquitto container temporarily to create the password file
docker run -it --rm -v ${PWD}/mosquitto/config:/mqtt/config eclipse-mosquitto sh

# Inside the container, create passwords for both users:
mosquitto_passwd -c /mqtt/config/passwd group24
# Enter password: group24pass

mosquitto_passwd /mqtt/config/passwd nodered
# Enter password: noderedpass

exit
```

### Step 3: Start Docker Services

```bash
docker-compose up -d
```

Verify all containers are running:
```bash
docker ps
# Should show: mosquitto, nodered, influxdb, grafana
```

### Step 4: Install Python Dependencies

```bash
pip install -r requirements.txt
```

### Step 5: Import Node-RED Flows

1. Open Node-RED: http://localhost:1880
2. Menu (☰) → Import → Clipboard
3. Paste the contents of `docs/flows.json`
4. Click "Import" → "Deploy"
5. Install required palettes: `Manage palette` → Install:
   - `node-red-dashboard`
   - `node-red-contrib-influxdb`

### Step 6: Run the Simulator

```bash
python simulator.py
```

You should see sensor data being published every 2 seconds.

## 🌐 Access URLs

| Service    | URL                          | Credentials       |
|-----------|------------------------------|-------------------|
| Node-RED  | http://localhost:1880         | (no auth)          |
| Node-RED Dashboard | http://localhost:1880/ui | (no auth)     |
| Grafana   | http://localhost:3000         | admin / admin      |
| InfluxDB  | http://localhost:8086         | admin / admin123   |

## 🔧 Digital Twin Features

### ✅ Bidirectional Synchronization
- **Physical → Digital:** Sensor data flows from simulator to dashboard in real-time
- **Digital → Physical:** Dashboard buttons send DCMD messages back to simulator

### ✅ Simulation Mode (What-If Scenarios)
- Use the "What-If Load" slider on the Node-RED dashboard to override the
  simulated current and observe how temperature and RUL respond

### ✅ State Consistency Monitoring
- The system monitors whether the actuator state is consistent with the
  anomaly detection results and alerts on inconsistencies

### ✅ Live Synchronization
- 2-second update interval with UTC timestamps
- Sparkplug B birth/death certificates for device lifecycle tracking

## 🤖 Edge AI

- **Primary:** Statistical thresholding (Temperature > 85°C or Current > 15A)
- **Secondary:** K-Means clustering (3 clusters, trained on first 100 normal samples)
- **Combined:** Anomaly if either method flags it
- See `docs/ml_model.md` for full details

## 🔐 Cybersecurity

- MQTT authentication (username/password)
- ACL-based topic access control
- Credentials in `.env` file (gitignored)
- Last Will & Testament (DDEATH on disconnect)
- Local data buffering during outages
- Automatic reconnection with exponential backoff
- See `docs/cybersecurity.md` for full details

## 📁 Repository Structure

```
edge-ai-group24/
├── docker-compose.yml          # Docker orchestration
├── simulator.py                # Edge device simulator (Layer 1)
├── modbus_server.py            # Modbus TCP server simulation
├── requirements.txt            # Python dependencies
├── .env                        # Environment variables (gitignored)
├── .gitignore
├── mosquitto/
│   └── config/
│       ├── mosquitto.conf      # MQTT broker configuration
│       ├── acl.conf            # Topic access control list
│       └── passwd              # Password file (gitignored)
├── grafana/
│   └── provisioning/
│       └── datasources/
│           └── influxdb.yml    # Auto-provision InfluxDB datasource
├── docs/
│   ├── architecture.png        # System architecture diagram
│   ├── wiring.png              # Electrical wiring diagram
│   ├── pid.png                 # Simplified P&ID
│   ├── mqtt_topics.md          # MQTT topic hierarchy
│   ├── flows.json              # Node-RED flow export
│   ├── ml_model.md             # ML model description
│   └── cybersecurity.md        # Cybersecurity design summary
└── README.md
```

## 📊 Demo Walkthrough

1. Start all services: `docker-compose up -d && python simulator.py`
2. Open the Node-RED dashboard: http://localhost:1880/ui
3. Observe live current and temperature readings
4. Move the "What-If Load" slider to 20A → watch temperature rise → anomaly triggers
5. Click "Trip Actuator" → actuator state changes, current drops
6. Click "Reset Actuator" → system returns to normal
7. Open Grafana → view time-series graphs of all metrics + RUL trend
8. Stop the simulator (Ctrl+C) → observe DDEATH message and offline status

## ⚠️ Troubleshooting

| Problem | Solution |
|---------|----------|
| MQTT connection refused | Check username/password. Ensure `mosquitto` container is running (`docker ps`) |
| Python: `ModuleNotFoundError` | Run `pip install -r requirements.txt` |
| Node-RED: no messages | Verify subscription topic: `spBv1.0/group24/DDATA/#` |
| InfluxDB not storing | Check database name (`digitaltwin`) and credentials in influx node config |
| Grafana: no data | Wait a few seconds, then check datasource URL: `http://influxdb:8086` |
| Modbus port conflict | Change `MODBUS_PORT` in `.env` (default 502 may need admin privileges) |
