# Industrial Digital Twin – Transformer Health Monitoring System
### CO326 Course Project | Group 24 | University of Peradeniya

---

## Group Members

| Student ID | Name | Role |
|-----------|------|------|
| E/20/009 | Member 1 | Edge AI & Simulation |
| E/20/199 | Member 2 | Node-RED & RUL Estimation |
| E/20/339 | Member 3 | Infrastructure & Security |
| E/20/371 | Member 4 | Documentation & Dashboards |

---

## Project Description

This project implements a fully functional **Industrial Digital Twin** for a distribution transformer health monitoring system. A Digital Twin is a real-time virtual replica of a physical asset — in this case, a 3-phase distribution transformer — that mirrors its state, enables bidirectional control, and supports predictive maintenance.

**Industrial Problem:** Distribution transformers are critical grid infrastructure. Overheating or overcurrent events cause insulation degradation, accelerate aging, and can lead to catastrophic failure. Early detection through continuous monitoring and predictive analytics can prevent unplanned outages and extend asset life.

**Our Solution:**
- A Python-based edge simulator (equivalent to an ESP32-S3 device) reads load current and winding temperature, runs on-device Edge AI anomaly detection, and publishes data via MQTT Sparkplug B.
- Node-RED processes the data stream, computes Remaining Useful Life (RUL) via linear regression, and drives a real-time dashboard.
- InfluxDB stores all time-series data; Grafana provides SCADA-style visualisation.
- Operators can send bidirectional commands (trip/reset actuator, simulate load scenarios) from the dashboard back to the edge device.

**Key Features:**
- ✅ 4-Layer IoT Reference Architecture (Perception → Transport → Edge Logic → Application)
- ✅ Edge AI: Hybrid K-Means clustering + statistical thresholding
- ✅ Sparkplug B Unified Namespace (DBIRTH / DDATA / DDEATH / DCMD)
- ✅ RUL Estimation via linear regression on temperature trend
- ✅ Bidirectional Digital Twin control (What-If scenarios)
- ✅ MQTT authentication + ACL-based topic access control
- ✅ Last Will & Testament (LWT) for device failure detection
- ✅ Local data buffering + automatic reconnection with exponential backoff
- ✅ Modbus TCP register exposure for SCADA/legacy system integration

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│              Layer 1: Perception (Edge Node)                        │
│  Python Simulator  ≡  ESP32-S3                                      │
│  • CT Sensor   → Load Current (A)        • Edge AI Anomaly Score    │
│  • Thermocouple→ Winding Temp (°C)       • Modbus TCP Registers     │
└────────────────────────────┬────────────────────────────────────────┘
                             │  MQTT Sparkplug B (spBv1.0/group24/…)
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│              Layer 2: Transport                                      │
│  Eclipse Mosquitto MQTT Broker v2.0                                 │
│  • Authentication (passwd/PBKDF2)  • ACL topic access control       │
│  • QoS 1                           • LWT / DDEATH on disconnect     │
└────────────────────────────┬────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│              Layer 3: Edge Logic                                     │
│  Node-RED Flow Engine                                               │
│  • Parse Sparkplug B metrics       • RUL Estimation (lin. regress.) │
│  • State consistency monitoring    • Device offline alerting        │
└──────────────┬──────────────────────────────────────┬──────────────┘
               │ Store                                │ Visualise
               ▼                                      ▼
┌──────────────────────────┐          ┌───────────────────────────────┐
│  Layer 4: Application    │          │  Grafana SCADA Dashboard      │
│  InfluxDB 1.8            │          │  Node-RED Dashboard (Digital  │
│  • transformer_data      │          │  Twin UI with Trip/Reset/      │
│  • rul_estimation        │          │  What-If controls)            │
└──────────────────────────┘          └───────────────────────────────┘
                             ▲
                             │ Bidirectional DCMD commands
                             └── Cloud → Edge (ActuatorCommand, WhatIfLoad)
```

### Technology Stack

| Component | Technology | Version |
|-----------|-----------|---------|
| Edge Simulator | Python 3.9+ (NumPy, scikit-learn, paho-mqtt) | – |
| MQTT Broker | Eclipse Mosquitto | 2.0 |
| Flow Engine | Node-RED | Latest |
| Time-Series DB | InfluxDB | 1.8 |
| Visualisation | Grafana | Latest |
| Containerisation | Docker / Docker Compose | v3.8 |
| Modbus Server | pymodbus | TCP, port 502 |

---

## How to Run

### Prerequisites
- Docker Desktop installed and running
- Python 3.9+ with pip
- Git

### Step 1 – Clone the Repository

```bash
git clone <repo-url>
cd edge-ai-group24
```

### Step 2 – Create the MQTT Password File

```bash
# Start a temporary Mosquitto container to generate the password file
docker run -it --rm -v ${PWD}/mosquitto/config:/mqtt/config eclipse-mosquitto sh

# Inside the container:
mosquitto_passwd -c /mqtt/config/passwd group24
# Enter: group24pass

