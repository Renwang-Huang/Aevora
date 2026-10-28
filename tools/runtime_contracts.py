"""Export public runtime contracts from the installed official Python MCP SDK.

No database, credentials or benchmark imports are required. Output is stable
source material, not validation evidence. The reference Core is this checkout.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import importlib.metadata
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'aevora_core/src'))


async def contracts():
    from aevora.mcp_server import ExperienceService, create_server, AGENT_INSTRUCTIONS
    from aevora.models import canonical_json, PUBLIC_CONTEXT_FACTS
    from aevora.fact_catalog import catalog
    catalogs = {}
    for enabled in (False, True):
        service = ExperienceService(run_id='contract-run', public_context={},
                                    repository=object(), enable_proposals=enabled)
        tools = await create_server(service).list_tools()
        catalogs['proposals' if enabled else 'default'] = [
            tool.model_dump(mode='json', by_alias=True, exclude_none=True)
            for tool in sorted(tools, key=lambda tool: tool.name)]
    inputs = ['null', 'true', '1', '1.0', '-0.0', '9007199254740993',
              '1e-7', '1e20', '{"z":[],"a":"中文<&>"}',
              '{"absent":null,"empty":{}}', '[false,0,0.0,""]']
    cases = []
    for raw in inputs:
        canonical = canonical_json(json.loads(raw))
        cases.append({'input_json': raw, 'canonical_utf8': canonical,
                      'sha256': hashlib.sha256(canonical.encode()).hexdigest()})
    return {
        'facts.json': catalog(),
        'tools.json': {'schema_version': 'aevora.tool-contract/1',
                       'reference_mcp_sdk': importlib.metadata.version('mcp'),
                       'instructions': AGENT_INSTRUCTIONS,
                       'protocol_versions': ['2025-11-25'], 'catalogs': catalogs},
        'json.json': {'schema_version': 'aevora.json-contract/1', 'cases': cases,
                     'rejected_json': ['{"x":1,"x":2}', 'NaN', 'Infinity'],
                     'public_fact_keys': sorted(PUBLIC_CONTEXT_FACTS)},
        'operations.json': {'schema_version': 'aevora.operation-contract/1',
            'consumer_operations': {'resolve_experience': {'side_effects': True},
                'search_observations': {'side_effects':False},
                'read_observation_sources': {'side_effects':False},
                'build_evidence_bundle': {'side_effects': False},
                'record_decision': {'side_effects': True},
                'record_observation_use': {'side_effects': True},
                'propose_experience': {'side_effects': True, 'opt_in': True}},
            'states': ['QUEUED', 'DISPATCHED', 'COMPLETED', 'FAILED_KNOWN', 'UNKNOWN'],
            'unknown_replay': False, 'completion_implies_disk_persistence': False,
            'limits': {'connections': 4, 'frames': 4096, 'message_bytes': 262144,
                'json_depth': 16, 'json_nodes': 20000, 'auth_bytes': 4096,
                'auth_seconds': 10, 'active_seconds': 60, 'max_active_seconds': 120,
                'worker_result_bytes': 65536}},
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    target = ROOT / 'go-runtime/contracts'
    failed = []
    for name, value in asyncio.run(contracts()).items():
        raw = (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + '\n').encode()
        path = target / name
        if args.check:
            if not path.is_file() or path.read_bytes() != raw:
                failed.append(name)
        else:
            target.mkdir(parents=True, exist_ok=True)
            path.write_bytes(raw)
    if failed:
        raise SystemExit('Runtime contract drift: ' + ', '.join(failed))


if __name__ == '__main__':
    main()
