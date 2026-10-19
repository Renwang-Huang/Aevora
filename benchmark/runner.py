"""Load -> Prepare -> Execute -> Evaluate -> Report -> Reset lifecycle."""
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
from uuid import UUID, uuid4

from app.service import OrderFlow
from benchmark.manifest import ROOT, load_manifest, manifest_digest, private_config
from benchmark.sandbox import runtime_python, sandbox_command
from benchmark.registry import get_episode
from evaluator.fingerprints import evaluation_fingerprints
from integrations.agents import (ExecutionContext, ExecutionTrace, ManualSubmissionAdapter,
                                  SubmissionArtifact, TaskInput, utc_timestamp)
from integrations.experience import DisabledExperienceAdapter


def write_json(path: Path, data):
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")
    temporary.replace(path)


def copy_app(source: Path, destination: Path):
    source = source.absolute()
    if source.is_symlink():
        raise ValueError("Submission root must not be a symlink")
    app = source / "app" if (source / "app").exists() else source
    if not app.is_dir() or not (app / "service.py").is_file():
        raise ValueError("Submission must contain app/service.py or be the app directory")
    total = 0
    entries = []
    for path in sorted(app.rglob("*")):
        if path.is_symlink():
            raise ValueError("Submission symlinks are forbidden")
        if path.is_file() and path.suffix == ".py":
            total += path.stat().st_size
            entries.append(path)
    if total > 2_000_000 or len(entries) > 100:
        raise ValueError("Submission exceeds Phase 1 source limits")
    destination.mkdir(parents=True)
    for path in entries:
        target = destination / path.relative_to(app)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(path.read_bytes())


def apply_patch(candidate: Path, patch: Path, *, expected_tree=None):
    from benchmark.submission import apply_verified_patch
    return apply_verified_patch(candidate, patch, expected_tree=expected_tree)


