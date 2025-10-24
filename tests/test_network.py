"""Tests for network layer implementation."""

import pytest
import asyncio
from conductor.network import Libp2pNetwork, NetworkManager, PeerInfo


class TestLibp2pNetwork:
    """Test cases for Libp2pNetwork class."""
    
    @pytest.fixture
    def network(self):
        """Create Libp2pNetwork instance for testing."""
        return Libp2pNetwork(
            listen_address="0.0.0.0:4001",
            bootstrap_peers=["peer1", "peer2"],
            node_id="test_node"
        )
        
    def test_init(self, network):
        """Test network initialization."""
        assert network.listen_address == "0.0.0.0:4001"
        assert network.bootstrap_peers == ["peer1", "peer2"]
        assert network.node_id == "test_node"
        assert len(network.peers) == 0
        assert len(network.connected_peers) == 0
        
    @pytest.mark.asyncio
    async def test_start(self, network):
        """Test network startup."""
        await network.start()
        
        # Check that bootstrap peers were connected
        assert len(network.connected_peers) > 0
        
    @pytest.mark.asyncio
    async def test_stop(self, network):
        """Test network shutdown."""
        await network.start()
        initial_peers = len(network.connected_peers)
        
        await network.stop()
        
        # All peers should be disconnected
        assert len(network.connected_peers) == 0
        
    @pytest.mark.asyncio
    async def test_broadcast_message(self, network):
        """Test message broadcasting."""
        await network.start()
        
        message = b"test_message"
        await network.broadcast_message(message, "test_topic")
        
        # Check that message was queued
        assert len(network.message_queue) > 0
        
    @pytest.mark.asyncio
    async def test_send_direct(self, network):
        """Test direct message sending."""
        await network.start()
        
        # Get a connected peer
        peer_id = list(network.connected_peers.keys())[0]
        
        message = b"direct_message"
        result = await network.send_direct(peer_id, message)
        
        assert result is True
        
    @pytest.mark.asyncio
    async def test_send_direct_unknown_peer(self, network):
        """Test sending to unknown peer."""
        await network.start()
        
        message = b"direct_message"
        result = await network.send_direct("unknown_peer", message)
        
        assert result is False
        
    @pytest.mark.asyncio
    async def test_subscribe_topic(self, network):
        """Test topic subscription."""
        await network.start()
        
        async def handler(message):
            pass
            
        await network.subscribe_topic("test_topic", handler)
        
        assert "test_topic" in network.gossip_topics
        assert "test_topic" in network.message_handlers
        
    @pytest.mark.asyncio
    async def test_request_fragment(self, network):
        """Test fragment request."""
        await network.start()
        
        fragment = await network.request_fragment("peer1", "batch1", 0)
        
        assert isinstance(fragment, bytes)
        assert len(fragment) > 0
        
    def test_get_peer_count(self, network):
        """Test peer count retrieval."""
        # Initially no peers
        assert network.get_peer_count() == 0
        
        # Add a peer
        peer_info = PeerInfo(
            peer_id="peer1",
            address="127.0.0.1:4001",
            public_key=b"key1",
            last_seen=0.0,
            is_connected=True
        )
        network.connected_peers["peer1"] = peer_info
        
        assert network.get_peer_count() == 1
        
    def test_get_peer_info(self, network):
        """Test peer info retrieval."""
        peer_info = PeerInfo(
            peer_id="peer1",
            address="127.0.0.1:4001",
            public_key=b"key1",
            last_seen=0.0,
            is_connected=True
        )
        network.connected_peers["peer1"] = peer_info
        
        retrieved = network.get_peer_info("peer1")
        assert retrieved is not None
        assert retrieved.peer_id == "peer1"
        
        # Test unknown peer
        assert network.get_peer_info("unknown") is None
        
    def test_is_peer_connected(self, network):
        """Test peer connection status."""
        peer_info = PeerInfo(
            peer_id="peer1",
            address="127.0.0.1:4001",
            public_key=b"key1",
            last_seen=0.0,
            is_connected=True
        )
        network.connected_peers["peer1"] = peer_info
        
        assert network.is_peer_connected("peer1") is True
        assert network.is_peer_connected("unknown") is False


class TestNetworkManager:
    """Test cases for NetworkManager class."""
    
    @pytest.fixture
    def mock_config(self):
        """Create mock configuration."""
        class MockConfig:
            class Network:
                listen_address = "0.0.0.0:4001"
                bootstrap_peers = ["peer1", "peer2"]
                
            network = Network()
            
        return MockConfig()
        
    @pytest.fixture
    def network_manager(self, mock_config):
        """Create NetworkManager instance for testing."""
        return NetworkManager(mock_config, "test_node")
        
    @pytest.mark.asyncio
    async def test_initialize(self, network_manager):
        """Test network manager initialization."""
        await network_manager.initialize()
        
        assert network_manager.network is not None
        assert network_manager.network.node_id == "test_node"
        
    @pytest.mark.asyncio
    async def test_broadcast_consensus_message(self, network_manager):
        """Test consensus message broadcasting."""
        await network_manager.initialize()
        
        message = b"consensus_message"
        await network_manager.broadcast_consensus_message(message)
        
        # Check that message was queued
        assert len(network_manager.network.message_queue) > 0
        
    @pytest.mark.asyncio
    async def test_broadcast_vdf_proof(self, network_manager):
        """Test VDF proof broadcasting."""
        await network_manager.initialize()
        
        proof = b"vdf_proof"
        await network_manager.broadcast_vdf_proof(proof)
        
        # Check that message was queued
        assert len(network_manager.network.message_queue) > 0
        
    @pytest.mark.asyncio
    async def test_send_direct_message(self, network_manager):
        """Test direct message sending."""
        await network_manager.initialize()
        
        # Get a connected peer
        peer_id = list(network_manager.network.connected_peers.keys())[0]
        
        message = b"direct_message"
        result = await network_manager.send_direct_message(peer_id, message)
        
        assert result is True
        
    def test_get_peer_count(self, network_manager):
        """Test peer count retrieval."""
        # Initially no network
        assert network_manager.get_peer_count() == 0
        
        # Initialize network
        network_manager.network = network_manager.network or type('MockNetwork', (), {
            'get_peer_count': lambda: 5
        })()
        
        assert network_manager.get_peer_count() == 5
