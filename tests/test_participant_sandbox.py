"""Physical bwrap tests; git is a test executable, not a simulated Codex run."""
import json
from pathlib import Path
import shutil
import subprocess

import pytest

from benchmark.participant_sandbox import participant_command


def _inputs(tmp_path):
    workspace = tmp_path / "participant"
    state = tmp_path / "state"
    workspace.mkdir()
    state.mkdir()
    return workspace, state, Path(shutil.which("git"))


def test_participant_physical_boundary_and_proc_root(tmp_path):
    workspace, state, executable = _inputs(tmp_path)
    (workspace / "public.txt").write_text("public canary")
    maintainer = tmp_path / "maintainer"
    maintainer.mkdir()
    files = {}
    for label in ("hidden_tests", "reference_patch", "private_manifest", "host_source", "other_run", "auth"):
        source = maintainer / label
        source.write_text("private synthetic canary: " + label)
        files[label] = str(source)
        files["proc_root_" + label] = "/proc/1/root" + str(source)
    root = Path(__file__).resolve().parents[1]
    files["real_hidden_suite"] = str(root / "evaluator")
    files["real_maintainer_source"] = str(root / "benchmark" / "runner.py")
    files["host_home_auth"] = "/home/private-user/.codex/auth.json"
    program = """
import json, pathlib, os
targets = json.loads(os.environ['TEST_TARGETS'])
result = {}
for label, path in targets.items():
    try:
        item = pathlib.Path(path)
        if item.is_dir():
            list(item.iterdir())
        else:
            item.read_bytes()
        result[label] = 'READABLE'
    except OSError:
        result[label] = 'DENIED'
result['public'] = pathlib.Path('/workspace/public.txt').read_text()
result['auth_files'] = list(pathlib.Path('/codex-state').glob('auth.json'))
result['host_environment'] = os.environ.get('PRIVATE_HOST_CANARY', 'ABSENT')
print(json.dumps(result))
"""
    command = participant_command(workspace, state, executable, ["/usr/bin/python3.12", "-c", program])
    # Test target paths are public probes, not a mount or host-secret contents.
    insertion = command.index("--clearenv") + 1
    command[insertion:insertion] = ["--setenv", "TEST_TARGETS", json.dumps(files)]
    completed = subprocess.run(command, text=True, capture_output=True, timeout=20,
                               env={"PRIVATE_HOST_CANARY": "must not survive", "PATH": "/tools:/usr/bin"})
    assert completed.returncode == 0, completed.stderr
    result = json.loads(completed.stdout)
    assert all(result[label] == "DENIED" for label in files), result
    assert result["public"] == "public canary"
    assert result["auth_files"] == []
    assert result["host_environment"] == "ABSENT"


def test_participant_mounts_real_tool_and_writable_public_workspace(tmp_path):
    workspace, state, executable = _inputs(tmp_path)
    completed = subprocess.run(participant_command(workspace, state, executable,
        ["/usr/bin/python3.12", "-c",
         "import pathlib,subprocess; pathlib.Path('/workspace/change').write_text('actual'); print(subprocess.check_output(['/tools/git','--version'],text=True).strip())"]),
        text=True, capture_output=True, timeout=20)
    assert completed.returncode == 0, completed.stderr
    assert completed.stdout.startswith("git version ")
    assert (workspace / "change").read_text() == "actual"


def test_missing_bwrap_never_falls_back(tmp_path, monkeypatch):
    workspace, state, executable = _inputs(tmp_path)
    monkeypatch.setattr(shutil, "which", lambda _: None)
    with pytest.raises(RuntimeError, match="refusing unisolated"):
        participant_command(workspace, state, executable, ["/opt/codex/codex", "--version"])


@pytest.mark.parametrize("option", ["danger-full-access", "--dangerously-bypass-approvals-and-sandbox", "--yolo"])
def test_native_bypass_options_are_rejected(tmp_path, option):
    workspace, state, executable = _inputs(tmp_path)
    with pytest.raises(ValueError, match="bypass"):
        participant_command(workspace, state, executable, ["/opt/codex/codex", option])


@pytest.mark.parametrize("name", ["auth.json", "credentials.json", "config.toml"])
def test_identity_cannot_enter_participant_state(tmp_path, name):
    workspace, state, executable = _inputs(tmp_path)
    (state / name).write_text("synthetic identity/config")
    with pytest.raises(ValueError, match="identity"):
        participant_command(workspace, state, executable, ["/opt/codex/codex", "--version"])


def test_only_fixed_native_cli_alias_is_allowed(tmp_path):
    workspace, state, executable = _inputs(tmp_path)
    alias = state / "native-alias"
    alias.symlink_to("/opt/codex/codex")
    assert participant_command(workspace, state, executable, ["/tools/git", "--version"])
    alias.unlink()
    alias.symlink_to(tmp_path / "maintainer-secret")
    with pytest.raises(ValueError, match="symlink"):
        participant_command(workspace, state, executable, ["/tools/git", "--version"])


def test_state_hardlinks_and_overlapping_directories_are_rejected(tmp_path):
    workspace, state, executable = _inputs(tmp_path)
    source = tmp_path / "secret"
    source.write_text("synthetic private canary")
    (state / "linked").hardlink_to(source)
    with pytest.raises(ValueError, match="hard link"):
        participant_command(workspace, state, executable, ["/tools/git", "--version"])
    with pytest.raises(ValueError, match="separate"):
        participant_command(workspace, workspace, executable, ["/tools/git", "--version"])


def test_mount_policy_has_no_host_identity_or_network_claim(tmp_path):
    workspace, state, executable = _inputs(tmp_path)
    args = participant_command(workspace, state, executable, ["/tools/git", "--version"])
    assert "--unshare-net" not in args
    assert "--clearenv" in args
    assert "--unshare-pid" in args
    assert "/maintainer/auth.json" not in args
    assert "/home/private-user/.codex" not in args
    assert args[args.index("CODEX_HOME") + 1] == "/codex-state"
