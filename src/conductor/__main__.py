import asyncio
from .conductor import Conductor
from .models import PostAnnounce, Commit, MembershipChange, MembershipChangeMessage, APExportNotice, DayProof

async def main():
    print("Starting Conductor node...")
    validator_id = "validator_1"
    validators = ["validator_1", "validator_2", "validator_3", "validator_4"]
    conductor = Conductor(validator_id, validators)

    print(f"Conductor initialized for {conductor.validator_id} in epoch {conductor.current_epoch}")

    # Simulate proposing a batch of events
    events = [
        PostAnnounce(content_cid="QmExample1", author_pubkey_hash="pubkey1", community_id="communityA", creation_day=conductor.current_epoch, sig="sig1"),
        PostAnnounce(content_cid="QmExample2", author_pubkey_hash="pubkey2", community_id="communityB", creation_day=conductor.current_epoch, sig="sig2"),
    ]
    await conductor.propose_batch(events)

    # Simulate receiving a commit message (this would normally come from other validators after consensus)
    dummy_commit = Commit(epoch=conductor.current_epoch, block_digest="blockhash123", quorum_cert="qc123")
    await conductor.handle_commit(dummy_commit)

    # Simulate day progression and VDF generation
    for _ in range(5): # Advance 5 days
        await conductor.advance_epoch()
        # Simulate other validators also generating and sharing day proofs
        # For now, we'll just print the local one
        if conductor.current_epoch in conductor.day_proofs and conductor.validator_id in conductor.day_proofs[conductor.current_epoch]:
            proof = conductor.day_proofs[conductor.current_epoch][conductor.validator_id]
            print(f"Day {proof.day_number} VDF Proof: {proof.canonical_proof_hash}")

    # Simulate a membership change (add a validator)
    add_validator_event = MembershipChange(
        change_type="add",
        validator_pubkey="validator_5",
        effective_day=conductor.current_epoch + 1,
        quorum_sig="qc_add_5",
        creation_day=conductor.current_epoch,
        sig="sig_add_5"
    )
    add_membership_message = MembershipChangeMessage(
        epoch=conductor.current_epoch,
        update=add_validator_event,
        quorum_cert="qc_add_5"
    )
    await conductor.handle_membership_change(add_membership_message)

    # Simulate a membership change (remove a validator)
    remove_validator_event = MembershipChange(
        change_type="remove",
        validator_pubkey="validator_2",
        effective_day=conductor.current_epoch + 1,
        quorum_sig="qc_remove_2",
        creation_day=conductor.current_epoch,
        sig="sig_remove_2"
    )
    remove_membership_message = MembershipChangeMessage(
        epoch=conductor.current_epoch,
        update=remove_validator_event,
        quorum_cert="qc_remove_2"
    )
    await conductor.handle_membership_change(remove_membership_message)

    # Simulate an ActivityPub export notice
    ap_export_event = APExportNotice(
        object_ref="object_ref_123",
        policy_hash="policy_hash_abc",
        creation_day=conductor.current_epoch,
        sig="sig_ap_export"
    )
    # In a real scenario, this event would be part of a committed batch
    # For now, we'll just simulate its processing after a commit.
    print(f"Simulating processing of APExportNotice: {ap_export_event}")

    print("Conductor node simulation finished.")

if __name__ == "__main__":
    asyncio.run(main())
