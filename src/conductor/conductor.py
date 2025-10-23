from typing import List, Dict, Any, Optional
from dataclasses import asdict
from collections import defaultdict
import time

from conductor.hashing import blake3_hash
from conductor.vdf import ChorusVDF
from conductor.models import Event, Message, RBCPropose, EncShare, CoinShare, Commit, MembershipChangeMessage, DayProof

# Constants from CFP-001
GENESIS_SEED = b"chorus_mainnet_v1_genesis_20241023"
GENESIS_TIMESTAMP = 1729670400  # Oct 23, 2024 00:00:00 UTC
SECONDS_PER_DAY = 86400
VDF_ITERATIONS_PER_DAY = 86_400_000  # ~86 seconds on modern hardware

class Conductor:
    """Manages the BFT consensus protocol for the Chorus network."""

    def __init__(self, validator_id: str, validators: List[str]):
        """Initializes the Conductor instance.

        Args:
            validator_id: The unique identifier for this validator node.
            validators: A list of all validator IDs in the network.
        """
        self.validator_id = validator_id
        self.validators = validators
        self.current_epoch = 0
        self.event_log: List[Event] = []
        self.committed_blocks: Dict[int, Any] = {}
        self.proposals: Dict[int, Dict[str, RBCPropose]] = defaultdict(dict) # Stores RBCPropose messages by epoch and proposer_id
        self.received_enc_chunks: Dict[int, Dict[str, Dict[int, str]]] = defaultdict(lambda: defaultdict(dict)) # epoch -> proposer_id -> chunk_index -> chunk_value
        self.reconstructed_payloads: Dict[int, Dict[str, str]] = defaultdict(dict) # epoch -> proposer_id -> reconstructed_payload_hash
        
        # Simulated Threshold Encryption state
        self.threshold_encryption_key: str = "dummy_threshold_key" # Placeholder
        self.encrypted_shares: Dict[int, Dict[str, List[str]]] = defaultdict(lambda: defaultdict(list)) # epoch -> proposer_id -> list of shares
        self.decrypted_batches: Dict[int, Dict[str, Any]] = defaultdict(dict) # epoch -> proposer_id -> decrypted batch
        self.encryption_threshold = len(self.validators) // 3 * 2 + 1 # 2f+1 for decryption

        # Simulated Common Coin state
        self.coin_shares: Dict[int, Dict[str, str]] = defaultdict(dict) # epoch -> proposer_id -> coin share
        self.common_coin_value: Dict[int, Optional[str]] = defaultdict(lambda: None) # epoch -> common coin value
        self.coin_threshold = len(self.validators) // 3 * 2 + 1 # 2f+1 for common coin

        # VDF and Day Counter state
        self.vdf = ChorusVDF(GENESIS_SEED)
        self.vdf_iterations: int = VDF_ITERATIONS_PER_DAY # Use the constant from CFP-001
        self.day_proofs: Dict[int, Dict[str, DayProof]] = defaultdict(dict) # epoch -> validator_id -> DayProof

    async def propose_batch(self, events: List[Event]) -> None:
        """Proposes a batch of events for consensus in the current epoch.

        Args:
            events: A list of events to be batched and proposed.
        """
        print(f"Validator {self.validator_id} proposing batch for epoch {self.current_epoch}")
        
        # Phase 1: Local batching
        serialized_batch = self._serialize_events(events)
        payload_hash = blake3_hash(serialized_batch)

        # Phase 2: Simulate Threshold Encryption
        # In a real scenario, this would involve actual cryptographic operations
        # For simulation, we'll just use the payload_hash as the 'encrypted' data
        # and distribute it as chunks.
        encrypted_batch_chunks = [f"{payload_hash}_chunk_{i}" for i in range(len(self.validators))]

        k = len(self.validators) // 3 + 1 # Minimum for BFT
        n = len(self.validators)

        rbc_propose_message = RBCPropose(
            epoch=self.current_epoch,
            proposer_id=self.validator_id,
            payload_hash=payload_hash,
            enc_chunks=encrypted_batch_chunks,
            k=k,
            n=n
        )
        
        # Simulate sending to other validators (for now, just process locally)
        await self.handle_rbc_propose(rbc_propose_message)

        # Simulate sending ENC_SHARE messages
        for i, chunk in enumerate(encrypted_batch_chunks):
            enc_share_message = EncShare(
                epoch=self.current_epoch,
                enc_payload_share=chunk,
                proposer_id=self.validator_id,
                chunk_index=i
            )
            # Simulate sending to other validators (for now, just process locally)
            await self.handle_enc_share(enc_share_message)

        # Simulate sending COIN_SHARE messages
        coin_share_value = self._simulate_generate_coin_share(self.current_epoch, self.validator_id)
        coin_share_message = CoinShare(
            epoch=self.current_epoch,
            coin_sig_share=coin_share_value,
            proposer_id=self.validator_id
        )
        await self.handle_coin_share(coin_share_message)

    async def handle_rbc_propose(self, message: RBCPropose) -> None:
        """Handles an RBC_PROPOSE message from another validator.

        Args:
            message: The RBCPropose message received.
        """
        print(f"Validator {self.validator_id} handling RBC_PROPOSE from {message.proposer_id} for epoch {message.epoch} with payload hash {message.payload_hash}")
        self.proposals[message.epoch][message.proposer_id] = message
        # Store the expected payload hash for later reconstruction verification
        self.reconstructed_payloads[message.epoch][message.proposer_id] = message.payload_hash
        
        # Check if RBC is complete for this proposer
        if self._is_rbc_complete(message.epoch, message.proposer_id):
            print(f"RBC for epoch {message.epoch}, proposer {message.proposer_id} is complete.")
            # Trigger further processing, e.g., threshold decryption

    async def handle_enc_share(self, message: EncShare) -> None:
        """Handles an ENC_SHARE message from another validator.

        Args:
            message: The EncShare message received.
        """
        print(f"Validator {self.validator_id} handling ENC_SHARE from {message.proposer_id} for epoch {message.epoch}, chunk {message.chunk_index}")
        self.received_enc_chunks[message.epoch][message.proposer_id][message.chunk_index] = message.enc_payload_share

        # Check if we have enough chunks to reconstruct the payload (simulated)
        if self._is_rbc_complete(message.epoch, message.proposer_id):
            if message.proposer_id not in self.decrypted_batches[message.epoch]:
                # Simulate reconstruction and decryption
                reconstructed_payload = self._simulate_reconstruct_payload(
                    list(self.received_enc_chunks[message.epoch][message.proposer_id].values())
                )
                # Verify reconstructed payload hash against the one in RBCPropose
                expected_payload_hash = self.proposals[message.epoch][message.proposer_id].payload_hash
                if reconstructed_payload == expected_payload_hash:
                    self.decrypted_batches[message.epoch][message.proposer_id] = reconstructed_payload # Store the reconstructed payload hash as the 'decrypted batch'
                    print(f"Validator {self.validator_id} successfully simulated reconstruction and decryption for epoch {message.epoch}, proposer {message.proposer_id}")
                else:
                    print(f"Validator {self.validator_id} failed payload hash verification for epoch {message.epoch}, proposer {message.proposer_id}")

    def _is_rbc_complete(self, epoch: int, proposer_id: str) -> bool:
        """Checks if Reliable Broadcast is complete for a given proposer in an epoch.

        This means we have received enough chunks to reconstruct the payload.
        For simulation, we assume 'enough' means all chunks for now.
        """
        if epoch not in self.proposals or proposer_id not in self.proposals[epoch]:
            return False
        
        expected_chunks_count = self.proposals[epoch][proposer_id].n # In a real system, this would be k
        received_chunks_count = len(self.received_enc_chunks[epoch][proposer_id])
        
        return received_chunks_count >= expected_chunks_count # For simulation, we need all chunks to 'reconstruct'

    def _simulate_reconstruct_payload(self, chunks: List[str]) -> str:
        """Simulates reconstructing the original payload hash from chunks.

        In a real system, this would involve erasure coding reconstruction.
        For simulation, we assume all chunks are the same and return the hash from the first chunk.
        """
        if not chunks:
            return ""
        # Extract the payload hash from the first chunk (e.g., "payload_hash_chunk_0")
        return chunks[0].split("_chunk_")[0]

    async def handle_coin_share(self, message: CoinShare) -> None:
        """Handles a COIN_SHARE message from another validator.

        Args:
            message: The CoinShare message received.
        """
        print(f"Validator {self.validator_id} handling COIN_SHARE for epoch {message.epoch} from {message.proposer_id}")
        self.coin_shares[message.epoch][message.proposer_id] = message.coin_sig_share

        # Simulate common coin derivation if threshold is met
        if len(self.coin_shares[message.epoch]) >= self.coin_threshold:
            if self.common_coin_value[message.epoch] is None:
                # Get coin shares in a deterministic order (sorted by proposer_id)
                deterministic_coin_shares = [
                    self.coin_shares[message.epoch][validator_id]
                    for validator_id in sorted(self.coin_shares[message.epoch].keys())
                ]
                self.common_coin_value[message.epoch] = self._simulate_derive_common_coin(
                    deterministic_coin_shares
                )
                print(f"Validator {self.validator_id} derived common coin for epoch {message.epoch}: {self.common_coin_value[message.epoch]}")

    async def handle_commit(self, message: Commit) -> None:
        """Handles a COMMIT message, finalizing an epoch block.

        Args:
            message: The Commit message received.
        """
        print(f"Validator {self.validator_id} handling COMMIT for epoch {message.epoch}")
        # Deterministic ordering of proposals
        if message.epoch in self.proposals:
            epoch_proposals = self.proposals[message.epoch]
            
            # Filter for proposals that have been reliably broadcast and decrypted
            valid_proposals = []
            for proposer_id, rbc_propose in epoch_proposals.items():
                if proposer_id in self.decrypted_batches[message.epoch] and \
                   self.decrypted_batches[message.epoch][proposer_id] == rbc_propose.payload_hash:
                    valid_proposals.append(rbc_propose)

            ordered_proposals = sorted(
                valid_proposals,
                key=lambda p: (p.proposer_id, p.payload_hash)
            )
            print(f"Ordered proposals for epoch {message.epoch}: {[p.proposer_id for p in ordered_proposals]}")
            
            # Construct the block (for simulation, we'll just use a hash of ordered payload hashes)
            block_content_hash = blake3_hash([p.payload_hash for p in ordered_proposals])

            # TODO: Implement quorum certificate verification and block commitment
            # For now, we assume the commit message is valid and commit the block
            self.committed_blocks[message.epoch] = {
                "block_digest": block_content_hash,
                "proposals": [asdict(p) for p in ordered_proposals],
                "common_coin": self.common_coin_value[message.epoch] # Include common coin if available
            }
            print(f"Validator {self.validator_id} committed block for epoch {message.epoch} with digest {block_content_hash}")

            # Placeholder for ActivityPub export callback
            print(f"Simulating ActivityPub export callback for epoch {message.epoch} with committed events.")

        # TODO: Implement quorum certificate verification and block commitment
        # self.committed_blocks[message.epoch] = message.block_digest # This line is replaced by the above logic
        await self.advance_epoch()

    async def handle_day_proof(self, day_proof: DayProof) -> None:
        """Handles a DayProof event from another validator.

        Args:
            day_proof: The DayProof event received.
        """
        print(f"Validator {self.validator_id} handling DayProof for day {day_proof.day_number} from {day_proof.validator_quorum_sig}")
        
        # Verify the VDF proof (simulated)
        is_valid = self.vdf.verify_day_proof(day_proof.day_number, day_proof.canonical_proof_hash, self.vdf_iterations)
        if is_valid:
            self.day_proofs[day_proof.day_number][day_proof.sig] = day_proof # Using sig as a placeholder for validator_id for now
            print(f"Validator {self.validator_id} verified valid DayProof for day {day_proof.day_number}")
            # TODO: Implement supermajority check to advance epoch
        else:
            print(f"Validator {self.validator_id} received invalid DayProof for day {day_proof.day_number}")

    async def handle_membership_change(self, message: MembershipChangeMessage) -> None:
        """Handles a MEMBERSHIP_CHANGE message.

        Args:
            message: The MembershipChangeMessage received.
        """
        print(f"Validator {self.validator_id} handling MEMBERSHIP_CHANGE for epoch {message.epoch}")
        membership_change_event: MembershipChange = message.update
        if membership_change_event.change_type == "add":
            if membership_change_event.validator_pubkey not in self.validators:
                self.validators.append(membership_change_event.validator_pubkey)
                print(f"Validator {membership_change_event.validator_pubkey} added to membership.")
        elif membership_change_event.change_type == "remove":
            if membership_change_event.validator_pubkey in self.validators:
                self.validators.remove(membership_change_event.validator_pubkey)
                print(f"Validator {membership_change_event.validator_pubkey} removed from membership.")
        # TODO: Implement quorum certificate verification for membership change
        print(f"Current validators: {self.validators}")

    async def advance_epoch(self) -> None:
        """Advances the Conductor to the next epoch (day number) and generates a VDF proof."""
        self.current_epoch += 1
        print(f"Validator {self.validator_id} advanced to epoch {self.current_epoch}")
        
        # Generate VDF proof for the new epoch
        vdf_proof = self.vdf.compute_day_proof(self.current_epoch, self.vdf_iterations)
        print(f"Validator {self.validator_id} generated VDF proof for epoch {self.current_epoch}: {vdf_proof}")

        # Create and store DayProof event
        day_proof_event = DayProof(
            day_number=self.current_epoch,
            canonical_proof_hash=vdf_proof,
            validator_quorum_sig="dummy_quorum_sig", # Placeholder
            creation_day=self.current_epoch,
            sig="dummy_sig"
        )
        self.day_proofs[self.current_epoch][self.validator_id] = day_proof_event

        # Calibrate VDF difficulty periodically (simulated) - removed as per CFP-011, difficulty adjustment is a separate phase
        # if self.current_epoch % 10 == 0: # Every 10 epochs
        #     self.vdf_iterations = VDF.calibrate_iterations(target_duration_seconds=1.0, reference_hardware_factor=1.0 + (self.current_epoch / 100.0)) # Simulate increasing difficulty
        #     print(f"VDF iterations recalibrated to: {self.vdf_iterations}")

        # TODO: Reset epoch-specific state

    def _serialize_events(self, events: List[Event]) -> List[Dict[str, Any]]:
        """Serializes a list of Event objects into a list of dictionaries.

        Args:
            events: A list of Event objects.

        Returns:
            A list of dictionaries representing the serialized events.
        """
        return [asdict(event) for event in events]

    def _simulate_encrypt_batch(self, batch: List[Dict[str, Any]], key: str) -> List[str]:
        """Simulates threshold encryption of a batch.

        In a real implementation, this would involve splitting the batch into shares
        and encrypting them using a threshold encryption scheme.
        """
        print(f"Simulating encryption of batch with key: {key}")
        # For simulation, we just create dummy shares based on the batch hash
        batch_hash = blake3_hash(batch)
        return [f"enc_share_{batch_hash}_{i}" for i in range(len(self.validators))]

    def _simulate_decrypt_batch(self, shares: List[str], key: str) -> List[Dict[str, Any]]:
        """Simulates threshold decryption of a batch.

        In a real implementation, this would involve combining enough shares
        to decrypt the original batch.
        """
        print(f"Simulating decryption with {len(shares)} shares and key: {key}")
        # For simulation, we just return a dummy decrypted batch
        return [{"simulated_decrypted_event": "data"}]

    def _simulate_generate_coin_share(self, epoch: int, validator_id: str) -> str:
        """Simulates generating a common coin share.

        In a real implementation, this would involve cryptographic signing.
        """
        return f"coin_share_{epoch}_{validator_id}_sig"

                print(f"Validator {self.validator_id} derived common coin for epoch {message.epoch}: {self.common_coin_value[message.epoch]}")

    async def handle_commit(self, message: Commit) -> None:
        print(f"[DEBUG] _simulate_derive_common_coin input: {coin_shares}")
        return blake3_hash(" ".join(sorted(coin_shares))) # Deterministic from shares

    def _simulate_derive_common_coin(self, coin_shares: List[str]) -> str:
        """Simulates deriving the common coin from collected shares.

        In a real implementation, this would involve combining cryptographic signatures.
        """
        print(f"[DEBUG] _simulate_derive_common_coin input: {coin_shares}")
        return blake3_hash(" ".join(sorted(coin_shares))) # Deterministic from shares

