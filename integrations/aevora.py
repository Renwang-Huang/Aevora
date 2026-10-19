"""Thin, opt-in Aevora MCP boundary; OrderFlow owns independent evaluation."""
from __future__ import annotations

from pathlib import Path
import hashlib
import importlib.metadata
import secrets
import tempfile


PUBLIC_GOVERNANCE_FACT_KEYS = frozenset({
    "operation_semantics", "authority_model", "authority_validation", "clock_domain",
    "supported_operation_set", "observed_failure_mode",
})


def public_runtime_context(public_manifest):
    """Project declared public task facts, never episode IDs or private labels.

    These are initial capabilities/symptoms. They do not certify the eventual
    Participant implementation or replace independently observed outcomes.
    Legacy manifests without governance_context retain their exact projection.
    """
    from aevora.historical_import import public_context
    from aevora.models import InvalidRecord, normalize_context

    runtime = public_manifest.get("runtime", {})
    facts = public_context(runtime.get("topology"), runtime.get("database"))
    extension = runtime.get("governance_context", {})
    if not isinstance(extension, dict) or set(extension) - PUBLIC_GOVERNANCE_FACT_KEYS:
        raise InvalidRecord("Public governance context contains unsupported facts")
    facts.update(normalize_context(extension))
    return normalize_context(facts)


def runtime_fingerprints():
    """Bind actual governance implementation and installed SDKs, not labels alone."""
    import aevora
    root = Path(aevora.__file__).resolve().parent
    files = {"aevora/" + path.name: hashlib.sha256(path.read_bytes()).hexdigest()
             for path in sorted(root.glob("*.py"))}
    files["integrations/aevora.py"] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    files["integrations/aevora_v2.py"] = hashlib.sha256(Path(__file__).with_name("aevora_v2.py").read_bytes()).hexdigest()
    versions = {name: importlib.metadata.version(name)
                for name in ("aevora-core", "falkordb", "redis", "mcp", "pydantic", "anyio")}
    return {"files_sha256": files, "packages": versions}


class AevoraRuntimeBridge:
    """Run-scoped capability; contains no governance algorithm or outcome tool."""

    def __init__(self, run_id, public_manifest, archive, *, enable_proposals=False,
                 protocol_profile="aevora.mcp/1.2", v2_bootstrap_path=None):
        from aevora.graph_repository import GraphRepository
        from aevora.mcp_broker import MCPBroker
        import aevora.mcp_proxy

        self.context = public_runtime_context(public_manifest)
        self.run_id = run_id
        self.archive = Path(archive)
        self.fingerprints = runtime_fingerprints()
        self.proxy_path = Path(aevora.mcp_proxy.__file__).resolve(strict=True)
        # Fail closed before giving Participant any tool configuration.
        self._directory = tempfile.TemporaryDirectory(prefix="aevora-channel-")
        broker_options = {}
        try:
            if protocol_profile == "aevora.mcp/2.0.0-rc2":
                if not enable_proposals or v2_bootstrap_path is None:
                    raise ValueError("Explicit trusted native v2 bootstrap required")
                from integrations.aevora_v2 import prepare_runtime_configuration
                config, state, count = prepare_runtime_configuration(
                    v2_bootstrap_path, run_id, self.context, Path(self._directory.name))
                self.initial_graph_state, self.initial_experience_count = state, count
                broker_options.update(protocol_profile=protocol_profile, v2_config_path=str(config))
            elif protocol_profile == "aevora.mcp/1.2" and v2_bootstrap_path is None:
                repository = GraphRepository.from_environment()
                try:
                    self.initial_graph_state = repository.state_fingerprint()
            # Availability and corpus size are distinct. A new developer's
            # initialized graph can legitimately return zero candidates; never
            # require hidden seed material to start an independent Session.
                    self.initial_experience_count = len(repository.experience_ids())
                finally:
                    repository.close()
            else:
                raise ValueError("Unsupported or ambiguous runtime profile")
        except BaseException:
            self._directory.cleanup()
            raise
        self.run_token = secrets.token_urlsafe(32)
        self.socket_path = Path(self._directory.name) / "mcp.sock"
        self.broker = MCPBroker(run_id=run_id, public_context=self.context,
            socket_path=self.socket_path, run_token=self.run_token,
            event_path=self.archive / "aevora_mcp_events.jsonl", enable_proposals=enable_proposals,
            **broker_options)
        self.protocol_profile = protocol_profile
        self.final_fingerprints = None

    def __enter__(self):
        try:
            self.broker.__enter__()
        except BaseException:
            self._directory.cleanup()
            self.run_token = None
            raise
        return self

    @property
    def metadata(self):
        return {"status": "ENABLED", "interface": "Aevora MCP Interface", "run_id": self.run_id,
            "protocol_profile": self.protocol_profile,
            "public_context": self.context, "initial_graph_state": self.initial_graph_state,
            "initial_experience_count": self.initial_experience_count,
            "initial_corpus_state": "EMPTY" if self.initial_experience_count == 0 else "AVAILABLE",
            "context_provenance": "INITIAL_PUBLIC_RUNTIME_CAPABILITY; not proof of repaired implementation",
            "runtime_fingerprints": self.fingerprints,
            "runtime_fingerprints_after": self.final_fingerprints,
            "source_integrity": "VERIFIED" if self.final_fingerprints == self.fingerprints else "UNVERIFIED",
            "broker": self.broker.metadata, "tools": self.broker.metadata["tools"],
            "raw_events": str(self.archive / "aevora_mcp_events.jsonl"),
            "outcome_ingestion": "TRUSTED_HOST_ONLY", "causal_influence": "UNVERIFIED"}

    def close(self):
        try:
            self.broker.close()
        finally:
            self.run_token = None
            self._directory.cleanup()
            self.final_fingerprints = runtime_fingerprints()
        if self.final_fingerprints != self.fingerprints:
            raise RuntimeError("Aevora implementation changed during Participant execution")

    def __exit__(self, *_):
        self.close()
        return False
