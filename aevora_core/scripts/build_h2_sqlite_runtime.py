#!/usr/bin/env python3
"""Build a separately pinned SQLite runtime; never modify a baseline runtime.

Uses the official SQLite 3.51.3 amalgamation (WAL-reset fix) and gcc. The
source's SHA3-256 is the official release value. New inputs/outputs/commands
are archived; these receipts are not a signed build attestation.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile
import time

URL = "https://www.sqlite.org/2026/sqlite-autoconf-3510300.tar.gz"
C_SHA3 = "32d5424f97e0a7fc5ed2f6335afbb58be4e0298bd7117a34e39d345ff13d859e"


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--runtime-root", type=Path, required=True)
    p.add_argument("--destination", type=Path, required=True)
    p.add_argument("--evidence-directory", type=Path, required=True)
    args = p.parse_args()
    source = args.runtime_root.resolve(strict=True)
    destination = args.destination.absolute()
    evidence = args.evidence_directory.absolute()
    if destination.exists() or evidence.exists():
        raise SystemExit("Refusing to overwrite runtime or evidence")
    if not (source / "bin/python3.12").is_file():
        raise SystemExit("Expected explicit Python 3.12 /usr runtime")
    evidence.mkdir(parents=True, mode=0o700)
    download = evidence / "sqlite-autoconf-3510300.tar.gz"
    env = {"PATH": "/usr/bin:/bin", "HOME": str(evidence), "LANG": "C.UTF-8",
           "CCACHE_DISABLE": "1"}

    def run(label, command, cwd=None):
        out = evidence / label
        out.mkdir()
        started = time.time()
        with (out / "stdout.log").open("wb") as stdout, (out / "stderr.log").open("wb") as stderr:
            result = subprocess.run(command, cwd=cwd, env=env, stdout=stdout, stderr=stderr,
                                    timeout=300, check=False)
        receipt = {"argv": command, "cwd": str(cwd) if cwd else str(Path.cwd()),
                   "started_unix": started, "elapsed_seconds": time.time() - started,
                   "exit_code": result.returncode,
                   "stdout_sha256": hashlib.sha256((out / "stdout.log").read_bytes()).hexdigest(),
                   "stderr_sha256": hashlib.sha256((out / "stderr.log").read_bytes()).hexdigest()}
        (out / "command.json").write_text(json.dumps(receipt, indent=2) + "\n")
        if result.returncode:
            raise RuntimeError(f"{label} exited {result.returncode}; raw receipt retained")

    run("01-download", ["/usr/bin/curl", "--fail", "--location", "--proto", "=https",
        "--tlsv1.2", "--max-time", "60", "--output", str(download), URL])
    if download.stat().st_size > 8 * 1024 * 1024:
        raise RuntimeError("Unexpected archive size")
    extracted = evidence / "source"
    extracted.mkdir()
    with tarfile.open(download) as archive:
        members = archive.getmembers()
        if len(members) > 1000 or sum(m.size for m in members) > 64 * 1024 * 1024:
            raise RuntimeError("Archive resource bounds exceeded")
        for member in members:
            path = Path(member.name)
            if (path.is_absolute() or ".." in path.parts or not path.parts
                    or path.parts[0] != "sqlite-autoconf-3510300"
                    or not (member.isfile() or member.isdir())):
                raise RuntimeError("Archive member rejected")
        archive.extractall(extracted, members=members)
    amalgamation = extracted / "sqlite-autoconf-3510300/sqlite3.c"
    actual = hashlib.sha3_256(amalgamation.read_bytes()).hexdigest()
    if actual != C_SHA3:
        raise RuntimeError("Official release amalgamation SHA3 mismatch")
    library = evidence / "libsqlite3.so.0.8.6"
    run("02-compile", ["/usr/bin/gcc", "-shared", "-O2", "-fPIC", "-DSQLITE_THREADSAFE=1",
        "-DSQLITE_ENABLE_COLUMN_METADATA", "-DSQLITE_ENABLE_FTS5", "-DSQLITE_ENABLE_RTREE",
        "-Wl,-soname,libsqlite3.so.0", "-o", str(library), str(amalgamation), "-lm", "-ldl", "-lpthread"])
    shutil.copytree(source, destination, symlinks=True)
    target = destination / "lib/x86_64-linux-gnu/libsqlite3.so.0.8.6"
    if not target.is_file() or target.is_symlink():
        raise RuntimeError("Unexpected original runtime SQLite library layout")
    original_sha = hashlib.sha256(target.read_bytes()).hexdigest()
    shutil.copyfile(library, target)
    probe = "import json, sqlite3, sys, os; print(json.dumps({'python':sys.version,'sqlite':sqlite3.sqlite_version,'source_id':sqlite3.connect(':memory:').execute('select sqlite_source_id()').fetchone()[0],'pidfd_open':hasattr(os,'pidfd_open')}))"
    run("03-runtime-probe", ["/usr/bin/bwrap", "--die-with-parent", "--unshare-user", "--unshare-pid",
        "--unshare-net", "--ro-bind", str(destination), "/usr", "--symlink", "usr/lib", "/lib",
        "--symlink", "usr/lib64", "/lib64", "--proc", "/proc", "--dev", "/dev", "--tmpfs", "/tmp",
        "--clearenv", "--setenv", "HOME", "/tmp", "/usr/bin/python3.12", "-I", "-c", probe])
    observed = json.loads((evidence / "03-runtime-probe/stdout.log").read_text())
    if observed["sqlite"] != "3.51.3" or not observed["pidfd_open"]:
        raise RuntimeError("Pinned runtime capability mismatch")
    result = {"status": "PASS_BUILD_CAPABILITIES_NOT_BUSINESS_ACCEPTANCE", "runtime_root": str(destination),
              "base_runtime": str(source), "source_url": URL, "sqlite3_c_sha3_256": actual,
              "download_sha256": hashlib.sha256(download.read_bytes()).hexdigest(),
              "original_sqlite_library_sha256": original_sha,
              "new_sqlite_library_sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
              "observed": observed, "original_runtime_modified": False,
              "limits": ["Base runtime branch remains EOL", "TLS and hashes are not independent attestation",
                         "Business regression must be executed separately"]}
    (evidence / "BUILD_RESULT.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result))


if __name__ == "__main__":
    main()
