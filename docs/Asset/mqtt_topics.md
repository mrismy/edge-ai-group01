# MQTT Topic Hierarchy – Group 24
# Unified Namespace (UNS) following Sparkplug B conventions

```
spBv1.0/
└── group24/                          # Group ID (namespace)
    ├── DBIRTH/                        # Device Birth Certificates
    │   └── plant01/                   # Edge Node ID
    │       └── transformer01          # Device ID
    │           → Published on connect: lists all metrics
    │
    ├── DDATA/                         # Device Data (telemetry)
    │   └── plant01/
    │       └── transformer01
    │           → Metrics: Current, Temperature, AnomalyScore,
    │             AnomalyMethod, ActuatorState, UptimeSeconds
    │
    ├── DDEATH/                        # Device Death Certificates
    │   └── plant01/
    │       └── transformer01
    │           → Published on disconnect (LWT)
    │
    └── DCMD/                          # Device Commands (bidirectional)
        └── plant01/
            └── transformer01
                → Commands: ActuatorCommand (trip/reset),
                  WhatIfLoad (simulation override)

status/
└── group24/
    └── transformer01                  # Simple online/offline status
        → Values: "online" | "offline" (retained)

modbus/
└── group24/
    └── transformer01/                 # Modbus TCP register readings
        └── registers                  # (published by Node-RED)
```

## Topic Reference Table

| Topic                                              | Direction    | QoS | Retain | Purpose                    |
|-----------------------------------------------------|-------------|-----|--------|----------------------------|
| `spBv1.0/group24/DBIRTH/plant01/transformer01`      | Edge → Cloud | 1   | Yes    | Birth certificate           |
| `spBv1.0/group24/DDATA/plant01/transformer01`       | Edge → Cloud | 1   | No     | Sensor telemetry            |
| `spBv1.0/group24/DDEATH/plant01/transformer01`      | Edge → Cloud | 1   | Yes    | Death certificate (LWT)     |
| `spBv1.0/group24/DCMD/plant01/transformer01`        | Cloud → Edge | 1   | No     | Control commands            |
| `status/group24/transformer01`                       | Edge → Cloud | 1   | Yes    | Simple online/offline flag  |
