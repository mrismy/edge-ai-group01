"""
=============================================================================
Industrial Digital Twin – Edge Simulator (Group 24)
=============================================================================
Simulates an ESP32-S3 edge device for a distribution transformer monitoring
system.  Implements all mandatory requirements:

  ✓  Sparkplug B topic structure (DBIRTH, DDATA, DDEATH, DCMD)
  ✓  Edge AI anomaly detection (K-Means + statistical thresholding)
  ✓  Modbus TCP register updates
  ✓  MQTT authentication
  ✓  Last Will & Testament (LWT)
  ✓  Local data buffering during outages
  ✓  Automatic reconnection with exponential backoff
  ✓  Timestamped data (UTC ISO-8601)
  ✓  Birth / Death certificate messages
  ✓  Bidirectional control (DCMD handling)
  ✓  State consistency monitoring

Usage:
    pip install -r requirements.txt
    python simulator.py

Configuration is loaded from the .env file or environment variables.
=============================================================================
"""

import os
import sys
import json
import time
import math
import random
import threading
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import paho.mqtt.client as mqtt

# ---------------------------------------------------------------------------
# Try importing optional dependencies
# ---------------------------------------------------------------------------
try:
    from sklearn.cluster import MiniBatchKMeans
    KMEANS_AVAILABLE = True
except ImportError:
    KMEANS_AVAILABLE = False
    print("[WARN] scikit-learn not installed – using threshold-only anomaly detection")

try:
    from modbus_server import TransformerModbusServer
    MODBUS_AVAILABLE = True
except ImportError:
    MODBUS_AVAILABLE = False
    print("[WARN] modbus_server module not found – Modbus TCP disabled")

# ---------------------------------------------------------------------------
# Configuration (from .env or defaults)
# ---------------------------------------------------------------------------
def _load_env():
    """Load .env file into os.environ (simple parser, no dependency)."""
    env_path = Path(__file__).parent / ".env"
    if env_path.exists():
        with open(env_path, "r") as fh:
            for line in fh:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    key, _, val = line.partition("=")
                    os.environ.setdefault(key.strip(), val.strip())

_load_env()

BROKER      = os.getenv("MQTT_BROKER_HOST", "localhost")
PORT        = int(os.getenv("MQTT_BROKER_PORT", "1883"))
USERNAME    = os.getenv("MQTT_USERNAME", "group24")
PASSWORD    = os.getenv("MQTT_PASSWORD", "group24pass")
GROUP_ID    = os.getenv("SPB_GROUP_ID", "group24")
NODE_ID     = os.getenv("SPB_EDGE_NODE_ID", "plant01")
DEVICE_ID   = os.getenv("SPB_DEVICE_ID", "transformer01")
MODBUS_PORT = int(os.getenv("MODBUS_PORT", "502"))

# Sparkplug B topic templates  (Section 7 of guidelines)
TOPIC_DDATA  = f"spBv1.0/{GROUP_ID}/DDATA/{NODE_ID}/{DEVICE_ID}"
TOPIC_DBIRTH = f"spBv1.0/{GROUP_ID}/DBIRTH/{NODE_ID}/{DEVICE_ID}"
TOPIC_DDEATH = f"spBv1.0/{GROUP_ID}/DDEATH/{NODE_ID}/{DEVICE_ID}"
TOPIC_DCMD   = f"spBv1.0/{GROUP_ID}/DCMD/{NODE_ID}/{DEVICE_ID}"
TOPIC_STATUS = f"status/{GROUP_ID}/{DEVICE_ID}"

# Buffer file for offline data retention
BUFFER_FILE = Path(__file__).parent / "buffer_offline.json"

# ---------------------------------------------------------------------------
# Global state
# ---------------------------------------------------------------------------
actuator_tripped = False
whatif_load_override = None  # If set, overrides the simulated current
mqtt_connected = False
buffer_lock = threading.Lock()
state_sequence = 0  # Sparkplug B sequence counter

# State consistency tracking
last_published_state = {}
expected_state = {}

