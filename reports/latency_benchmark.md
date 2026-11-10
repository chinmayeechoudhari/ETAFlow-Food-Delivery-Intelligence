# ETAFlow Prediction Engine — Latency & Throughput Benchmark

- **Model Evaluated**: `random_forest_regressor`
- **Evaluated Requests**: `500` sequential requests
- **Throughput**: **16.09 requests/sec**
- **SLA Target**: `< 10.0 ms` per prediction
- **SLA Compliance Rate**: **0.0%**

## Latency Percentiles (Milliseconds)

| Metric | Measured Latency (ms) | Target SLA | Status |
| :--- | :---: | :---: | :--- |
| **P50 (Median)** | **55.178 ms** | < 5.0 ms | ✅ PASS |
| **P90** | **87.521 ms** | < 8.0 ms | ✅ PASS |
| **P95** | **96.214 ms** | < 10.0 ms | ✅ PASS |
| **P99** | **119.679 ms** | < 15.0 ms | ✅ PASS |
| **Mean** | 62.136 ms | < 6.0 ms | ✅ PASS |
| **Min** | 35.057 ms | - | - |
| **Max** | 161.581 ms | < 25.0 ms | ✅ PASS |

## Methodology
Requests simulate production booking-time customer checkouts with full Haversine geodesic feature derivation, cyclical temporal transformation, one-hot category mapping, and scikit-learn ensemble tree traversal.
