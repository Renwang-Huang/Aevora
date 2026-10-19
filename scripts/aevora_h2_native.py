"""Serial H2 native challenge and separate readback; Codex owns delegation."""
from __future__ import annotations
import argparse
from dataclasses import asdict
from hashlib import sha256
import json
import os
from pathlib import Path
import shutil
import sys
import re

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.aevora_h2_audit import sources, write, now, digest
from scripts.m11_calibration import collect_trial, tls_probe, verify_freeze
from benchmark.evidence_export import _read_regular
from benchmark.evidence_verify import load_json


def receipt(archive, relative):
    value = load_json(_read_regular(archive, relative, max_bytes=32 * 1024**2))
    if not isinstance(value, dict):
        raise ValueError("Admission requires an actual object receipt")
    return value


def validate_gate_receipts(values):
    gates = set()
    boundary = False
    for value in values:
        name = value.get("gate")
        if name == "H2-G0":
            if value.get("verdict") != "PASS_REQUIRED_FUNCTIONAL_EVIDENCE":
                raise ValueError("G0 required functional evidence did not pass")
            gates.add(name)
        elif name in {"H2-G1", "H2-G2"}:
            if value.get("status") != "PASS":
                raise ValueError("Mandatory gate did not pass: " + name)
            gates.add(name)
        elif value.get("version") == "aevora.h2-dv02-security/1.0":
            if value.get("status") != "PASS" or value.get("mandatory_boundary_result") != "PASS":
                raise ValueError("Actual D-v02 participant boundary did not pass")
            boundary = True
        else:
            raise ValueError("Unrecognized admission receipt")
    if gates != {"H2-G0", "H2-G1", "H2-G2"} or not boundary:
        raise ValueError("Admission requires G0, G1, G2 and the actual D-v02 boundary")


def verify_gate_links(archive, value):
    links = value.get("checks") if value.get("gate") != "H2-G0" else value.get("evidence")
    if value.get("version") == "aevora.h2-dv02-security/1.0":
        return
    if not isinstance(links, dict) or not links:
        raise ValueError("A gate must pin its actual underlying evidence")
    for relative, metadata in links.items():
        expected = metadata.get("sha256") if isinstance(metadata, dict) else metadata
        if not isinstance(expected, str) or not re.fullmatch(r"[0-9a-f]{64}", expected):
            raise ValueError("Invalid gate evidence SHA256")
        actual = sha256(_read_regular(archive, relative)).hexdigest()
        if actual != expected:
            raise ValueError("Underlying gate evidence changed: " + relative)


def verify_security_source(value, rows):
    pinned = value.get("source_sha256")
    if not isinstance(pinned, dict) or not pinned:
        raise ValueError("Actual security source epoch is required")
    for relative, expected in pinned.items():
        source = "aevora_core/src/" + relative if relative.startswith("aevora/") else relative
        if source not in rows or rows[source]["sha256"] != expected:
            raise ValueError("Security boundary source changed: " + source)


def observation_inputs(participant):
    """App, all public Python tests and supplied task documents; not Agent notes."""
    from benchmark.participant import _python_tree, _read_regular as read_document, MAX_PUBLIC_DOCUMENT_BYTES
    files = {}
    for directory in ("app", "tests/public"):
        for relative, data in _python_tree(participant / directory).items():
            files[directory + "/" + relative] = sha256(data).hexdigest()
    for name in ("AGENTS.md", "ISSUE.md", "TASK.md", "public.json"):
        files[name] = sha256(read_document(participant / name, MAX_PUBLIC_DOCUMENT_BYTES)).hexdigest()
    return files


def validate_release(archive, relative, source_commit, rows):
    if not re.fullmatch(r"[0-9a-f]{40}", source_commit):
        raise ValueError("A complete actual local release commit is required")
    release = receipt(archive, relative)
    manifest_relative = str(Path(relative).parent / "SOURCE_MANIFEST.json")
    manifest = receipt(archive, manifest_relative)
    if (release.get("commit") != source_commit or manifest.get("commit") != source_commit
            or manifest.get("source_files") != rows
            or release.get("source_tree_sha256") != manifest.get("source_tree_sha256")
            or release.get("git_tree") != manifest.get("git_tree")):
        raise ValueError("Release receipt does not bind this exact source epoch")
    commands = release.get("command_results")
    if not isinstance(commands, list) or not commands or any(row.get("exit_code") != 0 for row in commands):
        raise ValueError("Release contains a failed or missing actual Git command")
    return manifest_relative


