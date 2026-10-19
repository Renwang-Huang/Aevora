"""Native CLI adapter. Scheduling and collaboration belong to Codex itself."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import signal
import shutil
import subprocess
import time
import tempfile
import secrets as secure_random
import math
from dataclasses import replace

from benchmark.resources import CgroupScope, ResourceWatchdog, PARTICIPANT_LIMITS, SecurityGateError
from integrations.gateway_broker import SecureModelBroker
from integrations.providers import ProviderConfig, deepseek_provider, gateway_provider
from integrations.runtime_evidence import seal_inputs, archive_native_rollouts

from benchmark.participant import NoPatchError, extract_submission
from benchmark.participant_sandbox import participant_command
from integrations.agents import (Availability, ExecutionContext, ExecutionResult,
                                 ExecutionStatus, ExecutionTrace, SubmissionArtifact,
                                 TaskInput, utc_timestamp)
from integrations.codex_trace import parse_trace, redact_jsonl, redact_text
from integrations.model_broker import ModelBroker
from integrations.runtime_control import RuntimeControl


def _provider_config(config: "CodexConfig") -> ProviderConfig:
    if "api.deepseek.com" in config.gateway_url:
        return deepseek_provider(
            base_url=config.gateway_url,
            model=config.model,
            effort=config.reasoning_effort or "max",
        )
    return gateway_provider(
        base_url=config.gateway_url,
        model=config.model,
        effort=config.reasoning_effort or "max",
    )


def _uses_deepseek_upstream(config: "CodexConfig") -> bool:
    return "api.deepseek.com" in config.gateway_url


@dataclass(frozen=True)
class CodexConfig:
    binary: Path
    auth_path: Path
    model: str = "gpt-6.1-sol"
    timeout_seconds: float | None = 900
    provider_id: str = "legacy"
    reasoning_effort: str | None = None
    gateway_url: str = "https://api.renwang-huang.top/v1"
    request_budget: int | None = 160
    max_request_concurrency: int = 4
    completion_policy: str = "bounded"
    agent_mode: str = "multi"
    stream_idle_timeout_ms: int | None = None
    connect_timeout_seconds: float = 30.0
    experience_mode: str = "disabled"
    enable_experience_proposals: bool = False
    experience_protocol_profile: str = "aevora.mcp/1.2"
    experience_v2_bootstrap_path: Path | None = None
    smoke_instruction: str | None = None
    model_catalog_path: Path | None = None
    agent_protocol: str = "v1"
    max_agent_threads: int = 8
    max_child_agents: int = 4
    required_verified_children: int = 2
    native_child_task: str | None = None

    @classmethod
    def from_environment(cls, *, model=None, timeout_seconds=900, provider_id="gateway",
                         reasoning_effort=None, request_budget=160, completion_policy="bounded",
                         agent_mode="multi", stream_idle_timeout_ms=None, connect_timeout_seconds=30.0,
                         max_request_concurrency=12, experience_mode="disabled",
                         enable_experience_proposals=False,
                         experience_protocol_profile="aevora.mcp/1.2", experience_v2_bootstrap_path=None,
                         smoke_instruction=None, model_catalog_path=None, agent_protocol=None,
                         max_agent_threads=8, max_child_agents=4, required_verified_children=2,
                         native_child_task=None):
        if provider_id == "legacy":
            raise SecurityGateError("BLOCKED_SECURITY_GATE: legacy provider retained for historical contracts; new live entry requires the hardened gateway profile")
        binary = os.environ.get("ORDERFLOW_CODEX_BINARY")
        auth = os.environ.get("ORDERFLOW_GATEWAY_SECRET_PATH" if provider_id == "gateway" else "ORDERFLOW_CODEX_AUTH_PATH")
        if not binary or not auth:
            raise RuntimeError("Configure the executable and project secret in the trusted launcher; participant identity files are forbidden")
        return cls(Path(binary), Path(auth), model or ("gpt-5.6-terra" if provider_id == "gateway" else "gpt-6.1-sol"),
                   timeout_seconds, provider_id, reasoning_effort or ("max" if provider_id == "gateway" else None),
                   os.environ.get("ORDERFLOW_GATEWAY_URL", "https://api.renwang-huang.top/v1"), request_budget,
                   max_request_concurrency=max_request_concurrency,
                   completion_policy=completion_policy, agent_mode=agent_mode,
                   stream_idle_timeout_ms=stream_idle_timeout_ms, connect_timeout_seconds=connect_timeout_seconds,
                   experience_mode=experience_mode, enable_experience_proposals=enable_experience_proposals,
                   experience_protocol_profile=experience_protocol_profile,
                   experience_v2_bootstrap_path=experience_v2_bootstrap_path,
                   smoke_instruction=smoke_instruction or os.environ.get("AEVORA_G24_SMOKE_INSTRUCTION"),
                   model_catalog_path=model_catalog_path or (
                       Path(os.environ["ORDERFLOW_MODEL_CATALOG_PATH"])
                       if os.environ.get("ORDERFLOW_MODEL_CATALOG_PATH") else None
                   ),
                   agent_protocol=agent_protocol or os.environ.get("AEVORA_G24_AGENT_PROTOCOL", "v1"),
                   max_agent_threads=max_agent_threads, max_child_agents=max_child_agents,
                   required_verified_children=required_verified_children,
                   native_child_task=native_child_task)

    def __post_init__(self):
        if self.experience_protocol_profile not in {"aevora.mcp/1.2", "aevora.mcp/2.0.0-rc2"}:
            raise ValueError("Explicit supported experience protocol required")
        if self.experience_protocol_profile != "aevora.mcp/1.2":
            if self.experience_mode != "aevora" or not self.enable_experience_proposals or self.experience_v2_bootstrap_path is None:
                raise ValueError("Native v2 requires trusted bootstrap and the four-tool profile")
        elif self.experience_v2_bootstrap_path is not None:
            raise ValueError("Legacy profile cannot accept v2 bootstrap")
        if type(self.enable_experience_proposals) is not bool or (self.enable_experience_proposals and self.experience_mode != 'aevora'):
            raise ValueError('Proposal capability requires explicit Aevora opt-in')
        if self.experience_mode not in ("disabled", "aevora"):
            raise ValueError("Unknown Experience Interface")
        if self.experience_mode == "aevora" and self.provider_id != "gateway":
            raise SecurityGateError("Aevora requires the hardened isolated Gateway profile")
        if self.completion_policy not in ("bounded", "completion-aware") or self.agent_mode not in ("single", "multi"):
            raise ValueError("Unknown completion policy or agent mode")
        if self.completion_policy == "completion-aware" and self.timeout_seconds is not None:
            raise ValueError("Completion-aware requires explicit timeout_seconds=None")
        if self.completion_policy == "bounded" and (isinstance(self.timeout_seconds, bool) or not isinstance(self.timeout_seconds, (int, float)) or not math.isfinite(self.timeout_seconds) or not 0 < self.timeout_seconds <= 7200):
            raise ValueError("Agent timeout must be in (0, 7200] seconds")
        if self.provider_id not in ("gateway", "legacy"):
            raise ValueError("Unknown provider")
        if self.provider_id == "gateway":
            _provider_config(self)
        if not (self.completion_policy == "completion-aware" and self.request_budget is None) and (type(self.request_budget) is not int or not 1 <= self.request_budget <= 500):
            raise ValueError("Request budgets must be finite and bounded")
        if type(self.max_request_concurrency) is not int or not 1 <= self.max_request_concurrency <= 32:
            raise ValueError("Concurrency must remain bounded")
        if self.stream_idle_timeout_ms is not None and (type(self.stream_idle_timeout_ms) is not int or not 1 <= self.stream_idle_timeout_ms <= 3600000):
            raise ValueError("Native SSE idle timeout must be finite positive milliseconds, at most one hour")
        if isinstance(self.connect_timeout_seconds, bool) or not isinstance(self.connect_timeout_seconds, (int, float)) or not math.isfinite(self.connect_timeout_seconds) or not 0 < self.connect_timeout_seconds <= 120:
            raise ValueError("Socket/TLS connect timeout must be finite and bounded")
        if not self.model or any(c.isspace() for c in self.model):
            raise ValueError("Model must be a nonempty identifier")
        if self.smoke_instruction is not None and (
                not isinstance(self.smoke_instruction, str) or not self.smoke_instruction.strip()
                or len(self.smoke_instruction.encode()) > 8192):
            raise ValueError("Smoke instruction must be bounded nonempty text")
        if self.model_catalog_path is not None and not self.model_catalog_path.is_file():
            raise ValueError("Model catalog path must name an ordinary file")
        if self.agent_protocol not in {"v1", "v2"}:
            raise ValueError("Agent protocol must be v1 or v2")
        if type(self.max_agent_threads) is not int or not 1 <= self.max_agent_threads <= 8:
            raise ValueError("Agent thread budget must be an integer in [1, 8]")
        if type(self.max_child_agents) is not int or not 0 <= self.max_child_agents <= 8:
            raise ValueError("Child-agent budget must be an integer in [0, 8]")
        if type(self.required_verified_children) is not int or not 0 <= self.required_verified_children <= self.max_child_agents:
            raise ValueError("Required verified children must fit within the child-agent budget")
        if self.native_child_task is not None and (
            not isinstance(self.native_child_task, str)
            or not self.native_child_task.strip()
            or len(self.native_child_task.encode()) > 8192
        ):
            raise ValueError("Native child task must be bounded nonempty text")
        if self.max_agent_threads < self.max_child_agents + 1:
            raise ValueError("Agent thread budget must include the parent and every child")


def native_command(config: CodexConfig, base_url: str) -> list[str]:
    # Only actual installed CLI switches and supported provider fields are used.
    # No resume/fork, host history, bypass switch, or custom Python orchestrator.
    command = ["/opt/codex/codex", "exec", "--json", "--ephemeral",
               "--ignore-user-config", "--ignore-rules", "--color", "never",
               "-s", "workspace-write", "-C", "/workspace", "-m", config.model]
    if config.agent_protocol == "v2":
        command += ["--enable" if config.agent_mode == "multi" else "--disable", "multi_agent_v2",
                    "--disable", "multi_agent"]
    else:
        command += ["--enable" if config.agent_mode == "multi" else "--disable", "multi_agent",
                    "--disable", "multi_agent_v2"]
    command += ["-o", "/workspace/FINAL.md"]
    # Installed feature names were verified with `codex features list`.
    for feature in ("apps", "plugins", "remote_plugin", "browser_use", "computer_use",
                    "code_mode_host", "memories", "shell_snapshot", "image_generation",
                    "workspace_dependencies", "skill_search", "in_app_browser", "goals",
                    "daemon_auto_start", "unbounded_connection_retries", "enable_request_compression"):
        if feature != "code_mode_host" or config.provider_id != "gateway" or _uses_deepseek_upstream(config):
            command.extend(["--disable", feature])
    if config.provider_id == "gateway":
        # Native child fork-context needs this run's public rollout. A fresh
        # CODEX_HOME provides independence; ephemeral prevents that native fork.
        command.remove("--ephemeral")
    if config.provider_id == "gateway" and not _uses_deepseek_upstream(config):
        command.extend(["--enable", "code_mode_host", "--enable", "code_mode",
                        "--enable", "code_mode_only"])
    if config.completion_policy == "completion-aware":
        command.insert(2, "--strict-config")
    overrides = {
        "approval_policy": "never",
        "model_provider": "orderflow_broker",
        "model_providers.orderflow_broker.name": "OrderFlow restricted credential broker",
        "model_providers.orderflow_broker.base_url": base_url,
        "model_providers.orderflow_broker.model_catalog_url": base_url + "/models",
        "model_providers.orderflow_broker.wire_api": "responses",
        "model_providers.orderflow_broker.requires_openai_auth": False,
        # Official finite retries; every new HTTP attempt still enters the
        # broker's per-Run budget and deadlines. Keep legacy contracts at zero.
        "model_providers.orderflow_broker.request_max_retries": 2 if config.provider_id == "gateway" else 0,
        "model_providers.orderflow_broker.stream_max_retries": 2 if config.provider_id == "gateway" else 0,
        "model_providers.orderflow_broker.stream_idle_timeout_ms": config.stream_idle_timeout_ms or (600000 if config.completion_policy == "completion-aware" else 120000),
        "projects.\"/workspace\".trust_level": "trusted",
        "agents.enabled": config.agent_mode == "multi",
        "agents.max_concurrent_threads_per_session": config.max_agent_threads,
        "analytics.enabled": False,
    }
    if config.provider_id == "gateway":
        overrides["model_providers.orderflow_broker.env_key"] = "ORDERFLOW_RUN_BROKER_TOKEN"
        overrides["model_reasoning_effort"] = config.reasoning_effort or "max"
    if config.model_catalog_path is not None:
        overrides["model_catalog_json"] = "/codex-state/model-catalog.json"
    if config.experience_mode == "aevora":
        overrides.update({
            "mcp_servers.aevora.command": "/usr/bin/python3.12",
            "mcp_servers.aevora.args": ["-I", "-B", "/aevora_mcp_proxy.py"],
            "mcp_servers.aevora.env_vars": ["AEVORA_RUN_TOKEN", "AEVORA_RUN_ID"],
            "mcp_servers.aevora.enabled": True, "mcp_servers.aevora.required": True,
            "mcp_servers.aevora.enabled_tools": ["resolve_experience", "build_evidence_bundle", "record_decision"],
            "mcp_servers.aevora.startup_timeout_sec": 20,
            "mcp_servers.aevora.tool_timeout_sec": 60,
            "mcp_servers.aevora.startup_readiness": "connection",
            "mcp_servers.aevora.default_tools_approval_mode": "auto",
        })
        if config.enable_experience_proposals:
            overrides['mcp_servers.aevora.enabled_tools'].append('propose_experience')
    for key, value in overrides.items():
        command.extend(["-c", f"{key}={json.dumps(value)}"])
    return command + ["-"]


def _write(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


class CodexAgentAdapter:
    """Run a fresh native session inside the physical participant boundary.

    The trusted caller builds the public workspace and keeps baseline/archive
    outside it. Runtime success requires a completed native turn and source
    changes; multi-agent evidence and hidden evaluation are separate results.
    """
    def __init__(self, config: CodexConfig):
        self.config = config

    def public_prompt(self, task, cooperation):
        prompt = (task.public_task + "\n\nRead ISSUE.md and AGENTS.md in the public workspace. " + cooperation +
                  "Before investigation, run the public tests and check that /maintainer, "
                  "/home/private-user/.codex/auth.json and /workspace/evaluator do not exist. "
                  "Report actual commands and results.\n").encode()
        if self.config.experience_mode == "aevora":
            prompt += ("\nAevora MCP tools are available for contextual experience evidence. "
                       "Evaluate whether available experience is relevant to your investigation. "
                       "When you consult it, retrieve actual query/bundle evidence and explain your own "
                       "APPLY/VERIFY/ABSTAIN interpretation through an untrusted decision with reasons. "
                       "These are conditional historical principles; investigate the current code independently. "
                       "A query does not prove adoption. Keep query/decision IDs in your final report. "
                       "Only the independent evaluator and trusted host can register verified outcomes.\n").encode()
            if self.config.enable_experience_proposals:
                prompt += ("Reflect on what your actual investigation, implementation and public regression establish. "
                    "If your observed work supports a reusable conditional principle, consider proposing it through "
                    "the available Aevora proposal capability. Include actual current-run Query/Decision "
                    "references, explicit necessary/inapplicable conditions, bounded scope, limitations and unknown facts. "
                    "Your proposal remains UNTRUSTED; do not claim verified outcome, host approval or causal benefit.\n").encode()
        if self.config.experience_protocol_profile == "aevora.mcp/2.0.0-rc2":
            prompt += ("\nIf you use Aevora, read AEVORA_MCP_CONTRACT.json for the exact public "
                       "tool argument contracts and declared task vocabulary. Task facts describe "
                       "the initial public task, not your repaired implementation. This reference "
                       "does not prescribe an experience, decision or proposal.\n").encode()
        return prompt

    def execute(self, task: TaskInput, context: ExecutionContext) -> ExecutionResult:
        archive = Path(context.constraints["archive"])
        baseline = Path(context.constraints["baseline"])
        workspace = Path(context.workspace)
        state = archive / "codex-state"
        state.mkdir(mode=0o700)
        if self.config.model_catalog_path is not None:
            shutil.copyfile(self.config.model_catalog_path, state / "model-catalog.json")
            (state / "model-catalog.json").chmod(0o600)
        raw_pending = archive / "codex_events.pending"
        stderr_pending = archive / "codex_stderr.pending"
        raw = archive / "codex_events.jsonl"
        trace_path = archive / "agent_trace.jsonl"
        started = utc_timestamp()
        clock_start = time.monotonic()
        metadata = {
            "schema_version": "1.0.0", "run_id": context.run_id,
            "episode_id": task.episode_id, "scenario_version": task.scenario_version,
            "adapter": "codex_exec", "started_at": started, "ended_at": None,
            "model": self.config.model, "fresh_session_requested": True,
            "fresh_session": "UNAVAILABLE",
            "timeout_seconds": self.config.timeout_seconds,
            "completion_policy": self.config.completion_policy,
            "agent_mode": self.config.agent_mode,
            "delegation_budget": {
                "max_agent_threads": self.config.max_agent_threads,
                "max_child_agents": self.config.max_child_agents,
                "max_depth": 1,
                "required_verified_children": self.config.required_verified_children,
            },
            "request_budget": self.config.request_budget,
            "transport_policy": {"socket_tls_connect_seconds": self.config.connect_timeout_seconds,
                "broker_first_response_seconds": None if self.config.completion_policy == "completion-aware" else 120,
                "broker_response_total_seconds": None if self.config.completion_policy == "completion-aware" else 120,
                "broker_sse_idle_seconds": None if self.config.completion_policy == "completion-aware" else 120,
                "native_stream_idle_timeout_ms": self.config.stream_idle_timeout_ms or (600000 if self.config.completion_policy == "completion-aware" else 120000),
                "native_stream_idle_limit": "FINITE_OFFICIAL_CLI_LIMIT; NOT_AN_AGENT_TOTAL_WALL_LIMIT"},
            "runtime_result": "ERROR", "failure_kind": None,
            "exit_code": None, "submission": None,
            "experience": "DISABLED", "isolation": "bubblewrap_participant",
            "experience_requested": self.config.experience_mode,
            "network_namespace_isolated": False,
            "credentials_in_participant": False,
            "session_id": "UNAVAILABLE", "thread_id": "UNAVAILABLE",
            "usage": {"availability": "UNAVAILABLE"},
            "subagents": {"availability": "UNAVAILABLE", "verified_count": 0},
            "artifacts": {"raw_events": str(raw), "trace": str(trace_path)},
            "errors": [],
        }
        project = Path(__file__).resolve().parents[1]
        metadata["integration_fingerprints"] = {
            relative: hashlib.sha256((project / relative).read_bytes()).hexdigest()
            for relative in ("integrations/codex_agent.py", "integrations/codex_trace.py",
                             "integrations/model_broker.py", "benchmark/participant.py",
                             "benchmark/participant_sandbox.py", "benchmark/runner.py", "benchmark/sandbox.py",
                             "benchmark/submission.py", "benchmark/resources.py", "integrations/providers.py",
                             "integrations/gateway_broker.py", "integrations/participant_bridge.py",
                             "integrations/runtime_evidence.py", "integrations/native_rollout_trace.py", "integrations/runtime_control.py")
        }
        if self.config.native_child_task is not None and self.config.agent_mode == "multi":
            child_task_path = workspace / "CHILD_TASK.md"
            child_task_path.write_text(self.config.native_child_task.strip() + "\n", encoding="utf-8")
            metadata["native_child_task_sha256"] = hashlib.sha256(
                child_task_path.read_bytes()
            ).hexdigest()
        metadata["public_inputs_sha256"] = {
            str(path.relative_to(workspace)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in [workspace / "public.json", workspace / "ISSUE.md", workspace / "AGENTS.md",
                         workspace / "CHILD_TASK.md",
                         *sorted((workspace / ".codex/agents").glob("*.toml"))]
            if path.is_file()
        }
        errors = metadata["errors"]
        status = ExecutionStatus.ERROR
        submission = None
        broker = None
        experience_bridge = None
        process = None
        secrets = ()
        scope = None
        watchdog = None
        channel_directory = None
        control = None
        strict = self.config.provider_id == "gateway"
        limits = replace(PARTICIPANT_LIMITS, wall_seconds=self.config.timeout_seconds)
        cooperation = ("Use native subagent tools for exactly one independent child task. "
                       "For each child, call spawn_agent with a distinct task_name and fork_turns=\"none\", "
                       "then call send_message to the returned child path with the same task text. "
                       "Never use fork_turns=\"all\". Each child must not spawn or delegate. "
                       "Wait for the actual terminal result, investigate and implement your own patch. " if self.config.agent_mode == "multi"
                       else "Investigate, test, and implement your own patch as the single lead Agent. Native delegation is disabled. ")
        prompt = (task.public_task + "\n\nRead ISSUE.md and AGENTS.md in the public workspace. " + cooperation +
                  "Before investigation, run the public tests and check that /maintainer, "
                  "/home/private-user/.codex/auth.json and /workspace/evaluator do not exist. "
                  "Report actual commands and results.\n").encode()
        if self.config.experience_mode == "aevora":
            prompt += ("\nAevora MCP tools are available for contextual experience evidence. "
                       "Evaluate whether available experience is relevant to your investigation. "
                       "When you consult it, retrieve actual query/bundle evidence and explain your own "
                       "APPLY/VERIFY/ABSTAIN interpretation through an untrusted decision with reasons. "
                       "These are conditional historical principles; investigate the current code independently. "
                       "A query does not prove adoption. Keep query/decision IDs in your final report. "
                       "Only the independent evaluator and trusted host can register verified outcomes.\n").encode()
            if self.config.enable_experience_proposals:
                prompt += ("Reflect on what your actual investigation, implementation and public regression establish. "
                    "If your observed work supports a reusable conditional principle, consider proposing it through "
                    "the available Aevora proposal capability. Include actual current-run Query/Decision "
                    "references, explicit necessary/inapplicable conditions, bounded scope, limitations and unknown facts. "
                    "Your proposal remains UNTRUSTED; do not claim verified outcome, host approval or causal benefit.\n").encode()
        metadata["child_internal_tool_events"] = "UNAVAILABLE: inspect separately archived official rollouts when available"
        metadata["provider"] = _provider_config(self.config).metadata if strict else {"provider_id": "legacy"}
        metadata["isolation_status"] = "NOT_STARTED"
        try:
            control = RuntimeControl(archive, context.run_id, completion_policy=self.config.completion_policy, agent_mode=self.config.agent_mode)
            control.install_signals()
            from benchmark.submission import snapshot_source_tree, source_tree_sha256
            control.baseline_tree_sha256 = source_tree_sha256(snapshot_source_tree(baseline))
            helper = self.config.binary.with_name("codex-code-mode-host") if strict else None
            if strict and not helper.is_file():
                metadata["failure_kind"] = "BLOCKED_SECURITY_GATE"
                raise SecurityGateError("BLOCKED_SECURITY_GATE: official bundled Code Mode host is missing")
            if strict:
                metadata["code_mode_host_sha256"] = hashlib.sha256(helper.read_bytes()).hexdigest()
            metadata["failure_kind"] = "INPUT_SEAL_FAILED"
            if self.config.experience_protocol_profile == "aevora.mcp/2.0.0-rc2":
                from integrations.aevora_v2 import write_public_contract
                metadata["public_experience_contract"] = write_public_contract(workspace, task.public_metadata)
                prompt += ("\nIf you use Aevora, read AEVORA_MCP_CONTRACT.json for the exact public "
                           "tool argument contracts and declared task vocabulary. Task facts describe "
                           "the initial public task, not your repaired implementation. This reference "
                           "does not prescribe an experience, decision or proposal.\n").encode()
            if self.config.smoke_instruction:
                prompt += ("\nNON-SCORED ADAPTER SMOKE INSTRUCTION:\n"
                           + self.config.smoke_instruction.strip() + "\n").encode()
            metadata["input_seal"] = seal_inputs(workspace, archive, prompt)
            if not self.config.binary.is_file():
                metadata["failure_kind"] = "STARTUP_FAILED"
                raise RuntimeError("Configured Codex executable does not exist")
            metadata["codex_binary_sha256"] = hashlib.sha256(self.config.binary.read_bytes()).hexdigest()
            if strict:
                metadata["failure_kind"] = "BLOCKED_SECURITY_GATE"
                scope = CgroupScope.create(limits)
            version_command = participant_command(workspace, state, self.config.binary,
                ["/opt/codex/codex", "--version"], network_isolated=strict, code_mode_host_binary=helper, resources=limits)
            if scope:
                version_command = scope.wrap_command(version_command)
            version = subprocess.run(version_command, capture_output=True,
                                      text=True, timeout=15)
            if version.returncode:
                metadata["failure_kind"] = "SANDBOX_STARTUP_FAILED"
                raise RuntimeError(f"Isolated Codex version probe failed: {version.stderr.strip()}")
            metadata["codex_version"] = version.stdout.strip()
            metadata["failure_kind"] = "MODEL_BROKER_STARTUP_FAILED"
            run_token = secure_random.token_urlsafe(32) if strict else ""
            if strict:
                channel_directory = tempfile.TemporaryDirectory(prefix="of-channel-")
                broker = SecureModelBroker(_provider_config(self.config), self.config.auth_path,
                    run_id=context.run_id, socket_path=Path(channel_directory.name) / "broker.sock", run_token=run_token,
                    request_budget=self.config.request_budget, max_concurrency=self.config.max_request_concurrency,
                    request_timeout=None if self.config.completion_policy == "completion-aware" else 120,
                    token_ttl_seconds=None if self.config.completion_policy == "completion-aware" else 1800,
                    completion_policy=self.config.completion_policy, connect_timeout_seconds=self.config.connect_timeout_seconds,
                    event_path=archive / "gateway_transport_events.jsonl")
            else:
                broker = ModelBroker(self.config.auth_path, request_timeout=120)
            # Used only for host-side log redaction, never arguments/environment.
            with broker:
                secrets = (*broker.secret_values, run_token) if strict else broker.secret_values
                if self.config.experience_mode == "aevora":
                    metadata["failure_kind"] = "AEVORA_STARTUP_FAILED"
                    from integrations.aevora import AevoraRuntimeBridge
                    bridge_options = {'enable_proposals': True} if self.config.enable_experience_proposals else {}
                    if self.config.experience_protocol_profile != "aevora.mcp/1.2":
                        bridge_options.update(protocol_profile=self.config.experience_protocol_profile,
                                              v2_bootstrap_path=self.config.experience_v2_bootstrap_path)
                    experience_bridge = AevoraRuntimeBridge(context.run_id, task.public_metadata, archive, **bridge_options)
                    experience_bridge.__enter__()
                    secrets = (*secrets, experience_bridge.run_token)
                    metadata["experience"] = experience_bridge.metadata
                    metadata["artifacts"]["aevora_mcp_events"] = str(archive / "aevora_mcp_events.jsonl")
                metadata["failure_kind"] = None
                native = native_command(self.config, "http://127.0.0.1:9180/v1" if strict else broker.base_url)
                inner = ["/usr/bin/python3.12", "-I", "-B", "/model_bridge.py", "--", *native] if strict else native
                command = participant_command(workspace, state, self.config.binary, inner,
                    network_isolated=strict, broker_socket=broker.socket_path if strict else None,
                    aevora_socket=experience_bridge.socket_path if experience_bridge else None,
                    aevora_proxy=experience_bridge.proxy_path if experience_bridge else None,
                    code_mode_host_binary=helper, resources=limits)
                if scope:
                    command = scope.wrap_command(command)
                metadata["command"] = command
                metadata["network_namespace_isolated"] = strict
                metadata["isolation_status"] = "PROVISIONED" if strict else "LEGACY_UNHARDENED_CONTRACT_PROFILE"
                private_header = {"run_token": run_token, "completion_policy": self.config.completion_policy}
                if experience_bridge:
                    private_header.update(aevora_run_token=experience_bridge.run_token, aevora_run_id=context.run_id)
                payload = (json.dumps(private_header).encode() + b"\n" + prompt) if strict else prompt
                with raw_pending.open("wb") as stdout, stderr_pending.open("wb") as stderr:
                    process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=stdout,
                                               stderr=stderr, start_new_session=True)
                    try:
                        watchdog = ResourceWatchdog(process.pid, limits, output_roots=(workspace, state, archive)).start() if strict else None
                        # communicate is polled for trusted cancellation/status;
                        # only bounded mode has an actual overall deadline.
                        launched = time.monotonic()
                        first_input = payload
                        while True:
                            cancel = control.cancellation()
                            if cancel:
                                metadata["cancellation"] = cancel
                                metadata["failure_kind"] = cancel["classification"]
                                metadata["runtime_result"] = "CANCELLED"
                                status = ExecutionStatus.CANCELLED
                                control.event("CANCELLED_BY_OPERATOR" if cancel["classification"] == "CANCELLED_BY_OPERATOR" else "COLLECTOR_INTERRUPTED", cancel)
                                os.killpg(process.pid, signal.SIGKILL)
                                process.communicate(timeout=10)
                                break
                            if self.config.timeout_seconds is not None and time.monotonic() - launched >= self.config.timeout_seconds:
                                raise subprocess.TimeoutExpired(command, self.config.timeout_seconds)
                            try:
                                interval = min(0.25, max(0.001, self.config.timeout_seconds - (time.monotonic() - launched))) if self.config.timeout_seconds is not None else 0.25
                                process.communicate(first_input, timeout=interval)
                                break
                            except subprocess.TimeoutExpired:
                                first_input = None
                                control.observe_exec(raw_pending, secret_values=secrets)
                                control.publish(broker, watchdog, workspace, secret_values=secrets)
                        control.observe_exec(raw_pending, secret_values=secrets)
                        control.publish(broker, watchdog, workspace, secret_values=secrets)
                    except subprocess.TimeoutExpired:
                        metadata["failure_kind"] = "EXECUTION_TIMEOUT"
                        status = ExecutionStatus.TIMEOUT
                        os.killpg(process.pid, signal.SIGKILL)
                        process.communicate(timeout=10)
                        errors.append("Codex execution exceeded the configured timeout")
                    finally:
                        if process.poll() is None:
                            try:
                                os.killpg(process.pid, signal.SIGKILL)
                            except ProcessLookupError:
                                pass
                            process.wait(timeout=10)
                        metadata["exit_code"] = process.returncode
            if watchdog is not None:
                metadata["resource_watchdog"] = watchdog.close(cleanup=True)
            if scope is not None:
                metadata["resource_cgroup"] = scope.close()
            metadata["model_broker"] = broker.metadata
            if strict:
                metadata["provider"] = {key: broker.metadata.get(key, metadata["provider"].get(key, "UNAVAILABLE")) for key in
                    ("provider_id", "endpoint_hostname", "api_root", "requested_model", "requested_effort", "selected_effort", "effective_model", "effective_effort")}
            stderr_text = redact_text(stderr_pending.read_text(errors="replace"), secret_values=secrets)
            (archive / "codex_stderr.log").write_text(stderr_text)
            metadata["raw_archive"] = redact_jsonl(raw_pending, raw, secret_values=secrets)
            observations = parse_trace(raw, trace_path, context.run_id, collected_at=utc_timestamp())
            metadata["trace_observations"] = observations
            for key in ("thread_id", "session_id", "usage", "subagents"):
                metadata[key] = observations[key]
            metadata["fresh_session"] = True if observations["thread_id"] != "UNAVAILABLE" else "UNAVAILABLE"
            if strict and observations["thread_id"] != "UNAVAILABLE":
                metadata["isolation_status"] = "PASS"
            if status == ExecutionStatus.CANCELLED:
                metadata["runtime_result"] = "CANCELLED"
            elif status == ExecutionStatus.TIMEOUT:
                metadata["runtime_result"] = "TIMEOUT"
            elif metadata["exit_code"] != 0 or observations["turn_status"] == "FAILED":
                terminal_requests = [item for item in broker.metadata.get("request_records", []) if item.get("route") == "/v1/responses"]
                last_request = max(terminal_requests, key=lambda item: item.get("ended_at", 0)) if terminal_requests else {}
                last_category = last_request.get("category", "")
                provider_failure = strict and last_request.get("outcome") in ("ERROR", "REJECTED") and (last_category.startswith("UPSTREAM_") or last_category == "REQUEST_WALL_TIMEOUT")
                metadata["failure_kind"] = "PROVIDER_FAILURE" if provider_failure else "CODEX_EXECUTION_FAILED"
                metadata["terminal_provider_evidence"] = {"classification": "CORRELATED_LAST_RESPONSE_ATTEMPT" if provider_failure else "UNAVAILABLE",
                    "category": last_category if provider_failure else None,
                    "source": "gateway_transport_events.jsonl" if strict else "UNAVAILABLE"}
                errors.append(f"Codex failed (exit {metadata['exit_code']}, turn {observations['turn_status']})")
            elif observations["integrity"]["status"] != "COMPLETE":
                metadata["failure_kind"] = "TRACE_INCOMPLETE"
                errors.extend(json.dumps(item, sort_keys=True) for item in observations["integrity"]["errors"])
            elif observations["turn_status"] != "COMPLETED":
                metadata["failure_kind"] = "TRACE_INCOMPLETE"
                errors.append("Native trace contains no completed turn")
            else:
                try:
                    final_tree = snapshot_source_tree(workspace)
                    if any(secret.encode() in data for secret in secrets if secret for data in final_tree.values()):
                        raise ValueError("Credentials in submitted source are forbidden")
                    evidence = extract_submission(baseline, workspace, archive / "submission.diff")
                    submission = SubmissionArtifact("patch", evidence["patch_path"], evidence["sha256"], utc_timestamp())
                    metadata["submission"] = evidence
                    metadata["runtime_result"] = "PASS"
                    status = ExecutionStatus.SUBMITTED
                except NoPatchError as error:
                    metadata["failure_kind"] = "NO_PATCH"
                    errors.append(str(error))
                except (OSError, ValueError) as error:
                    metadata["failure_kind"] = "INVALID_SUBMISSION"
                    errors.append(str(error))
        except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
            metadata["failure_kind"] = metadata["failure_kind"] or "STARTUP_FAILED"
            errors.append(redact_text(f"{type(error).__name__}: {error}", secret_values=secrets))
        finally:
            if experience_bridge is not None:
                try:
                    experience_bridge.close()
                    metadata["experience"] = experience_bridge.metadata
                    cleanup = metadata["experience"]["broker"]
                    if (cleanup["active_connections"] != 0 or cleanup["active_sdk_children"] != 0
                            or not cleanup["token_revoked"] or not cleanup["socket_unlinked"]
                            or not cleanup["handler_cleanup_complete"] or not cleanup["server_thread_stopped"]):
                        raise RuntimeError("Aevora owned channel cleanup incomplete")
                except (OSError, ValueError, RuntimeError) as error:
                    errors.append("Aevora cleanup failed: " + type(error).__name__)
                    metadata["failure_kind"] = "AEVORA_CLEANUP_FAILED"
                    metadata["runtime_result"] = "ERROR"
                    status, submission = ExecutionStatus.ERROR, None
            if process is not None and process.poll() is None:
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait(timeout=10)
                except (OSError, subprocess.SubprocessError) as error:
                    errors.append(f"Native process cleanup failed: {type(error).__name__}")
                    metadata["failure_kind"] = "PROCESS_CLEANUP_FAILED"
                    metadata["runtime_result"] = "ERROR"
                    status = ExecutionStatus.ERROR
                    submission = None
            if watchdog is not None:
                try:
                    metadata["resource_watchdog"] = watchdog.close(cleanup=True)
                    observation = metadata["resource_watchdog"]
                    if observation["violation"] or observation["remaining_pids"]:
                        metadata["failure_kind"] = "RESOURCE_LIMIT_EXCEEDED" if observation["violation"] else "PROCESS_CLEANUP_FAILED"
                        metadata["runtime_result"] = "TIMEOUT" if observation["violation"] and observation["violation"]["resource"] == "wall_seconds" else "ERROR"
                        status = ExecutionStatus.TIMEOUT if metadata["runtime_result"] == "TIMEOUT" else ExecutionStatus.ERROR
                        submission = None
                except (OSError, RuntimeError) as error:
                    errors.append("Resource monitor cleanup failed: " + type(error).__name__)
                    metadata["runtime_result"] = "ERROR"
                    metadata["failure_kind"] = "PROCESS_CLEANUP_FAILED"
                    status = ExecutionStatus.ERROR
                    submission = None
            if scope is not None:
                try:
                    metadata["resource_cgroup"] = scope.close()
                except (OSError, RuntimeError) as error:
                    errors.append("Resource cgroup cleanup failed: " + type(error).__name__)
                    metadata["runtime_result"] = "ERROR"
                    metadata["failure_kind"] = "PROCESS_CLEANUP_FAILED"
                    status = ExecutionStatus.ERROR
                    submission = None
            if broker is not None:
                metadata["model_broker"] = broker.metadata
                if strict and metadata["model_broker"].get("started_at") is not None and (not all(metadata["model_broker"].get(key) is True for key in (
                        "handler_cleanup_complete", "server_thread_stopped", "socket_unlinked", "token_revoked"))
                        or metadata["model_broker"].get("active_requests") != 0):
                    errors.append("Secure model channel cleanup evidence is incomplete")
                    metadata["failure_kind"] = "PROCESS_CLEANUP_FAILED"
                    metadata["runtime_result"] = "ERROR"
                    status, submission = ExecutionStatus.ERROR, None
            if channel_directory is not None:
                try:
                    channel_directory.cleanup()
                except OSError as error:
                    errors.append("Model channel cleanup failed: " + type(error).__name__)
                    metadata["runtime_result"] = "ERROR"
                    metadata["failure_kind"] = "PROCESS_CLEANUP_FAILED"
                    status = ExecutionStatus.ERROR
                    submission = None
            kernel = metadata.get("resource_cgroup", {}).get("kernel_controls", {})
            memory_events = dict(line.split() for line in kernel.get("memory.events", "").splitlines() if len(line.split()) == 2)
            if int(memory_events.get("oom_kill", 0)) > 0:
                metadata["failure_kind"] = "RESOURCE_LIMIT_EXCEEDED"
                metadata["resource_violation"] = "CGROUP_MEMORY_OOM_KILL"
                metadata["runtime_result"] = "ERROR"
                status = ExecutionStatus.ERROR
                submission = None
            # Stop all native processes before touching untrusted source. State
            # contains public session data only and is not reusable next run.
            if strict:
                try:
                    metadata["native_rollouts"] = archive_native_rollouts(state, archive, secret_values=secrets)
                    from integrations.native_rollout_trace import analyze_native_rollouts
                    native_evidence = analyze_native_rollouts(context.run_id, archive, metadata["native_rollouts"],
                        expected_parent_thread_id=metadata["thread_id"] if metadata["thread_id"] != "UNAVAILABLE" else None)
                    native_summary = native_evidence["summary"]
                    metadata["native_rollout_observations"] = native_summary
                    _write(archive / "native_rollout_summary.json", native_summary)
                    native_trace = archive / "native_agent_trace.jsonl"
                    with native_trace.open("x") as output:
                        for native_event in native_evidence["events"]:
                            output.write(json.dumps(native_event, sort_keys=True) + "\n")
                    metadata["artifacts"]["native_trace"] = str(native_trace)
                    metadata["native_trace_sha256"] = hashlib.sha256(native_trace.read_bytes()).hexdigest()
                    metadata["exec_subagents"] = metadata["subagents"]
                    metadata["exec_usage"] = metadata["usage"]
                    if native_summary["subagents"]["availability"] == "AVAILABLE":
                        metadata["subagents"] = native_summary["subagents"]
                    if native_summary["usage"]["availability"] == "AVAILABLE":
                        metadata["usage"] = native_summary["usage"]
                    if native_summary["session_id"] != "UNAVAILABLE":
                        metadata["session_id"] = native_summary["session_id"]
                    metadata["child_internal_tool_events"] = {"availability": "AVAILABLE" if any(
                        agent.get("execution_verified") for agent in native_summary["subagents"]["agents"]
                    ) else "UNAVAILABLE", "source": "codex.native.rollout", "trace": str(native_trace)}
                    if self.config.agent_mode == "multi":
                        child_agents = native_summary["subagents"].get("agents", [])
                        root_thread = metadata.get("thread_id")
                        direct_children = all(
                            agent.get("parent_thread_id") == root_thread
                            for agent in child_agents
                        )
                        within_budget = len(child_agents) <= self.config.max_child_agents
                        metadata["delegation_verification"] = (
                            "PASS" if child_agents and direct_children and within_budget
                            else "FAIL" if child_agents and (not direct_children or not within_budget)
                            else "UNVERIFIED"
                        )
                        if metadata["delegation_verification"] == "FAIL":
                            errors.append(
                                "DELEGATION_BOUNDARY_VIOLATION: "
                                f"{len(child_agents)} children, max {self.config.max_child_agents}, "
                                f"direct_children={direct_children}"
                            )
                            metadata["failure_kind"] = "DELEGATION_BOUNDARY_VIOLATION"
                            metadata["runtime_result"] = "ERROR"
                            status, submission = ExecutionStatus.ERROR, None
                except (OSError, ValueError, RuntimeError) as error:
                    metadata["native_rollouts"] = {"availability": "UNAVAILABLE", "reason": type(error).__name__}
                    # A collection exception must not upgrade incomplete native
                    # evidence by falling back to otherwise complete exec facts.
                    previous_native = metadata.get("native_rollout_observations", {})
                    previous_integrity = previous_native.get("integrity", {})
                    metadata["native_rollout_observations"] = {
                        **previous_native,
                        "integrity": {"status": "INCOMPLETE", "errors": [
                            *previous_integrity.get("errors", []),
                            {"code": "NATIVE_ROLLOUT_ARCHIVE_FAILED", "error_type": type(error).__name__},
                        ]},
                    }
                    errors.append("Native rollout archive failed: " + type(error).__name__)
            metadata["ended_at"] = utc_timestamp()
            metadata["elapsed_seconds"] = time.monotonic() - clock_start
            metadata["multi_agent_result"] = "PASS" if (
                metadata["subagents"].get("verified_count", 0) >= self.config.required_verified_children
                and metadata.get("trace_observations", {}).get("integrity", {}).get("status") == "COMPLETE"
                and metadata.get("native_rollout_observations", {}).get("integrity", {}).get("status", "COMPLETE") == "COMPLETE"
                and (self.config.agent_mode != "multi"
                     or metadata.get("delegation_verification") == "PASS")
            ) else "PARTIAL"
            if self.config.agent_mode == "single":
                agents = metadata["subagents"].get("agents", [])
                metadata["multi_agent_result"] = "DISABLED"
                metadata["single_agent_verification"] = "PASS" if not agents and metadata.get("trace_observations", {}).get("integrity", {}).get("status") == "COMPLETE" and (not strict or metadata.get("native_rollout_observations", {}).get("integrity", {}).get("status") == "COMPLETE") else "UNVERIFIED"
                metadata["single_agent_verified"] = metadata["single_agent_verification"] == "PASS"
                metadata["single_agent_observed_child_count"] = len(agents)
                if agents:
                    metadata["failure_kind"] = "UNEXPECTED_NATIVE_CHILD_IN_SINGLE_MODE"
                    metadata["runtime_result"] = "ERROR"
                    status, submission = ExecutionStatus.ERROR, None
            if status == ExecutionStatus.TIMEOUT:
                metadata["runtime_result"] = "TIMEOUT"
            if not raw.exists():
                if raw_pending.exists():
                    redact_jsonl(raw_pending, raw, secret_values=secrets)
                else:
                    raw.write_text("")
            if not trace_path.exists():
                trace_path.write_text("")
            if stderr_pending.exists():
                (archive / "codex_stderr.log").write_text(redact_text(
                    stderr_pending.read_text(errors="replace"), secret_values=secrets))
            raw_pending.unlink(missing_ok=True)
            stderr_pending.unlink(missing_ok=True)
            _write(archive / "runtime_metadata.json", metadata)
            if control is not None:
                metadata["first_patch_observed"] = control._first_patch_observed
                metadata["runtime_observation_artifacts"] = {
                    "activity": str(archive / "runtime_activity.jsonl"),
                    "status": str(archive / "runtime_status.json"),
                    "gateway_transport": str(archive / "gateway_transport_events.jsonl") if strict else "UNAVAILABLE"}
                control.finish(metadata["runtime_result"], metadata["failure_kind"], metadata)
                _write(archive / "runtime_metadata.json", metadata)
        event = ExecutionTrace(context.run_id, "codex_exec", "agent.execution_finished",
                               {"status": status.value, "runtime_metadata": str(archive / "runtime_metadata.json"),
                                "failure_kind": metadata["failure_kind"]})
        return ExecutionResult(status, submission, (event,), tuple(errors),
                               Availability.AVAILABLE if metadata["thread_id"] != "UNAVAILABLE" else Availability.UNAVAILABLE,
                               tuple(metadata["subagents"].get("agents", [])) or None,
                               metadata["usage"], metadata)
