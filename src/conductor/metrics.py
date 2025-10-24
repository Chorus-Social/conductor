"""Prometheus metrics for Conductor."""

import time
from typing import Dict, List
from prometheus_client import Counter, Histogram, Gauge, start_http_server, CollectorRegistry

# Consensus metrics
consensus_rounds = Counter(
    'conductor_consensus_rounds_total',
    'Total consensus rounds',
    ['status']  # success, failure, timeout
)

consensus_duration = Histogram(
    'conductor_consensus_duration_seconds',
    'Consensus round duration in seconds',
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0, 120.0]
)

event_batch_size = Histogram(
    'conductor_event_batch_size_bytes',
    'Event batch size in bytes',
    buckets=[100, 1000, 10000, 100000, 1000000, 10000000]
)

# VDF metrics
vdf_computation_duration = Histogram(
    'conductor_vdf_computation_duration_seconds',
    'VDF computation duration in seconds',
    buckets=[3600, 7200, 14400, 21600, 28800, 36000, 43200, 86400]  # 1h to 24h
)

vdf_difficulty = Gauge(
    'conductor_vdf_difficulty',
    'Current VDF difficulty (iterations)'
)

day_number = Gauge(
    'conductor_day_number_current',
    'Current day number'
)

# Network metrics
rbc_messages = Counter(
    'conductor_rbc_messages_total',
    'RBC messages by type',
    ['message_type']  # propose, echo, ready
)

peer_connections = Gauge(
    'conductor_peer_connections',
    'Active peer connections'
)

network_latency = Histogram(
    'conductor_network_latency_seconds',
    'Network message latency',
    ['peer_id'],
    buckets=[0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0, 5.0]
)

# Storage metrics
storage_operations = Counter(
    'conductor_storage_operations_total',
    'Storage operations',
    ['operation', 'status']  # read, write, delete; success, failure
)

storage_size_bytes = Gauge(
    'conductor_storage_size_bytes',
    'Storage size in bytes'
)

# API metrics
grpc_requests = Counter(
    'conductor_grpc_requests_total',
    'gRPC requests',
    ['method', 'status']  # GetDayProof, SubmitEventBatch; success, failure
)

grpc_latency = Histogram(
    'conductor_grpc_latency_seconds',
    'gRPC request latency',
    ['method'],
    buckets=[0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0, 5.0]
)

rest_requests = Counter(
    'conductor_rest_requests_total',
    'REST API requests',
    ['endpoint', 'method', 'status']
)

rest_latency = Histogram(
    'conductor_rest_latency_seconds',
    'REST API latency',
    ['endpoint', 'method'],
    buckets=[0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0, 5.0]
)

# Blacklist metrics
blacklist_size = Gauge(
    'conductor_blacklist_size',
    'Number of blacklisted validators'
)

blacklist_votes = Counter(
    'conductor_blacklist_votes_total',
    'Blacklist votes',
    ['target_validator', 'action']  # add, remove
)

# System metrics
memory_usage_bytes = Gauge(
    'conductor_memory_usage_bytes',
    'Memory usage in bytes'
)

cpu_usage_percent = Gauge(
    'conductor_cpu_usage_percent',
    'CPU usage percentage'
)

disk_usage_bytes = Gauge(
    'conductor_disk_usage_bytes',
    'Disk usage in bytes'
)


class MetricsCollector:
    """Centralized metrics collection for Conductor."""
    
    def __init__(self, port: int = 9090):
        self.port = port
        self.registry = CollectorRegistry()
        self._start_server()
        
    def _start_server(self):
        """Start Prometheus metrics server."""
        try:
            start_http_server(self.port, registry=self.registry)
            print(f"Metrics server started on port {self.port}")
        except Exception as e:
            print(f"Failed to start metrics server: {e}")
            
    def record_consensus_round(self, status: str, duration: float):
        """Record consensus round metrics."""
        consensus_rounds.labels(status=status).inc()
        consensus_duration.observe(duration)
        
    def record_vdf_computation(self, duration: float, difficulty: int):
        """Record VDF computation metrics."""
        vdf_computation_duration.observe(duration)
        vdf_difficulty.set(difficulty)
        
    def record_event_batch(self, size_bytes: int):
        """Record event batch metrics."""
        event_batch_size.observe(size_bytes)
        
    def record_rbc_message(self, message_type: str):
        """Record RBC message metrics."""
        rbc_messages.labels(message_type=message_type).inc()
        
    def record_network_latency(self, peer_id: str, latency: float):
        """Record network latency metrics."""
        network_latency.labels(peer_id=peer_id).observe(latency)
        
    def record_storage_operation(self, operation: str, status: str):
        """Record storage operation metrics."""
        storage_operations.labels(operation=operation, status=status).inc()
        
    def record_grpc_request(self, method: str, status: str, latency: float):
        """Record gRPC request metrics."""
        grpc_requests.labels(method=method, status=status).inc()
        grpc_latency.labels(method=method).observe(latency)
        
    def record_rest_request(self, endpoint: str, method: str, status: str, latency: float):
        """Record REST request metrics."""
        rest_requests.labels(endpoint=endpoint, method=method, status=status).inc()
        rest_latency.labels(endpoint=endpoint, method=method).observe(latency)
        
    def update_system_metrics(self, memory_bytes: int, cpu_percent: float, disk_bytes: int):
        """Update system resource metrics."""
        memory_usage_bytes.set(memory_bytes)
        cpu_usage_percent.set(cpu_percent)
        disk_usage_bytes.set(disk_bytes)
        
    def update_peer_count(self, count: int):
        """Update peer connection count."""
        peer_connections.set(count)
        
    def update_day_number(self, day: int):
        """Update current day number."""
        day_number.set(day)
        
    def update_blacklist_size(self, size: int):
        """Update blacklist size."""
        blacklist_size.set(size)
        
    def record_blacklist_vote(self, target_validator: str, action: str):
        """Record blacklist vote."""
        blacklist_votes.labels(target_validator=target_validator, action=action).inc()


# Global metrics collector instance
metrics = MetricsCollector()
