import asyncio
import json
import logging
import pickle
import time
from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Set

import nacl.signing
import lmdb
import grpc.aio # Added
import concurrent.futures # Added
import random # Added

import conductor_pb2
import conductor_pb2_grpc

from conductor.vdf import (
    GENESIS_SEED,
    GENESIS_TIMESTAMP,
    SECONDS_PER_DAY,
    VDF_ITERATIONS_PER_DAY,
    ChorusVDF,
)

from conductor.models import (
    APExportNotice,
    CoinShare,
    Commit,
    ConsensusError,
    DayProof,
    EncShare,
    Event,
    MembershipChange,
    MembershipChangeMessage,
    Message,
    ModerationEvent,
    PostAnnounce,
    RBCPropose,
    UserRegistration,
    EventBatch,
    BlacklistVote,
    QuorumCertificate,
)
from conductor.config import Config, load_config # Added
from conductor.hashing import blake3_hash
from conductor.crypto import ThresholdCrypto # Added

# Setup logging
logger = logging.getLogger(__name__)

# --- Storage Layer ---
class ValidatorStorage:
    """Persistent storage for validator node using LMDB."""

    def __init__(self, path: str):
        # max_dbs=0 means no named databases are supported, use the default unnamed database.
        self.env = lmdb.open(path, map_size=10*1024*1024*1024, max_dbs=0, sync=True)
        logger.info(f"Initialized LMDB at {path}")

    async def save_proof(self, proof: DayProof):
        """Store proof in local database."""
        key = f"proof:day:{proof.day_number}".encode()
        value = self._serialize(proof)
        with self.env.begin(write=True) as txn:
            txn.put(key, value)
        logger.debug(f"Saved proof for day {proof.day_number}")

    async def get_proof(self, day_number: int) -> Optional[DayProof]:
        """Retrieve proof from local database."""
        key = f"proof:day:{day_number}".encode()
        with self.env.begin() as txn:
            value = txn.get(key)
        if value:
            logger.debug(f"Retrieved proof for day {day_number}")
            return self._deserialize(value)
        logger.debug(f"No proof found for day {day_number}")
        return None

    async def has_proof(self, day_number: int) -> bool:
        """Check if proof exists locally."""
        key = f"proof:day:{proof.day_number}".encode()
        with self.env.begin() as txn:
            return txn.get(key) is not None

    def _serialize(self, proof: DayProof) -> bytes:
        """Serialize proof for storage."""
        return pickle.dumps(proof)

    def _deserialize(self, data: bytes) -> DayProof:
        """Deserialize proof from storage."""
        return pickle.loads(data)


