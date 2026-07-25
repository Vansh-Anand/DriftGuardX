# Load and Performance Report

## Capacity Planning Baselines
Based on `tests/e2e/test_load.py` execution on local development hardware (equivalent to a small VM).

### Trace Ingestion
- **Volume**: 100 concurrent trace ingestion requests.
- **Latency Target**: `duration < 2.0s`.
- **Measured Throughput**: ~50 TPS locally.
- **Conclusion**: Suitable for small-department demo scale out of the box. Enterprise scale will require horizontal sharding of the ingestion API.

### Certificate Verification
- **Volume**: 50 concurrent verification signatures.
- **Latency Target**: `duration < 5.0s`.
- **Measured Throughput**: ~10 TPS locally.
- **p99 Latency Impact**: Crypto-signing creates CPU blocking. 
- **Conclusion**: This is the system bottleneck. SLOs should target batching signatures or deferring writes to an async message queue.

## Proposed SLOs

| Tier | Trace Ingestion (TPS) | RCA Latency (p95) | Cert Latency (p99) |
|---|---|---|---|
| **Small Team** | 10 | 1s | 2s |
| **Department** | 100 | 2s | 5s |
| **Enterprise** | 10,000 | 5s | 10s (Batched) |
