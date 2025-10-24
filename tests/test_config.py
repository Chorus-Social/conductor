import pytest
import os
import yaml
from src.conductor.config import load_config, Config, ValidatorConfig, NetworkConfig, StorageConfig, ConsensusConfig, MonitoringConfig

@pytest.fixture
def config_file(tmp_path):
    content = {
        "validator": {
            "keypair_path": "./keys/test_key.pem",
            "network": {
                "listen_address": "127.0.0.1:5000",
                "bootstrap_peers": ["/ip4/1.2.3.4/tcp/5001/p2p/QmTest1"]
            },
            "storage": {
                "path": "./test_validator_data"
            },
            "consensus": {
                "threshold": 0.75
            },
            "monitoring": {
                "log_level": "DEBUG"
            }
        }
    }
    path = tmp_path / "validator.yaml"
    with open(path, 'w') as f:
        yaml.dump(content, f)
    return str(path)

class TestConfigLoading:
    def test_load_default_config(self):
        config = load_config()
        assert isinstance(config, Config)
        assert config.validator.keypair_path == "./keys/validator_key.pem"
        assert config.validator.network.listen_address == "0.0.0.0:4001"
        assert config.validator.consensus.threshold == 0.67
        assert config.validator.monitoring.log_level == "INFO"

    def test_load_config_from_file(self, config_file):
        config = load_config(config_path=config_file)
        assert config.validator.keypair_path == "./keys/test_key.pem"
        assert config.validator.network.listen_address == "127.0.0.1:5000"
        assert config.validator.network.bootstrap_peers == ["/ip4/1.2.3.4/tcp/5001/p2p/QmTest1"]
        assert config.validator.storage.path == "./test_validator_data"
        assert config.validator.consensus.threshold == 0.75
        assert config.validator.monitoring.log_level == "DEBUG"

    def test_override_with_env_variables(self, config_file):
        os.environ["VALIDATOR_KEYPAIR_PATH"] = "./keys/env_key.pem"
        os.environ["VALIDATOR_NETWORK_LISTEN_ADDRESS"] = "192.168.1.1:6000"
        os.environ["CONSENSUS_THRESHOLD"] = "0.8"
        os.environ["VALIDATOR_LOG_LEVEL"] = "WARNING"

        config = load_config(config_path=config_file)

        assert config.validator.keypair_path == "./keys/env_key.pem"
        assert config.validator.network.listen_address == "192.168.1.1:6000"
        assert config.validator.consensus.threshold == 0.8
        assert config.validator.monitoring.log_level == "WARNING"

        # Clean up environment variables
        del os.environ["VALIDATOR_KEYPAIR_PATH"]
        del os.environ["VALIDATOR_NETWORK_LISTEN_ADDRESS"]
        del os.environ["CONSENSUS_THRESHOLD"]
        del os.environ["VALIDATOR_LOG_LEVEL"]

    def test_load_config_non_existent_file(self):
        config = load_config(config_path="/non/existent/path/config.yaml")
        assert isinstance(config, Config)
        assert config.validator.keypair_path == "./keys/validator_key.pem"
        assert config.validator.network.listen_address == "0.0.0.0:4001"

    def test_env_override_without_file(self):
        os.environ["VALIDATOR_STORAGE_PATH"] = "./env_only_data"
        config = load_config()
        assert config.validator.storage.path == "./env_only_data"
        del os.environ["VALIDATOR_STORAGE_PATH"]
