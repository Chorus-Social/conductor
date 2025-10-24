from dataclasses import dataclass
from typing import List, Optional, Dict, Any

# --- Exceptions ---
class ConsensusError(Exception):
    """Custom exception for consensus-related errors."""
    pass

# --- Event Data Models ---

@dataclass
class Event:
    """Base class for all events in the Conductor network."""
    creation_day: int
    sig: str  # Ed25519 signature

@dataclass
class PostAnnounce(Event):
    """Represents an announcement of a new post."""
    content_cid: str
    author_pubkey_hash: str
    community_id: str

@dataclass
class ModerationEvent(Event):
    """Represents a moderation action."""
    target_ref: str
    action: str
    reason_hash: str

@dataclass
class UserRegistration(Event):
    """Represents a new user registration."""
    user_pubkey: str
    registration_day: int
    day_proof_hash: str

@dataclass
class DayProof:
    """Represents a computed day proof as per CFP-001 Proof Object."""
    day_number: int
    proof: bytes

    validator_id: bytes
    signature: bytes
    quorum_cert: Optional[QuorumCertificate] = None # Quorum certificate for this day proof

@dataclass
class MembershipChange(Event):
    """Represents a change in validator membership."""
    change_type: str  # e.g., "add", "remove"
    validator_pubkey: str
    effective_day: int
    quorum_sig: str

@dataclass
class ThresholdSignature:
    """Represents a threshold signature, including individual shares and the aggregated signature."""
    epoch: int
    signer_id: str
    signature_share: str # Individual share of the signature
    aggregated_signature: Optional[str] = None # The combined signature once enough shares are collected

@dataclass
class EncryptedShare:
    """Represents a single encrypted share of a payload."""
    share_id: int
    data: str # The encrypted data for this share
    # In a real implementation, this would also include metadata like encryption key info, etc.

@dataclass
class APExportNotice(Event):
    """Represents a notice for exporting content to ActivityPub."""
    object_ref: str
    policy_hash: str

@dataclass
class EventBatch:
    """Placeholder for a batch of events received via gRPC."""
    events: List[Event]

# --- Message Types ---

@dataclass
class Message:
    """Base class for all messages exchanged in the Conductor network."""
    epoch: int

@dataclass
class RBCPropose(Message):
    """Reliable Broadcast Propose message."""
    proposer_id: str
    payload_hash: str
    enc_chunks: List[EncryptedShare]  # Encrypted erasure-coded fragments
    k: int  # Threshold parameter k
    n: int  # Total number of participants n

@dataclass
class EncShare(Message):
    """Encrypted payload share message."""
    enc_payload_share: EncryptedShare
    proposer_id: str
    chunk_index: int

@dataclass
class CoinShare(Message):
    """Common Coin share message."""
    coin_sig_share: ThresholdSignature
    proposer_id: str

@dataclass
class Commit(Message):
    """Commit message for an epoch block."""
    block_digest: str
    quorum_cert: str

@dataclass
class QuorumCertificate:
    """Represents a cryptographic quorum certificate for a block or day proof."""
    epoch_or_day: int
    payload_hash: str # Hash of the data being certified (e.g., block hash, day proof hash)
    signatures: Dict[str, str] # Dictionary of validator_id -> signature_share
    aggregated_signature: Optional[str] = None # The combined signature once enough shares are collected

@dataclass
class MembershipChangeMessage(Message):
    """Message for propagating membership changes."""
    update: MembershipChange
    quorum_cert: str

@dataclass
class BlacklistVote(Message):
    """Represents a vote to blacklist a validator."""
    voter_id: str
    target_validator_id: str
    reason: str
    # In a real implementation, this would include a signature from the voter.
