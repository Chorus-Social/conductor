"""Integration tests for Conductor."""

import pytest
import asyncio
import tempfile
import os
from conductor.config import Config
from conductor.node import ValidatorNode
from conductor.crypto import ThresholdCrypto
from conductor.consensus import ReliableBroadcast, CommonCoin
from conductor.network import Libp2pNetwork


class TestConductorIntegration:
    """Integration tests for the complete Conductor system."""
    
    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for testing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir
            
    @pytest.fixture
    def config(self, temp_dir):
        """Create test configuration."""
        config = Config()
        config.validator.storage.path = os.path.join(temp_dir, "data")
        config.validator.network.listen_address = "0.0.0.0:4001"
        config.validator.network.bootstrap_peers = []
        return config
        
    @pytest.fixture
    def validator_keypair(self):
        """Generate validator keypair."""
        crypto = ThresholdCrypto(n=3, t=2)
        return crypto.generate_keypair()
        
    @pytest.fixture
    def validator_ids(self):
        """Generate validator IDs."""
        return ["validator1", "validator2", "validator3"]
        
    @pytest.mark.asyncio
    async def test_validator_node_initialization(self, config, validator_keypair, validator_ids):
        """Test validator node initialization."""
        node = ValidatorNode(
            config=config,
            validator_keypair=validator_keypair,
            all_validator_ids=validator_ids
        )
        
        assert node.config == config
        assert node.keypair == validator_keypair
        assert node.public_key == validator_keypair[1]
        assert len(node.consensus.validators) == 3
        
    @pytest.mark.asyncio
    async def test_consensus_flow(self, config, validator_keypair, validator_ids):
        """Test complete consensus flow."""
        # Create validator node
        node = ValidatorNode(
            config=config,
            validator_keypair=validator_keypair,
            all_validator_ids=validator_ids
        )
        
        # Initialize network
        await node.dht.initialize()
        
        # Test consensus module
        consensus = node.consensus
        assert consensus.validator_id == validator_keypair[1].hex()
        assert len(consensus.validators) == 3
        
        # Test threshold crypto
        assert consensus.threshold_crypto.n == 3
        assert consensus.threshold_crypto.t == 2
        
    @pytest.mark.asyncio
    async def test_reliable_broadcast_integration(self, config):
        """Test ReliableBroadcast integration."""
        rbc = ReliableBroadcast(n=5, f=1)
        
        # Create test batch
        from conductor.models import EventBatch, Event
        events = [Event(creation_day=1, sig="test_sig")]
        batch = EventBatch(events=events)
        
        # Test propose
        batch_id = await rbc.rbc_propose(batch, "proposer1")
        assert batch_id in rbc.pending_batches
        
        # Test echo handling
        from conductor.consensus import Fragment
        fragment = Fragment(index=0, data=b"test_fragment")
        await rbc.handle_echo("validator1", batch_id, fragment, 0)
        
        # Test ready handling
        await rbc.handle_ready("validator1", batch_id)
        assert batch_id in rbc.ready_messages
        
    @pytest.mark.asyncio
    async def test_common_coin_integration(self, config):
        """Test CommonCoin integration."""
        crypto = ThresholdCrypto(n=5, t=3)
        coin = CommonCoin(crypto)
        
        # Test coin share generation
        private_key = b"test_private_key"
        share = await coin.coin_share(day=1, round_num=1, validator_id="validator1", private_key=private_key)
        assert isinstance(share, bytes)
        
        # Test coin computation
        shares = [b"share1", b"share2", b"share3"]
        coin_value = await coin.compute_coin(day=1, round_num=1, shares=shares)
        assert coin_value in [0, 1]
        
    @pytest.mark.asyncio
    async def test_network_integration(self, config):
        """Test network layer integration."""
        network = Libp2pNetwork(
            listen_address="0.0.0.0:4001",
            bootstrap_peers=["peer1", "peer2"],
            node_id="test_node"
        )
        
        # Test network startup
        await network.start()
        assert len(network.connected_peers) > 0
        
        # Test message broadcasting
        message = b"test_message"
        await network.broadcast_message(message, "test_topic")
        assert len(network.message_queue) > 0
        
        # Test direct messaging
        peer_id = list(network.connected_peers.keys())[0]
        result = await network.send_direct(peer_id, message)
        assert result is True
        
        # Test network shutdown
        await network.stop()
        assert len(network.connected_peers) == 0
        
    @pytest.mark.asyncio
    async def test_storage_integration(self, config, validator_keypair):
        """Test storage integration."""
        from conductor.node import ValidatorStorage
        from conductor.models import DayProof
        
        storage = ValidatorStorage(config.validator.storage.path)
        
        # Create test proof
        proof = DayProof(
            day_number=1,
            proof=b"test_proof",
            validator_id=validator_keypair[1],
            signature=b"test_signature"
        )
        
        # Test save and retrieve
        await storage.save_proof(proof)
        retrieved = await storage.get_proof(1)
        
        assert retrieved is not None
        assert retrieved.day_number == proof.day_number
        assert retrieved.proof == proof.proof
        
    @pytest.mark.asyncio
    async def test_vdf_integration(self, config):
        """Test VDF integration."""
        from conductor.vdf import ChorusVDF
        
        vdf = ChorusVDF(b"test_seed", iterations=1000)  # Small iteration count for testing
        
        # Test VDF computation
        proof = await asyncio.to_thread(vdf.compute_day_proof, 1)
        assert isinstance(proof, bytes)
        assert len(proof) > 0
        
        # Test VDF verification
        is_valid = vdf.verify_day_proof(1, proof)
        assert is_valid is True
        
    @pytest.mark.asyncio
    async def test_error_handling_integration(self, config, validator_keypair, validator_ids):
        """Test error handling integration."""
        from conductor.errors import ConductorError, ConsensusTimeoutError
        from conductor.retry import exponential_backoff
        
        # Test retry mechanism
        retry_count = 0
        
        async def failing_function():
            nonlocal retry_count
            retry_count += 1
            if retry_count < 3:
                raise ConsensusTimeoutError("Simulated timeout")
            return "success"
            
        result = await exponential_backoff(
            failing_function,
            max_retries=5,
            base_delay=0.01
        )
        
        assert result == "success"
        assert retry_count == 3
        
    @pytest.mark.asyncio
    async def test_metrics_integration(self, config):
        """Test metrics integration."""
        from conductor.metrics import metrics
        
        # Test metrics recording
        metrics.record_consensus_round("success", 1.5)
        metrics.record_vdf_computation(3600.0, 86400000)
        metrics.record_event_batch(1024)
        metrics.record_rbc_message("propose")
        
        # Test system metrics
        metrics.update_system_metrics(1024*1024, 50.0, 10*1024*1024)
        metrics.update_peer_count(5)
        metrics.update_day_number(123)
        metrics.update_blacklist_size(2)
        
        # Metrics should be recorded without errors
        assert True  # If we get here, metrics recording worked
        
    @pytest.mark.asyncio
    async def test_logging_integration(self, config):
        """Test logging integration."""
        from conductor.logging_config import configure_logging, get_logger
        
        # Configure logging
        configure_logging(log_level="DEBUG", enable_json=False)
        
        # Test logger
        logger = get_logger("test")
        logger.info("Test message", extra_field="test_value")
        
        # Logging should work without errors
        assert True  # If we get here, logging worked