# --- DHT Network Layer (Placeholder) ---
class DHTNetwork:
    """Distributed Hash Table for proof storage and discovery (Simulated)."""

    def __init__(self, bootstrap_peers: List[str], keypair: tuple, validator_node_instance: "ValidatorNode" = None, peers: List["DHTNetwork"] = None):
        self.bootstrap_peers = bootstrap_peers
        self.keypair = keypair
        self.validator_node_instance = validator_node_instance # Store the ValidatorNode instance
        self.node = None
        self.peers = peers if peers is not None else [] # References to other DHTNetwork instances

        # Instance-level storage for proofs and completion times
        self._proofs: Dict[int, Dict[bytes, DayProof]] = defaultdict(dict) # day_number -> validator_id (pubkey bytes) -> DayProof
        self._canonical_proofs: Dict[int, DayProof] = {}
        self._vdf_completion_times: Dict[int, Dict[bytes, float]] = defaultdict(dict) # day_number -> validator_id (pubkey bytes) -> completion_time_seconds

        logger.info(f"Initialized DHTNetwork with {len(bootstrap_peers)} bootstrap peers and {len(self.peers)} simulated peers")
        self.bootstrap_peers = bootstrap_peers
        self.keypair = keypair
        self.node = None
        logger.info(f"Initialized DHTNetwork with {len(bootstrap_peers)} bootstrap peers")

    async def initialize(self):
        """Initialize the simulated DHT network."""
        logger.info("DHT network initialized (simulated).")
        await asyncio.sleep(0.1)  # Simulate async operation
        self.node = True  # Simulate node being initialized

    async def publish_proof(self, proof: DayProof):
        """Publish day proof to DHT (Simulated)."""
        logger.info(f"Publishing proof for day {proof.day_number} from {proof.validator_id.hex()} to DHT (simulated)...")
        self._proofs[proof.day_number][proof.validator_id] = proof # Store locally
        for peer in self.peers:
            await peer.handle_published_proof(proof)
        await asyncio.sleep(0.05)  # Simulate async operation

    async def fetch_proof(self, day_number: int) -> Optional[DayProof]:
        """Fetch canonical proof for a specific day (Simulated)."""
        logger.info(f"Fetching canonical proof for day {day_number} from DHT (simulated)...")
        # Try local store first
        local_proof = self._canonical_proofs.get(day_number)
        if local_proof:
            return local_proof

        # If not found locally, ask peers
        for peer in self.peers:
            peer_proof = await peer.get_canonical_proof(day_number)
            if peer_proof:
                self._canonical_proofs[day_number] = peer_proof # Store locally for future use
                return peer_proof
        await asyncio.sleep(0.05)  # Simulate async operation
        return None

    async def collect_peer_proofs(self, day_number: int, local_proof: DayProof, timeout: int = 120) -> List[DayProof]:
        """Collect proofs from all available validators (Simulated)."""
        logger.info(f"Collecting peer proofs for day {day_number} from DHT (simulated)...")
        await asyncio.sleep(0.05)  # Simulate async operation

        all_proofs_for_day = {local_proof.validator_id: local_proof} # Start with local proof

        # Collect proofs from local store
        for validator_id, proof in self._proofs[day_number].items():
            all_proofs_for_day[validator_id] = proof

        # Collect proofs from peers
        for peer in self.peers:
            peer_proofs = await peer.get_proof_for_day(day_number)
            for validator_id, proof in peer_proofs.items():
                all_proofs_for_day[validator_id] = proof

        return list(all_proofs_for_day.values())

    async def publish_canonical_proof(self, canonical_proof: DayProof, day_number: int):
        """Publish canonical proof to DHT (Simulated)."""
        logger.info(f"Publishing canonical proof for day {day_number} from {canonical_proof.validator_id.hex()} to DHT (simulated)...")
        self._canonical_proofs[day_number] = canonical_proof # Store locally
        for peer in self.peers:
            await peer.handle_canonical_proof(canonical_proof, day_number)
        await asyncio.sleep(0.05)  # Simulate async operation

    async def publish_vdf_completion_time(self, day_number: int, validator_id: bytes, completion_time_seconds: float):
        """Publish VDF completion time to DHT (Simulated)."""
        logger.info(f"Publishing VDF completion time for day {day_number} from {validator_id.hex()}: {completion_time_seconds:.2f}s (simulated)...")
        self._vdf_completion_times[day_number][validator_id] = completion_time_seconds
        for peer in self.peers:
            await peer.handle_vdf_completion_time(day_number, validator_id, completion_time_seconds)
        await asyncio.sleep(0.05)  # Simulate async operation

    async def handle_published_proof(self, proof: DayProof):
        """Handle a published proof from a peer."""
        self._proofs[proof.day_number][proof.validator_id] = proof
        logger.debug(f"Received published proof for day {proof.day_number} from {proof.validator_id.hex()} from peer.")

    async def handle_canonical_proof(self, canonical_proof: DayProof, day_number: int):
        """Handle a canonical proof from a peer."""
        self._canonical_proofs[day_number] = canonical_proof
        logger.debug(f"Received canonical proof for day {day_number} from peer.")

    async def handle_vdf_completion_time(self, day_number: int, validator_id: bytes, completion_time_seconds: float):
        """Handle a VDF completion time from a peer."""
        self._vdf_completion_times[day_number][validator_id] = completion_time_seconds
        logger.debug(f"Received VDF completion time for day {day_number} from {validator_id.hex()} from peer.")

    async def get_canonical_proof(self, day_number: int) -> Optional[DayProof]:
        """Get canonical proof for a specific day from local store."""
        return self._canonical_proofs.get(day_number)

    async def get_proof_for_day(self, day_number: int) -> Dict[bytes, DayProof]:
        """Get all proofs for a specific day from local store."""
        return self._proofs[day_number]

    async def publish_enc_share(self, enc_share_message: EncShare):
        """Publish an EncShare message to peers (Simulated)."""
        logger.debug(f"Publishing EncShare for epoch {enc_share_message.epoch} from {enc_share_message.proposer_id} to DHT (simulated)...")
        for peer in self.peers:
            await peer.handle_enc_share_from_peer(enc_share_message)
        await asyncio.sleep(0.05) # Simulate network delay

    async def handle_enc_share_from_peer(self, enc_share_message: EncShare):
        """Handle an EncShare message received from a peer."""
        if self.validator_node_instance:
            await self.validator_node_instance.consensus.handle_rbc_enc_share(enc_share_message)
        else:
            logger.debug(f"Received EncShare for epoch {enc_share_message.epoch} from {enc_share_message.proposer_id} from peer, but no ValidatorNode instance is set.")

    async def publish_blacklist_vote(self, blacklist_vote: BlacklistVote):
        """Publish a BlacklistVote message to peers (Simulated)."""
        logger.debug(f"Publishing BlacklistVote for {blacklist_vote.target_validator_id} from {blacklist_vote.voter_id} to DHT (simulated)...")
        for peer in self.peers:
            # In a real system, this would involve sending the message over the network.
            # For simulation, we directly call the peer's consensus module.
            if peer.validator_node_instance:
                await peer.validator_node_instance.consensus.handle_blacklist_vote(blacklist_vote)
        await asyncio.sleep(0.05) # Simulate network delay