mosquitto_passwd /mqtt/config/passwd nodered
# Enter: noderedpass

exit
```

### Step 3 – Start All Docker Services

```bash
docker-compose up -d
```

Verify all containers are running:
```bash
docker ps
# Expected: mosquitto, nodered, influxdb, grafana, simulator
```

### Step 4 – Install Python Dependencies

```bash
pip install -r requirements.txt
```

### Step 5 – Import Node-RED Flows

1. Open Node-RED: [http://localhost:1880](http://localhost:1880)
2. Click **☰ Menu → Import → Clipboard**
3. Paste the contents of `docs/flows.json`
4. Click **Import** → **Deploy**
5. Install required palettes via **Manage Palette → Install**:
   - `node-red-dashboard`
   - `node-red-contrib-influxdb`

### Step 6 – Run the Edge Simulator

```bash
python simulator.py
```

You should see sensor data published every 2 seconds:
```
[10:15:30] I= 10.42A  T= 33.1°C  🟢 Normal (threshold)  Actuator=✅ Normal  seq=1
[10:15:32] I= 10.56A  T= 33.2°C  🟢 Normal (threshold)  Actuator=✅ Normal  seq=2
```

### Access URLs

| Service | URL | Default Credentials |
|---------|-----|-------------------|
| Node-RED | http://localhost:1880 | (no auth) |
| Node-RED Dashboard | http://localhost:1880/ui | (no auth) |
| Grafana | http://localhost:3000 | admin / admin |
| InfluxDB | http://localhost:8086 | admin / admin123 |

### Digital Twin Demo Walkthrough

1. Start services: `docker-compose up -d && python simulator.py`
2. Open the Node-RED dashboard: http://localhost:1880/ui
3. Observe live Current and Temperature gauges updating every 2 s
4. Move the **What-If Load** slider to **20 A** → temperature rises → anomaly triggers (🔴)
5. Click **⚡ TRIP ACTUATOR** → current drops to 10 %; temperature recovers
6. Click **✅ RESET ACTUATOR** → system returns to normal load
7. Open Grafana → view time-series graphs of all metrics + RUL trend line
8. Stop the simulator (Ctrl+C) → observe DDEATH message + offline status in dashboard

---

## MQTT Topics Used

The system uses the **Sparkplug B (spBv1.0) Unified Namespace** convention.

### Topic Tree

```
spBv1.0/
└── group24/                              ← Group ID
    ├── DBIRTH/plant01/transformer01      ← Birth certificate (on connect)
    ├── DDATA/ plant01/transformer01      ← Telemetry (every 2 s)
    ├── DDEATH/plant01/transformer01      ← Death cert / LWT (on disconnect)
    └── DCMD/  plant01/transformer01      ← Commands (cloud → edge)

