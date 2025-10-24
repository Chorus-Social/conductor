import asyncio
import logging
from typing import List, Dict, Optional, Set
from dataclasses import dataclass

from conductor.crypto import ThresholdCrypto
from conductor.models import EventBatch
from conductor.hashing import blake3_hash

logger = logging.getLogger(__name__)

@dataclass
class Fragment:
    """Represents a single fragment of an erasure-coded message."""
    index: int
    data: bytes
    merkle_proof: Optional[bytes] = None

class ReliableBroadcast:
    """Reliable Broadcast implementation with erasure coding using Reed-Solomon."""
    
    def __init__(self, n: int, f: int):
        """
        Initialize Reliable Broadcast.
        
        Args:
            n: Total number of validators
            f: Maximum number of Byzantine nodes (f < n/3)
        """
        self.n = n
        self.f = f
        self.k = n - 2 * f  # Reconstruction threshold
        if self.k <= 0:
            raise ValueError("Invalid parameters: k must be positive")
            
        # Reed-Solomon parameters
        self.rs_redundancy = 2 * f
        self.threshold_crypto = ThresholdCrypto(n=n, t=2*f+1)
        
        # State tracking
        self.pending_batches: Dict[str, Dict[str, any]] = {}  # batch_id -> state
        self.received_fragments: Dict[str, Dict[int, Fragment]] = {}  # batch_id -> index -> fragment
        self.ready_messages: Dict[str, Set[str]] = {}  # batch_id -> set of validator_ids
        self.delivered_batches: Set[str] = set()
        
        logger.info("Initialized ReliableBroadcast with n=%s, f=%s, k=%s", n, f, self.k)

    async def rbc_propose(self, batch: EventBatch, proposer_id: str) -> str:
        """
        Propose a new batch for reliable broadcast.
        
        Args:
            batch: Event batch to broadcast
            proposer_id: ID of the proposing validator
            
        Returns:
            Batch ID for tracking
        """
        # Serialize batch
        batch_data = self._serialize_batch(batch)
        batch_id = blake3_hash(batch_data).hex()
        
        # Erasure code the batch
        fragments = self._erasure_encode(batch_data)
        
        # Create merkle tree for verification
        merkle_root = self._create_merkle_tree(fragments)
        
        # Initialize state
        self.pending_batches[batch_id] = {
            'proposer_id': proposer_id,
            'batch_data': batch_data,
            'fragments': fragments,
            'merkle_root': merkle_root,
            'echo_count': 0,
            'ready_count': 0,
            'delivered': False
        }
        
        self.received_fragments[batch_id] = {}
        self.ready_messages[batch_id] = set()
        
        # Send fragments to all validators
        await self._send_fragments(batch_id, fragments, proposer_id)
        
        logger.info(f"RBC propose: batch {batch_id} from {proposer_id}")
        return batch_id

    def _serialize_batch(self, batch: EventBatch) -> bytes:
        """Serialize event batch to bytes."""
        # Simple serialization - in production, use protobuf or similar
        events_data = []
        for event in batch.events:
            event_data = {
                'creation_day': event.creation_day,
                'sig': event.sig,
                'type': type(event).__name__
            }
            # Add event-specific fields
            if hasattr(event, 'content_cid'):
                event_data['content_cid'] = event.content_cid
            if hasattr(event, 'author_pubkey_hash'):
                event_data['author_pubkey_hash'] = event.author_pubkey_hash
            # Add other fields as needed
            events_data.append(event_data)
            
        return str(events_data).encode('utf-8')

    def _erasure_encode(self, data: bytes) -> List[Fragment]:
        """
        Erasure encode data into n fragments using Reed-Solomon.
        
        Args:
            data: Data to encode
            
        Returns:
            List of fragments
        """
        # Simple erasure coding simulation
        # In production, use a proper Reed-Solomon library
        fragment_size = len(data) // self.k + 1
        fragments = []
        
        for i in range(self.n):
            start_idx = (i * fragment_size) % len(data)
            end_idx = min(start_idx + fragment_size, len(data))
            
            if start_idx < len(data):
                fragment_data = data[start_idx:end_idx]
            else:
                # Padding for last fragment
                fragment_data = data[-fragment_size:] if len(data) >= fragment_size else data
                
            fragment = Fragment(
                index=i,
                data=fragment_data
            )
            fragments.append(fragment)
            
        logger.debug("Erasure encoded %s bytes into %s fragments", len(data), len(fragments))
        return fragments

    def _create_merkle_tree(self, fragments: List[Fragment]) -> bytes:
        """Create Merkle tree for fragment verification."""
        # Simple Merkle tree implementation
        leaves = [blake3_hash(f.data) for f in fragments]
        
        while len(leaves) > 1:
            next_level = []
            for i in range(0, len(leaves), 2):
                if i + 1 < len(leaves):
                    combined = leaves[i] + leaves[i + 1]
                else:
                    combined = leaves[i] + leaves[i]  # Duplicate last leaf if odd
                next_level.append(blake3_hash(combined))
            leaves = next_level
            
        return leaves[0] if leaves else b""

    async def _send_fragments(self, batch_id: str, fragments: List[Fragment], proposer_id: str):
        """Send fragments to all validators."""
        # In a real implementation, this would send over the network
        # For now, we simulate by calling handle_echo directly
        for i, fragment in enumerate(fragments):
            # Simulate network delay
            await asyncio.sleep(0.01)
            await self.handle_echo(proposer_id, batch_id, fragment, i)

    async def handle_echo(self, sender: str, batch_id: str, fragment: Fragment, fragment_index: int):
        """
        Handle an ECHO message from a validator.
        
        Args:
            sender: ID of the sending validator
            batch_id: ID of the batch
            fragment: Fragment data
            fragment_index: Index of the fragment
        """
        if batch_id not in self.pending_batches:
            logger.warning(f"Received echo for unknown batch {batch_id}")
            return
            
        # Store fragment
        if batch_id not in self.received_fragments:
            self.received_fragments[batch_id] = {}
            
        self.received_fragments[batch_id][fragment_index] = fragment
        
        # Verify fragment against merkle root
        if not self._verify_fragment(fragment, batch_id):
            logger.warning(f"Invalid fragment {fragment_index} from {sender}")
            return
            
        # Check if we have enough fragments to send READY
        if len(self.received_fragments[batch_id]) >= self.k:
            if batch_id not in self.ready_messages:
                self.ready_messages[batch_id] = set()
                
            if sender not in self.ready_messages[batch_id]:
                await self._send_ready(batch_id, sender)
                self.ready_messages[batch_id].add(sender)
                
        logger.debug(f"Echo from {sender} for batch {batch_id}, fragment {fragment_index}")

    def _verify_fragment(self, fragment: Fragment, batch_id: str) -> bool:
        """Verify fragment against merkle root."""
        if batch_id not in self.pending_batches:
            return False
            
        # Simple verification - in production, verify merkle proof
        fragment_hash = blake3_hash(fragment.data)
        return len(fragment.data) > 0  # Basic validation

    async def _send_ready(self, batch_id: str, validator_id: str):
        """Send READY message for a batch."""
        logger.debug(f"Sending READY for batch {batch_id} from {validator_id}")
        # In a real implementation, broadcast READY message
        await self.handle_ready(validator_id, batch_id)

    async def handle_ready(self, sender: str, batch_id: str):
        """
        Handle a READY message from a validator.
        
        Args:
            sender: ID of the sending validator
            batch_id: ID of the batch
        """
        if batch_id not in self.pending_batches:
            return
            
        if batch_id not in self.ready_messages:
            self.ready_messages[batch_id] = set()
            
        self.ready_messages[batch_id].add(sender)
        
        # Check if we have enough READY messages
        ready_count = len(self.ready_messages[batch_id])
        if ready_count >= self.f + 1 and batch_id not in self.delivered_batches:
            # Send our own READY if we haven't already
            if sender not in self.ready_messages[batch_id]:
                await self._send_ready(batch_id, sender)
                
        # Check if we can deliver
        if ready_count >= 2 * self.f + 1 and batch_id not in self.delivered_batches:
            await self._deliver_batch(batch_id)
            
        logger.debug(f"Ready from {sender} for batch {batch_id}, count: {ready_count}")

    async def _deliver_batch(self, batch_id: str):
        """Deliver a batch after successful RBC."""
        if batch_id in self.delivered_batches:
            return
            
        # Reconstruct batch from fragments
        if batch_id not in self.received_fragments:
            logger.error(f"Cannot deliver batch {batch_id}: no fragments received")
            return
            
        fragments = list(self.received_fragments[batch_id].values())
        if len(fragments) < self.k:
            logger.error(f"Cannot deliver batch {batch_id}: insufficient fragments ({len(fragments)} < {self.k})")
            return
            
        # Reconstruct original data
        reconstructed_data = self._reconstruct_batch(fragments)
        
        # Verify reconstruction
        if batch_id in self.pending_batches:
            original_data = self.pending_batches[batch_id]['batch_data']
            if reconstructed_data == original_data:
                self.delivered_batches.add(batch_id)
                self.pending_batches[batch_id]['delivered'] = True
                logger.info(f"Delivered batch {batch_id}")
            else:
                logger.error(f"Reconstruction failed for batch {batch_id}")

    def _reconstruct_batch(self, fragments: List[Fragment]) -> bytes:
        """Reconstruct original data from fragments."""
        # Simple reconstruction - in production, use proper Reed-Solomon decoding
        fragments.sort(key=lambda f: f.index)
        
        # Concatenate fragment data
        reconstructed = b""
        for fragment in fragments:
            reconstructed += fragment.data
            
        return reconstructed

    def is_delivered(self, batch_id: str) -> bool:
        """Check if a batch has been delivered."""
        return batch_id in self.delivered_batches

    def get_delivered_batch(self, batch_id: str) -> Optional[EventBatch]:
        """Get a delivered batch by ID."""
        if batch_id not in self.delivered_batches:
            return None
            
        # In a real implementation, you'd deserialize the batch data
        # For now, return a placeholder
        return EventBatch(events=[])


