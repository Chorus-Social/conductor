import pytest
from src.conductor.vdf import ChorusVDF
from src.conductor.vdf import GENESIS_SEED, VDF_TEST_ITERATIONS

class TestChorusVDF:
    @pytest.fixture
    def chorus_vdf(self):
        return ChorusVDF(GENESIS_SEED, iterations=VDF_TEST_ITERATIONS)

    def test_compute_day_seed_determinism(self, chorus_vdf):
        seed1 = chorus_vdf.compute_day_seed(1)
        seed2 = chorus_vdf.compute_day_seed(1)
        assert seed1 == seed2

    def test_compute_day_seed_different_days(self, chorus_vdf):
        seed1 = chorus_vdf.compute_day_seed(1)
        seed2 = chorus_vdf.compute_day_seed(2)
        assert seed1 != seed2

    def test_compute_day_proof_determinism(self, chorus_vdf):
        proof1 = chorus_vdf.compute_day_proof(1)
        proof2 = chorus_vdf.compute_day_proof(1)
        assert proof1 == proof2

    def test_compute_day_proof_different_days(self, chorus_vdf):
        proof1 = chorus_vdf.compute_day_proof(1)
        proof2 = chorus_vdf.compute_day_proof(2)
        assert proof1 != proof2

    def test_verify_day_proof_valid(self, chorus_vdf):
        day_number = 1
        proof = chorus_vdf.compute_day_proof(day_number)
        assert chorus_vdf.verify_day_proof(day_number, proof) is True

    def test_verify_day_proof_invalid_proof(self, chorus_vdf):
        day_number = 1
        proof = chorus_vdf.compute_day_proof(day_number)
        invalid_proof = b"invalid_proof"
        assert chorus_vdf.verify_day_proof(day_number, invalid_proof) is False

    def test_verify_day_proof_invalid_day_number(self, chorus_vdf):
        day_number = 1
        proof = chorus_vdf.compute_day_proof(day_number)
        assert chorus_vdf.verify_day_proof(day_number + 1, proof) is False
