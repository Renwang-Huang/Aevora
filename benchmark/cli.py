"""Unified Phase 1 command line; JSON stdout is suitable for automation."""
import argparse
from dataclasses import asdict
import json
from pathlib import Path
import sys
from benchmark.manifest import list_manifests, load_manifest, private_config
from benchmark.runner import BenchmarkRunner
from benchmark.registry import get_episode

EXIT = {"PASS": 0, "PREPARED": 0, "RESET": 0, "FAIL": 1, "ERROR": 2, "TIMEOUT": 3, "NOT_IMPLEMENTED": 4, "CANCELLED": 5}


def optional_positive_number(value):
    if value.lower() == "none":
        return None
    try:
        result = float(value)
        import math
        if not math.isfinite(result) or result <= 0:
            raise ValueError
        return result
    except ValueError as error:
        raise argparse.ArgumentTypeError("Expected a positive finite number or 'none'") from error


def optional_positive_integer(value):
    if value.lower() == "none":
        return None
    try:
        result = int(value)
        if result <= 0:
            raise ValueError
        return result
    except ValueError as error:
        raise argparse.ArgumentTypeError("Expected a positive integer or 'none'") from error


def main(argv=None):
    parser = argparse.ArgumentParser(prog="orderflow")
    parser.add_argument("--runs-root", type=Path, help="Host-only run archive root")
    sub = parser.add_subparsers(dest="action", required=True)
    sub.add_parser("list")
    for action in ("validate", "prepare", "evaluate", "reset"):
        command = sub.add_parser(action)
        command.add_argument("--episode", required=True)
        if action in ("validate", "prepare", "evaluate"):
            command.add_argument("--variant", help="Registered scenario variant")
        if action == "evaluate":
            command.add_argument("--submission", type=Path)
            command.add_argument("--run-id")
            command.add_argument("--timeout", type=float)
    sub.add_parser("report").add_argument("--run-id", required=True)
    native = sub.add_parser("run-codex", help="Fresh isolated native Codex session and independent evaluation")
    native.add_argument("--episode", required=True)
    native.add_argument("--variant")
    native.add_argument("--model")
    native.add_argument("--provider", choices=("gateway", "legacy"), default="gateway")
    native.add_argument("--reasoning-effort", choices=("max", "xhigh", "high", "medium", "low"))
    native.add_argument("--request-budget", type=optional_positive_integer, default=160,
                        help="Total model request limit; 'none' requires completion-aware")
    native.add_argument("--agent-timeout", type=optional_positive_number, default=900,
                        help="Bounded total seconds (default 900); use 'none' for completion-aware")
    native.add_argument("--completion-policy", choices=("bounded", "completion-aware"), default="bounded",
                        help="Completion-aware has no total wall-clock deadline; requires --agent-timeout none")
    native.add_argument("--agent-mode", choices=("single", "multi"), default="multi",
                        help="Official native subagent capability: single disables it in configuration")
    native.add_argument("--stream-idle-timeout-ms", type=int,
                        help="Official Codex stream idle limit, not a total runtime limit")
    native.add_argument("--connect-timeout-seconds", type=float, default=30,
                        help="Gateway socket/TLS connection limit, not total response duration")
    native.add_argument("--evaluation-timeout", type=float)
    native.add_argument("--experience", choices=("disabled", "aevora"), default="disabled",
                        help="Explicit Aevora MCP opt-in; trusted Aevora launcher required")
    native.add_argument("--experience-profile", choices=("aevora.mcp/1.2", "aevora.mcp/2.0.0-rc2"), default="aevora.mcp/1.2")
    native.add_argument("--experience-v2-bootstrap", type=Path,
                        help="Host-only owned bootstrap file; never mounted into Participant")
    native.add_argument("--enable-experience-proposals", action="store_true")
    for name in ("status", "snapshot", "cancel"):
        control = sub.add_parser(name, help="Trusted-host live runtime control")
        control.add_argument("--run-id", required=True)
        if name == "cancel":
            control.add_argument("--reason", default="operator request")
    exporter = sub.add_parser("export", help="Read-only Full Archive to independent Audit-Lite ZIP")
    exporter.add_argument("--full-archive", type=Path, required=True)
    exporter.add_argument("--output", type=Path, required=True)
    exporter.add_argument("--run-id", action="append", dest="run_ids")
    exporter.add_argument("--created-at", help="Explicit UTC export timestamp for deterministic output")
    for name in ("verify", "inspect"):
        sub.add_parser(name, help="Offline Audit-Lite validation").add_argument("bundle", type=Path)
    shell = sub.add_parser("shell")
    shell.add_argument("--run-id", required=True)
    shell.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)
    try:
        if args.action == "list":
            result = [{"id": m.id, "version": m.version, "status": m.status} for m in list_manifests()]
        elif args.action == "validate":
            manifest = load_manifest(args.episode)
            private_config(args.episode)
            if manifest.status == "IMPLEMENTED" and args.variant is not None and args.variant not in get_episode(manifest.id).variants:
                raise ValueError("Unknown scenario variant")
            result = {"episode_id": manifest.id, "manifest_valid": True, "status": manifest.status,
                      "evaluation_status": "READY" if manifest.status == "IMPLEMENTED" else "NOT_IMPLEMENTED"}
        elif args.action in {"export", "verify", "inspect"}:
            from benchmark.evidence_export import export_archive, verify_bundle, inspect_bundle
            if args.action == "export":
                result = export_archive(args.full_archive, args.output, run_ids=args.run_ids, created_at=args.created_at)
            else:
                result = (verify_bundle if args.action == "verify" else inspect_bundle)(args.bundle)
        else:
            runner = BenchmarkRunner(args.runs_root)
            if args.action in {"status", "snapshot", "cancel"}:
                from integrations.runtime_control import status_run, cancel_run
                directory = runner._run_dir(args.run_id)
                result = cancel_run(directory, reason=args.reason) if args.action == "cancel" else status_run(directory)
                import os
                result = {**result, "control_query": {"source": "trusted_cli_observer",
                    "caller_pid_namespace": os.readlink("/proc/self/ns/pid")}}
            elif args.action == "shell":
                command = args.command
                if command and command[0] == "--":
                    command = command[1:]
                return runner.sandbox(args.run_id, command or ["/usr/bin/bash"])
            elif args.action == "report":
                result = runner.report(args.run_id)
            elif args.action == "evaluate":
                result = runner.evaluate(args.episode, args.submission, run_id=args.run_id, timeout=args.timeout, variant=args.variant)
            elif args.action == "prepare":
                result = runner.prepare(args.episode, args.variant)
            elif args.action == "run-codex":
                if load_manifest(args.episode).status == "PLANNED":
                    result = runner.prepare(args.episode, args.variant)
                else:
                    from integrations.codex_agent import CodexConfig
                    result = runner.run_agent(args.episode,
                        config=CodexConfig.from_environment(model=args.model, timeout_seconds=args.agent_timeout,
                            provider_id=args.provider, reasoning_effort=args.reasoning_effort,
                            request_budget=args.request_budget, completion_policy=args.completion_policy,
                            agent_mode=args.agent_mode, stream_idle_timeout_ms=args.stream_idle_timeout_ms,
                            connect_timeout_seconds=args.connect_timeout_seconds, experience_mode=args.experience,
                            enable_experience_proposals=args.enable_experience_proposals,
                            experience_protocol_profile=args.experience_profile,
                            experience_v2_bootstrap_path=args.experience_v2_bootstrap),
                        variant=args.variant, evaluation_timeout=args.evaluation_timeout)
            else:
                result = getattr(runner, args.action)(args.episode)
        print(json.dumps(result, indent=2, sort_keys=True))
        # Read-only status queries succeed independently of the stored outcome.
        if args.action in {"report", "status", "snapshot"}:
            return 0
        status = result.get("overall_status", result.get("evaluation_status", result.get("status"))) if isinstance(result, dict) else None
        return EXIT.get(status, 0)
    except (OSError, ValueError, RuntimeError, TypeError, KeyError) as error:
        print(json.dumps({"status": "ERROR", "error": f"{type(error).__name__}: {error}"}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