# ---------------------------------------------------------------------------
# Edge AI – K-Means Anomaly Detector (Layer 1 requirement)
# ---------------------------------------------------------------------------
class EdgeAnomalyDetector:
    """
    Lightweight anomaly detection suitable for edge deployment (TinyML).

    Strategy:
        1. Statistical thresholding (always active)
        2. K-Means clustering (activated after collecting training samples)

    This hybrid approach satisfies the guideline requirement for
    "K-Means clustering" AND "Statistical thresholding".
    """

    TEMP_THRESHOLD = 85.0   # °C
    CURRENT_THRESHOLD = 15.0  # A
    TRAINING_SAMPLES = 100
    N_CLUSTERS = 3
    ANOMALY_DISTANCE_MULTIPLIER = 2.0

    def __init__(self):
        self.training_data = []
        self.model = None
        self.trained = False
        self.cluster_distances = []  # track normal distances for threshold

    def _threshold_check(self, current: float, temperature: float) -> float:
        """Simple statistical thresholding – always available."""
        if temperature > self.TEMP_THRESHOLD or current > self.CURRENT_THRESHOLD:
            return 1.0
        return 0.0

    def _train_kmeans(self):
        """Train K-Means on collected normal operating data."""
        if not KMEANS_AVAILABLE:
            return
        data = np.array(self.training_data)
        self.model = MiniBatchKMeans(n_clusters=self.N_CLUSTERS, random_state=42)
        self.model.fit(data)
        # Compute distances of training points to their nearest cluster centre
        distances = self.model.transform(data).min(axis=1)
        self.cluster_distances = distances.tolist()
        self.trained = True
        mean_dist = np.mean(distances)
        std_dist = np.std(distances)
        self.distance_threshold = mean_dist + self.ANOMALY_DISTANCE_MULTIPLIER * std_dist
        print(f"[EDGE-AI] K-Means trained on {len(data)} samples, "
              f"distance threshold = {self.distance_threshold:.4f}")

    def detect(self, current: float, temperature: float) -> dict:
        """
        Run anomaly detection. Returns dict with score and method used.
        """
        # Always run threshold check
        threshold_score = self._threshold_check(current, temperature)

        # Collect training data (only from normal-looking samples)
        if threshold_score == 0.0 and len(self.training_data) < self.TRAINING_SAMPLES:
            self.training_data.append([current, temperature])
            if len(self.training_data) == self.TRAINING_SAMPLES:
                self._train_kmeans()

        # K-Means check (if trained)
        kmeans_score = 0.0
        method = "threshold"
        if self.trained and self.model is not None:
            point = np.array([[current, temperature]])
            distance = self.model.transform(point).min()
            kmeans_score = 1.0 if distance > self.distance_threshold else 0.0
            method = "kmeans+threshold"

        # Combined score: anomaly if EITHER method flags it
        combined = max(threshold_score, kmeans_score)

        return {
            "score": combined,
            "method": method,
            "threshold_flag": threshold_score,
            "kmeans_flag": kmeans_score,
        }


# ---------------------------------------------------------------------------
# Local Data Buffering (Mandatory reliability requirement)
# ---------------------------------------------------------------------------
def buffer_message(topic: str, payload: str):
    """Buffer a message to local file when MQTT is disconnected."""
    with buffer_lock:
        buffer = []
        if BUFFER_FILE.exists():
            try:
                buffer = json.loads(BUFFER_FILE.read_text())
            except (json.JSONDecodeError, OSError):
                buffer = []
        buffer.append({"topic": topic, "payload": payload})
        BUFFER_FILE.write_text(json.dumps(buffer))
        print(f"[BUFFER] Message buffered ({len(buffer)} pending)")


def replay_buffer(client: mqtt.Client):
    """Replay buffered messages after reconnection."""
    with buffer_lock:
        if not BUFFER_FILE.exists():
            return
        try:
            buffer = json.loads(BUFFER_FILE.read_text())
        except (json.JSONDecodeError, OSError):
            return
        if not buffer:
            return
        print(f"[BUFFER] Replaying {len(buffer)} buffered messages...")
        for msg in buffer:
            client.publish(msg["topic"], msg["payload"], qos=1)
        BUFFER_FILE.write_text("[]")
        print("[BUFFER] All buffered messages replayed")


