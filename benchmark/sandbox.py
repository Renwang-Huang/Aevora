"""Physical filesystem boundary using the existing bubblewrap sandbox tool.

Never fall back to an ordinary subprocess when isolation is unavailable.
Hidden pytest runs on the host, and only a generic business RPC worker is mounted.
"""
from pathlib import Path
import json
import shutil
import stat
import sys

from benchmark.resources import CANDIDATE_LIMITS, ResourceLimits


def sandbox_command(workspace: Path, command: list[str], *, writable=False,
                    data_dir: Path | None = None, worker: Path | None = None,
                    control_socket: Path | None = None,
                    resources: ResourceLimits = CANDIDATE_LIMITS) -> list[str]:
    bwrap = shutil.which("bwrap")
    if not bwrap:
        raise RuntimeError("bubblewrap is required; refusing unisolated execution")
    workspace = workspace.resolve(strict=True)
    if not workspace.is_dir():
        raise ValueError("Workspace must be a directory")
    args = [bwrap, "--die-with-parent", "--unshare-user", "--unshare-pid",
            "--unshare-ipc", "--unshare-uts", "--unshare-net", "--cap-drop", "ALL",
            "--ro-bind", "/usr", "/usr"]
    for path in ("/lib", "/lib64", "/bin"):
        p = Path(path)
        if p.is_symlink():
            args += ["--symlink", str(p.readlink()), path]
        elif p.exists():
            args += ["--ro-bind", path, path]
    args += ["--proc", "/proc", "--dev", "/dev", "--tmpfs", "/tmp"]
    base = Path(sys.base_prefix).resolve()
    if base != Path("/usr"):
        # Venv's base runtime only: the evaluator package and editable .pth stay outside.
        args += ["--ro-bind", str(base), str(base)]
    args += ["--bind" if writable else "--ro-bind", str(workspace), "/workspace"]
    if data_dir is not None:
        args += ["--bind", str(data_dir.resolve(strict=True)), "/data"]
    if worker is not None:
        args += ["--ro-bind", str(worker.resolve(strict=True)), "/worker.py"]
    if control_socket is not None:
        # Only this explicitly selected scheduling endpoint is visible. Never
        # mount its parent, a model channel, or a host file-service directory.
        socket_path = Path(control_socket).absolute()
        if (socket_path.is_symlink() or socket_path.resolve(strict=True) != socket_path
                or not stat.S_ISSOCK(socket_path.lstat().st_mode)):
            raise ValueError("Control endpoint must be an ordinary Unix-domain socket")
        parent = socket_path.parent.lstat()
        if not stat.S_ISDIR(parent.st_mode) or parent.st_uid != socket_path.lstat().st_uid or parent.st_mode & 0o077:
            raise ValueError("Control socket requires a private, owner-only directory")
        args += ["--ro-bind", str(socket_path), "/control.sock"]
    args += ["--ro-bind", str(Path(__file__).with_name("resources.py").resolve(strict=True)),
             "/resource_launcher.py"]
    args += ["--chdir", "/workspace", "--clearenv", "--setenv", "HOME", "/tmp",
             "--setenv", "PATH", f"{base}/bin:/usr/bin:/bin", "--setenv", "PYTHONHASHSEED", "0",
             "--setenv", "MALLOC_ARENA_MAX", "2"]
    return args + [runtime_python(), "-I", "-B", "/resource_launcher.py", "--supervise",
                   "--limits", json.dumps(resources.as_dict(), separators=(",", ":")),
                   "--", *command]


def runtime_python() -> str:
    return str(Path(sys.base_prefix) / "bin" / "python3.12")
