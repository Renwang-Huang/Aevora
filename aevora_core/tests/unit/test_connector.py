from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import pytest

from aevora.mcp_connect import read_grant
from aevora.cli import parser


@pytest.fixture
def grant(tmp_path):
    d = tmp_path / "private"
    d.mkdir(mode=0o700)
    p = d / "grant.json"
    value = {
        "AEVORA_RUN_ID": "test-ordinary",
        "AEVORA_RUN_TOKEN": "test_only_" + ("x" * 40),
        "socket": str(d / "mcp.sock"),
        "consumer_socket": "/aevora-channel/mcp.sock",
        "transport": "aevora-mcp-uds-v1",
    }
    p.write_text(json.dumps(value))
    p.chmod(0o600)
    return p


def test_local_scoped_grant(grant):
    assert read_grant(grant)["AEVORA_RUN_ID"] == "test-ordinary"


@pytest.mark.parametrize(
    "change",
    [
        lambda v: v.update(
            expires_at=(datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat()
        ),
        lambda v: v.update(socket="/tmp/arbitrary-other-socket"),
        lambda v: v.update(password="must-not-be-a-db-credential"),
        lambda v: v.update(transport="unknown"),
    ],
)
def test_invalid_scoped_grant(grant, change):
    v = json.loads(grant.read_text())
    change(v)
    grant.write_text(json.dumps(v))
    with pytest.raises(ValueError):
        read_grant(grant)


def test_grant_world_access_refused(grant):
    grant.chmod(0o644)
    with pytest.raises(ValueError):
        read_grant(grant)


def test_linked_grant_refused(grant):
    p = grant.parent / "linked.json"
    p.symlink_to(grant)
    with pytest.raises(ValueError):
        read_grant(p)


def test_duplicate_grant_key_refused(grant):
    grant.write_text('{"transport":"aevora-mcp-uds-v1","transport":"unknown"}')
    with pytest.raises(ValueError):
        read_grant(grant)


def test_default_connection_has_no_fixed_ttl():
    args = parser().parse_args(
        [
            "serve",
            "--run-id",
            "r",
            "--context",
            "context.json",
            "--socket",
            "mcp.sock",
            "--capability-file",
            "grant.json",
            "--events",
            "events.jsonl",
        ]
    )
    assert args.capability_ttl is None


def test_public_cli_error_boundary_is_sanitized(monkeypatch, capsys):
    from aevora import cli
    from aevora.models import GraphUnavailable

    def fail(_=None):
        raise GraphUnavailable("test only confidential connection detail")

    monkeypatch.setattr(cli, "main", fail)
    assert cli.entrypoint(["health"]) == 2
    captured = capsys.readouterr()
    assert json.loads(captured.err) == {
        "status": "ERROR",
        "error_type": "GraphUnavailable",
    }
    assert "confidential" not in captured.err and "Traceback" not in captured.err
