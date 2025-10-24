from pydantic import BaseModel, Field
from typing import List, Optional
import yaml
import os

class NetworkConfig(BaseModel):
    listen_address: str = "0.0.0.0:4001"
    bootstrap_peers: List[str] = Field(default_factory=list)
    # dht: DHTConfig # Placeholder for future DHT config

class VDFConfig(BaseModel):
    iterations: int = 2_000_000_000 # Updated default to match vdf.py
    progress_interval: int = 1000000
    adjustment_interval_days: int = 10

class StorageConfig(BaseModel):
    backend: str = "lmdb" # Changed from rocksdb to lmdb as per current implementation
    path: str = "./validator_data"

class ConsensusConfig(BaseModel):
    min_validators: int = 3
    threshold: float = 0.67
    timeout: int = 120

class MonitoringConfig(BaseModel):
    prometheus_port: int = 9090
    log_level: str = "INFO"

class ValidatorConfig(BaseModel):
    keypair_path: str = "./keys/validator_key.pem"
    network: NetworkConfig = Field(default_factory=NetworkConfig)
    vdf: VDFConfig = Field(default_factory=VDFConfig)
    storage: StorageConfig = Field(default_factory=StorageConfig)
    consensus: ConsensusConfig = Field(default_factory=ConsensusConfig)
    monitoring: MonitoringConfig = Field(default_factory=MonitoringConfig)

class Config(BaseModel):
    validator: ValidatorConfig = Field(default_factory=ValidatorConfig)

def load_config(config_path: Optional[str] = None) -> Config:
    config_data = {}
    if config_path and os.path.exists(config_path):
        with open(config_path, 'r') as f:
            config_data = yaml.safe_load(f)

    # Load from environment variables, overriding YAML values
    # This is a simplified example; a more robust solution would handle nested structures
    # e.g., VALIDATOR_NETWORK_LISTEN_ADDRESS
    env_overrides = {
        "VALIDATOR_KEYPAIR_PATH": "validator.keypair_path",
        "VALIDATOR_NETWORK_LISTEN_ADDRESS": "validator.network.listen_address",
        "VALIDATOR_STORAGE_PATH": "validator.storage.path",
        "VALIDATOR_VDF_ITERATIONS": "validator.vdf.iterations",
        "VALIDATOR_VDF_ADJUSTMENT_INTERVAL_DAYS": "validator.vdf.adjustment_interval_days",
        "CONSENSUS_THRESHOLD": "validator.consensus.threshold",
        "VALIDATOR_PROMETHEUS_PORT": "validator.monitoring.prometheus_port",
        "VALIDATOR_LOG_LEVEL": "validator.monitoring.log_level",
    }

    for env_var, config_key in env_overrides.items():
        if env_var in os.environ:
            value = os.environ[env_var]
            # Simple nested dict update
            keys = config_key.split('.')
            current_dict = config_data
            for i, key in enumerate(keys):
                if i == len(keys) - 1:
                    # Convert to appropriate type if necessary
                    if key == "threshold":
                        current_dict[key] = float(value)
                    elif key in ["prometheus_port", "iterations", "adjustment_interval_days"]:
                        current_dict[key] = int(value)
                    else:
                        current_dict[key] = value
                else:
                    if key not in current_dict or not isinstance(current_dict[key], dict):
                        current_dict[key] = {}
                    current_dict = current_dict[key]

    return Config(**config_data)