# --- Consensus Module ---
class ConsensusModule:
    """Manages the BFT consensus protocol for the Chorus network."""



    def __init__(self, config: Config, validator_id: str, validators: List[str]):
        """Initializes the ConsensusModule instance."""
        self.config = config
        self.validator_id = validator_id
        self.validators = validators
        self.current_epoch = 0
        self.event_log: List[Event] = []
        self.committed_blocks: Dict[int, Any] = {}
        self.proposals: Dict[int, Dict[str, RBCPropose]] = defaultdict(dict)  # Stores RBCPropose messages by epoch and proposer_id
        self.received_enc_chunks: Dict[int, Dict[str, Dict[int, str]]] = defaultdict(lambda: defaultdict(dict))  # epoch -> proposer_id -> chunk_index -> chunk_value
        self.reconstructed_payloads: Dict[int, Dict[str, str]] = defaultdict(dict)  # epoch -> proposer_id -> reconstructed_payload_hash

        # Simulated Common Coin state
        self.coin_shares: Dict[int, Dict[str, str]] = defaultdict(dict)  # epoch -> proposer_id -> coin share
        self.common_coin_value: Dict[int, Optional[str]] = defaultdict(lambda: None)  # epoch -> common coin value
        self.coin_threshold = self.config.validator.consensus.min_validators // 3 * 2 + 1  # 2f+1 for common coin
        self._blacklisted_validators: Set[str] = set() # Stores IDs of blacklisted validators
        self._blacklist_votes: Dict[str, Set[str]] = defaultdict(set) # target_validator_id -> set of voter_ids
        self.threshold_crypto = ThresholdCrypto(n=len(self.validators), t=self.coin_threshold) # Initialize ThresholdCrypto

        # VDF and Day Counter state (Note: VDF is managed by ValidatorNode, not ConsensusModule directly)
        self.day_proofs: Dict[int, Dict[bytes, DayProof]] = defaultdict(dict)  # day_number -> validator_id (pubkey bytes) -> DayProof
        logger.info("Initialized ConsensusModule")

    async def propose_batch(self, event_hashes: List[str], dht_network: "DHTNetwork") -> None:
        """Proposes a batch of event hashes for consensus in the current epoch."""
        self.logger.info(f"Validator {self.validator_id} proposing batch for epoch {self.current_epoch} with {len(event_hashes)} events.")

        # In a real implementation, these event_hashes would correspond to actual events
        # that have been received and validated by the Bridge.
        # For now, we'll treat the list of hashes as the payload.
        payload_hash = blake3_hash(str(event_hashes)) # Hash of the list of event hashes

        # Simulate erasure coding and threshold encryption
        # In a real implementation, this would involve complex cryptographic operations.
        # For now, we generate dummy encrypted chunks and a dummy coin share.
        k = len(self.validators) // 3 + 1  # Minimum for BFT
        n = len(self.validators)
        # Generate dummy EncryptedShare objects
        encrypted_batch_chunks = [EncryptedShare(share_id=i, data=f"enc_chunk_{i}_of_{payload_hash}") for i in range(n)]
        coin_share_value = ThresholdSignature(epoch=self.current_epoch, signer_id=self.validator_id, signature_share=f"coin_share_for_{self.current_epoch}_from_{self.validator_id}") # Dummy coin share

        rbc_propose_message = RBCPropose(
            epoch=self.current_epoch,
            proposer_id=self.validator_id,
            payload_hash=payload_hash,
            enc_chunks=encrypted_batch_chunks,
            k=k,
            n=n
        )

        await self.handle_rbc_propose(rbc_propose_message)

        # Publish each encrypted chunk as an EncShare message concurrently
        publish_tasks = []
        for i, chunk in enumerate(encrypted_batch_chunks):
            enc_share_message = EncShare(
                epoch=self.current_epoch,
                proposer_id=self.validator_id,
                chunk_index=i,
                enc_payload_share=chunk
            )
            publish_tasks.append(dht_network.publish_enc_share(enc_share_message))
        await asyncio.gather(*publish_tasks)

        coin_share_message = CoinShare(
            epoch=self.current_epoch,
            coin_sig_share=coin_share_value,
            proposer_id=self.validator_id
        )
        await self.handle_coin_share(coin_share_message)

    async def handle_rbc_propose(self, message: RBCPropose) -> None:
        """Handles an RBC_PROPOSE message from another validator."""
        logger.debug(f"Handling RBC_PROPOSE from {message.proposer_id} for epoch {message.epoch}. Received {len(message.enc_chunks)} encrypted chunks.")
        self.proposals[message.epoch][message.proposer_id] = message
        self.reconstructed_payloads[message.epoch][message.proposer_id] = message.payload_hash

        # Simulate requesting EncShare messages from other validators concurrently
        handle_enc_share_tasks = []
        for i, enc_share_data in enumerate(message.enc_chunks):
            enc_share_message = EncShare(
                epoch=message.epoch,
                proposer_id=message.proposer_id,
                chunk_index=i,
                enc_payload_share=enc_share_data
            )
            handle_enc_share_tasks.append(self.handle_enc_share(enc_share_message))
        await asyncio.gather(*handle_enc_share_tasks)

        if self._is_rbc_complete(message.epoch, message.proposer_id):
            logger.debug(f"RBC for epoch {message.epoch}, proposer {message.proposer_id} is complete.")

    async def handle_enc_share(self, message: EncShare) -> None:
        """Handles an ENC_SHARE message from another validator."""
        logger.debug(f"Handling ENC_SHARE from {message.proposer_id} for epoch {message.epoch}, chunk {message.chunk_index}. Encrypted share: {message.enc_payload_share}")
        self.received_enc_chunks[message.epoch][message.proposer_id][message.chunk_index] = message.enc_payload_share.data

        if self._is_rbc_complete(message.epoch, message.proposer_id):
            self.logger.debug(f"Enough ENC_SHAREs collected for epoch {message.epoch}, proposer {message.proposer_id}. Simulating decryption.")
            # In a real implementation, this would involve using threshold decryption
            # to reconstruct the original payload from the collected shares.
            # For now, we'll assume successful reconstruction and store the payload hash.
            # The actual payload would be reconstructed here.
            self.reconstructed_payloads[message.epoch][message.proposer_id] = self.proposals[message.epoch][message.proposer_id].payload_hash

    def _is_rbc_complete(self, epoch: int, proposer_id: str) -> bool:
        """Checks if Reliable Broadcast is complete for a given proposer in an epoch."""
        if epoch not in self.proposals or proposer_id not in self.proposals[epoch]:
            return False

        expected_chunks_count = self.proposals[epoch][proposer_id].n
        received_chunks_count = len(self.received_enc_chunks[epoch][proposer_id])

        return received_chunks_count >= expected_chunks_count

    async def handle_coin_share(self, message: CoinShare) -> None:
        """Handles a COIN_SHARE message from another validator."""
        self.logger.debug(f"Handling COIN_SHARE for epoch {message.epoch} from {message.proposer_id}")
        self.coin_shares[message.epoch][message.proposer_id] = message.coin_sig_share.signature_share

        if len(self.coin_shares[message.epoch]) >= self.coin_threshold: # Use config for threshold
            if self.common_coin_value[message.epoch] is None:
                # In a real implementation, we would derive the common coin from collected shares
                # using a verifiable random function or threshold signatures.
                # For now, we'll just log that we have enough shares and simulate derivation.
                self.logger.info(f"Enough coin shares collected for epoch {message.epoch}. Simulating common coin derivation.")
                # The common coin value should be deterministic based on the collected shares
                self.common_coin_value[message.epoch] = blake3_hash(str(sorted(self.coin_shares[message.epoch].values()))) # Simulated derivation

    async def handle_rbc_enc_share(self, enc_share_message: EncShare):
        """Handles an EncShare message received from the DHTNetwork and passes it to the internal handler."""
        await self.handle_enc_share(enc_share_message)

    async def handle_commit(self, message: Commit) -> None:
        """Handles a COMMIT message, finalizing an epoch block."""
        self.logger.info(f"Handling COMMIT for epoch {message.epoch}")
        if message.epoch in self.proposals:
            epoch_proposals = self.proposals[message.epoch]

            # In a real implementation, we would decrypt the batch here
            # and verify its content against the payload_hash.
            self.logger.debug(f"Simulating decryption and verification of batch for epoch {message.epoch}.")
            # For now, we'll assume any proposal that completed RBC is valid.
            valid_proposals = []
            for proposer_id, rbc_propose in epoch_proposals.items():
                # Check if RBC is complete for this proposer
                if self._is_rbc_complete(message.epoch, proposer_id):
                    valid_proposals.append(rbc_propose)

            # Use the common coin to deterministically order the proposals
            if self.common_coin_value[message.epoch]:
                # Sort validators based on their hash with the common coin
                def sort_key(proposer_id):
                    return blake3_hash(f"{self.common_coin_value[message.epoch]}{proposer_id}")
                
                # Filter valid proposals to only include those from validators that are part of the current epoch's consensus
                # and sort them deterministically using the common coin
                ordered_proposals = await asyncio.to_thread(lambda: sorted(
                    [p for p in valid_proposals if p.proposer_id in self.validators],
                    key=lambda p: sort_key(p.proposer_id)
                ))
            else:
                # Fallback to a simple sort if common coin is not available (should not happen in a healthy network)
                self.logger.warning(f"Common coin not available for epoch {message.epoch}. Falling back to simple sort.")
                ordered_proposals = await asyncio.to_thread(lambda: sorted(
                    valid_proposals,
                    key=lambda p: (p.proposer_id, p.payload_hash)
                ))

            self.logger.debug(f"Ordered proposals for epoch {message.epoch}: {[p.proposer_id for p in ordered_proposals]}")

            # The block_content_hash should be a hash of the *decrypted* and ordered events.
            # For now, we'll hash the payload_hashes from the proposals.
            block_content_hash = blake3_hash([p.payload_hash for p in ordered_proposals])

            self.committed_blocks[message.epoch] = {
                "block_digest": block_content_hash,
                "proposals": [asdict(p) for p in ordered_proposals],
                "common_coin": self.common_coin_value[message.epoch]
            }
            self.logger.info(f"Committed block for epoch {message.epoch} with digest {block_content_hash}")

            self.logger.info(f"Simulating ActivityPub export callback for epoch {message.epoch} with committed events.")

        await self.advance_epoch()

    async def handle_day_proof(self, day_proof: DayProof) -> None:
        """Handles a DayProof event from another validator."""
        self.logger.debug(f"Handling DayProof for day {day_proof.day_number} from {day_proof.validator_id.hex()}")

        # This method is primarily for the ConsensusModule to track proofs from other validators.
        # Actual VDF verification happens in ValidatorNode.
        # Here, we just store the proof if it's considered valid by the ValidatorNode.
        self.day_proofs[day_proof.day_number][day_proof.validator_id] = day_proof
        self.logger.debug(f"Stored DayProof for day {day_proof.day_number} from {day_proof.validator_id.hex()}")

    async def handle_membership_change(self, message: MembershipChangeMessage) -> None:
        """Handles a MEMBERSHIP_CHANGE message."""
        self.logger.info(f"Handling MEMBERSHIP_CHANGE for epoch {message.epoch}")
        membership_change_event: MembershipChange = message.update
        if membership_change_event.change_type == "add":
            if membership_change_event.validator_pubkey not in self.validators:
                self.validators.append(membership_change_event.validator_pubkey)
                self.logger.info(f"Validator {membership_change_event.validator_pubkey} added to membership.")
        elif membership_change_event.change_type == "remove":
            if membership_change_event.validator_pubkey in self.validators:
                self.validators.remove(membership_change_event.validator_pubkey)
                self.logger.info(f"Validator {membership_change_event.validator_pubkey} removed from membership.")
        self.logger.debug(f"Current validators: {self.validators}")

    async def advance_epoch(self) -> None:
        """Advances the Conductor to the next epoch (day number)."""
        self.current_epoch += 1
        self.logger.info(f"Advanced to epoch {self.current_epoch}")

    async def _manage_blacklist(self):
        """Placeholder for managing the blacklist (detecting and voting on malicious nodes)."""
        self.logger.info("Placeholder: Performing blacklist management. (Future implementation will include evidence collection and BFT voting).")
        await self._detect_malicious_behavior(self.dht)

    async def _detect_malicious_behavior(self, dht_network: "DHTNetwork"):
        """Placeholder for detecting malicious behavior and initiating a voting process."""
        self.logger.debug("Placeholder: Detecting malicious behavior.")
        # In a real implementation, this would involve monitoring validator behavior,
        # verifying proofs, and identifying deviations from the protocol.
        # For simulation, let's assume a random validator (not self) is detected as malicious.
        other_validators = [v for v in self.validators if v != self.validator_id and v not in self._blacklisted_validators]
        if other_validators:
            malicious_validator = random.choice(other_validators)
            self.logger.warning(f"Simulated detection: Validator {malicious_validator} is behaving maliciously. Initiating blacklist vote.")

            # Create a blacklist vote message
            blacklist_vote = BlacklistVote(
                epoch=self.current_epoch, # Or a specific epoch related to the malicious act
                voter_id=self.validator_id,
                target_validator_id=malicious_validator,
                reason="Simulated malicious behavior (e.g., invalid proof, non-participation)"
            )
            # Simulate sending this vote to all other validators (including self for local processing)
            # In a real system, this would be broadcast over the DHT.
            await dht_network.publish_blacklist_vote(blacklist_vote)

    async def handle_blacklist_vote(self, message: BlacklistVote):
        """Handles a blacklist vote message from another validator."""
        self.logger.info(f"Received blacklist vote from {message.voter_id} against {message.target_validator_id} for reason: {message.reason}")
        self._blacklist_votes[message.target_validator_id].add(message.voter_id)

        # Check if enough votes have been collected to blacklist the validator
        if len(self._blacklist_votes[message.target_validator_id]) >= self.coin_threshold:
            if message.target_validator_id not in self._blacklisted_validators:
                self.logger.warning(f"Validator {message.target_validator_id} has been blacklisted by supermajority vote.")
                self._blacklisted_validators.add(message.target_validator_id)
                # Remove from active validators if present
                if message.target_validator_id in self.validators:
                    self.validators.remove(message.target_validator_id)
                # Clear votes for this validator
                del self._blacklist_votes[message.target_validator_id]

    def _serialize_events(self, events: List[Event]) -> List[Dict[str, Any]]:
        """Serializes a list of Event objects into a list of dictionaries."""
        return [asdict(event) for event in events]

    def _simulate_encrypt_batch(self, batch: List[Dict[str, Any]], key: str) -> List[EncryptedShare]:
        """Simulates threshold encryption of a batch.
        In a real implementation, this would involve using a threshold encryption scheme
        to encrypt the batch and generate 'n' shares, where 'k' shares are needed for decryption.
        """
        self.logger.debug(f"Simulating encryption of batch with key: {key}")
        batch_hash = blake3_hash(str(batch)) # Hash of the batch content
        # Generate dummy EncryptedShare objects
        return [EncryptedShare(share_id=i, data=f"enc_share_{batch_hash}_{i}") for i in range(len(self.validators))]

    def _simulate_decrypt_batch(self, shares: List[EncryptedShare], key: str) -> List[Dict[str, Any]]:
        """Simulates threshold decryption of a batch.
        In a real implementation, this would involve collecting 'k' (threshold) shares
        and using a threshold decryption scheme to reconstruct the original batch.
        """
        self.logger.debug(f"Simulating decryption with {len(shares)} shares and key: {key}")
        # For now, we just return a dummy decrypted event.
        return [{"simulated_decrypted_event": "data"}]

    def _generate_quorum_certificate(self, epoch_or_day: int, payload_hash: str, signatures: Dict[str, str]) -> QuorumCertificate:
        """Simulates the generation of a Quorum Certificate.
        In a real implementation, this would involve aggregating individual signatures
        from a supermajority of validators into a single, verifiable quorum certificate.
        """
        self.logger.debug(f"Simulating Quorum Certificate generation for epoch/day {epoch_or_day}")
        # For now, we just create a dummy aggregated signature.
        aggregated_signature = blake3_hash(str(sorted(signatures.items()))) if signatures else ""
        return QuorumCertificate(
            epoch_or_day=epoch_or_day,
            payload_hash=payload_hash,
            signatures=signatures,
            aggregated_signature=aggregated_signature
        )

    def _verify_quorum_certificate(self, qc: QuorumCertificate) -> bool:
        """Simulates the verification of a Quorum Certificate.
        In a real implementation, this would involve verifying the aggregated signature
        against the payload hash and ensuring it was signed by a supermajority of valid validators.
        """
        self.logger.debug(f"Simulating Quorum Certificate verification for epoch/day {qc.epoch_or_day}")
        # For now, we just check if there are enough signatures (simulated supermajority).
        return len(qc.signatures) >= self.coin_threshold

    def _verify_signature(self, proof: DayProof) -> bool:
        """Verifies the Ed25519 signature of a DayProof object."""
        try:
            verify_key = nacl.signing.VerifyKey(proof.validator_id)
            # The signed message is the proof bytes itself
            verify_key.verify(proof.proof, proof.signature)
            return True
        except nacl.exceptions.BadSignatureError:
            self.logger.warning(f"Bad signature for proof from {proof.validator_id.hex()} for day {proof.day_number}")
            return False
        except Exception as e:
            self.logger.error(f"Error verifying signature for proof from {proof.validator_id.hex()}: {e}")
            return False

    async def reach_consensus(self, day_number: int, local_proof: DayProof, dht_network: "DHTNetwork", vdf_instance: ChorusVDF) -> DayProof:
        """
        Orchestrates the consensus process for a given day's proof.
        Collects proofs from peers, verifies them, and determines the canonical proof.
        """
        self.logger.info(f"Initiating consensus for day {day_number} with local proof from {local_proof.validator_id.hex()}")

        # Store our local proof
        self.day_proofs[day_number][local_proof.validator_id] = local_proof

        # Collect proofs from other validators via DHT
        # Pass local_proof to collect_peer_proofs as it now expects it.
        peer_proofs = await dht_network.collect_peer_proofs(day_number, local_proof)
        for proof in peer_proofs:
            if proof.validator_id not in self.day_proofs[day_number]:
                self.day_proofs[day_number][proof.validator_id] = proof
                self.logger.debug(f"Collected peer proof for day {day_number} from {proof.validator_id.hex()}")

        valid_proofs = []
        for proof in self.day_proofs[day_number].values():
            # Verify the VDF proof and the signature
            if vdf_instance.verify_day_proof(proof.day_number, proof.proof) and self._verify_signature(proof):
                # If a quorum certificate is present, verify it
                if proof.quorum_cert:
                    if self._verify_quorum_certificate(proof.quorum_cert):
                        valid_proofs.append(proof)
                    else:
                        self.logger.warning(f"Invalid quorum certificate for proof from {proof.validator_id.hex()} for day {day_number}. Ignoring.")
                else:
                    # For now, if no QC is present, we still consider it valid if VDF and signature are good.
                    # In a real system, a QC would likely be mandatory.
                    valid_proofs.append(proof)
            else:
                self.logger.warning(f"Invalid proof from {proof.validator_id.hex()} for day {day_number}. Ignoring.")

        # Simulate generating a quorum certificate for the canonical proof
        # In a real system, this would involve collecting signatures from a supermajority
        # of validators on the chosen canonical proof.
        if valid_proofs:
            # For simplicity, let's assume the first valid proof is chosen as canonical for now.
            # In a real system, a more robust selection mechanism would be used.
            canonical_proof = valid_proofs[0]

            # Collect simulated signatures for the canonical proof
            simulated_signatures = {p.validator_id.hex(): p.signature.hex() for p in valid_proofs}
            quorum_cert = self._generate_quorum_certificate(day_number, blake3_hash(canonical_proof.proof), simulated_signatures)
            canonical_proof.quorum_cert = quorum_cert
            return canonical_proof
        else:
            raise ConsensusError(f"Could not reach consensus for day {day_number}: No valid proofs found.")