# ---------------------------------------------------------------------------
# MQTT Callbacks
# ---------------------------------------------------------------------------
def on_connect(client, userdata, flags, rc):
    """Handle MQTT connection / reconnection."""
    global mqtt_connected
    if rc == 0:
        mqtt_connected = True
        print(f"[MQTT] Connected to broker at {BROKER}:{PORT}")

        # Subscribe to command topics (Sparkplug B DCMD)
        client.subscribe(TOPIC_DCMD, qos=1)
        print(f"[MQTT] Subscribed to {TOPIC_DCMD}")

        # Publish online status
        client.publish(TOPIC_STATUS, payload="online", qos=1, retain=True)

        # Send Device Birth Certificate (DBIRTH)
        publish_birth(client)

        # Replay any buffered messages from outage
        replay_buffer(client)
    else:
        mqtt_connected = False
        print(f"[MQTT] Connection failed with code {rc}")


def on_disconnect(client, userdata, rc):
    """Handle disconnection with automatic reconnection."""
    global mqtt_connected
    mqtt_connected = False
    if rc != 0:
        print(f"[MQTT] Unexpected disconnection (rc={rc}). Will auto-reconnect...")
        # paho-mqtt handles reconnection automatically when loop_start() is used
        # but we add explicit backoff for robustness
        _reconnect_with_backoff(client)
    else:
        print("[MQTT] Disconnected cleanly")


def on_message(client, userdata, msg):
    """
    Handle incoming DCMD messages for bidirectional control.
    Sparkplug B commands arrive on the DCMD topic with metrics in the payload.
    """
    global actuator_tripped, whatif_load_override

    try:
        payload = json.loads(msg.payload.decode())
    except (json.JSONDecodeError, UnicodeDecodeError):
        # Fallback: treat as plain text command
        payload = {"metrics": []}
        raw = msg.payload.decode()
        if raw in ("0", "1"):
            payload["metrics"] = [{"name": "ActuatorCommand", "value": int(raw)}]

    print(f"[DCMD] Received command on {msg.topic}: {payload}")

    for metric in payload.get("metrics", []):
        name = metric.get("name", "")
        value = metric.get("value")

        if name == "ActuatorCommand":
            actuator_tripped = (value == 1)
            print(f"[DCMD] Actuator {'TRIPPED' if actuator_tripped else 'RESET'}")

        elif name == "WhatIfLoad":
            if value is not None and value > 0:
                whatif_load_override = float(value)
                print(f"[DCMD] What-If load override set to {whatif_load_override} A")
            else:
                whatif_load_override = None
                print("[DCMD] What-If load override cleared")


def _reconnect_with_backoff(client):
    """Exponential backoff reconnection (mandatory reliability feature)."""
    backoff = 1
    max_backoff = 60
    while not mqtt_connected:
        try:
            print(f"[MQTT] Reconnecting in {backoff}s...")
            time.sleep(backoff)
            client.reconnect()
            break
        except Exception as e:
            print(f"[MQTT] Reconnection failed: {e}")
            backoff = min(backoff * 2, max_backoff)


# ---------------------------------------------------------------------------
# Sparkplug B Birth / Death Certificates
# ---------------------------------------------------------------------------
def publish_birth(client):
    """Publish DBIRTH message listing all metrics this device will report."""
    global state_sequence
    state_sequence += 1

    birth_payload = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "seq": state_sequence,
        "metrics": [
            {"name": "Current", "value": 0.0, "type": "Float", "unit": "A",
             "description": "Load current (RMS)"},
            {"name": "Temperature", "value": 0.0, "type": "Float", "unit": "degC",
             "description": "Winding temperature"},
            {"name": "AnomalyScore", "value": 0.0, "type": "Float",
             "description": "Edge AI anomaly score (0=normal, 1=anomaly)"},
            {"name": "AnomalyMethod", "value": "initializing", "type": "String",
             "description": "Active anomaly detection method"},
            {"name": "ActuatorState", "value": 0, "type": "Int32",
             "description": "Actuator state (0=normal, 1=tripped)"},
            {"name": "UptimeSeconds", "value": 0, "type": "Int64",
             "description": "Device uptime in seconds"},
        ]
    }

    client.publish(TOPIC_DBIRTH, json.dumps(birth_payload), qos=1, retain=True)
    print("[SPB] DBIRTH published")