class CommonCoin:
    """Common coin implementation using threshold signatures."""
    
    def __init__(self, threshold_crypto: ThresholdCrypto):
        self.crypto = threshold_crypto
        self.coin_shares: Dict[int, Dict[str, bytes]] = {}  # epoch -> validator_id -> share
        self.coin_values: Dict[int, Optional[int]] = {}  # epoch -> coin_value
        
    async def coin_share(self, day: int, round_num: int, validator_id: str, private_key: bytes) -> bytes:
        """
        Generate a coin share for a given day and round.
        
        Args:
            day: Day number
            round_num: Round number
            validator_id: ID of the validator
            private_key: Validator's private key
            
        Returns:
            Coin share as bytes
        """
        message = f"COIN_{day}_{round_num}".encode()
        share = self.crypto.sign_share(message, int(validator_id, 16) % 1000, private_key)
        
        # Store share
        epoch = day * 1000 + round_num  # Combine day and round into epoch
        if epoch not in self.coin_shares:
            self.coin_shares[epoch] = {}
        self.coin_shares[epoch][validator_id] = share
        
        logger.debug(f"Generated coin share for day {day}, round {round_num}")
        return share

    async def compute_coin(self, day: int, round_num: int, shares: List[bytes]) -> int:
        """
        Compute common coin value from shares.
        
        Args:
            day: Day number
            round_num: Round number
            shares: List of signature shares
            
        Returns:
            Coin value (0 or 1)
        """
        if len(shares) < self.crypto.t:
            raise ValueError(f"Insufficient shares for coin: {len(shares)} < {self.crypto.t}")
            
        message = f"COIN_{day}_{round_num}".encode()
        
        # Aggregate signatures
        aggregated_sig = self.crypto.aggregate_signatures(shares)
        
        # Extract coin value from aggregated signature
        # Use LSB of hash of aggregated signature
        coin_hash = blake3_hash(aggregated_sig)
        coin_value = coin_hash[0] % 2
        
        epoch = day * 1000 + round_num
        self.coin_values[epoch] = coin_value
        
        logger.debug(f"Computed coin value {coin_value} for day {day}, round {round_num}")
        return coin_value

    def get_coin_value(self, day: int, round_num: int) -> Optional[int]:
        """Get computed coin value for a day and round."""
        epoch = day * 1000 + round_num
        return self.coin_values.get(epoch)