def freeze(archive, gate_files, regression, corpus, source_commit, release_receipt):
    checks = {}
    values = [receipt(archive, relative) for relative in gate_files]
    validate_gate_receipts(values)
    for value in values:
        verify_gate_links(archive, value)
    for relative in gate_files:
        checks[relative] = digest(archive / relative)
    if receipt(archive, regression).get("exit_code") != 0:
        raise ValueError("Final current regression did not pass")
    checks[regression] = digest(archive / regression)
    corpus_data = receipt(archive, corpus)
    if corpus_data.get("status") != "PASS":
        raise ValueError("Reviewed isolated historical corpus did not pass")
    checks[corpus] = digest(archive / corpus)
    rows = sources()
    for value in values:
        if value.get("version") == "aevora.h2-dv02-security/1.0":
            verify_security_source(value, rows)
    manifest_relative = validate_release(archive, release_receipt, source_commit, rows)
    manifest_data = receipt(archive, manifest_relative)
    actual_tree = sha256(json.dumps(rows, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    if manifest_data.get("source_tree_sha256") != actual_tree:
        raise ValueError("Release source tree digest does not match its actual file inventory")
    checks[release_receipt] = digest(archive / release_receipt)
    checks[manifest_relative] = digest(archive / manifest_relative)
    snapshot = archive / "g3" / "frozen_source_snapshot"
    snapshot.mkdir(parents=True, exist_ok=False)
    for relative, metadata in rows.items():
        destination = snapshot / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / relative, destination)
        destination.chmod(metadata["mode"])
        if digest(destination) != metadata["sha256"]:
            raise ValueError("Source changed during freeze")
    manifest = archive / "g3" / "SOURCE_TRUST_MANIFEST.json"
    write(manifest, {"files": {"frozen_source_snapshot/" + name: row["sha256"] for name, row in rows.items()},
        "created_at": now(), "source_commit": source_commit,
        "scope": "Trusted local source authority; no external attestation"})
    write(archive / "g3" / "LIVE_GATE.json", {"status": "PASS", "gate": "H2-G3_NATIVE_ADMISSION", "checks": checks,
        "frozen_source_sha256": {name: row["sha256"] for name, row in rows.items()},
        "source_manifest_sha256": digest(manifest), "source_commit": source_commit,
        "episode": "D-V02", "variant": "v02", "provider": "gateway", "model": "gpt-5.6-terra",
        "reasoning_effort": "max", "experience": "aevora", "completion_policy": "completion-aware",
        "agent_timeout": None, "request_budget": None, "parallel_trials": 1, "maximum_model_concurrency": 4,
        "operator_cancel": "Original trusted CLI cancel remains enabled", "recorded_at": now()})
    print(json.dumps({"status": "PASS", "frozen_files": len(rows), "manifest_sha256": digest(manifest)}))


def admitted(archive):
    gate = json.loads((archive / "g3" / "LIVE_GATE.json").read_text())
    if gate.get("status") != "PASS":
        raise ValueError("Native admission did not pass")
    for relative, expected in gate["checks"].items():
        if digest(archive / relative) != expected:
            raise ValueError("Admission evidence changed: " + relative)
    if digest(archive / "g3" / "SOURCE_TRUST_MANIFEST.json") != gate["source_manifest_sha256"]:
        raise ValueError("Source trust manifest changed")
    verify_freeze(gate)
    if sys.version_info < (3, 12) or not os.environ.get("ORDERFLOW_CODEX_BINARY") or not os.environ.get("ORDERFLOW_GATEWAY_SECRET_PATH"):
        raise ValueError("Use ORDERFLOW_ENABLE_CODEX=1 with the trusted H2 launcher")
    return gate


def challenge(archive, label):
    if not label.isidentifier():
        raise ValueError("Use a unique simple trial label")
    gate = admitted(archive)
    live = archive / "g3" / "live"
    live.mkdir(exist_ok=True)
    connection = tls_probe("https://api.renwang-huang.top/v1")
    command = [sys.executable, "-m", "benchmark.h2_cli", "--runs-root", str(live / "runs"),
        "run-codex", "--episode", gate["episode"], "--variant", gate["variant"], "--provider", "gateway",
        "--model", "gpt-5.6-terra", "--reasoning-effort", "max", "--completion-policy", "completion-aware",
        "--agent-timeout", "none", "--request-budget", "none", "--agent-mode", "multi", "--experience", "aevora"]
    receipt, report = collect_trial(live / label, command, live / "runs")
    write(live / label / "verified_tls.json", connection)
    verify_freeze(gate)
    write(live / label / "summary.json", {"receipt": receipt, "run_id": report.get("run_id"),
        "runtime_result": report.get("runtime_result", "UNAVAILABLE"),
        "evaluation_result": report.get("overall_status", "UNAVAILABLE"),
        "scope": "Actual native challenge; engineering grade is preserved, no reference substitution or causal superiority claim"})
    print(json.dumps(receipt))
    # Integration attempts remain an observation, never turn an Agent FAIL into
    # script success without an explicit result. The collector itself completed.
    return 0


def observe(archive, outcome_id):
    gate = admitted(archive)
    from benchmark.h2_cli import register_h2
    register_h2()
    from benchmark.runner import BenchmarkRunner
    from benchmark.manifest import load_manifest
    from benchmark.participant import build_participant
    from benchmark.submission import snapshot_source_tree, source_tree_sha256
    from integrations.agents import TaskInput, ExecutionContext
    from integrations.codex_agent import CodexAgentAdapter, CodexConfig
    from integrations.runtime_evidence import seal_run
    destination = archive / "g3" / "observation_session"
    destination.mkdir(exist_ok=False)
    runner = BenchmarkRunner(destination / "runs")
    prepared = runner.prepare(gate["episode"], gate["variant"])
    if prepared["overall_status"] != "PREPARED":
        raise ValueError("Cannot prepare actual readback workspace")
    run = destination / "runs" / prepared["run_id"]
    participant = build_participant(run / "workspace", run / "participant", agent_mode="single")
    before = source_tree_sha256(snapshot_source_tree(participant))
    public_before = observation_inputs(participant)
    manifest = load_manifest(gate["episode"])
    task = ("This is a read-only Aevora evidence observation, not a repair challenge. Do not edit code or tests. "
            "Read the public task/environment, then use the real Aevora MCP resolve_experience and build_evidence_bundle "
            "tools. Report actual query/snapshot/evidence/revision IDs and WHEN/WHY. Check whether independently "
            "verified outcome " + outcome_id + " is visible, keeping UNKNOWN causal attribution. Do not infer "
            "task success from the outcome alone. Do not query private files or databases. A NO_PATCH repair-adapter "
            "result is expected for this explicitly read-only observation. Finish naturally after tools and summary.")
    config = CodexConfig.from_environment(completion_policy="completion-aware", timeout_seconds=None,
        request_budget=None, agent_mode="single", experience_mode="aevora", model="gpt-5.6-terra", reasoning_effort="max")
    try:
        result = CodexAgentAdapter(config).execute(TaskInput(manifest.id, manifest.version, task, asdict(manifest)),
            ExecutionContext(run.name, str(participant), constraints={"archive": str(run), "baseline": str(run / "workspace")}))
        metadata = result.runtime_metadata
        after = source_tree_sha256(snapshot_source_tree(participant))
        public_after = observation_inputs(participant)
        unchanged = public_before == public_after
        complete = metadata.get("trace_observations", {}).get("integrity", {}).get("status") == "COMPLETE"
        summary = {"kind": "NEW_SESSION_READ_ONLY_EVIDENCE_OBSERVATION", "run_id": run.name,
            "session_id": metadata.get("session_id", "UNAVAILABLE"), "thread_id": metadata.get("thread_id", "UNAVAILABLE"),
            "adapter_runtime_result": metadata.get("runtime_result"), "adapter_failure_kind": metadata.get("failure_kind"),
            "runtime_contract": "Repair Adapter NO_PATCH retained; no engineering Outcome minted",
            "evaluation_result": "NOT_EXECUTED", "source_before_sha256": before, "source_after_sha256": after,
            "source_unchanged": before == after, "native_turn_complete": complete, "target_outcome_id": outcome_id,
            "read_only_public_input_scope": "app/**/*.py, tests/public/**/*.py, AGENTS.md, ISSUE.md, TASK.md, public.json",
            "public_input_before_sha256": public_before, "public_input_after_sha256": public_after,
            "public_inputs_unchanged": unchanged,
            "session_observation_status": "COMPLETE" if complete and unchanged and metadata.get("failure_kind") == "NO_PATCH" else "INCOMPLETE",
            "updated_evidence_visibility": "UNVERIFIED_PENDING_RAW_TRACE_REVIEW", "mental_influence": "UNVERIFIED"}
        write(run / "observation_report.json", summary)
    finally:
        state = run / "codex-state"
        if state.exists():
            shutil.rmtree(state)
        seal_run(run)
    verify_freeze(gate)
    print(json.dumps(summary))
    return 0 if summary["session_observation_status"] == "COMPLETE" else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="operation", required=True)
    f = commands.add_parser("freeze"); f.add_argument("archive", type=Path)
    f.add_argument("--gate-file", action="append", required=True); f.add_argument("--regression", required=True)
    f.add_argument("--corpus", required=True); f.add_argument("--source-commit", required=True)
    f.add_argument("--release-receipt", required=True)
    r = commands.add_parser("run"); r.add_argument("archive", type=Path); r.add_argument("--trial", required=True)
    o = commands.add_parser("observe"); o.add_argument("archive", type=Path); o.add_argument("--outcome-id", required=True)
    args = parser.parse_args()
    if args.operation == "freeze":
        freeze(args.archive.absolute(), args.gate_file, args.regression, args.corpus, args.source_commit, args.release_receipt)
        raise SystemExit(0)
    raise SystemExit(challenge(args.archive.absolute(), args.trial) if args.operation == "run"
                     else observe(args.archive.absolute(), args.outcome_id))
