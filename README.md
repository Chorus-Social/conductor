# Chorus Conductor

Production-ready implementation of the Chorus Conductor consensus engine, featuring asynchronous Byzantine Fault Tolerant (ABFT) consensus with VDF-proven day counters.

## Features

- **Asynchronous BFT Consensus**: Leaderless consensus tolerating up to f < n/3 Byzantine nodes
- **VDF-Proven Day Counter**: Cryptographically verified time progression without real-world timestamps
- **Threshold Cryptography**: Shamir Secret Sharing and Ed25519 signatures
- **Reliable Broadcast**: Erasure-coded message dissemination with Reed-Solomon encoding
- **Network Layer**: libp2p-based peer-to-peer networking with GossipSub
- **API Surface**: gRPC and REST APIs for Bridge integration
- **Observability**: Structured logging, Prometheus metrics, and distributed tracing
- **Production Ready**: Error handling, circuit breakers, retry logic, and comprehensive testing

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     Layer 4: Conductor                          │
│   (Leaderless ABFT Consensus, VDF-Proven Day Counter, Warden)  │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            │ Consensus Integration
                            │ (gRPC, Threshold Encryption, BFT)
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                     Layer 3: Chorus Bridge                      │
│       (Replication & Federation Layer, P2P Mesh, Gossipsub)     │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            │ Bridge Integration API
                            │ (REST/gRPC, mTLS, Signed Requests)
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                     Layer 2: Chorus Stage                       │
│            (FastAPI, PostgreSQL, Privacy Enforcement)           │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            │ REST API / WebSocket
                            │ (HTTPS, JWT Authentication)
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Layer 1: Clients                           │
│  (Web, Mobile, Desktop, Third-Party — Official & Community)     │
└─────────────────────────────────────────────────────────────────┘
```

## Quick Start

### Prerequisites

- Python 3.11+
- Poetry (for dependency management)
- Docker (for containerized deployment)

### Installation

1. **Clone the repository**:
   ```bash
   git clone https://github.com/chorus/conductor.git
   cd conductor
   ```

2. **Install dependencies**:
   ```bash
   poetry install
   ```

3. **Generate validator keypair**:
   ```bash
   poetry run python generate_keys.py
   ```

4. **Run tests**:
   ```bash
   poetry run pytest
   ```

### Development

1. **Start a single validator**:
   ```bash
   poetry run python -m conductor.main
   ```

2. **Start with custom config**:
   ```bash
   poetry run python -m conductor.main validator.yaml
   ```

### Docker Deployment

1. **Build the image**:
   ```bash
   docker build -t chorus/conductor:latest .
   ```

2. **Run with Docker Compose**:
   ```bash
   docker-compose up -d
   ```

### Kubernetes Deployment

1. **Create namespace**:
   ```bash
   kubectl apply -f k8s/namespace.yaml
   ```

2. **Deploy Conductor**:
   ```bash
   kubectl apply -f k8s/
   ```

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `VALIDATOR_KEYPAIR_PATH` | Path to validator keypair | `./keys/validator_key.pem` |
| `VALIDATOR_NETWORK_LISTEN_ADDRESS` | Network listen address | `0.0.0.0:4001` |
| `VALIDATOR_STORAGE_PATH` | Storage path | `./validator_data` |
| `VALIDATOR_VDF_ITERATIONS` | VDF difficulty | `86400000` |
| `VALIDATOR_LOG_LEVEL` | Log level | `INFO` |

### Configuration File

```yaml
validator:
  keypair_path: ./keys/validator_key.pem
  network:
    listen_address: 0.0.0.0:4001
    bootstrap_peers: []
  vdf:
    iterations: 86400000
    progress_interval: 1000000
    adjustment_interval_days: 10
  storage:
    backend: lmdb
    path: ./validator_data
  consensus:
    min_validators: 3
    threshold: 0.67
    timeout: 120
  monitoring:
    prometheus_port: 9090
    log_level: INFO