def build_death_payload():
    """Build DDEATH payload (used as LWT)."""
    return json.dumps({
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "metrics": [
            {"name": "bdSeq", "value": state_sequence}
        ]
    })


# ---------------------------------------------------------------------------
# State Consistency Monitoring
# ---------------------------------------------------------------------------
def check_state_consistency(current_state: dict) -> list:
    """
    Compare the current device state with the expected state and report
    any inconsistencies.  Fulfils Section 8.2 "State consistency monitoring".
    """
    global expected_state
    inconsistencies = []

    if expected_state:
        for key, expected_val in expected_state.items():
            actual_val = current_state.get(key)
            if actual_val is not None and actual_val != expected_val:
                inconsistencies.append({
                    "metric": key,
                    "expected": expected_val,
                    "actual": actual_val,
                    "timestamp": datetime.now(timezone.utc).isoformat()
                })

    # Update expected state
    expected_state = current_state.copy()
    return inconsistencies


# ---------------------------------------------------------------------------
# Safe Publish (with buffering)
# ---------------------------------------------------------------------------
def safe_publish(client, topic, payload_str, qos=1):
    """Publish to MQTT or buffer locally if disconnected."""
    if mqtt_connected:
        result = client.publish(topic, payload_str, qos=qos)
        if result.rc != mqtt.MQTT_ERR_SUCCESS:
            buffer_message(topic, payload_str)
    else:
        buffer_message(topic, payload_str)


