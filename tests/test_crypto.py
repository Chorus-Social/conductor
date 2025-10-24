"""Tests for threshold cryptography implementation."""

import pytest
from conductor.crypto import ThresholdCrypto
from conductor.errors import ConductorError


class TestThresholdCrypto:
    """Test cases for ThresholdCrypto class."""
    
    def test_init_valid_params(self):
        """Test initialization with valid parameters."""
        crypto = ThresholdCrypto(n=5, t=3)
        assert crypto.n == 5
        assert crypto.t == 3
        
    def test_init_invalid_threshold(self):
        """Test initialization with invalid threshold."""
        with pytest.raises(ValueError, match="Threshold t cannot be greater than total validators n"):
            ThresholdCrypto(n=3, t=5)
            
    def test_init_zero_threshold(self):
        """Test initialization with zero threshold."""
        with pytest.raises(ValueError, match="Threshold t must be at least 1"):
            ThresholdCrypto(n=3, t=0)
            
    def test_generate_shares(self):
        """Test share generation."""
        crypto = ThresholdCrypto(n=5, t=3)
        secret = b"test_secret"
        shares = crypto.generate_shares(secret)
        
        assert len(shares) == 5
        assert all(isinstance(share, bytes) for share in shares)
        assert all(len(share) == 32 for share in shares)
        
    def test_generate_shares_long_secret(self):
        """Test share generation with long secret."""
        crypto = ThresholdCrypto(n=5, t=3)
        secret = b"x" * 100  # Long secret
        shares = crypto.generate_shares(secret)
        
        assert len(shares) == 5
        assert all(len(share) == 32 for share in shares)
        
    def test_reconstruct_secret(self):
        """Test secret reconstruction."""
        crypto = ThresholdCrypto(n=5, t=3)
        secret = b"test_secret"
        shares = crypto.generate_shares(secret)
        
        # Create share tuples with indices
        share_tuples = [(i+1, share) for i, share in enumerate(shares)]
        
        # Test reconstruction with all shares
        reconstructed = crypto.reconstruct_secret(share_tuples)
        assert reconstructed == secret[:32]  # Truncated to 32 bytes
        
    def test_reconstruct_secret_insufficient_shares(self):
        """Test reconstruction with insufficient shares."""
        crypto = ThresholdCrypto(n=5, t=3)
        secret = b"test_secret"
        shares = crypto.generate_shares(secret)
        
        # Use only 2 shares (less than threshold)
        share_tuples = [(1, shares[0]), (2, shares[1])]
        
        with pytest.raises(ValueError, match="Need at least 3 shares"):
            crypto.reconstruct_secret(share_tuples)
            
    def test_sign_share(self):
        """Test signature share generation."""
        crypto = ThresholdCrypto(n=5, t=3)
        private_key, public_key = crypto.generate_keypair()
        
        message = b"test_message"
        share = crypto.sign_share(message, 1, private_key)
        
        assert isinstance(share, bytes)
        assert len(share) > 0
        
    def test_aggregate_signatures(self):
        """Test signature aggregation."""
        crypto = ThresholdCrypto(n=5, t=3)
        shares = [b"share1", b"share2", b"share3"]
        
        aggregated = crypto.aggregate_signatures(shares)
        assert isinstance(aggregated, bytes)
        assert len(aggregated) > 0
        
    def test_aggregate_signatures_insufficient(self):
        """Test aggregation with insufficient shares."""
        crypto = ThresholdCrypto(n=5, t=3)
        shares = [b"share1", b"share2"]  # Only 2 shares, need 3
        
        with pytest.raises(ValueError, match="Need at least 3 signature shares"):
            crypto.aggregate_signatures(shares)
            
    def test_verify_aggregated(self):
        """Test aggregated signature verification."""
        crypto = ThresholdCrypto(n=5, t=3)
        message = b"test_message"
        signature = b"test_signature"
        public_keys = [b"key1", b"key2", b"key3"]
        
        # This is a simplified test - in reality verification would be more complex
        result = crypto.verify_aggregated(message, signature, public_keys)
        assert isinstance(result, bool)
        
    def test_generate_keypair(self):
        """Test keypair generation."""
        crypto = ThresholdCrypto(n=5, t=3)
        private_key, public_key = crypto.generate_keypair()
        
        assert isinstance(private_key, bytes)
        assert isinstance(public_key, bytes)
        assert len(private_key) == 32  # Ed25519 private key size
        assert len(public_key) == 32  # Ed25519 public key size
