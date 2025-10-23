from dataclasses import dataclass
from typing import List, Optional, Dict, Any

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
class DayProof(Event):
    """Represents a proof for a specific day number."""
    canonical_proof_hash: str
    day_number: int
    validator_quorum_sig: str

@dataclass
class MembershipChange(Event):
    """Represents a change in validator membership."""
    change_type: str  # e.g., "add", "remove"
    validator_pubkey: str
    effective_day: int
    quorum_sig: str

@dataclass
class APExportNotice(Event):
    """Represents a notice for exporting content to ActivityPub."""
    object_ref: str
    policy_hash: str

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
    enc_chunks: List[str]  # Encrypted erasure-coded fragments
    k: int  # Threshold parameter k
    n: int  # Total number of participants n

@dataclass
class EncShare(Message):
    """Encrypted payload share message."""
    enc_payload_share: str
    proposer_id: str
    chunk_index: int

@dataclass
class CoinShare(Message):
    """Common Coin share message."""
    coin_sig_share: str
    proposer_id: str

@dataclass
class Commit(Message):
    """Commit message for an epoch block."""
    block_digest: str
    quorum_cert: str

@dataclass
class MembershipChangeMessage(Message):
    """Message for propagating membership changes."""
    update: MembershipChange
    quorum_cert: str
