from pathlib import Path

import pytest

from integrations.codex_agent import CodexConfig, native_command
from integrations.providers import ProviderConfig, deepseek_provider


def _config(*, protocol="v2", mode="multi"):
    return CodexConfig(
        binary=Path("/opt/codex/codex"),
        auth_path=Path("/maintainer/deepseek.token"),
        model="deepseek-flash",
        timeout_seconds=None,
        provider_id="gateway",
        reasoning_effort="max",
        gateway_url="https://api.deepseek.com",
        request_budget=None,
        completion_policy="completion-aware",
        agent_mode=mode,
        agent_protocol=protocol,
    )


def test_deepseek_provider_is_explicitly_authorized():
    provider = deepseek_provider(model="deepseek-flash", effort="max")
    assert provider.provider_id == "deepseek"
    assert provider.endpoint_hostname == "api.deepseek.com"
    assert provider.metadata["requested_model"] == "deepseek-flash"


def test_deepseek_provider_rejects_other_hosts():
    with pytest.raises(ValueError):
        ProviderConfig(provider_id="deepseek", base_url="https://api.renwang-huang.top")


def test_deepseek_native_command_uses_v2_rollout_without_ephemeral_or_code_mode():
    command = native_command(_config(protocol="v2"), "http://127.0.0.1:9180/v1")
    assert "--ephemeral" not in command
    assert command[command.index("--enable") + 1] == "multi_agent_v2"
    assert "multi_agent" in command and "multi_agent_v2" in command
    assert "--disable" in command
    assert "code_mode" not in command
    assert "code_mode_only" not in command


def test_deepseek_native_command_can_freeze_v1_protocol():
    command = native_command(_config(protocol="v1"), "http://127.0.0.1:9180/v1")
    assert "--ephemeral" not in command
    index = command.index("multi_agent")
    assert command[index - 1] == "--enable"
    assert command[command.index("multi_agent_v2") - 1] == "--disable"


def test_deepseek_native_command_carries_explicit_delegation_budget():
    config = _config(protocol="v2", mode="multi")
    config = config.__class__(
        binary=config.binary,
        auth_path=config.auth_path,
        model=config.model,
        timeout_seconds=config.timeout_seconds,
        provider_id=config.provider_id,
        reasoning_effort=config.reasoning_effort,
        gateway_url=config.gateway_url,
        request_budget=config.request_budget,
        completion_policy=config.completion_policy,
        agent_mode=config.agent_mode,
        agent_protocol=config.agent_protocol,
        max_agent_threads=3,
        max_child_agents=2,
    )
    command = native_command(config, "http://127.0.0.1:9180/v1")
    assert 'agents.max_concurrent_threads_per_session=3' in command
