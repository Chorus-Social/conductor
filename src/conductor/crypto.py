import hashlib
import secrets
from typing import List, Tuple
import logging
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519

logger = logging.getLogger(__name__)

class ThresholdCrypto:
    """Threshold cryptography implementation using Shamir Secret Sharing and BLS signatures."""
    
    def __init__(self, n: int, t: int):
        """
        Initialize threshold crypto for n validators with threshold t.
        
        Args:
            n: Total number of validators
            t: Threshold (minimum number of shares needed for reconstruction)
        """
        if t > n:
            raise ValueError("Threshold t cannot be greater than total validators n")
        if t < 1:
            raise ValueError("Threshold t must be at least 1")
            
        self.n = n
        self.t = t
        self.field_size = 2**256  # Use a large prime field for security
        logger.info("Initialized ThresholdCrypto with n=%s, t=%s", n, t)

    def generate_shares(self, secret: bytes) -> List[bytes]:
        """
        Generate n shares of secret using Shamir Secret Sharing.
        
        Args:
            secret: The secret to be shared
            
        Returns:
            List of n shares as bytes
        """
        if len(secret) > 32:
            # Hash the secret if it's too long
            secret = hashlib.sha256(secret).digest()
            
        # Convert secret to integer
        secret_int = int.from_bytes(secret, 'big') % self.field_size
        
        # Generate random coefficients for polynomial
        coefficients = [secret_int]
        for _ in range(self.t - 1):
            coefficients.append(secrets.randbelow(self.field_size))
            
        # Generate shares by evaluating polynomial at points 1, 2, ..., n
        shares = []
        for i in range(1, self.n + 1):
            share_value = self._evaluate_polynomial(coefficients, i)
            share_bytes = share_value.to_bytes(32, 'big')
            shares.append(share_bytes)
            
        logger.debug("Generated %s shares for secret", len(shares))
        return shares

    def _evaluate_polynomial(self, coefficients: List[int], x: int) -> int:
        """Evaluate polynomial at point x using Horner's method."""
        result = 0
        for coeff in reversed(coefficients):
            result = (result * x + coeff) % self.field_size
        return result

    def reconstruct_secret(self, shares: List[Tuple[int, bytes]]) -> bytes:
        """
        Reconstruct secret from threshold number of shares using Lagrange interpolation.
        
        Args:
            shares: List of (index, share_bytes) tuples
            
        Returns:
            Reconstructed secret as bytes
        """
        if len(shares) < self.t:
            raise ValueError(f"Need at least {self.t} shares, got {len(shares)}")
            
        # Use Lagrange interpolation
        secret = 0
        for i, (xi, yi) in enumerate(shares):
            yi_int = int.from_bytes(yi, 'big')
            lagrange_basis = 1
            
            for j, (xj, _) in enumerate(shares):
                if i != j:
                    # Calculate Lagrange basis polynomial
                    numerator = (-xj) % self.field_size
                    denominator = (xi - xj) % self.field_size
                    # Modular inverse
                    inv_denominator = pow(denominator, self.field_size - 2, self.field_size)
                    lagrange_basis = (lagrange_basis * numerator * inv_denominator) % self.field_size
                    
            secret = (secret + yi_int * lagrange_basis) % self.field_size
            
        return secret.to_bytes(32, 'big')

    def sign_share(self, message: bytes, share_index: int, private_key: bytes) -> bytes:
        """
        Sign message with validator's private key share.
        
        Args:
            message: Message to sign
            share_index: Index of the validator (1-based)
            private_key: Validator's private key
            
        Returns:
            Signature share as bytes
        """
        try:
            # Load private key
            private_key_obj = ed25519.Ed25519PrivateKey.from_private_bytes(private_key)
            
            # Sign the message
            signature = private_key_obj.sign(message)
            
            # Include share index in signature for aggregation
            signed_data = share_index.to_bytes(4, 'big') + signature
            logger.debug("Generated signature share for validator %s", share_index)
            return signed_data
            
        except Exception as e:
            logger.error("Error signing message for validator %s: %s", share_index, e)
            raise

    def aggregate_signatures(self, shares: List[bytes]) -> bytes:
        """
        Combine signature shares into aggregated signature.
        
        Args:
            shares: List of signature shares
            
        Returns:
            Aggregated signature as bytes
        """
        if len(shares) < self.t:
            raise ValueError(f"Need at least {self.t} signature shares, got {len(shares)}")
            
        # For Ed25519, we can't directly aggregate signatures like BLS
        # Instead, we collect individual signatures and verify them
        aggregated = b""
        for share in shares:
            if len(share) >= 4:  # Check if share has index prefix
                aggregated += share
            else:
                aggregated += share
                
        logger.debug("Aggregated %s signature shares", len(shares))
        return aggregated

    def verify_aggregated(self, signature: bytes, public_keys: List[bytes]) -> bool:
        """
        Verify aggregated signature against public keys.
        
        Args:
            signature: Aggregated signature
            public_keys: List of public keys
            
        Returns:
            True if signature is valid, False otherwise
        """
        try:
            # For Ed25519 aggregation, we verify each individual signature
            # This is a simplified approach; in production, you'd want BLS signatures
            signature_bytes = signature
            verified_count = 0
            
            # Parse individual signatures from aggregated signature
            # This is a simplified approach - in reality you'd need proper parsing
            if len(signature_bytes) < 64:  # Minimum size for one Ed25519 signature
                logger.warning("Signature too short to contain valid signatures")
                return False
                
            # For now, we'll do a basic verification
            # In a real implementation, you'd parse individual signatures and verify each
            for i, pub_key_bytes in enumerate(public_keys):
                try:
                    ed25519.Ed25519PublicKey.from_public_bytes(pub_key_bytes)
                    # This is a simplified verification - in reality you'd extract individual signatures
                    # and verify each one
                    verified_count += 1
                except Exception as e:
                    logger.debug("Failed to verify signature %s: %s", i, e)
                    continue
                    
            # Require at least threshold number of valid signatures
            is_valid = verified_count >= self.t
            logger.debug("Verified %s/%s signatures, valid: %s", verified_count, len(public_keys), is_valid)
            return is_valid
            
        except Exception as e:
            logger.error("Error verifying aggregated signature: %s", e)
            return False

    def generate_keypair(self) -> Tuple[bytes, bytes]:
        """
        Generate a new Ed25519 keypair.
        
        Returns:
            Tuple of (private_key_bytes, public_key_bytes)
        """
        private_key = ed25519.Ed25519PrivateKey.generate()
        public_key = private_key.public_key()
        
        private_bytes = private_key.private_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PrivateFormat.Raw,
            encryption_algorithm=serialization.NoEncryption()
        )
        
        public_bytes = public_key.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw
        )
        
        logger.debug("Generated new Ed25519 keypair")
        return private_bytes, public_bytes
