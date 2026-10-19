"""Bounded Linux execution using rlimits, cgroup v2 and a host watchdog.

cgroup memory/pids limits are kernel enforced. CPU is bounded by inherited
RLIMIT_CPU and aggregate /proc sampling when the cpu controller is not delegated.
The sampled fallback is explicitly weaker than cgroups: it has a polling window.
Only the trusted runner may mount or write the cgroup hierarchy.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import argparse
import json
import math
import os
from pathlib import Path
import resource
import signal
import stat
import subprocess
import sys
import threading
import time
import uuid


class SecurityGateError(RuntimeError):
    """A requested safety mechanism cannot be established; do not fall back."""


@dataclass(frozen=True)
class ResourceLimits:
    wall_seconds: float | None = 1200
    cpu_seconds: int = 600
    address_space_bytes: int = 2 * 1024**4
    memory_bytes: int = 2 * 1024**3
    max_tasks: int = 768
    file_bytes: int = 64 * 1024**2
    open_files: int = 512
    output_bytes: int = 128 * 1024**2
    max_files: int = 10000
    poll_seconds: float = 0.05

    def __post_init__(self):
        for name in ("wall_seconds", "poll_seconds"):
            value = getattr(self, name)
            if name == "wall_seconds" and value is None:
                continue  # Explicit completion-aware policy; other limits remain.
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
                raise ValueError(f"{name} must be a finite positive number")
        for name in ("cpu_seconds", "address_space_bytes", "memory_bytes", "max_tasks", "file_bytes", "open_files", "output_bytes", "max_files"):
            value = getattr(self, name)
            if type(value) is not int or value <= 0:
                raise ValueError(f"{name} must be a positive integer")
        if (self.wall_seconds is not None and self.wall_seconds > 7200) or self.cpu_seconds > 7200 or self.poll_seconds > 1:
            raise ValueError("Runtime budgets exceed the permitted bounded range")
        if self.memory_bytes > 16 * 1024**3 or self.memory_bytes > self.address_space_bytes:
            raise ValueError("Resident memory budget must not exceed address-space budget")
        if self.max_tasks > 2048 or self.open_files > 8192:
            raise ValueError("Process/file budgets exceed the permitted bounded range")

    def as_dict(self) -> dict:
        return asdict(self)


PARTICIPANT_LIMITS = ResourceLimits()
CANDIDATE_LIMITS = ResourceLimits(wall_seconds=90, cpu_seconds=45,
    address_space_bytes=4 * 1024**3, memory_bytes=512 * 1024**2,
    max_tasks=512, file_bytes=16 * 1024**2, open_files=256,
    output_bytes=32 * 1024**2, max_files=2000)


def apply_rlimits(limits: ResourceLimits) -> None:
    """Apply hard limits before executing any untrusted code; child inherits them."""
    for kind, value in ((resource.RLIMIT_CPU, limits.cpu_seconds),
                        (resource.RLIMIT_AS, limits.address_space_bytes),
                        (resource.RLIMIT_FSIZE, limits.file_bytes),
                        (resource.RLIMIT_NOFILE, limits.open_files),
                        (resource.RLIMIT_CORE, 0)):
        _, old_hard = resource.getrlimit(kind)
        if old_hard != resource.RLIM_INFINITY:
            value = min(value, old_hard)
        resource.setrlimit(kind, (value, value))
    # RLIMIT_NPROC is per real UID rather than per run, so it is not used as a
    # misleading substitute for cgroup pids.max. Aggregate sampling also counts
    # threads in addition to processes.


def _processes() -> dict[int, dict]:
    result = {}
    page_size = os.sysconf("SC_PAGE_SIZE")
    clock_ticks = os.sysconf("SC_CLK_TCK")
    for path in Path("/proc").iterdir():
        if not path.name.isdecimal():
            continue
        try:
            raw = (path / "stat").read_text()
            parts = raw[raw.rindex(")") + 2:].split()
            result[int(path.name)] = {
                "ppid": int(parts[1]), "pgrp": int(parts[2]),
                "start_ticks": int(parts[19]), "threads": int(parts[17]),
                "rss_bytes": max(0, int(parts[21])) * page_size,
                "cpu_seconds": (int(parts[11]) + int(parts[12])) / clock_ticks,
                "state": parts[0],
            }
        except (OSError, ValueError, IndexError):
            continue
    return result


class ResourceWatchdog:
    """Trusted aggregate monitor for a root process and all observed descendants.

    cgroups should be used in addition for strict memory/pid enforcement. This
    watchdog accounts for children that create new process groups; exited/reaped
    very short children can escape CPU sampling, a documented fallback limit.
    """
    def __init__(self, pid: int, limits: ResourceLimits, *, output_roots: tuple[Path, ...] = ()):
        if type(pid) is not int or pid <= 1 or pid == os.getpid():
            raise ValueError("Watchdog requires a separate child process")
        self.pid = pid
        self.limits = limits
        self.output_roots = tuple(Path(path) for path in output_roots)
        self._stop = threading.Event()
        self._thread = None
        self._lock = threading.Lock()
        self._known: dict[int, int] = {}
        self._cpu: dict[tuple[int, int], float] = {}
        self._started = time.monotonic()
        self._violation = None
        self._peak_rss = 0
        self._peak_tasks = 0
        self._peak_output = 0
        self._peak_files = 0
        self._last_pids: list[int] = []
        self._cleanup_remaining: list[int] = []
        self._output_error = None

    def _sample(self) -> dict:
        processes = _processes()
        root = processes.get(self.pid)
        if root and self.pid not in self._known:
            self._known[self.pid] = root["start_ticks"]
        selected = {pid for pid, ticks in self._known.items()
                    if pid in processes and processes[pid]["start_ticks"] == ticks}
        while True:
            new = {pid for pid, row in processes.items() if row["ppid"] in selected} - selected
            if not new:
                break
            selected |= new
        for pid in selected:
            row = processes[pid]
            self._known[pid] = row["start_ticks"]
            self._cpu[(pid, row["start_ticks"])] = max(
                self._cpu.get((pid, row["start_ticks"]), 0), row["cpu_seconds"])
        active = [pid for pid in selected if processes[pid]["state"] != "Z"]
        output_bytes = files = 0
        directories = list(self.output_roots)
        visited = set()
        while directories:
            directory = directories.pop()
            try:
                identity = directory.stat(follow_symlinks=False)
                if not stat.S_ISDIR(identity.st_mode) or (identity.st_dev, identity.st_ino) in visited:
                    continue
                visited.add((identity.st_dev, identity.st_ino))
                with os.scandir(directory) as entries:
                    for entry in entries:
                        item = entry.stat(follow_symlinks=False)
                        # Count directories and links too, so an empty-directory
                        # flood cannot make the scan itself unbounded.
                        files += 1
                        if stat.S_ISDIR(item.st_mode):
                            directories.append(Path(entry.path))
                        else:
                            if stat.S_ISREG(item.st_mode):
                                output_bytes += item.st_size
                        if files > self.limits.max_files or output_bytes > self.limits.output_bytes:
                            directories.clear()
                            break
            except (FileNotFoundError, NotADirectoryError):
                continue
            except OSError as error:
                # Candidate chmod/races must not silently disable the monitor.
                self._output_error = {"kind": type(error).__name__, "errno": error.errno}
                directories.clear()
        sample = {"wall_seconds": time.monotonic() - self._started,
                  "rss_bytes": sum(processes[pid]["rss_bytes"] for pid in active),
                  "tasks": sum(processes[pid]["threads"] for pid in active),
                  "cpu_seconds": sum(self._cpu.values()), "pids": active,
                  "output_bytes": output_bytes, "files": files}
        with self._lock:
            self._peak_rss = max(self._peak_rss, sample["rss_bytes"])
            self._peak_tasks = max(self._peak_tasks, sample["tasks"])
            self._peak_output = max(self._peak_output, output_bytes)
            self._peak_files = max(self._peak_files, files)
            self._last_pids = active
        return sample

    def _kill_observed(self, signum: int) -> None:
        processes = _processes()
        # Only kill identity-matched observed PIDs. Do not signal an unrelated
        # process group, and do not trust a reused numerical PID.
        for pid, ticks in reversed(list(self._known.items())):
            if pid in processes and processes[pid]["start_ticks"] == ticks:
                try:
                    os.kill(pid, signum)
                except ProcessLookupError:
                    pass

    def _run(self) -> None:
        while not self._stop.is_set():
            sample = self._sample()
            violation = None
            if self._output_error:
                violation = {"kind": "RESOURCE_MONITOR_FAILED", "resource": "output_scan",
                             "error": self._output_error,
                             "monotonic_elapsed": sample["wall_seconds"]}
            for key, limit in (("wall_seconds", self.limits.wall_seconds),
                               ("cpu_seconds", self.limits.cpu_seconds),
                               ("rss_bytes", self.limits.memory_bytes),
                               ("tasks", self.limits.max_tasks),
                               ("output_bytes", self.limits.output_bytes),
                               ("files", self.limits.max_files)):
                if violation:
                    break
                if limit is not None and sample[key] > limit:
                    violation = {"kind": "RESOURCE_LIMIT_EXCEEDED", "resource": key,
                                 "observed": sample[key], "limit": limit,
                                 "monotonic_elapsed": sample["wall_seconds"]}
                    break
            if violation:
                with self._lock:
                    self._violation = violation
                self._kill_observed(signal.SIGTERM)
                self._stop.wait(min(0.2, self.limits.poll_seconds * 2))
                self._sample()
                self._kill_observed(signal.SIGKILL)
                return
            if not sample["pids"]:
                return
            self._stop.wait(self.limits.poll_seconds)

    def start(self) -> "ResourceWatchdog":
        if self._thread is not None:
            raise ValueError("Watchdog already started")
        self._thread = threading.Thread(target=self._run, name="orderflow-resource-watchdog", daemon=True)
        self._thread.start()
        return self

    def snapshot(self) -> dict:
        with self._lock:
            return {"enforcement": "RLIMIT_AND_AGGREGATE_PROC_WATCHDOG",
                    "limits": self.limits.as_dict(), "violation": self._violation,
                    "peak_rss_bytes": self._peak_rss, "peak_tasks": self._peak_tasks,
                    "peak_output_bytes": self._peak_output, "peak_files": self._peak_files,
                    "output_roots": [str(path) for path in self.output_roots],
                    "observed_process_count": len(self._known),
                    "remaining_pids": list(self._cleanup_remaining),
                    "cpu_seconds_sampled": sum(self._cpu.values()),
                    "limitations": ["Polling has a bounded detection window",
                        "CPU of reaped short-lived children can be undercounted without a cpu cgroup"]}

    def close(self, *, cleanup: bool = True) -> dict:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=2)
        self._sample()
        if cleanup:
            self._kill_observed(signal.SIGKILL)
            for _ in range(20):
                sample = self._sample()
                if not sample["pids"]:
                    break
                time.sleep(0.01)
        self._cleanup_remaining = self._sample()["pids"]
        return self.snapshot()


class CgroupScope:
    """One dedicated cgroup; its hierarchy is never mounted into untrusted code."""
    def __init__(self, path: Path, limits: ResourceLimits):
        self.path = path
        self.limits = limits
        self._closed = False
        self._final = None

    @classmethod
    def create(cls, limits: ResourceLimits, *, parent: Path | None = None) -> "CgroupScope":
        if parent is not None:
            choices = [Path(parent)]
        elif os.environ.get("ORDERFLOW_CGROUP_PARENT"):
            choices = [Path(os.environ["ORDERFLOW_CGROUP_PARENT"])]
        else:
            try:
                text = Path("/proc/self/cgroup").read_text().splitlines()
                relative = next(row[3:] for row in text if row.startswith("0::"))
                current = Path("/sys/fs/cgroup") / relative.lstrip("/")
                choices = [current, current.parent]
            except (OSError, StopIteration):
                choices = []
        for base in choices:
            path = base / ("orderflow-" + str(uuid.uuid4()))
            try:
                available = set((base / "cgroup.subtree_control").read_text().split())
                if not {"memory", "pids"} <= available:
                    continue
                path.mkdir(mode=0o700)
                if not all((path / name).exists() for name in ("memory.max", "pids.max")):
                    raise OSError("Required cgroup controls are not delegated")
                (path / "memory.max").write_text(str(limits.memory_bytes))
                if (path / "memory.swap.max").exists():
                    (path / "memory.swap.max").write_text("0")
                (path / "pids.max").write_text(str(limits.max_tasks))
                (path / "memory.oom.group").write_text("1")
                return cls(path, limits)
            except OSError:
                if path.exists():
                    try:
                        path.rmdir()
                    except OSError:
                        pass
        raise SecurityGateError("BLOCKED_SECURITY_GATE: delegated cgroup v2 memory/pids controls unavailable")

    def wrap_command(self, command: list[str]) -> list[str]:
        if self._closed:
            raise SecurityGateError("Cannot execute in a closed cgroup")
        return [sys.executable, "-I", "-B", str(Path(__file__).resolve()),
                "--limits", json.dumps(self.limits.as_dict(), separators=(",", ":")),
                "--cgroup", str(self.path), "--", *command]

    @property
    def metadata(self) -> dict:
        if self._final is not None:
            return dict(self._final)
        values = {}
        for name in ("memory.max", "memory.peak", "memory.events", "pids.max", "pids.peak", "pids.events"):
            try:
                values[name] = (self.path / name).read_text().strip()
            except OSError:
                values[name] = "UNAVAILABLE"
        return {"enforcement": "CGROUP_V2_MEMORY_PIDS", "path": str(self.path),
                "limits": self.limits.as_dict(), "kernel_controls": values,
                "cpu_controller": "UNAVAILABLE; RLIMIT_CPU and aggregate watchdog required",
                "cleanup_complete": self._closed}

    def close(self) -> dict:
        if self._closed:
            return self.metadata
        self._final = self.metadata
        try:
            if (self.path / "cgroup.kill").exists():
                (self.path / "cgroup.kill").write_text("1")
            else:
                for row in (self.path / "cgroup.procs").read_text().splitlines():
                    try:
                        os.kill(int(row), signal.SIGKILL)
                    except ProcessLookupError:
                        pass
            for _ in range(100):
                try:
                    self.path.rmdir()
                    self._closed = True
                    break
                except OSError:
                    time.sleep(0.01)
            self._final["cleanup_complete"] = self._closed
            if not self._closed:
                raise SecurityGateError("Dedicated resource cgroup could not be cleaned up")
        except FileNotFoundError:
            self._closed = True
            self._final["cleanup_complete"] = True
        return self.metadata


def _main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limits", required=True)
    parser.add_argument("--cgroup")
    parser.add_argument("--supervise", action="store_true")
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = args.command[1:] if args.command[:1] == ["--"] else args.command
    if not command:
        parser.error("A command is required")
    limits = ResourceLimits(**json.loads(args.limits))
    if args.cgroup:
        # This launcher is trusted and runs outside the participant namespace.
        # Move itself before exec/fork so every descendant inherits the cgroup.
        (Path(args.cgroup) / "cgroup.procs").write_text(str(os.getpid()))
    apply_rlimits(limits)
    if not args.supervise:
        os.execvpe(command[0], command, os.environ)
    process = subprocess.Popen(command, start_new_session=True)
    output_roots = tuple(path for path in (Path("/workspace"), Path("/codex-state"),
        Path("/data"), Path("/tmp")) if path.is_dir())
    watchdog = ResourceWatchdog(process.pid, limits, output_roots=output_roots).start()
    try:
        process.wait()
    finally:
        observation = watchdog.close(cleanup=True)
    if observation["violation"] is not None:
        print(json.dumps({"source": "trusted_resource_supervisor", **observation}), file=sys.stderr)
        return 124 if observation["violation"]["resource"] == "wall_seconds" else 137
    return process.returncode if process.returncode >= 0 else 128 - process.returncode


if __name__ == "__main__":
    raise SystemExit(_main())