class BenchmarkRunner:
    def __init__(self, runs_root: Path | None = None):
        self.runs_root = (runs_root or ROOT / "runs").absolute()
        self.runs_root.mkdir(parents=True, exist_ok=True)

    def _run_dir(self, run_id):
        if str(UUID(run_id)) != run_id:
            raise ValueError("Run ID must be a canonical UUID")
        directory = self.runs_root / run_id
        if directory.is_symlink():
            raise ValueError("Run directory must not be a symlink")
        return directory

    def _event(self, directory, event_type, payload=None):
        event = ExecutionTrace(directory.name, "runner", event_type, payload or {}).to_dict()
        with (directory / "execution_trace.jsonl").open("a") as trace:
            trace.write(json.dumps(event) + "\n")

    def _new(self, episode, variant=None):
        manifest = load_manifest(episode)
        config = private_config(episode)
        registration = get_episode(episode) if manifest.status == "IMPLEMENTED" else None
        if registration and variant is not None and variant not in registration.variants:
            raise ValueError(f"Unknown {episode} variant: {variant}")
        directory = self.runs_root / str(uuid4())
        directory.mkdir()
        write_json(directory / "public_manifest.json", asdict(manifest))
        report = {
            "schema_version": "1.1.0", "episode_id": manifest.id, "scenario_version": manifest.version,
            "run_id": directory.name, "implementation_status": manifest.status,
            "manifest_sha256": manifest_digest(manifest),
            "overall_status": "PREPARED", "started_at": utc_timestamp(), "ended_at": None,
            "submission": None, "test_results": None, "execution_errors": [], "artifacts": {},
            "experience": DisabledExperienceAdapter().metadata(),
            "agent": {"adapter": "manual", "execution": "UNAVAILABLE", "assignments": None,
                      "metrics": None, "trace": None},
            "runtime": {"python": sys.version, "sqlite": __import__("sqlite3").sqlite_version,
                        "isolation": "bubblewrap", "network_isolated": True},
            "lifecycle": ["LOAD"],
            "scenario_variant": variant or (registration.default_variant if registration else None),
            "scenario_metadata": asdict(manifest),
            "fingerprints": evaluation_fingerprints(episode, registration, config) if registration else None,
        }
        self._event(directory, "run.loaded", {"episode_id": episode})
        write_json(directory / "evaluation_report.json", report)
        return directory, manifest, report

    def prepare(self, episode, variant=None):
        directory, manifest, report = self._new(episode, variant)
        if manifest.status == "PLANNED":
            return self._finish(directory, report, "NOT_IMPLEMENTED")
        try:
            self._prepare_workspace(directory, manifest, report["scenario_variant"])
            report["lifecycle"].append("PREPARE")
            report["artifacts"]["workspace"] = str(directory / "workspace")
            self._event(directory, "run.prepared")
            write_json(directory / "evaluation_report.json", report)
            return report
        except Exception as error:
            report["execution_errors"].append(f"{type(error).__name__}: {error}")
            return self._finish(directory, report, "ERROR")

    def _prepare_workspace(self, directory, manifest, variant=None):
        registration = get_episode(manifest.id)
        workspace = registration.build(directory / "workspace", variant)
        public_tests = workspace / "tests" / "public"
        public_tests.mkdir(parents=True)
        for test in registration.public_tests:
            shutil.copy(test, public_tests)
        write_json(workspace / "public.json", asdict(manifest))
        (workspace / "TASK.md").write_text(manifest.public_task["description"] + "\n\n" +
                                             "\n".join("- " + c for c in manifest.public_task["constraints"]) + "\n")
        # Initialize trusted fixture, do not execute the defective submission on the host.
        flow = OrderFlow(workspace / "business.sqlite")
        flow.initialize(manifest.initial_state["stock"], reset=True)

    def evaluate(self, episode, submission: Path | None = None, *, run_id=None, timeout=None, variant=None):
        if run_id:
            directory = self._run_dir(run_id)
            report = self.report(run_id)
            manifest = load_manifest(episode)
            if report["episode_id"] != episode or report["manifest_sha256"] != manifest_digest(manifest):
                raise ValueError("Run and current manifest do not match")
            if report["overall_status"] != "PREPARED":
                raise ValueError("Run is already finalized; create a new run to repeat")
            if variant is not None and variant != report["scenario_variant"]:
                raise ValueError("Variant does not match prepared run")
        else:
            report = self.prepare(episode, variant)
            directory = self._run_dir(report["run_id"])
            manifest = load_manifest(episode)
        if report["overall_status"] != "PREPARED":
            return report
        try:
            source = submission or directory / "workspace"
            kind = "workspace" if source.is_dir() else "patch"
            patch_bytes = None
            if kind == "patch":
                from benchmark.submission import read_submission_patch
                patch_bytes = read_submission_patch(source)
            # Only app/ is an accepted workspace source; tests and environment files are ignored.
            artifact_source = source / "app" if kind == "workspace" and (source / "app").is_dir() else source
            result = ManualSubmissionAdapter(SubmissionArtifact(kind, str(artifact_source))).execute(
                TaskInput(episode, manifest.version, manifest.public_task["description"]),
                ExecutionContext(directory.name, str(directory / "workspace")))
            report["submission"] = {"kind": kind, "original_reference": str(source.absolute()),
                                    "reference": str(artifact_source.absolute()), "sha256": None}
            for event in result.trace:
                with (directory / "execution_trace.jsonl").open("a") as trace:
                    trace.write(json.dumps(event.to_dict()) + "\n")
            if result.errors:
                raise ValueError("; ".join(result.errors))
            report["submission"].update(asdict(result.submission))
            candidate = directory / "candidate"
            if kind == "patch":
                get_episode(episode).build(candidate, report["scenario_variant"])
                if hashlib.sha256(patch_bytes).hexdigest() != result.submission.sha256:
                    raise ValueError("SUBMISSION_INTEGRITY_ERROR: patch changed during receipt")
                (directory / "patch.diff").write_bytes(patch_bytes)
                expected = directory / "participant" if report.get("agent", {}).get("adapter") == "codex_exec" else None
                integrity = apply_patch(candidate, directory / "patch.diff", expected_tree=expected)
                extracted = report.get("agent", {}).get("extracted_submission")
                if report.get("agent", {}).get("adapter") == "codex_exec" and not isinstance(extracted, dict):
                    raise ValueError("SUBMISSION_INTEGRITY_ERROR: automatic submission lacks sealed extraction metadata")
                if extracted is not None:
                    for field, saved in (("patch_sha256", extracted.get("sha256")),
                                         ("baseline_tree_sha256", extracted.get("baseline_tree_sha256")),
                                         ("expected_tree_sha256", extracted.get("expected_tree_sha256"))):
                        if not saved or integrity.get(field) != saved:
                            raise ValueError("SUBMISSION_INTEGRITY_ERROR: staged " + field + " differs from sealed extraction")
                    from benchmark.submission import snapshot_source_tree
                    actual_files = {name: hashlib.sha256(data).hexdigest() for name, data in snapshot_source_tree(candidate).items()}
                    if extracted.get("expected_files_sha256") != actual_files:
                        raise ValueError("SUBMISSION_INTEGRITY_ERROR: per-file extraction identities differ")
                    if report["agent"].get("submission_sha256") != integrity["patch_sha256"]:
                        raise ValueError("SUBMISSION_INTEGRITY_ERROR: runtime artifact identity changed")
                report["submission_integrity"] = integrity
                report["submission_integrity_status"] = "PASS"
                report["artifacts"]["patch"] = str(directory / "patch.diff")
            else:
                candidate.mkdir()
                from benchmark.submission import snapshot_source_tree, source_tree_sha256
                expected = snapshot_source_tree(source, app_directory=not (source / "app").is_dir())
                copy_app(source, candidate / "app")
                applied = snapshot_source_tree(candidate, require_only_python=True)
                if expected != applied:
                    raise ValueError("SUBMISSION_INTEGRITY_ERROR: staged workspace differs from submission")
                report["submission_integrity"] = {"baseline_tree_sha256": "NOT_APPLICABLE", "patch_sha256": "NOT_APPLICABLE",
                    "expected_tree_sha256": source_tree_sha256(expected), "applied_candidate_tree_sha256": source_tree_sha256(applied)}
                report["submission_integrity_status"] = "PASS"
            digest = ManualSubmissionAdapter(SubmissionArtifact("workspace", str(candidate))).execute(
                TaskInput(episode, manifest.version, manifest.public_task["description"]),
                ExecutionContext(directory.name, str(candidate))).submission.sha256
            report["submission"]["evaluated_sha256"] = digest
            report["lifecycle"].append("EXECUTE")
            self._event(directory, "submission.staged", {"sha256": digest})
            from evaluator.runner import evaluate
            config = private_config(episode)
            before = evaluation_fingerprints(episode, get_episode(episode), config)
            if before != report["fingerprints"]:
                raise ValueError("Trusted evaluator/fixture environment changed after preparation; create a fresh run")
            if timeout is not None and not 0 < timeout <= config["timeout_seconds"]:
                raise ValueError("Timeout override must be positive and may only reduce the limit")
            evaluation = evaluate(candidate, directory / "artifacts", timeout_seconds=timeout or config["timeout_seconds"],
                                  suite_id=config["suite"], expected_test_count=config["expected_test_count"],
                                  expected_tests=config["expected_tests"])
            report["lifecycle"].append("EVALUATE")
            report["evaluator_status"] = evaluation["status"]
            report["evaluation_status"] = evaluation["status"]
            report["test_results"] = evaluation["test_results"]
            report["pytest_exit_code"] = evaluation["pytest_exit_code"]
            report["evaluation_started_at"] = evaluation["started_at"]
            report["evaluation_ended_at"] = evaluation["ended_at"]
            report["execution_errors"].extend(evaluation["errors"])
            report["artifacts"].update(evaluation["artifacts"])
            after = evaluation_fingerprints(episode, get_episode(episode), config)
            report["fingerprints"] = before
            report["concurrency_evidence"] = evaluation.get("concurrency_evidence", [])
            report["database_oracle"] = evaluation.get("database_oracle", [])
            report["worker_topology_evidence"] = evaluation.get("worker_topology_evidence", [])
            report["recovery_evidence"] = evaluation.get("recovery_evidence", [])
            report["recovery_coverage"] = evaluation.get("recovery_coverage", {"status": "UNVERIFIED"})
            if after != before:
                report["fingerprints_after_evaluation"] = after
                report["execution_errors"].append("Trusted evaluator/fixture environment changed during evaluation")
                return self._finish(directory, report, "ERROR")
            return self._finish(directory, report, evaluation["status"])
        except Exception as error:
            if "SUBMISSION_INTEGRITY_ERROR" in str(error):
                report["submission_integrity_status"] = "ERROR"
                report["failure_kind"] = "SUBMISSION_INTEGRITY_ERROR"
            report["execution_errors"].append(f"{type(error).__name__}: {error}")
            return self._finish(directory, report, "ERROR")

    def _finish(self, directory, report, status):
        report["overall_status"] = status
        report["ended_at"] = utc_timestamp()
        report["lifecycle"].append("REPORT")
        self._event(directory, "run.reported", {"status": status})
        # Preserve code and reports; mutable execution databases are reset/removed.
        try:
            self._reset_environment(directory, report["episode_id"])
            report["lifecycle"].append("RESET")
            report["environment_reset"] = True if (directory / "workspace").exists() else "NOT_REQUIRED"
            self._event(directory, "run.reset", {"automatic": True, "status": report["environment_reset"]})
        except Exception as error:
            report["overall_status"] = "ERROR"
            report["environment_reset"] = False
            report["execution_errors"].append(f"Environment reset failed: {type(error).__name__}: {error}")
            self._event(directory, "run.reset_failed", {"error": str(error)})
        report["ended_at"] = utc_timestamp()
        write_json(directory / "evaluation_report.json", report)
        return report

    def run_agent(self, episode, *, config, variant=None, evaluation_timeout=None):
        """Prepare a fresh native session, accept its real diff, then evaluate.

        This is lifecycle integration, not an agent scheduler. Native Codex
        owns all delegation. The existing manual submission/evaluator path
        remains the authority for validation and scoring.
        """
        from benchmark.participant import build_participant
        from integrations.codex_agent import CodexAgentAdapter
        from integrations.agents import ExecutionStatus
        report = self.prepare(episode, variant)
        if report["overall_status"] != "PREPARED":
            return report
        directory = self._run_dir(report["run_id"])
        manifest = load_manifest(episode)
        report["agent"] = {"adapter": "codex_exec", "execution": "ERROR",
                           "assignments": None, "metrics": None, "trace": None}
        report["runtime_result"] = "ERROR"
        report["evaluation_result"] = "NOT_RUN"
        report["integration_result"] = "ERROR"
        try:
            participant = build_participant(directory / "workspace", directory / "participant",
                                            agent_mode=getattr(config, "agent_mode", "multi"),
                                            child_budget=getattr(config, "max_child_agents", None))
            report["artifacts"]["participant_workspace"] = str(participant)
            self._event(directory, "participant.prepared", {"public_only": True,
                "agent_mode": getattr(config, "agent_mode", "multi")})
            report["lifecycle"].append("AGENT_EXECUTE")
            result = CodexAgentAdapter(config).execute(
                TaskInput(episode, manifest.version, manifest.public_task["description"], asdict(manifest)),
                ExecutionContext(directory.name, str(participant), constraints={
                    "archive": str(directory), "baseline": str(directory / "workspace")}))
            metadata = result.runtime_metadata or {}
            if isinstance(metadata.get("experience"), dict):
                report["experience"] = metadata["experience"]
                report["artifacts"]["aevora_mcp_events"] = str(directory / "aevora_mcp_events.jsonl")
            report["agent"].update({"execution": result.status.value,
                                   "assignments": result.agent_assignments,
                                   "metrics": result.agent_metrics,
                                   "trace": str(directory / "agent_trace.jsonl"),
                                   "data_availability": result.agent_data_availability.value,
                                   "thread_id": metadata.get("thread_id", "UNAVAILABLE"),
                                   "subagents": metadata.get("subagents", {"availability": "UNAVAILABLE"})})
            report["runtime_result"] = metadata.get("runtime_result", "ERROR")
            report["runtime_status"] = report["runtime_result"]
            report["multi_agent_status"] = metadata.get("multi_agent_result", "PARTIAL")
            report["isolation_status"] = metadata.get("isolation_status", "UNAVAILABLE")
            report["provider"] = metadata.get("provider", {"provider_id": "legacy"})
            report["agent_mode"] = metadata.get("agent_mode", getattr(config, "agent_mode", "multi"))
            report["completion_policy"] = metadata.get("completion_policy", getattr(config, "completion_policy", "bounded"))
            if metadata.get("failure_kind"):
                report["failure_kind"] = metadata["failure_kind"]
            report["artifacts"].update({"runtime_metadata": str(directory / "runtime_metadata.json"),
                                       "codex_events": str(directory / "codex_events.jsonl"),
                                       "agent_trace": str(directory / "agent_trace.jsonl")})
            for event in result.trace:
                with (directory / "execution_trace.jsonl").open("a") as trace:
                    trace.write(json.dumps(event.to_dict()) + "\n")
            report["execution_errors"].extend(result.errors)
            if result.status != ExecutionStatus.SUBMITTED:
                report["integration_result"] = "PARTIAL"
                terminal_status = {ExecutionStatus.TIMEOUT: "TIMEOUT", ExecutionStatus.CANCELLED: "CANCELLED"}.get(result.status, "ERROR")
                return self._finish(directory, report, terminal_status)
            report["artifacts"]["agent_submission"] = result.submission.reference
            report["agent"]["submission_sha256"] = result.submission.sha256
            report["agent"]["extracted_submission"] = metadata.get("submission")
            write_json(directory / "evaluation_report.json", report)
            # Evaluate the untouched native artifact; never substitute a repair.
            evaluated = self.evaluate(episode, Path(result.submission.reference), run_id=directory.name,
                                      timeout=evaluation_timeout, variant=variant)
            evaluated["evaluation_result"] = evaluated.get("evaluator_status", "NOT_RUN")
            evaluated["integration_result"] = "PASS" if (
                "EVALUATE" in evaluated["lifecycle"] and evaluated.get("environment_reset") is True
                and evaluated["overall_status"] == evaluated.get("evaluator_status")
                and "fingerprints_after_evaluation" not in evaluated
            ) else "ERROR"
            write_json(directory / "evaluation_report.json", evaluated)
            metadata["evaluation_report_id"] = directory.name
            metadata["evaluation_result"] = evaluated["evaluation_result"]
            write_json(directory / "runtime_metadata.json", metadata)
            report = evaluated
            return evaluated
        except Exception as error:
            report["execution_errors"].append(f"{type(error).__name__}: {error}")
            return self._finish(directory, report, "ERROR")
        finally:
            # No state/session inheritance. This path never contains host auth.
            state = directory / "codex-state"
            try:
                if state.is_symlink():
                    state.unlink()
                elif state.exists():
                    shutil.rmtree(state)
                report["agent_state_cleanup"] = "PASS"
            except OSError as error:
                report["agent_state_cleanup"] = "ERROR"
                report["integration_result"] = "ERROR"
                report["overall_status"] = "ERROR"
                report["execution_errors"].append(f"Agent state cleanup failed: {type(error).__name__}: {error}")
                self._event(directory, "participant.cleanup_failed", {"error": str(error)})
            report["runtime_status"] = report.get("runtime_result", "ERROR")
            report["multi_agent_status"] = report.get("multi_agent_status", "UNAVAILABLE")
            report["submission_integrity_status"] = report.get("submission_integrity_status", "NOT_RUN")
            report["evaluation_status"] = report.get("evaluation_result", "NOT_RUN")
            report["integration_status"] = report.get("integration_result", "ERROR")
            write_json(directory / "evaluation_report.json", report)
            from integrations.runtime_evidence import seal_run
            seal_run(directory)

    def _reset_environment(self, directory, episode):
        directory = self._run_dir(directory.name)
        data = directory / "artifacts" / "pytest-tmp"
        if data.is_symlink():
            data.unlink()
        elif data.exists():
            shutil.rmtree(data)
        workspace = directory / "workspace"
        if workspace.is_symlink():
            raise ValueError("Refusing to reset a symlinked workspace")
        if not workspace.exists():
            return
        stock = load_manifest(episode).initial_state["stock"]
        # Construct the database outside the writable Agent workspace, then atomically
        # replace its path. Never open a supplied DB symlink or hardlink on the host.
        with tempfile.TemporaryDirectory(prefix="reset-", dir=directory) as temporary:
            fresh = Path(temporary) / "business.sqlite"
            OrderFlow(fresh).initialize(stock, reset=True)
            for suffix in ("-wal", "-shm", "-journal"):
                (workspace / ("business.sqlite" + suffix)).unlink(missing_ok=True)
            fresh.replace(workspace / "business.sqlite")

    def report(self, run_id):
        report = json.loads((self._run_dir(run_id) / "evaluation_report.json").read_text())
        if not isinstance(report, dict) or report.get("run_id") != run_id or not all(
            key in report for key in ("episode_id", "overall_status", "manifest_sha256")
        ):
            raise ValueError("Invalid archived report")
        return report

    def reset(self, episode):
        manifest = load_manifest(episode)
        resets = []
        for file in sorted(self.runs_root.glob("*/evaluation_report.json")):
            report = json.loads(file.read_text())
            if report["episode_id"] == episode and (file.parent / "workspace").exists():
                self._reset_environment(file.parent, episode)
                self._event(file.parent, "run.reset", {"automatic": False})
                resets.append(file.parent.name)
        return {"episode_id": episode, "status": "NOT_IMPLEMENTED" if manifest.status == "PLANNED" else "RESET", "run_ids": resets}

    def sandbox(self, run_id, command):
        report = self.report(run_id)
        if report["overall_status"] != "PREPARED":
            raise ValueError("Agent sandbox requires a prepared, unfinished run")
        self._event(self._run_dir(run_id), "workspace.command_started", {"command": command})
        completed = subprocess.run(sandbox_command(self._run_dir(run_id) / "workspace", command, writable=True))
        self._event(self._run_dir(run_id), "workspace.command_finished", {"exit_code": completed.returncode})
        return completed.returncode