status/group24/transformer01              ← "online" | "offline" (retained)
modbus/group24/transformer01/registers    ← Modbus register mirror (Node-RED)
```

### Topic Reference Table

| Topic | Direction | QoS | Retain | Purpose |
|-------|-----------|-----|--------|---------|
| `spBv1.0/group24/DBIRTH/plant01/transformer01` | Edge → Cloud | 1 | Yes | Birth certificate – lists all metrics on connect |
| `spBv1.0/group24/DDATA/plant01/transformer01`  | Edge → Cloud | 1 | No  | Sensor telemetry (2-second interval) |
| `spBv1.0/group24/DDEATH/plant01/transformer01` | Edge → Cloud | 1 | Yes | Death certificate / Last Will & Testament |
| `spBv1.0/group24/DCMD/plant01/transformer01`   | Cloud → Edge | 1 | No  | Actuator trip/reset & What-If load commands |
| `status/group24/transformer01`                  | Edge → Cloud | 1 | Yes | Simple online / offline flag |

### DDATA Payload Example (Sparkplug B JSON)

```json
{
  "timestamp": "2026-04-30T10:15:30.123456+00:00",
  "seq": 42,
  "metrics": [
    { "name": "Current",       "value": 10.42, "type": "Float",  "unit": "A" },
    { "name": "Temperature",   "value": 33.1,  "type": "Float",  "unit": "degC" },
    { "name": "AnomalyScore",  "value": 0.0,   "type": "Float" },
    { "name": "AnomalyMethod", "value": "kmeans+threshold", "type": "String" },
    { "name": "ActuatorState", "value": 0,     "type": "Int32" },
    { "name": "UptimeSeconds", "value": 120,   "type": "Int64" }
  ]
}
```

### DCMD Command Example (Cloud → Edge)

```json
{
  "timestamp": "2026-04-30T10:20:00.000Z",
  "metrics": [
    { "name": "ActuatorCommand", "value": 1 }
  ]
}
```

---

## Results (Screenshots)

> **Note:** The following screenshots demonstrate the live system in operation.

### Architecture Diagram
![System Architecture](docs/architecture.png)

### Electrical Wiring Diagram
![Electrical Wiring](docs/wiring.png)

### Simplified P&ID
![P&ID Diagram](docs/pid.png)

### Key Observations from Testing

| Test Scenario | Result |
|---------------|--------|
| Normal operation (I ≈ 10 A, T ≈ 33 °C) | 🟢 No anomaly; RUL = Stable |
| What-If load set to 20 A | 🔴 Anomaly detected (current threshold exceeded); RUL drops |
| What-If load set to 30 A | 🔴 Anomaly detected; temperature > 85 °C; RUL = CRITICAL |
| Trip Actuator command sent | Current drops to ≈1 A; temperature recovers within 10 samples |
| Simulator stopped (Ctrl+C) | DDEATH published; dashboard shows device OFFLINE |
| Broker restarted during run | Buffered messages replayed; reconnection in < 5 s |

---

## Challenges

1. **Sparkplug B payload parsing in Node-RED** – The metrics array structure required a custom parse function node to flatten into key-value pairs before routing to gauges and InfluxDB writers.

2. **K-Means training window selection** – Balancing training speed (faster = less data) against model quality (more data = better centroids). Settled on 100 normal samples (~3 minutes at 2 s interval) as a practical tradeoff.

3. **Modbus port 502 requires elevated privileges** – On Linux/macOS, ports below 1024 require root. Documented workaround: change `MODBUS_PORT` in `.env` to a value ≥ 1024 (e.g., 5020).

4. **InfluxDB measurement schema design** – Choosing between single vs. multiple measurements for sensor data and RUL. Separated into `transformer_data` and `rul_estimation` to allow independent retention policies in production.

5. **State consistency detection logic** – Defining meaningful consistency rules without generating excessive false-positive alerts during the K-Means training phase required careful threshold tuning.

6. **Docker networking for Node-RED ↔ Mosquitto** – Ensuring Node-RED connects to `mosquitto` (container hostname) rather than `localhost` required explicit Docker Compose service name configuration in the flow broker settings.

---

## Future Improvements

1. **TLS/mTLS Encryption** – Enable MQTT over port 8883 with X.509 certificates for end-to-end encryption and mutual device authentication.

2. **ONNX / TFLite Model Export** – Train a more sophisticated anomaly detection model (e.g., Autoencoder or Isolation Forest) offline and deploy as a TFLite model on actual ESP32-S3 hardware using TensorFlow Lite Micro.

3. **Sparkplug B Binary Protobuf Encoding** – Replace the JSON-based Sparkplug B implementation with proper Protocol Buffer binary encoding for reduced bandwidth and strict spec compliance.

4. **Grafana Alerting & PagerDuty Integration** – Configure automated alert rules in Grafana to notify on-call engineers via SMS/email when anomaly score = 1 or RUL < 24 hours.

5. **Multi-Asset Scaling** – Extend the namespace to monitor multiple transformers (`plant01/transformer02`, `plant02/transformer01`) and add a fleet-level overview dashboard.

6. **Actual ESP32-S3 Hardware Deployment** – Port the Python simulator logic to ESP-IDF / MicroPython firmware and deploy on real ESP32-S3 hardware with actual CT sensors and thermocouples.

7. **Federated Learning for K-Means Updates** – Periodically upload cluster centroids from multiple edge nodes to a central server for model aggregation, improving anomaly detection across the fleet without sharing raw data.

8. **Digital Twin Asset Administration Shell (AAS)** – Implement an IEC 63278 / IDTA Asset Administration Shell for full standards-compliant Digital Twin interoperability.

---

## Repository Structure

```
edge-ai-group24/
├── docker-compose.yml          # Docker orchestration (5 services)
├── Dockerfile                  # Simulator container image
├── simulator.py                # Edge device simulator – Layer 1
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
└── docs/
    ├── architecture.png        # System architecture diagram
    ├── wiring.png              # Electrical wiring diagram
    ├── pid.png                 # Simplified P&ID
    ├── mqtt_topics.md          # MQTT topic hierarchy (detailed)
    ├── flows.json              # Node-RED flow export
    ├── ml_model.md             # ML model description
    ├── cybersecurity.md        # Cybersecurity design summary
    └── Group24_Documentation.docx  # Full project documentation
```

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| MQTT connection refused | Check username/password in `.env`; verify `mosquitto` container is running (`docker ps`) |
| `ModuleNotFoundError` | Run `pip install -r requirements.txt` |
| Node-RED: no messages arriving | Verify subscription topic: `spBv1.0/group24/DDATA/#` |
| InfluxDB not storing data | Check database name (`digitaltwin`) and credentials in influx node config |
| Grafana: no data showing | Wait a few seconds; verify datasource URL is `http://influxdb:8086` |
| Modbus port conflict | Change `MODBUS_PORT` in `.env` (default 502 may need admin privileges; use 5020) |
| K-Means not training | Ensure at least 100 normal (non-anomalous) samples are collected first |

---

> **Documentation:** Full mandatory documentation (architecture diagram, wiring diagram, P&ID, MQTT hierarchy, Node-RED flows, ML model description, cybersecurity design) is available in [`docs/Group24_Documentation.docx`](docs/Group24_Documentation.docx).
