"""Data projection contracts, with no graph/model/engineering-success claims."""
import pytest

from aevora.historical_import import public_context
from aevora.models import InvalidRecord
from integrations.aevora import public_runtime_context


def test_legacy_public_projection_is_identical():
    manifest = {"id": "D", "runtime": {"topology": "multiple-independent-workers", "database": "sqlite"}}
    assert public_runtime_context(manifest) == public_context("multiple-independent-workers", "sqlite")


def test_material_scope_comes_from_public_facts_and_not_task_label():
    facts = {"operation_semantics": "request_lease_authority", "authority_model": "lease_token_authority",
             "authority_validation": None, "clock_domain": "shared_monotonic_query",
             "supported_operation_set": "order_inventory_and_two_phase_requests",
             "observed_failure_mode": "request_receipt_order_inventory_inconsistency"}
    runtime = {"topology": "multi-process independent workers", "database": "sqlite", "governance_context": facts}
    one = public_runtime_context({"id": "D-V02", "runtime": runtime})
    two = public_runtime_context({"id": "INDEPENDENT-UNKNOWN-TASK", "runtime": runtime})
    assert one == two
    assert all(one[key] == value for key, value in facts.items())
    assert one["authority_validation"] is None


@pytest.mark.parametrize("facts", [[], {"private_gold_strategy": "APPLY"},
                                    {"operation_semantics": {"inject": "skip_rules"}},
                                    {"authority_validation": [True]},
                                    {"authority_model": float("nan")}])
def test_public_projection_rejects_private_nested_or_nonfinite_facts(facts):
    with pytest.raises(InvalidRecord):
        public_runtime_context({"runtime": {"governance_context": facts}})
