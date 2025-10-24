"""Tests for consensus implementation."""

import pytest
import asyncio
from conductor.consensus import ReliableBroadcast, CommonCoin, Fragment
from conductor.crypto import ThresholdCrypto
from conductor.models import EventBatch, Event


class TestReliableBroadcast:
    """Test cases for ReliableBroadcast class."""
    
    @pytest.fixture
    def rbc(self):
        """Create ReliableBroadcast instance for testing."""
        return ReliableBroadcast(n=5, f=1)  # 5 validators, 1 Byzantine
        
    @pytest.fixture
    def sample_batch(self):
        """Create sample event batch for testing."""
        events = [
            Event(creation_day=1, sig="sig1"),
            Event(creation_day=1, sig="sig2")
        ]
        return EventBatch(events=events)
        
    def test_init(self, rbc):
        """Test ReliableBroadcast initialization."""
        assert rbc.n == 5
        assert rbc.f == 1
        assert rbc.k == 3  # n - 2*f = 5 - 2*1 = 3
        
    def test_init_invalid_params(self):
        """Test initialization with invalid parameters."""
        with pytest.raises(ValueError, match="Invalid parameters: k must be positive"):
            ReliableBroadcast(n=2, f=1)  # k = 2 - 2*1 = 0
            
    @pytest.mark.asyncio
    async def test_rbc_propose(self, rbc, sample_batch):
        """Test RBC propose functionality."""
        batch_id = await rbc.rbc_propose(sample_batch, "proposer1")
        
        assert isinstance(batch_id, str)
        assert len(batch_id) > 0
        assert batch_id in rbc.pending_batches
        
    def test_serialize_batch(self, rbc, sample_batch):
        """Test batch serialization."""
        serialized = rbc._serialize_batch(sample_batch)
        
        assert isinstance(serialized, bytes)
        assert len(serialized) > 0
        
    def test_erasure_encode(self, rbc):
        """Test erasure encoding."""
        data = b"test_data_for_erasure_coding"
        fragments = rbc._erasure_encode(data)
        
        assert len(fragments) == rbc.n
        assert all(isinstance(f, Fragment) for f in fragments)
        assert all(f.index >= 0 and f.index < rbc.n for f in fragments)
        
    def test_create_merkle_tree(self, rbc):
        """Test Merkle tree creation."""
        fragments = [
            Fragment(index=0, data=b"fragment0"),
            Fragment(index=1, data=b"fragment1"),
            Fragment(index=2, data=b"fragment2")
        ]
        
        merkle_root = rbc._create_merkle_tree(fragments)
        
        assert isinstance(merkle_root, bytes)
        assert len(merkle_root) > 0
        
    @pytest.mark.asyncio
    async def test_handle_echo(self, rbc, sample_batch):
        """Test echo message handling."""
        # First propose a batch
        batch_id = await rbc.rbc_propose(sample_batch, "proposer1")
        
        # Create a fragment
        fragment = Fragment(index=0, data=b"test_fragment")
        
        # Handle echo
        await rbc.handle_echo("validator1", batch_id, fragment, 0)
        
        # Check that fragment was stored
        assert batch_id in rbc.received_fragments
        assert 0 in rbc.received_fragments[batch_id]
        
    @pytest.mark.asyncio
    async def test_handle_ready(self, rbc, sample_batch):
        """Test ready message handling."""
        # First propose a batch
        batch_id = await rbc.rbc_propose(sample_batch, "proposer1")
        
        # Handle ready message
        await rbc.handle_ready("validator1", batch_id)
        
        # Check that ready message was recorded
        assert batch_id in rbc.ready_messages
        assert "validator1" in rbc.ready_messages[batch_id]
        
    def test_reconstruct_batch(self, rbc):
        """Test batch reconstruction."""
        fragments = [
            Fragment(index=0, data=b"fragment0"),
            Fragment(index=1, data=b"fragment1"),
            Fragment(index=2, data=b"fragment2")
        ]
        
        reconstructed = rbc._reconstruct_batch(fragments)
        
        assert isinstance(reconstructed, bytes)
        # In this simplified implementation, reconstruction concatenates fragments
        expected = b"fragment0fragment1fragment2"
        assert reconstructed == expected
        
    def test_is_delivered(self, rbc):
        """Test delivery status check."""
        batch_id = "test_batch"
        
        # Initially not delivered
        assert not rbc.is_delivered(batch_id)
        
        # Mark as delivered
        rbc.delivered_batches.add(batch_id)
        assert rbc.is_delivered(batch_id)


class TestCommonCoin:
    """Test cases for CommonCoin class."""
    
    @pytest.fixture
    def coin(self):
        """Create CommonCoin instance for testing."""
        crypto = ThresholdCrypto(n=5, t=3)
        return CommonCoin(crypto)
        
    @pytest.mark.asyncio
    async def test_coin_share(self, coin):
        """Test coin share generation."""
        private_key = b"test_private_key"
        share = await coin.coin_share(day=1, round_num=1, validator_id="validator1", private_key=private_key)
        
        assert isinstance(share, bytes)
        assert len(share) > 0
        
        # Check that share was stored
        epoch = 1 * 1000 + 1
        assert epoch in coin.coin_shares
        assert "validator1" in coin.coin_shares[epoch]
        
    @pytest.mark.asyncio
    async def test_compute_coin(self, coin):
        """Test coin computation."""
        shares = [b"share1", b"share2", b"share3"]
        coin_value = await coin.compute_coin(day=1, round_num=1, shares=shares)
        
        assert coin_value in [0, 1]
        
        # Check that value was stored
        epoch = 1 * 1000 + 1
        assert coin.coin_values[epoch] == coin_value
        
    @pytest.mark.asyncio
    async def test_compute_coin_insufficient_shares(self, coin):
        """Test coin computation with insufficient shares."""
        shares = [b"share1", b"share2"]  # Only 2 shares, need 3
        
        with pytest.raises(ValueError, match="Insufficient shares for coin"):
            await coin.compute_coin(day=1, round_num=1, shares=shares)
            
    def test_get_coin_value(self, coin):
        """Test getting coin value."""
        # Initially no value
        assert coin.get_coin_value(day=1, round_num=1) is None
        
        # Set a value
        epoch = 1 * 1000 + 1
        coin.coin_values[epoch] = 1
        
        # Now should return the value
        assert coin.get_coin_value(day=1, round_num=1) == 1
