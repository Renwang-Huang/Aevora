"""Outer filesystem boundary for the entire native Codex participant runtime.

The host runner owns the mounts. Neither host identity files nor maintainer
directories are mounted. There is deliberately no ordinary-subprocess fallback.
Strict execution has a private network namespace and only an explicitly mounted
per-run Unix-domain model channel. The default argument remains the historical
offline helper policy for compatibility; live adapters must request strict mode.
"""
from pathlib import Path
import json
import shutil
import stat

from benchmark.resources import PARTICIPANT_LIMITS, ResourceLimits


def _directory(path: Path, label: str) -> Path:
    if path.is_symlink():
        raise ValueError(f"{label} must not be a symlink")
    resolved = path.resolve(strict=True)
    if not resolved.is_dir():
        raise ValueError(f"{label} must be a directory")
    return resolved


def _executable(path: Path, label: str) -> Path:
    resolved = path.resolve(strict=True)
    mode = resolved.stat().st_mode
    if not stat.S_ISREG(mode) or not mode & 0o111:
        raise ValueError(f"{label} must be an executable regular file")
    return resolved


def participant_command(workspace: Path, state: Path, codex_binary: Path,
                        command: list[str], *, broker_socket: Path | None = None,
                        aevora_socket: Path | None = None,
                        aevora_proxy: Path | None = None,
                        code_mode_host_binary: Path | None = None,
                        network_isolated: bool = False,
                        resources: ResourceLimits = PARTICIPANT_LIMITS) -> list[str]:
    """Build an explicit bwrap invocation for a fresh participant session.

    ``state`` is a host-created directory; it is not the host CODEX_HOME. Native
    CLI metadata from an earlier version probe in this same run may exist.
    The native CLI must retain its own workspace-write/never approval policy.
    Local offline probes may run under this same outer boundary. This helper
    rejects known native sandbox bypass options even though the outer boundary
    would remain in place.
    """
    bwrap_name = shutil.which("bwrap")
    git_name = shutil.which("git")
    if not bwrap_name or not git_name:
        raise RuntimeError("bubblewrap and git are required; refusing unisolated participant execution")
    workspace = _directory(workspace, "Participant workspace")
    state = _directory(state, "Participant state")
    if workspace == state or workspace in state.parents or state in workspace.parents:
        raise ValueError("Participant workspace and state must be separate directories")
    for item in state.rglob("*"):
        if item.name in ("auth.json", "credentials.json", "config.toml"):
            raise ValueError("Participant state must not contain identity or host configuration")
        if item.is_symlink():
            # Native CLI creates aliases to itself while checking its version.
            # An exact sandbox destination is safe; arbitrary host links are not.
            if str(item.readlink()) != "/opt/codex/codex":
                raise ValueError("Participant state contains an unsafe symlink")
        elif item.is_file():
            if item.stat().st_nlink != 1:
                raise ValueError("Participant state contains a hard link")
        elif not item.is_dir():
            raise ValueError("Participant state contains a special file")
    codex_binary = _executable(codex_binary, "Codex binary")
    if broker_socket is not None:
        if broker_socket.is_symlink() or not stat.S_ISSOCK(broker_socket.lstat().st_mode):
            raise ValueError("Model channel must be a dedicated Unix-domain socket")
        broker_socket = broker_socket.resolve(strict=True)
        network_isolated = True
    if (aevora_socket is None) != (aevora_proxy is None):
        raise ValueError("Aevora requires both a scoped socket and its trusted stdlib proxy")
    if aevora_socket is not None:
        if aevora_socket.is_symlink() or not stat.S_ISSOCK(aevora_socket.lstat().st_mode):
            raise ValueError("Aevora channel must be a dedicated Unix-domain socket")
        if aevora_proxy.is_symlink() or not aevora_proxy.is_file() or aevora_proxy.stat().st_nlink != 1:
            raise ValueError("Aevora proxy must be an ordinary trusted single-link file")
        aevora_socket = aevora_socket.resolve(strict=True)
        aevora_proxy = aevora_proxy.resolve(strict=True)
        network_isolated = True
    if not isinstance(network_isolated, bool):
        raise ValueError("network_isolated must be a boolean")
    bwrap = _executable(Path(bwrap_name), "bubblewrap binary")
    git = _executable(Path(git_name), "git binary")
    if not command or not all(isinstance(part, str) and part and "\x00" not in part for part in command):
        raise ValueError("A nonempty argument vector is required")
    forbidden = ("danger-full-access", "dangerously-bypass-approvals-and-sandbox", "--yolo")
    if any(marker in argument for marker in forbidden for argument in command):
        raise ValueError("Native Codex sandbox bypass is forbidden")
    args = [str(bwrap), "--die-with-parent", "--unshare-user", "--unshare-pid",
            "--unshare-ipc", "--unshare-uts", "--cap-drop", "ALL",
            "--ro-bind", "/usr", "/usr"]
    if network_isolated:
        args += ["--unshare-net"]
    for path in ("/lib", "/lib64", "/bin"):
        source = Path(path)
        if source.is_symlink():
            args += ["--symlink", str(source.readlink()), path]
        elif source.exists():
            args += ["--ro-bind", path, path]
    args += ["--proc", "/proc", "--dev", "/dev", "--tmpfs", "/tmp",
             "--dir", "/tools", "--dir", "/opt", "--dir", "/opt/codex",
             "--ro-bind", str(bwrap), "/tools/bwrap",
             "--ro-bind", str(git), "/tools/git",
             "--ro-bind", str(codex_binary), "/opt/codex/codex",
             "--bind", str(workspace), "/workspace",
             "--bind", str(state), "/codex-state"]
    args += ["--ro-bind", str(Path(__file__).with_name("resources.py").resolve(strict=True)),
             "/resource_launcher.py"]
    if aevora_socket is not None:
        args += ["--dir", "/aevora-channel", "--ro-bind", str(aevora_socket),
                 "/aevora-channel/mcp.sock", "--ro-bind", str(aevora_proxy), "/aevora_mcp_proxy.py"]
    if code_mode_host_binary is not None:
        helper = _executable(code_mode_host_binary, "Official Code Mode host")
        args += ["--ro-bind", str(helper), "/opt/codex/codex-code-mode-host"]
    if broker_socket is not None:
        args += ["--dir", "/model-channel", "--ro-bind", str(broker_socket),
                 "/model-channel/broker.sock"]
        bridge = Path(__file__).resolve().parents[1] / "integrations" / "participant_bridge.py"
        args += ["--ro-bind", str(bridge.resolve(strict=True)), "/model_bridge.py"]
    # Infrastructure only. No /etc directory, user home or host Codex settings.
    args += ["--dir", "/etc"]
    resolver = Path("/etc/resolv.conf")
    if resolver.exists() and not network_isolated:
        args += ["--ro-bind", str(resolver.resolve(strict=True)), "/etc/resolv.conf"]
    certificates = Path("/etc/ssl/certs")
    if certificates.exists():
        args += ["--dir", "/etc/ssl", "--ro-bind", str(certificates.resolve(strict=True)), "/etc/ssl/certs"]
    args += ["--chdir", "/workspace", "--clearenv",
             "--setenv", "HOME", "/tmp", "--setenv", "CODEX_HOME", "/codex-state",
             "--setenv", "PATH", "/tools:/opt/codex:/usr/bin:/bin",
             "--setenv", "LANG", "C.UTF-8", "--setenv", "PYTHONHASHSEED", "0",
             "--setenv", "MALLOC_ARENA_MAX", "2"]
    return args + ["/usr/bin/python3.12", "-I", "-B", "/resource_launcher.py", "--supervise",
                   "--limits", json.dumps(resources.as_dict(), separators=(",", ":")),
                   "--", *command]