# --- gRPC Service (Placeholder) ---
class ConductorService(conductor_pb2_grpc.ConductorServiceServicer):
    """gRPC service for Conductor."""

    def __init__(self, validator_node_instance: "ValidatorNode"):
        self.validator_node = validator_node_instance
        self.logger = logging.getLogger("ConductorService")

    async def SubmitEventBatch(self, request: conductor_pb2.SubmitEventBatchRequest, context) -> conductor_pb2.SubmitEventBatchResponse:
        self.logger.info(f"Received event batch with {len(request.events)} events for epoch {request.epoch}.")
        try:
            await self.validator_node.consensus.propose_batch(list(request.events), self.validator_node.dht)
            return conductor_pb2.SubmitEventBatchResponse(batch_id="placeholder_batch_id", status="pending")
        except ConsensusError as e:
            context.set_code(grpc.StatusCode.ABORTED)
            context.set_details(f"Consensus error during batch proposal: {e}")
            return conductor_pb2.SubmitEventBatchResponse(batch_id="", status="failed")
        except Exception as e:
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(f"Internal error during batch proposal: {e}")
            return conductor_pb2.SubmitEventBatchResponse(batch_id="", status="failed")

    async def GetBlock(self, request: conductor_pb2.GetBlockRequest, context) -> conductor_pb2.GetBlockResponse:
        self.logger.info(f"Received request for block {request.epoch}.")
        block = self.validator_node.consensus.committed_blocks.get(request.epoch)
        if block:
            return conductor_pb2.GetBlockResponse(
                epoch=block["epoch"],
                block_hash=block["block_digest"],
                merkle_root="placeholder_merkle_root", # Merkle root not yet implemented
                events=[p["payload_hash"] for p in block["proposals"]], # Assuming proposals contain payload_hash
                quorum_cert=block["quorum_cert"] if "quorum_cert" in block else "placeholder_quorum_cert"
            )
        else:
            context.set_code(grpc.StatusCode.NOT_FOUND)
            context.set_details(f"Block for epoch {request.epoch} not found.")
            return conductor_pb2.GetBlockResponse()

    async def GetDayProof(self, request: conductor_pb2.GetDayProofRequest, context) -> conductor_pb2.GetDayProofResponse:
        self.logger.info(f"Received request for day proof {request.day}.")
        day_proof = self.validator_node.dht._canonical_proofs.get(request.day)
        if day_proof:
            return conductor_pb2.GetDayProofResponse(
                day_number=day_proof.day_number,
                vdf_proof=day_proof.proof.hex(), # Convert bytes to hex string
                difficulty=self.validator_node.vdf.iterations, # Use current VDF difficulty
                quorum_cert=day_proof.quorum_cert.aggregated_signature if day_proof.quorum_cert else "" # Return aggregated signature if present
            )
        else:
            context.set_code(grpc.StatusCode.NOT_FOUND)
            context.set_details(f"Day proof for day {request.day} not found.")
            return conductor_pb2.GetDayProofResponse()

