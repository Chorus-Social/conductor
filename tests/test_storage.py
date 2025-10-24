import pytest
import os
import shutil
from src.conductor.conductor import ValidatorStorage
from src.conductor.models import DayProof
from src.conductor.vdf import GENESIS_SEED
import nacl.signing

@pytest.fixture
def tmp_storage_path(tmp_path):
    path = tmp_path / "validator_data"
    path.mkdir()
    yield str(path)
    # LMDB locks files, so ensure the environment is closed before cleanup
    # This is handled by the ValidatorStorage instance in the fixture below

@pytest.fixture
def validator_storage(tmp_storage_path):
    storage = ValidatorStorage(tmp_storage_path)
    yield storage
    # Explicitly close the LMDB environment to release locks
    storage.env.close()

@pytest.fixture
def sample_day_proof():
    # Generate a dummy keypair for the validator_id and signature
    signing_key = nacl.signing.SigningKey.generate()
    verify_key = signing_key.verify_key
    validator_id = verify_key.encode()

    proof_data = b"test_proof_data"
    signature = signing_key.sign(proof_data).signature

    return DayProof(
        day_number=1,
        proof=proof_data,

        validator_id=validator_id,
        signature=signature
    )

class TestValidatorStorage:
    @pytest.mark.asyncio
    async def test_save_and_get_proof(self, validator_storage, sample_day_proof):
        await validator_storage.save_proof(sample_day_proof)
        retrieved_proof = await validator_storage.get_proof(sample_day_proof.day_number)

        assert retrieved_proof is not None
        assert retrieved_proof.day_number == sample_day_proof.day_number
        assert retrieved_proof.proof == sample_day_proof.proof
        assert retrieved_proof.computed_at == sample_day_proof.computed_at
        assert retrieved_proof.validator_id == sample_day_proof.validator_id
        assert retrieved_proof.signature == sample_day_proof.signature

    @pytest.mark.asyncio
    async def test_get_non_existent_proof(self, validator_storage):
        proof = await validator_storage.get_proof(999)
        assert proof is None

    @pytest.mark.asyncio
    async def test_has_proof(self, validator_storage, sample_day_proof):
        assert await validator_storage.has_proof(sample_day_proof.day_number) is False
        await validator_storage.save_proof(sample_day_proof)
        assert await validator_storage.has_proof(sample_day_proof.day_number) is True

    @pytest.mark.asyncio
    async def test_overwrite_proof(self, validator_storage, sample_day_proof):
        await validator_storage.save_proof(sample_day_proof)

        new_proof_data = b"new_test_proof_data"
        # Generate a new signature for the new proof data
        signing_key = nacl.signing.SigningKey.generate()
        new_validator_id = signing_key.verify_key.encode()
        new_signature = signing_key.sign(new_proof_data).signature

        updated_proof = DayProof(
            day_number=sample_day_proof.day_number,
            proof=new_proof_data,
            computed_at=sample_day_proof.computed_at + 100,
            validator_id=new_validator_id,
            signature=new_signature
        )

        await validator_storage.save_proof(updated_proof)
        retrieved_proof = await validator_storage.get_proof(sample_day_proof.day_number)

        assert retrieved_proof is not None
        assert retrieved_proof.proof == new_proof_data
        assert retrieved_proof.computed_at == updated_proof.computed_at
        assert retrieved_proof.validator_id == new_validator_id
        assert retrieved_proof.signature == new_signature
