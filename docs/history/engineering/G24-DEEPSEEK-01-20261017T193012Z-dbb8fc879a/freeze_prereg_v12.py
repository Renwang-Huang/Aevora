"""Create the append-only G24 analysis-protocol v1.2.

The v1.1 files are inputs only. This script also rewrites the formal arm order
with a fixed seed and a constrained balanced design; it does not run any model,
Pilot, or formal episode.
"""
from __future__ import annotations

import csv
import hashlib
import itertools
import json
import random
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from audit import E, sha, write


SEED = 20261018
ARMS = ("GRAPH", "RAW_MEMORY", "NO_MEMORY")


def load(path: Path):
    return json.loads(Path(path).read_text())


def main() -> int:
    old_tasks_path = E / "01_protocol/TASKS_FROZEN.json"
    old_protocol_path = E / "01_protocol/PRE_REGISTERED_PROTOCOL.json"
    old_tasks = load(old_tasks_path)
    old_protocol = load(old_protocol_path)
    fairness = load(E / "01_protocol/memory/FAIRNESS_RECEIPT.json")
    fairness_check = load(E / "01_protocol/memory/FAIRNESS_VERIFICATION.json")
    calibration = load(E / "02_calibration/attempt2/GATE.json")
    pagination = load(E / "09_evidence/PAGINATION_RESULT.json")
    native = load(E / "09_evidence/NATIVE_IDENTITY_AUDIT.json")
    oracle = load(E / "09_evidence/ORACLE_REFERENCE_PROBE.json")

    if calibration.get("status") != "PASS":
        raise SystemExit("CALIBRATION_NOT_PASS")
    if pagination.get("status") != "PASS" or not pagination.get(
        "production_wire_budget_changed"
    ) is False:
        raise SystemExit("PAGINATION_NOT_CLOSED")
    if fairness_check.get("status") != "PASS" or fairness_check.get(
        "hidden_oracle_test_content_exposed"
    ):
        raise SystemExit("FAIRNESS_OR_BOUNDARY_NOT_CLOSED")
    if not native.get("native_identity"):
        raise SystemExit("NATIVE_IDENTITY_NOT_OBSERVED")

    formal = [item for item in old_tasks if item["stage"] == "FORMAL"]
    pilot = [item for item in old_tasks if item["stage"] == "PILOT"]
    if len(formal) != 8 or len(pilot) != 2:
        raise SystemExit("UNEXPECTED_BLOCK_COUNT")

    permutations = list(itertools.permutations(ARMS))
    rng = random.Random(SEED)
    selected = None
    attempts = 0
    while selected is None:
        attempts += 1
        candidate = [rng.choice(permutations) for _ in range(8)]
        counts = {
            arm: [sum(row[index] == arm for row in candidate) for index in range(3)]
            for arm in ARMS
        }
        if all(2 <= count <= 3 for values in counts.values() for count in values):
            selected = candidate
    if attempts > 100000:
        raise SystemExit("ARM_ORDER_SEARCH_FAILED")

    formal_by_block = {item["block"]: dict(item) for item in formal}
    new_formal = []
    order_rows = []
    for block, order in zip([item["block"] for item in formal], selected):
        task = formal_by_block[block]
        task["arm_order"] = list(order)
        task["arm_order_seed"] = SEED
        new_formal.append(task)
        order_rows.append({"block": block, "arm_order": list(order)})
    new_tasks = pilot + new_formal
    counts = {
        arm: [sum(list(item["arm_order"])[index] == arm for item in new_formal)
              for index in range(3)]
        for arm in ARMS
    }
    if any(not 2 <= value <= 3 for values in counts.values() for value in values):
        raise SystemExit("ARM_ORDER_NOT_BALANCED")

    tasks_v12_path = E / "01_protocol/TASKS_FROZEN_v1.2.json"
    write(tasks_v12_path, new_tasks)
    with (E / "01_protocol/EPISODE_MANIFEST_v1.2.csv").open("w", newline="") as stream:
        fields = [
            "block", "stage", "condition", "episode", "fault", "journal",
            "busy_timeout", "seed", "arm_order",
        ]
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for item in new_tasks:
            writer.writerow({**item, "arm_order": ">".join(item["arm_order"])})
    order_path = E / "01_protocol/FORMAL_ARM_ORDER.json"
    write(order_path, {
        "schema": "aevora.g24.formal_arm_order/1.0",
        "seed": SEED,
        "algorithm": "seeded random choice with rejection until every arm has 2..3 occurrences at each of positions 1..3",
        "attempts": attempts,
        "blocks": order_rows,
        "position_counts": counts,
        "balanced": True,
        "pilot_separate": True,
    })

    frozen_at = datetime.now(timezone.utc).isoformat()
    commit = subprocess.check_output(
        ["git", "-C", str(E / "worktree"), "rev-parse", "HEAD"], text=True
    ).strip()
    tree = subprocess.check_output(
        ["git", "-C", str(E / "worktree"), "rev-parse", "HEAD^{tree}"], text=True
    ).strip()
    v11_sha = sha(old_protocol_path)
    v11_tasks_sha = sha(old_tasks_path)
    v12_protocol = dict(old_protocol)
    v12_protocol.update({
        "schema": "aevora.g24.preregistered.protocol/1.2",
        "version": "1.2",
        "status": "FROZEN_ANALYSIS_PROTOCOL_PILOT_CONDITIONAL_PENDING_NATIVE_ADAPTER_SMOKE",
        "frozen_at": frozen_at,
        "previous_version": {
            "version": "1.1",
            "protocol_sha256": v11_sha,
            "tasks_sha256": v11_tasks_sha,
            "preserved_and_not_rewritten": True,
        },
        "source_commit": commit,
        "source_tree": tree,
        "taskbook": "G24-A v1.1 + D2/D3 closure revision",
        "taskbook_sha256": old_protocol.get("taskbook_sha256"),
        "runtime": {
            **old_protocol.get("runtime", {}),
            "profile_id": "G24_DEEPSEEK_01_NATIVE_MULTI_AGENT_CANDIDATE",
            "agent_mode": "multi",
            "agent_protocol": "v2",
            "runtime_class": "NATIVE_CODEX",
            "native_parent_child_claimed": True,
            "native_parent_child_status": "PASS",
            "native_task_delivery": "PASS_WITH_EXPLICIT_SEND_MESSAGE",
            "default_spawn_only_task_delivery": "NOT_VERIFIED",
            "fallback_profile_id": "G24_DEEPSEEK_01_SINGLE_AGENT_FALLBACK",
            "fallback_native_claim": False,
            "runtime_note": "Native identity and an explicit send_message child result passed. The default spawn-only path remained generic; a full Participant adapter smoke with MCP, code modification, public tests, and Oracle is still required before Pilot.",
        },
        "runtime_gate": {
            **old_protocol.get("runtime_gate", {}),
            "mcp_pagination": "PASS",
            "full_native_adapter_smoke": "NOT_RUN",
            "functional_smoke_scope": "SINGLE_AGENT_ADAPTER_ONLY",
            "native_functional_adapter_smoke": "NOT_RUN",
            "native_identity": "PASS",
            "native_task_delivery": "PASS_WITH_EXPLICIT_SEND_MESSAGE",
            "native_parent_child": "PASS",
            "native_default_spawn_task_delivery": "NOT_VERIFIED",
            "oracle_boundary": "VERIFIED",
            "pilot_readiness": "CONDITIONAL",
            "formal_execution": "BLOCKED_PENDING_NATIVE_ADAPTER_SMOKE_AND_USER_APPROVAL",
            "pilot_requires_explicit_user_approval": True,
        },
        "design": {
            **old_protocol.get("design", {}),
            "formal_blocks": [item["block"] for item in new_formal],
            "formal_arm_order": order_rows,
            "formal_arm_order_sha256": sha(order_path),
            "formal_arm_order_seed": SEED,
            "formal_arm_order_algorithm": "seeded random choice with rejection; each arm at each position 2-3 times",
            "arm_order_position_counts": counts,
            "arm_order_balanced": True,
            "arm_order_search_attempts": attempts,
            "negative_transfer_formal_blocks": [
                item["block"] for item in new_formal
                if item["condition"] == "NEGATIVE_TRANSFER"
            ],
            "negative_transfer_inference": "EXPLORATORY_ONLY_3_FORMAL_BLOCKS",
            "pilot_blocks": [item["block"] for item in pilot],
            "formal_minimum_runs": 24,
            "formal_target_runs": 24,
            "formal_expansion_after_start": "FORBIDDEN",
            "fresh_session_per_run": True,
            "paired_block_unit": True,
        },
        "evidence": {
            "smoke_result_sha256": sha(E / "09_evidence/ADAPTER_SMOKE_RESULT_SINGLE_ORACLE_FAIL.json"),
            "pagination_result_sha256": sha(E / "09_evidence/PAGINATION_RESULT.json"),
            "pagination_closure_evidence_sha256": sha(E / "09_evidence/PAGINATION_CLOSURE_EVIDENCE.json"),
            "oracle_reference_probe_sha256": sha(E / "09_evidence/ORACLE_REFERENCE_PROBE.json"),
            "native_identity_audit_sha256": sha(E / "09_evidence/NATIVE_IDENTITY_AUDIT.json"),
            "fairness_receipt_sha256": sha(E / "01_protocol/memory/FAIRNESS_RECEIPT.json"),
            "fairness_verification_sha256": sha(E / "01_protocol/memory/FAIRNESS_VERIFICATION.json"),
            "arm_equivalence_matrix_sha256": sha(E / "01_protocol/ARM_EQUIVALENCE_MATRIX_v1.2.csv"),
            "formal_arm_order_sha256": sha(order_path),
            "native_identity": "PASS",
            "native_parent_child": "PASS",
            "native_task_delivery": "PASS_WITH_EXPLICIT_SEND_MESSAGE",
            "upstream_terra_failure": "NOT_OBSERVED",
        },
        "fairness": {
            **old_protocol.get("fairness", {}),
            "status": fairness.get("status"),
            "receipt_sha256": sha(E / "01_protocol/memory/FAIRNESS_RECEIPT.json"),
            "verification_sha256": sha(E / "01_protocol/memory/FAIRNESS_VERIFICATION.json"),
            "trusted_oracle_authority_metadata_visible": True,
            "hidden_oracle_test_content_exposed": False,
            "same_source_experience": True,
            "same_scope_and_version": True,
            "same_historical_counterexamples": True,
            "same_tool_interaction_opportunity": "INTERFACE_ASYMMETRY_DECLARED; GRAPH USES FOUR AEVORA MCP TOOLS, RAW USES READ-ONLY TEXT",
        },
        "contracts": {
            "inherited_regression_count": 2109,
            "inherited_contract_count": 86,
            "historical_g23_outcomes_not_pooled": True,
            "native_multi_agent_proof_not_replaced_by_single_agent": True,
        },
        "pilot": {
            "status": "NOT_RUN",
            "readiness": "CONDITIONAL",
            "requires_user_approval": True,
            "reason": "Native identity is proven with explicit send_message, but the full native Participant adapter smoke and user review are still required; no Pilot or formal episode was started.",
        },
        "prohibitions": sorted(set(old_protocol.get("prohibitions", []) + [
            "NO_PILOT_BEFORE_USER_APPROVAL",
            "NO_SINGLE_AGENT_RESULT_PRESENTED_AS_NATIVE_MULTI_AGENT",
            "NO_UPSTREAM_TERRA_FAILURE_CLAIM_WITHOUT_DIRECT_LOG",
        ])),
    })
    protocol_path = E / "01_protocol/PRE_REGISTERED_PROTOCOL_v1.2.json"
    write(protocol_path, v12_protocol)
    (E / "01_protocol/PRE_REGISTRATION_v1.2.md").write_text(
        f"""# G24 DeepSeek Pre-Registration v1.2

**Status:** `FROZEN_ANALYSIS_PROTOCOL_PILOT_CONDITIONAL_PENDING_NATIVE_ADAPTER_SMOKE`  
**Frozen at:** `{frozen_at}`  
**Source commit / tree:** `{commit}` / `{tree}`  
**Previous protocol:** v1.1 `{v11_sha}` (preserved, not rewritten)

## Runtime decision

The D2/D3 closure verifies real DeepSeek model calls, code modification, public
tests, four Aevora MCP tools, pagination, and isolated Oracle execution. The
official session rollout also contains a real `spawn_agent` function call,
direct child session, child terminal event, and parent receipt for both
`multi_agent_v1` and `multi_agent_v2`. However, the child task body is present
only as `encrypted_content` in the default spawn path, and those children
returned generic answers. An explicit `spawn_agent` plus `send_message` probe
returned the exact `CHILD_OK` terminal result and a parent receipt. A
`fork_turns=all` diagnostic demonstrated recursive spawning and hit the agent
thread limit.

Therefore native identity and task delivery are recorded as `PASS` for the
explicit `send_message` path. The default spawn-only path remains
`NOT_VERIFIED` for task delivery. The adapted profile
`G24_DEEPSEEK_01_SINGLE_AGENT_FALLBACK` is a contingency. It is not a native Multi-Agent proof
and cannot be pooled with G23 Terra results. Native runtime integration still
requires review before it can be chosen for Pilot.

## Design

Pilot `{', '.join(item['block'] for item in pilot)}` remains separate. Formal
blocks `{', '.join(item['block'] for item in new_formal)}` retain task
conditions, seeds, journals, and faults. The formal order was regenerated with
seed `{SEED}` under a constrained rejection algorithm. Position counts are:
`{json.dumps(counts, sort_keys=True)}`.

All formal runs must use the same model and runtime profile. The primary
endpoints, ITT denominator, NO_PATCH handling, infrastructure-failure rules,
and no-post-hoc-expansion rule are unchanged from v1.1. NEGATIVE_TRANSFER has
only three formal blocks and is exploratory.

## Closure evidence

- Pagination: `PASS`, 24,576-byte test fixture, 7 pages, 87 entries, terminal
  page, reconstructed/document SHA equal. Production 196,608-byte budget was
  not changed.
- Native identity audit: `PASS`; task delivery:
  `PASS_WITH_EXPLICIT_SEND_MESSAGE`; default spawn-only task delivery:
  `NOT_VERIFIED`.
- Oracle boundary: `VERIFIED` for the inspected Participant mount; hidden
  oracle test content and Host credentials were not exposed.
- Calibration: inherited 27-run gate `PASS`; not rerun.
- Pilot: `NOT_RUN`; formal: `NOT_RUN`.
""",
        encoding="utf-8",
    )
    (E / "01_protocol/EXPERIMENT_PROTOCOL_CHANGELOG.md").write_text(
        f"""# G24 Protocol Changelog

## v1.2 — D2/D3 closure freeze

Changes from v1.1 (`{v11_sha}`):

1. Preserved v1.1 and `TASKS_FROZEN.json` without rewriting them.
2. Added a new formal order generated with seed `{SEED}` and constrained
   position balance `{json.dumps(counts, sort_keys=True)}`. Graph is no longer
   always last.
3. Recorded session-level native identity and the explicit `send_message`
   child result as observed. The default spawn-only path remained generic and
   is not treated as task-capable.
4. Recorded pagination as PASS using the sub-production 24,576-byte fixture;
   the original 12 KiB failure and production 196,608-byte limit are retained.
5. Split Oracle authority metadata visibility from hidden test-content
   exposure. `trusted_oracle_authority_metadata_visible=true`,
   `hidden_oracle_test_content_exposed=false`.
6. Added the explicit `G24_DEEPSEEK_01_SINGLE_AGENT_FALLBACK` candidate as a
   contingency, labeled adapted runtime and not a native Multi-Agent result.
7. Set Pilot readiness to `CONDITIONAL` pending user review. No Pilot or formal
   episode was executed.

## v1.1

Inherited calibration/fairness protocol. Its hash and task manifest are
preserved in the v1.2 evidence map.
""",
        encoding="utf-8",
    )
    print(json.dumps({
        "status": "PASS",
        "protocol_sha256": sha(protocol_path),
        "tasks_sha256": sha(tasks_v12_path),
        "episode_manifest_sha256": sha(E / "01_protocol/EPISODE_MANIFEST_v1.2.csv"),
        "formal_arm_order_sha256": sha(order_path),
        "position_counts": counts,
        "native_identity": "PASS",
        "native_parent_child": "PASS",
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
