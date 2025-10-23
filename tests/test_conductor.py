import pytest
from src.conductor.conductor import Conductor, GENESIS_SEED, VDF_ITERATIONS_PER_DAY
from src.conductor.models import Event, RBCPropose, EncShare, CoinShare, Commit
from src.conductor.hashing import blake3_hash
import asyncio

@pytest.fixture
def mock_validators():
    return ["validator1", "validator2", "validator3", "validator4"]

@pytest.fixture
def conductor_instance(mock_validators):
    return Conductor("validator1", mock_validators)

@pytest.fixture
def other_conductor_instance(mock_validators):
    return Conductor("validator2", mock_validators)

@pytest.fixture
def sample_events():
    return [Event(creation_day=1, sig="sig1"), Event(creation_day=1, sig="sig2")]

class TestConductorRBC:

    @pytest.mark.asyncio
    async def test_propose_batch_generates_messages(self, conductor_instance, sample_events):
        await conductor_instance.propose_batch(sample_events)
        # Check if RBCPropose message was stored locally
        assert conductor_instance.proposals[conductor_instance.current_epoch][conductor_instance.validator_id] is not None
        # Check if enc_chunks were generated and stored (simulated)
        assert len(conductor_instance.received_enc_chunks[conductor_instance.current_epoch][conductor_instance.validator_id]) == len(conductor_instance.validators)

    @pytest.mark.asyncio
    async def test_handle_rbc_propose_stores_proposal(self, conductor_instance, other_conductor_instance, sample_events):
        # Simulate other_conductor_instance proposing a batch
        await other_conductor_instance.propose_batch(sample_events)
        rbc_message = other_conductor_instance.proposals[other_conductor_instance.current_epoch][other_conductor_instance.validator_id]
        
        # Conductor instance handles the message
        await conductor_instance.handle_rbc_propose(rbc_message)
        assert conductor_instance.proposals[rbc_message.epoch][rbc_message.proposer_id] == rbc_message
        assert conductor_instance.reconstructed_payloads[rbc_message.epoch][rbc_message.proposer_id] == rbc_message.payload_hash

    @pytest.mark.asyncio
    async def test_handle_enc_share_collects_chunks_and_reconstructs(self, conductor_instance, other_conductor_instance, sample_events):
        # Simulate other_conductor_instance proposing a batch
        await other_conductor_instance.propose_batch(sample_events)
        rbc_message = other_conductor_instance.proposals[other_conductor_instance.current_epoch][other_conductor_instance.validator_id]
        
        # Conductor instance handles the RBCPropose first
        await conductor_instance.handle_rbc_propose(rbc_message)

        # Simulate sending all enc_shares from other_conductor_instance to conductor_instance
        for i in range(len(other_conductor_instance.validators)):
            enc_share_message = EncShare(
                epoch=other_conductor_instance.current_epoch,
                enc_payload_share=f"{rbc_message.payload_hash}_chunk_{i}",
                proposer_id=other_conductor_instance.validator_id,
                chunk_index=i
            )
            await conductor_instance.handle_enc_share(enc_share_message)
        
        # Check if RBC is complete and payload is reconstructed
        assert conductor_instance._is_rbc_complete(rbc_message.epoch, rbc_message.proposer_id) is True
        assert conductor_instance.decrypted_batches[rbc_message.epoch][rbc_message.proposer_id] == rbc_message.payload_hash

    @pytest.mark.asyncio
    async def test_is_rbc_complete(self, conductor_instance, other_conductor_instance, sample_events):
        # Simulate other_conductor_instance proposing a batch
        await other_conductor_instance.propose_batch(sample_events)
        rbc_message = other_conductor_instance.proposals[other_conductor_instance.current_epoch][other_conductor_instance.validator_id]
        
        # Conductor instance handles the RBCPropose first
        await conductor_instance.handle_rbc_propose(rbc_message)

        # Initially, RBC should not be complete
        assert conductor_instance._is_rbc_complete(rbc_message.epoch, rbc_message.proposer_id) is False

        # Simulate sending some enc_shares (not all)
        for i in range(len(other_conductor_instance.validators) - 1):
            enc_share_message = EncShare(
                epoch=other_conductor_instance.current_epoch,
                enc_payload_share=f"{rbc_message.payload_hash}_chunk_{i}",
                proposer_id=other_conductor_instance.validator_id,
                chunk_index=i
            )
            await conductor_instance.handle_enc_share(enc_share_message)
        
        # RBC should still not be complete
        assert conductor_instance._is_rbc_complete(rbc_message.epoch, rbc_message.proposer_id) is False

        # Simulate sending the last enc_share
        enc_share_message = EncShare(
            epoch=other_conductor_instance.current_epoch,
            enc_payload_share=f"{rbc_message.payload_hash}_chunk_{len(other_conductor_instance.validators) - 1}",
            proposer_id=other_conductor_instance.validator_id,
            chunk_index=len(other_conductor_instance.validators) - 1
        )
        await conductor_instance.handle_enc_share(enc_share_message)

        # RBC should now be complete
        assert conductor_instance._is_rbc_complete(rbc_message.epoch, rbc_message.proposer_id) is True

    def test_simulate_reconstruct_payload(self, conductor_instance):
        payload_hash = blake3_hash("test_data")
        chunks = [f"{payload_hash}_chunk_0", f"{payload_hash}_chunk_1", f"{payload_hash}_chunk_2"]
        reconstructed = conductor_instance._simulate_reconstruct_payload(chunks)
        assert reconstructed == payload_hash

    @pytest.mark.asyncio
    async def test_handle_coin_share_derives_common_coin(self, conductor_instance, mock_validators):
        epoch = conductor_instance.current_epoch
        # Simulate enough validators sending coin shares
        for i, validator_id in enumerate(mock_validators):
            coin_share_message = CoinShare(
                epoch=epoch,
                coin_sig_share=f"coin_share_{epoch}_{validator_id}_sig",
                proposer_id=validator_id # Add proposer_id to CoinShare for testing
            )
            await conductor_instance.handle_coin_share(coin_share_message)
        
        assert conductor_instance.common_coin_value[epoch] is not None
        # Verify that the common coin is deterministic based on the shares
        expected_common_coin = conductor_instance._simulate_derive_common_coin(
            [f"coin_share_{epoch}_{v}_sig" for v in mock_validators]
        )
        assert conductor_instance.common_coin_value[epoch] == expected_common_coin

    @pytest.mark.asyncio
    async def test_handle_commit_orders_and_commits_block(self, conductor_instance, mock_validators, sample_events):
        epoch = conductor_instance.current_epoch
        proposals_data = {}

        # 1. Simulate validators proposing batches and completing RBC
        for validator_id in mock_validators:
            # Create a temporary conductor for each validator to simulate their proposal
            temp_conductor = Conductor(validator_id, mock_validators)
            await temp_conductor.propose_batch(sample_events)
            rbc_message = temp_conductor.proposals[epoch][validator_id]
            proposals_data[validator_id] = rbc_message

            # Conductor instance handles RBCPropose from each validator
            await conductor_instance.handle_rbc_propose(rbc_message)

            # Conductor instance handles all enc_shares from each validator
            for i in range(len(mock_validators)):
                enc_share_message = EncShare(
                    epoch=epoch,
                    enc_payload_share=f"{rbc_message.payload_hash}_chunk_{i}",
                    proposer_id=validator_id,
                    chunk_index=i
                )
                await conductor_instance.handle_enc_share(enc_share_message)
            
            # Ensure RBC is complete and decrypted batch is available
            assert conductor_instance._is_rbc_complete(epoch, validator_id) is True
            assert conductor_instance.decrypted_batches[epoch][validator_id] == rbc_message.payload_hash

        # 2. Simulate validators sending coin shares to derive common coin
        for validator_id in mock_validators:
            coin_share_message = CoinShare(
                epoch=epoch,
                coin_sig_share=f"coin_share_{epoch}_{validator_id}_sig",
                proposer_id=validator_id
            )
            await conductor_instance.handle_coin_share(coin_share_message)
        
        assert conductor_instance.common_coin_value[epoch] is not None

        # 3. Simulate a Commit message
        commit_message = Commit(
            epoch=epoch,
            block_digest="dummy_block_digest", # This will be replaced by the actual computed digest
            quorum_cert="dummy_quorum_cert"
        )
        await conductor_instance.handle_commit(commit_message)

        # 4. Verify the committed block
        assert epoch in conductor_instance.committed_blocks
        committed_block = conductor_instance.committed_blocks[epoch]
        assert committed_block["common_coin"] == conductor_instance.common_coin_value[epoch]
        
        # Verify ordered proposals
        expected_ordered_proposals = sorted(
            [proposals_data[v] for v in mock_validators],
            key=lambda p: (p.proposer_id, p.payload_hash)
        )
        assert [p["proposer_id"] for p in committed_block["proposals"]] == [p.proposer_id for p in expected_ordered_proposals]
        assert [p["payload_hash"] for p in committed_block["proposals"]] == [p.payload_hash for p in expected_ordered_proposals]

        # Verify block digest
        expected_block_digest = blake3_hash([p.payload_hash for p in expected_ordered_proposals])
        assert committed_block["block_digest"] == expected_block_digest

        # Verify epoch advanced
        assert conductor_instance.current_epoch == epoch + 1