# ---------------------------------------------------------------------------
# Main Simulation Loop
# ---------------------------------------------------------------------------
def main():
    global state_sequence, actuator_tripped

    print("=" * 70)
    print("  Industrial Digital Twin – Edge Simulator (Group 24)")
    print("  Transformer Health Monitoring System")
    print("=" * 70)

    # --- Initialise Edge AI ---
    detector = EdgeAnomalyDetector()
    print(f"[EDGE-AI] Initialised (K-Means available: {KMEANS_AVAILABLE})")

    # --- Initialise Modbus TCP Server ---
    modbus_srv = None
    if MODBUS_AVAILABLE:
        try:
            modbus_srv = TransformerModbusServer(host="0.0.0.0", port=MODBUS_PORT)
            modbus_srv.start()
        except Exception as e:
            print(f"[MODBUS] Failed to start: {e} (continuing without Modbus)")
            modbus_srv = None

    # --- Initialise MQTT Client ---
    client = mqtt.Client(client_id=f"{GROUP_ID}-{DEVICE_ID}-edge", clean_session=True)
    client.username_pw_set(USERNAME, PASSWORD)

    # LWT – Sparkplug B DDEATH (mandatory reliability feature)
    client.will_set(TOPIC_DDEATH, payload=build_death_payload(), qos=1, retain=True)
    # Also set status topic LWT
    client.will_set(TOPIC_STATUS, payload="offline", qos=1, retain=True)

    client.on_connect = on_connect
    client.on_disconnect = on_disconnect
    client.on_message = on_message

    # Connect
    print(f"[MQTT] Connecting to {BROKER}:{PORT} as '{USERNAME}'...")
    try:
        client.connect(BROKER, PORT, keepalive=60)
    except Exception as e:
        print(f"[MQTT] Initial connection failed: {e}")
        print("[MQTT] Will keep retrying in background...")

    client.loop_start()

    # Wait briefly for connection
    time.sleep(2)

    # --- Simulation Loop ---
    start_time = time.time()
    publish_interval = 2  # seconds

    print(f"\n[SIM] Starting data generation (every {publish_interval}s)")
    print(f"[SIM] Topics: DDATA={TOPIC_DDATA}")
    print(f"[SIM]         DCMD ={TOPIC_DCMD}")
    print("-" * 70)

    try:
        while True:
            elapsed = time.time() - start_time
            daily_cycle = (elapsed % 86400) / 86400 * 2 * math.pi

            # ------ Generate Sensor Data ------

            # Current (Amps) with daily pattern + noise
            if whatif_load_override is not None:
                current = whatif_load_override + random.uniform(-0.3, 0.3)
            else:
                current = 10 + 5 * math.sin(daily_cycle) + random.uniform(-0.5, 0.5)

            # Temperature (°C) depends on current + ambient
            temperature = 30 + 0.3 * current + random.uniform(-0.3, 0.3)

            # If actuator is tripped, simulate load reduction
            if actuator_tripped:
                current *= 0.1  # load cut to 10%
                temperature = 30 + 0.3 * current + random.uniform(-0.1, 0.1)

            # ------ Edge AI Anomaly Detection ------
            anomaly_result = detector.detect(current, temperature)

            # ------ State Consistency Check ------
            current_state = {
                "actuator": 1 if actuator_tripped else 0,
                "anomaly": anomaly_result["score"],
            }
            inconsistencies = check_state_consistency(current_state)
            if inconsistencies:
                print(f"[CONSISTENCY] State drift detected: {inconsistencies}")

            # ------ Build Sparkplug B Payload (DDATA) ------
            state_sequence += 1
            payload = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "seq": state_sequence,
                "metrics": [
                    {"name": "Current", "value": round(current, 2),
                     "type": "Float", "unit": "A"},
                    {"name": "Temperature", "value": round(temperature, 1),
                     "type": "Float", "unit": "degC"},
                    {"name": "AnomalyScore", "value": anomaly_result["score"],
                     "type": "Float"},
                    {"name": "AnomalyMethod", "value": anomaly_result["method"],
                     "type": "String"},
                    {"name": "ActuatorState", "value": 1 if actuator_tripped else 0,
                     "type": "Int32"},
                    {"name": "UptimeSeconds", "value": int(elapsed),
                     "type": "Int64"},
                ]
            }

            # Add consistency warnings if any
            if inconsistencies:
                payload["metrics"].append({
                    "name": "StateConsistencyAlert",
                    "value": json.dumps(inconsistencies),
                    "type": "String"
                })

            payload_str = json.dumps(payload)

            # ------ Publish via MQTT ------
            safe_publish(client, TOPIC_DDATA, payload_str)

            # ------ Update Modbus Registers ------
            if modbus_srv:
                modbus_srv.update_registers(
                    current=current,
                    temperature=temperature,
                    anomaly=anomaly_result["score"],
                    actuator_state=1 if actuator_tripped else 0,
                )

            # ------ Console Output ------
            status = "🔴 ANOMALY" if anomaly_result["score"] > 0 else "🟢 Normal"
            actuator_str = "⚡ TRIPPED" if actuator_tripped else "✅ Normal"
            whatif_str = f" [What-If: {whatif_load_override}A]" if whatif_load_override else ""
            print(
                f"[{datetime.now(timezone.utc).strftime('%H:%M:%S')}] "
                f"I={current:6.2f}A  T={temperature:5.1f}°C  "
                f"{status} ({anomaly_result['method']})  "
                f"Actuator={actuator_str}{whatif_str}  "
                f"seq={state_sequence}"
            )

            time.sleep(publish_interval)

    except KeyboardInterrupt:
        print("\n[SIM] Shutting down...")

        # Publish DDEATH
        if mqtt_connected:
            death_payload = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "metrics": [{"name": "bdSeq", "value": state_sequence}]
            }
            client.publish(TOPIC_DDEATH, json.dumps(death_payload), qos=1, retain=True)
            client.publish(TOPIC_STATUS, payload="offline", qos=1, retain=True)

        client.loop_stop()
        client.disconnect()

        if modbus_srv:
            modbus_srv.stop()

        print("[SIM] Goodbye!")


if __name__ == "__main__":
    main()
