# Cybersecurity Design Summary – Group 24

## 1. Overview

This document describes the cybersecurity measures implemented in the
Industrial Digital Twin system for Group 24. All measures align with the
mandatory security and reliability requirements in Sections 10 and 11 of
the project guidelines.

## 2. Security Architecture

```
┌──────────────────────────────────────────────────────────┐
│                    MQTT Broker (Mosquitto)                │
│  ┌──────────────┐  ┌──────────────┐  ┌───────────────┐  │
│  │ Authentication│  │  ACL Engine  │  │  LWT Handler  │  │
│  │ (passwd file) │  │ (acl.conf)   │  │  (DDEATH msg) │  │
│  └──────────────┘  └──────────────┘  └───────────────┘  │
└──────────────────────────────────────────────────────────┘
         ▲                    ▲                  ▲
         │                    │                  │
    ┌────┴────┐         ┌────┴────┐        ┌────┴────┐
    │  Edge   │         │ Node-RED│        │ Grafana │
    │Simulator│         │  Flows  │        │Dashboard│
    └─────────┘         └─────────┘        └─────────┘
```

## 3. Mandatory Security Features

### 3.1 MQTT Authentication

| Aspect         | Implementation                          |
|---------------|----------------------------------------|
| Method         | Username / password                     |
| Password storage | Mosquitto `passwd` file (hashed with PBKDF2-SHA512) |
| Credential management | `.env` file (gitignored), never committed to VCS |
| Broker config  | `allow_anonymous false` in `mosquitto.conf` |

**Users configured:**

| Username  | Role                | Purpose                    |
|-----------|---------------------|----------------------------|
| `group24` | Edge device         | Publish sensor data, subscribe to commands |
| `nodered` | Flow logic engine   | Subscribe to data, publish commands, write to DB |

### 3.2 Encrypted / Protected Credentials

- Passwords in the `passwd` file are hashed (not plaintext)
- Application credentials stored in `.env` file, excluded from Git via `.gitignore`
- Docker Compose references `${VARIABLE}` syntax to inject credentials at runtime
- No credentials are hard-coded in source code

### 3.3 Controlled Topic Access (ACLs)

The `acl.conf` file enforces topic-level authorization:

```
# Edge device: can publish data, subscribe to commands
user group24
topic readwrite spBv1.0/group24/#
topic readwrite status/group24/#
topic read cmd/group24/#

# Node-RED: full access to all group topics
user nodered
topic readwrite spBv1.0/group24/#
topic readwrite status/group24/#
topic readwrite cmd/group24/#
topic readwrite modbus/group24/#
```

**Principle of Least Privilege:**
- The edge device cannot subscribe to other groups' topics
- The edge device has read-only access to command topics
- No user has access to `$SYS/#` broker internals

## 4. Mandatory Reliability Features

### 4.1 Last Will & Testament (LWT)

| LWT Aspect    | Configuration                          |
|--------------|---------------------------------------|
| Topic         | `spBv1.0/group24/DDEATH/plant01/transformer01` |
| Payload       | Sparkplug B DDEATH message with timestamp |
| QoS           | 1 (at least once)                      |
| Retain        | true                                   |

When the edge device disconnects unexpectedly, the broker automatically
publishes the DDEATH message, notifying all subscribers that the device
is offline.

### 4.2 Local Data Buffering

When the MQTT broker is unreachable:
1. Messages are serialised to `buffer_offline.json` on the local filesystem
2. A thread-safe lock prevents concurrent writes
3. Upon reconnection, all buffered messages are replayed in order
4. The buffer file is cleared after successful replay

### 4.3 Automatic Reconnection

The simulator implements exponential backoff reconnection:

```
Initial delay:  1 second
Backoff factor: ×2 per attempt
Maximum delay:  60 seconds
```

Combined with `paho-mqtt`'s built-in reconnection and the `on_disconnect`
callback, the system recovers automatically from network outages.

### 4.4 Timestamped Data

Every MQTT message includes a UTC ISO-8601 timestamp:

```json
{
  "timestamp": "2026-04-29T10:15:30.123456+00:00",
  "seq": 42,
  "metrics": [...]
}
```

This ensures data integrity and enables accurate time-series analysis in
InfluxDB.

## 5. Threat Model (Summary)

| Threat                     | Mitigation                          |
|---------------------------|-------------------------------------|
| Unauthorised MQTT access   | Username/password authentication    |
| Topic hijacking            | ACL-based topic access control      |
| Credential leakage         | `.env` file + `.gitignore`          |
| Device failure detection   | LWT + DDEATH messages               |
| Network outage data loss   | Local file buffering + replay       |
| Stale/duplicate data       | Sequence numbers + timestamps       |
| State inconsistency        | State consistency monitoring logic  |

## 6. Recommendations for Production

In a production deployment, the following additional measures would be
implemented (not required for this project):

- **TLS encryption** on MQTT (port 8883) with X.509 certificates
- **Role-Based Access Control (RBAC)** with a central identity provider
- **Audit logging** of all MQTT connections and command executions
- **Network segmentation** between OT and IT zones (Purdue Model)
- **Certificate-based mutual authentication (mTLS)** for edge devices
