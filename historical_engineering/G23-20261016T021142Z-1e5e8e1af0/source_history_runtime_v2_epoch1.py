"""Trusted native launch binding for the existing v2 Broker, never a tool.

The bootstrap contains no Native identity. Its session_id is a scoped MCP
capability session; the official thread is joined only after native evidence
collection. Run identity is supplied by the unchanged Runner, not a model.
"""
from pathlib import Path
import os
import stat
from aevora.contracts import (PROFILE, TenantBinding, canonical_json, decode_json,
                              digest, record, require)
from aevora.graph_repository import GraphRepository
from aevora.host_pins import read_registry
from aevora.mcp_v2 import ReadGrant


def read_bootstrap(path):
    path = Path(path).absolute()
    require(".." not in path.parts, "UNAUTHORIZED")
    fd = os.open("/", os.O_RDONLY | os.O_DIRECTORY)
    try:
        for part in path.parts[1:-1]:
            nxt = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd); fd = nxt
        f = os.open(path.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=fd)
        try:
            before = os.fstat(f)
            require(stat.S_ISREG(before.st_mode) and before.st_uid == os.getuid()
                    and before.st_nlink == 1 and before.st_mode & 0o077 == 0
                    and before.st_size <= 1024 * 1024, "UNAUTHORIZED")
            raw = os.read(f, 1024 * 1024 + 1)
            after = os.fstat(f)
            require(len(raw) == before.st_size and
                    (before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns) ==
                    (after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns), "UNAUTHORIZED")
        finally:
            os.close(f)
    finally:
        os.close(fd)
    body = decode_json(raw)
    require(set(body) == {"binding", "registry", "facts", "grant"}, "UNAUTHORIZED")
    require(set(body["registry"]) == {"pin_root"}, "UNAUTHORIZED")
    require("run_id" not in body["grant"] and body["grant"].get("profile") == PROFILE, "UNAUTHORIZED")
    return body


def prepare_runtime_configuration(path, run_id, public_context, directory):
    body = read_bootstrap(path)
    grant = ReadGrant(run_id=run_id, **body["grant"])
    grant.check()
    binding = TenantBinding(**body["binding"])
    require(binding.tenant_id == grant.tenant, "UNAUTHORIZED")
    registry = read_registry(body["registry"]["pin_root"])
    for key, value in body["facts"].items():
        registry.verify_fact(value)
        # Trusted known task declarations must describe these actual public
        # inputs. Artifact-before facts require independent registered pins.
        if key.startswith("task.") and value["availability"] == "KNOWN":
            require(key[5:] in public_context and
                    type(value["value"]) is type(public_context[key[5:]]) and
                    value["value"] == public_context[key[5:]], "CONTEXT_CONFLICT")
    transport = GraphRepository.from_environment()
    try:
        require(transport.graph_name == binding.graph_name, "UNAUTHORIZED")
        repo = transport.v2(binding, registry)
        session = record(grant.tenant, "Session", [run_id, grant.session_id, grant.generation],
                         run_id=run_id, session_id=grant.session_id,
                         grant_generation=grant.generation, profile=PROFILE,
                         state="ACTIVE", valid_until=grant.valid_until)
        repo.put_node(session)
        state = repo.authorize(grant)
        count = len(repo.discover(body["facts"], state))
        config = Path(directory) / "HOST_V2_CONFIG.json"
        raw = canonical_json({**body, "grant": grant.__dict__}).encode()
        fd = os.open(config, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        try:
            require(os.write(fd, raw) == len(raw)); os.fsync(fd)
        finally:
            os.close(fd)
        return config, {"tenant_state": state, "sha256": digest(state)}, count
    finally:
        transport.close()