```

## API Reference

### gRPC API

The Conductor exposes a gRPC API on port 50051:

```protobuf
service ConductorService {
  rpc GetDayProof(GetDayProofRequest) returns (GetDayProofResponse);
  rpc SubmitEventBatch(SubmitEventBatchRequest) returns (SubmitEventBatchResponse);
  rpc GetBlock(GetBlockRequest) returns (GetBlockResponse);
  rpc GetConsensusStatus(GetConsensusStatusRequest) returns (GetConsensusStatusResponse);
}
```

### REST API

The Conductor also exposes a REST API on port 8080:

- `GET /health` - Health check
- `GET /health/ready` - Readiness probe
- `GET /day-proof/{day_number}` - Get day proof
- `POST /events/batch` - Submit event batch
- `GET /block/{epoch}` - Get finalized block
- `GET /consensus/status/{batch_id}` - Get consensus status
- `GET /metrics` - Prometheus metrics

## Monitoring

### Metrics

The Conductor exposes Prometheus metrics on port 9090:

- `conductor_consensus_rounds_total` - Total consensus rounds
- `conductor_consensus_duration_seconds` - Consensus round duration
- `conductor_vdf_computation_duration_seconds` - VDF computation time
- `conductor_peer_connections` - Active peer connections
- `conductor_grpc_requests_total` - gRPC request metrics
- `conductor_rest_requests_total` - REST request metrics

### Logging

Structured JSON logging with context:

```json
{
  "timestamp": "2025-01-27T10:00:00Z",
  "level": "info",
  "message": "Consensus round started",
  "validator_id": "abc123",
  "day_number": 42,
  "round": 1
}
```

### Health Checks

- **Liveness**: `GET /health` - Basic health check
- **Readiness**: `GET /health/ready` - Ready to accept traffic

## Testing

### Unit Tests

```bash
poetry run pytest tests/test_crypto.py
poetry run pytest tests/test_consensus.py
poetry run pytest tests/test_network.py
```

### Integration Tests

```bash
poetry run pytest tests/test_integration.py
```

### Load Testing

```bash
poetry run python tests/load_test.py
```

## Security

### Cryptographic Security

- **Ed25519 signatures** for all validator operations
- **Shamir Secret Sharing** for threshold cryptography
- **BLAKE3 hashing** for VDF computation
- **mTLS** for gRPC communication

### Privacy Guarantees

- **No real-world timestamps** stored or transmitted
- **Day numbers only** for temporal ordering
- **RAM-only day counter** (ephemeral, never persisted)
- **Content hashing** for federation (full content stays local)

## Performance

### Targets

| Metric | Target |
|--------|--------|
| Consensus Latency | p50 < 30s, p99 < 120s |
| VDF Computation | ~24 hours (reference hardware) |
| Event Throughput | >10,000 events/day |
| Memory Usage | <1GB per validator |
| Storage Growth | <100MB/day |

### Optimization

- **Parallel VDF computation** across multiple cores
- **Efficient erasure coding** with Reed-Solomon
- **Optimized network protocols** with libp2p
- **LMDB storage** for high-performance persistence

## Troubleshooting

### Common Issues

1. **VDF computation too slow**:
   - Check CPU usage and thermal throttling
   - Adjust `VALIDATOR_VDF_ITERATIONS` if needed
   - Ensure adequate cooling

2. **Network connectivity issues**:
   - Verify bootstrap peers are reachable
   - Check firewall rules for port 4001
   - Ensure NAT traversal is configured

3. **Storage issues**:
   - Check disk space and I/O performance
   - Verify LMDB permissions
   - Monitor storage growth

### Debug Mode

Enable debug logging:

```bash
VALIDATOR_LOG_LEVEL=DEBUG poetry run python -m conductor.main
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests for new functionality
5. Ensure all tests pass
6. Submit a pull request

## License

GPLv3 - See LICENSE file for details.

## Support

- **Documentation**: [docs.chorus.social](https://docs.chorus.social)
- **Issues**: [GitHub Issues](https://github.com/chorus/conductor/issues)
- **Discord**: [Chorus Discord](https://discord.gg/chorus)
- **Email**: conductor-team@chorus.social
