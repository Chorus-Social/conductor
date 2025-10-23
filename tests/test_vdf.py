import pytest
from src.conductor.vdf import ChorusVDF
from src.conductor.conductor import GENESIS_SEED

TEST_VDF_ITERATIONS = 1000  # Significantly reduced iterations for testing

class TestChorusVDF:
    @pytest.fixture
    def chorus_vdf(self):
        return ChorusVDF(GENESIS_SEED)

    def test_compute_day_seed_determinism(self, chorus_vdf):
        seed1 = chorus_vdf.compute_day_seed(1)
        seed2 = chorus_vdf.compute_day_seed(1)
        assert seed1 == seed2

    def test_compute_day_seed_different_days(self, chorus_vdf):
        seed1 = chorus_vdf.compute_day_seed(1)
        seed2 = chorus_vdf.compute_day_seed(2)
        assert seed1 != seed2

    def test_compute_day_proof_determinism(self, chorus_vdf):
        proof1 = chorus_vdf.compute_day_proof(1, TEST_VDF_ITERATIONS)
        proof2 = chorus_vdf.compute_day_proof(1, TEST_VDF_ITERATIONS)
        assert proof1 == proof2

    def test_compute_day_proof_different_days(self, chorus_vdf):
        proof1 = chorus_vdf.compute_day_proof(1, TEST_VDF_ITERATIONS)
        proof2 = chorus_vdf.compute_day_proof(2, TEST_VDF_ITERATIONS)
        assert proof1 != proof2

    def test_verify_day_proof_valid(self, chorus_vdf):
        day_number = 1
        proof = chorus_vdf.compute_day_proof(day_number, TEST_VDF_ITERATIONS)
        assert chorus_vdf.verify_day_proof(day_number, proof, TEST_VDF_ITERATIONS) is True

    def test_verify_day_proof_invalid_proof(self, chorus_vdf):
        day_number = 1
        proof = chorus_vdf.compute_day_proof(day_number, TEST_VDF_ITERATIONS)
        invalid_proof = b"invalid_proof"
        assert chorus_vdf.verify_day_proof(day_number, invalid_proof, TEST_VDF_ITERATIONS) is False

    def test_verify_day_proof_invalid_day_number(self, chorus_vdf):
        day_number = 1
        proof = chorus_vdf.compute_day_proof(day_number, TEST_VDF_ITERATIONS)
        assert chorus_vdf.verify_day_proof(day_number + 1, proof, TEST_VDF_ITERATIONS) is False
