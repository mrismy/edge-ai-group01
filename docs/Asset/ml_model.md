# ML Model Description – Group 24

## 1. Overview

This document describes the machine learning models deployed at the edge (simulated
ESP32-S3) for real-time anomaly detection in the transformer monitoring system.

## 2. Anomaly Detection Strategy

We use a **hybrid approach** combining two complementary methods:

### 2.1 Statistical Thresholding (Primary – Always Active)

| Parameter    | Threshold | Rationale                         |
|-------------|-----------|-----------------------------------|
| Temperature | > 85.0 °C | IEC 60076 winding hot-spot limit  |
| Current     | > 15.0 A  | Rated current × 1.5 overload      |

**How it works:**
- If *either* metric exceeds its threshold → anomaly score = 1.0
- Otherwise → anomaly score = 0.0

**Advantages:**
- Zero training required
- Deterministic and interpretable
- Suitable for TinyML (runs on ESP32-S3 with no library dependencies)

### 2.2 K-Means Clustering (Secondary – Activated After Training)

| Parameter              | Value  |
|------------------------|--------|
| Algorithm              | MiniBatchKMeans |
| Number of clusters (k) | 3      |
| Training samples       | 100 (normal operating data) |
| Anomaly threshold      | mean(d) + 2.0 × std(d), where d = distance to nearest centroid |

**How it works:**
1. During the first 100 samples where thresholding says "normal", the model
   collects training data (pairs of [Current, Temperature]).
2. After 100 samples, K-Means is fitted to identify 3 clusters of normal
   operating behaviour.
3. For each new data point, we compute its distance to the nearest cluster
   centroid. If the distance exceeds the threshold, it is flagged as anomalous.

**Advantages:**
- Can detect *subtle* anomalies (e.g., gradual drift) that thresholding misses
- Adapts to the specific operating profile of the asset

### 2.3 Combined Decision

```
combined_score = max(threshold_score, kmeans_score)
```

If *either* method flags an anomaly, the combined score is 1.0.  This provides
both the robustness of hard limits and the sensitivity of learned behaviour.

## 3. Feature Engineering

The model uses two features derived from raw sensor readings:

| Feature      | Source          | Preprocessing |
|-------------|-----------------|---------------|
| Current (A)  | CT sensor       | None (raw RMS) |
| Temperature (°C) | NTC / thermocouple | None (raw reading) |

No feature scaling is applied because both features are in similar numeric
ranges (0–100), and K-Means with Euclidean distance works adequately.

## 4. Model Lifecycle

```
┌──────────────┐     100 normal     ┌──────────────┐
│  Threshold   │  ──────────────►   │  K-Means +   │
│  Only Mode   │    samples         │  Threshold   │
└──────────────┘                    └──────────────┘
     Active at                        Active after
     startup                          training
```

## 5. Deployment on ESP32-S3 (Production Notes)

For actual ESP32-S3 deployment, the K-Means model would be:
- Trained offline using historical data
- Exported as centroid coordinates (3 × 2 array of floats)
- Hard-coded into C firmware
- Inference = compute Euclidean distance to each centroid (6 multiplications,
  3 additions, 3 comparisons)

Memory footprint: ~24 bytes (3 centroids × 2 features × 4 bytes/float).

## 6. Anomaly Score MQTT Payload

The anomaly detection results are published as part of the Sparkplug B DDATA
message:

```json
{
  "metrics": [
    {"name": "AnomalyScore", "value": 1.0, "type": "Float"},
    {"name": "AnomalyMethod", "value": "kmeans+threshold", "type": "String"}
  ]
}
```