# --- Validator Node ---
class ValidatorNode:
    """Complete Chorus Federation Validator Node as per CFP-001."""

    def __init__(self,
                 config: Config,
                 validator_keypair: tuple,  # (private_key_bytes, public_key_bytes)
                 all_validator_ids: List[str]): # All validator public key hex strings in the simulated network
        self.config = config
        self.keypair = validator_keypair
        self.public_key = validator_keypair[1]
        self.bootstrap_peers = config.validator.network.bootstrap_peers
        self.storage = ValidatorStorage(config.validator.storage.path)
        self.vdf = ChorusVDF(GENESIS_SEED, iterations=config.validator.vdf.iterations)
        self.dht = DHTNetwork(self.bootstrap_peers, self.keypair, self) # Pass self (ValidatorNode instance)
        # Initialize ConsensusModule with the full list of validator IDs
        self.consensus = ConsensusModule(self.config, self.public_key.hex(), all_validator_ids)
        self._current_day = 0  # Initialize internal day counter
        self.logger = logging.getLogger(__name__) # Add logger instance
        self.logger.info("Initialized ValidatorNode")

    async def start(self):
        """Initialize and start validator node."""
        logger.info("Starting Chorus Validator Node...")

        await self.dht.initialize()
        await self._sync_historical_proofs()

        # Start gRPC server
        asyncio.create_task(self._start_grpc_server())

        asyncio.create_task(self._daily_computation_loop())

        logger.info("Validator node running")

    async def _daily_computation_loop(self):
        """Main loop: compute and reach consensus on day proofs."""
        while True:
            # Ensure we have a current day to work on.
            # This loop will continuously try to compute and finalize the current day's proof.
            # The self._current_day is advanced only after successful consensus.
            current_day_to_compute = self._current_day
            self.logger.info(f"Attempting to compute and finalize proof for day {current_day_to_compute}")

            try:
                start_time = time.monotonic()
                proof_bytes = await asyncio.to_thread(
                    self.vdf.compute_day_proof,
                    current_day_to_compute
                )
                end_time = time.monotonic()
                completion_time_seconds = end_time - start_time

                proof = DayProof(
                    day_number=current_day_to_compute,
                    proof=proof_bytes,
                    validator_id=self.public_key,
                    signature=self._sign_proof(proof_bytes)
                )

                await self.storage.save_proof(proof)
                await self.dht.publish_proof(proof)
                await self.dht.publish_vdf_completion_time(current_day_to_compute, self.public_key, completion_time_seconds)

                canonical = await self.consensus.reach_consensus(
                    current_day_to_compute,
                    proof,
                    self.dht,
                    self.vdf
                )

                if canonical.proof == proof.proof:
                    self.logger.info(f"✓ Our proof matches canonical for day {current_day_to_compute}. Advancing to next day.")
                    self._current_day += 1  # Increment internal day counter on successful consensus
                    await self._adjust_vdf_difficulty() # Call difficulty adjustment here
                    await self.consensus._manage_blacklist() # Add this line
                else:
                    self.logger.warning(f"✗ Our proof differs from canonical for day {current_day_to_compute}. Retrying for the same day.")
                    # If our proof differs, we don't advance the day. We will retry for the same day.
                    await asyncio.sleep(self.config.validator.consensus.timeout) # Wait before retrying

            except ConsensusError as e:
                self.logger.error(f"Consensus error for day {current_day_to_compute}: {e}. Retrying after delay.")
                await asyncio.sleep(self.config.validator.consensus.timeout) # Wait before retrying
            except Exception as e:
                self.logger.error(f"Unhandled error computing day proof for day {current_day_to_compute}: {e}. Retrying after delay. (More specific exception handling needed for production)")
                await asyncio.sleep(5) # Small delay before retrying

    def _sign_proof(self, proof: bytes) -> bytes:
        """Sign proof with validator's private key."""
        signing_key = nacl.signing.SigningKey(self.keypair[0])
        return signing_key.sign(proof).signature

    async def _sync_historical_proofs(self):
        """Download historical proofs from DHT and initialize _current_day."""
        self.logger.info("Syncing historical proofs...")

        # Try to fetch the latest canonical day from DHT
        latest_canonical_day = -1
        # In a real system, this would involve querying the DHT for the highest day number
        # For simulation, we can assume _canonical_proofs has the latest.
        if self.dht._canonical_proofs:
            latest_canonical_day = max(self.dht._canonical_proofs.keys())

        day_to_fetch = 0
        if latest_canonical_day >= 0:
            self.logger.info(f"Latest canonical day found on DHT: {latest_canonical_day}. Syncing backwards.")
            # Sync from the latest canonical day down to 0
            for day in range(latest_canonical_day, -1, -1):
                proof = await self.dht.fetch_proof(day)
                if proof:
                    await self.storage.save_proof(proof)
                    self.logger.info(f"Synced historical proof for day {day}")
                else:
                    self.logger.warning(f"No canonical proof found on DHT for day {day}. Stopping backward sync.")
                    break
            day_to_fetch = latest_canonical_day + 1 # Start computing from the next day
        else:
            self.logger.info("No canonical proofs found on DHT. Starting from day 0.")
            # If no canonical proofs are found, check local storage for the highest day
            highest_local_day = -1
            for day in range(0, 1000): # Arbitrary limit for initial sync, should be dynamic
                if await self.storage.has_proof(day):
                    highest_local_day = day
                else:
                    break # Stop if there's a gap in local proofs
            day_to_fetch = highest_local_day + 1

        self._current_day = day_to_fetch
        self.logger.info(f"Historical proof sync complete. Starting VDF computation from day {self._current_day}")

    

    async def _adjust_vdf_difficulty(self):
        """Dynamically adjusts VDF difficulty based on network conditions."""
        if self._current_day > 0 and self._current_day % self.config.validator.vdf.adjustment_interval_days == 0:
            self.logger.info(f"Day {self._current_day}: Initiating VDF difficulty adjustment.")

            # Collect VDF completion times from all validators for the previous day
            # In a real implementation, this would involve fetching actual completion times
            # and potentially a BFT consensus on the median.
            previous_day = self._current_day - 1
            completion_times = [t for t in self.dht._vdf_completion_times[previous_day].values() if t > 0]

            if completion_times:
                median_completion_seconds = sorted(completion_times)[len(completion_times) // 2]
                self.logger.info(f"Median VDF completion time for day {previous_day}: {median_completion_seconds:.2f}s")
            else:
                self.logger.warning(f"No VDF completion times available for day {previous_day}. Using simulated value.")
                median_completion_seconds = 23 * 3600 # Default to 23 hours if no data

            target_completion_seconds = SECONDS_PER_DAY # 24 hours

            if median_completion_seconds > 0:
                adjustment_factor = target_completion_seconds / median_completion_seconds
                new_iterations = int(self.vdf.iterations * adjustment_factor)
                
                self.vdf.iterations = new_iterations
                self.logger.info(f"VDF difficulty adjusted. New iterations: {self.vdf.iterations}")
            else:
                self.logger.warning("Median completion time is zero, skipping difficulty adjustment.")

    

        async def _start_grpc_server(self):
            """Starts the gRPC server for receiving event batches."""
            server = grpc.aio.server(concurrent.futures.ThreadPoolExecutor(max_workers=10))
            conductor_pb2_grpc.add_ConductorServiceServicer_to_server(ConductorService(self), server)
            server.add_insecure_port(f"[::]:{self.config.validator.network.listen_address.split(':')[1]}") # Use configured port
            self.logger.info(f"gRPC server listening on {self.config.validator.network.listen_address}")
            await server.start()
            await server.wait_for_termination()

    