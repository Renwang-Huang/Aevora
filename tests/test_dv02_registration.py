"""Additive registration and fail-closed metadata contracts, without models."""
from benchmark.h2_cli import register_h2
from benchmark.registry import REGISTRY
from benchmark.manifest import load_manifest, private_config
from evaluator.suites import SUITES
from evaluator.dv02_admission import recovery_matrix
import pytest


def test_h2_registration_is_idempotent_and_preserves_every_existing_factory():
    existing = {name: REGISTRY[name] for name in ("SMOKE-001", "A", "D")}
    suites = {name: SUITES[name] for name in ("smoke", "episode_a", "episode_d")}
    register_h2()
    register_h2()
    assert all(REGISTRY[name] is value for name, value in existing.items())
    assert all(SUITES[name] is value for name, value in suites.items())
    manifest, private = load_manifest("D-V02"), private_config("D-V02")
    assert manifest.metadata["family"] == "D" and manifest.metadata["variant"] == "v02"
    assert REGISTRY["D"].variants == ("v01",) and REGISTRY["D-V02"].variants == ("v02",)
    assert private["expected_test_count"] == len(SUITES["episode_d_v02"].expected_tests)
    assert private["suite"] == "episode_d_v02" and private["execution_strategy"] == "shared-db-workers"


def test_matrix_requires_actual_method_phase_records_for_every_obligation():
    register_h2()
    configuration = private_config("D-V02")
    matrix = recovery_matrix({"recovery_evidence": [], "worker_topology_evidence": []}, configuration)
    assert matrix["status"] == "PARTIAL"
    assert len(matrix["matrix"]) == 8
    assert all(row["availability"] == "UNVERIFIED" and row["verified_interruptions"] == 0 for row in matrix["matrix"])
    assert len({(row["method"], row["label"], row["phase"]) for row in matrix["matrix"]}) == 8


def test_matrix_does_not_misread_owned_resource_cleanup_lists_as_crash_receipts():
    register_h2()
    result = {"recovery_evidence": [[{"cleanup_complete": True}], None, "not an interruption"],
              "worker_topology_evidence": []}
    matrix = recovery_matrix(result, private_config("D-V02"))
    assert matrix["status"] == "PARTIAL"
    assert all(row["recorded_attempts"] == 0 for row in matrix["matrix"])


@pytest.mark.parametrize("configuration", [{}, {"required_recovery_observations": []},
    {"required_recovery_observations": [{"method": "claim_request", "label": "before_commit"}] * 2},
    {"required_recovery_observations": [{"method": "claim_request", "label": "before_commit", "readonly_stale_allowed": True}]},
    {"required_recovery_observations": [{"method": "complete_request", "label": "before_response", "readonly_stale_allowed": "true"}]}])
def test_matrix_refuses_invalid_trusted_configuration(configuration):
    with pytest.raises(ValueError):
        recovery_matrix({}, configuration)
