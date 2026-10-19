"""Recover owned worker scopes after trusted pytest terminates abruptly."""
import json
import os
from pathlib import Path
import re
import stat

from benchmark.resources import CgroupScope, ResourceLimits


def recover_worker_scopes(artifacts: Path) -> list[dict]:
    records = []
    parent = Path(os.environ.get("ORDERFLOW_CGROUP_PARENT", "/nonexistent")).absolute()
    for path in sorted(artifacts.glob("pool-resource-*.json")):
        result = {"source_record": str(path), "availability": "AVAILABLE", "cleanup_complete": False}
        try:
            entry = path.lstat()
            if not stat.S_ISREG(entry.st_mode) or entry.st_nlink != 1 or entry.st_uid != os.getuid() or entry.st_size > 100_000:
                raise ValueError("Invalid owned pool receipt")
            record = json.loads(path.read_text())
            if record.get("source") != "trusted_worker_supervisor" or record.get("owner_uid") != os.getuid():
                raise ValueError("Pool receipt is not from this trusted supervisor owner")
            scope = Path(record["cgroup_path"]).absolute()
            if (scope.parent != parent or not re.fullmatch(r"orderflow-[a-f0-9-]{36}", scope.name)
                    or scope.is_symlink() or parent.resolve() != parent):
                raise ValueError("Refusing to recover an unowned cgroup path")
            if not str(parent).startswith("/sys/fs/cgroup/"):
                raise ValueError("Pool parent is outside cgroup v2")
            limits = ResourceLimits(**record["limits"])
            result["original_cleanup_complete"] = record.get("cleanup_complete")
            result["cgroup"] = CgroupScope(scope, limits).close()
            control = record.get("control_directory")
            if control:
                directory = Path(control).absolute()
                if directory.parent != Path("/tmp") or not directory.name.startswith("of-worker-control-"):
                    raise ValueError("Refusing to recover an unowned control directory")
                if directory.exists():
                    metadata = directory.lstat()
                    if (not stat.S_ISDIR(metadata.st_mode) or directory.is_symlink()
                            or metadata.st_uid != os.getuid() or metadata.st_mode & 0o077):
                        raise ValueError("Invalid control directory ownership")
                    # No active worker remains after cgroup.kill. Delete only
                    # bounded ordinary socket endpoints, never follow links.
                    entries = list(directory.iterdir())
                    if len(entries) > 4 or any(not stat.S_ISSOCK(p.lstat().st_mode) for p in entries):
                        raise ValueError("Unexpected contents in owned control directory")
                    for endpoint in entries:
                        endpoint.unlink()
                    directory.rmdir()
                result["control_directory_removed"] = not directory.exists()
            result["cleanup_complete"] = result["cgroup"]["cleanup_complete"]
        except (OSError, ValueError, TypeError, KeyError) as error:
            result.update(availability="UNAVAILABLE", error=f"{type(error).__name__}: {error}")
        records.append(result)
    return records
