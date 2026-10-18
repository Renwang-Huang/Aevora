"""Legacy optional host-only API. Public Core does not ship the maintainer body.

Install the explicit MAINTAINER_ONLY OrderFlow distribution to use Audit-Lite
collection. Ordinary Core query/MCP/Console never needs this module.
"""
import sys
try:
    from aevora_maintainer import audit_capsule as _implementation
except ModuleNotFoundError as error:
    if error.name not in {"aevora_maintainer", "aevora_maintainer.audit_capsule"}:
        raise
    raise ImportError("aevora.audit_capsule requires the private MAINTAINER_ONLY distribution") from None
# Preserve module identity, private helpers and monkeypatch behavior for old users.
sys.modules[__name__] = _implementation
