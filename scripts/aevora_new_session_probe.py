#!/usr/bin/env python3
"""Fresh read-only native Codex evidence observation, not a Benchmark score.

Reuse the exact hardened Adapter. Its repair submission contract returns
NO_PATCH for a successful read-only probe; preserve that original result.
"""
from __future__ import annotations
import argparse
from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from benchmark.runner import BenchmarkRunner
from benchmark.manifest import load_manifest
from benchmark.participant import build_participant
from benchmark.submission import snapshot_source_tree,source_tree_sha256
from integrations.agents import TaskInput,ExecutionContext
from integrations.codex_agent import CodexAgentAdapter,CodexConfig
from integrations.runtime_evidence import seal_run
from scripts.m11_calibration import verify_freeze


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('archive',type=Path);args=parser.parse_args()
    gate=json.loads((args.archive/'LIVE_GATE.json').read_text());verify_freeze(gate)
    destination=args.archive/'observation_session'
    destination.mkdir(exist_ok=False)
    runner=BenchmarkRunner(destination/'runs');prepared=runner.prepare('D','v01')
    run=destination/'runs'/prepared['run_id']
    participant=build_participant(run/'workspace',run/'participant',agent_mode='single')
    before=source_tree_sha256(snapshot_source_tree(participant))
    task=('This is a read-only Aevora evidence observation, not a repair challenge. '
          'Do not edit business code or public tests, do not claim engineering success. '
          'Read the public task and environment. Use the real Aevora MCP resolve_experience '
          'and build_evidence_bundle tools for the returned candidates. Identify the '
          'historical support, counterexample and newly observed outcome evidence and '
          'revision IDs, preserving UNKNOWN attribution. Report exact query IDs and '
          'evidence IDs from actual tool responses. A NO_PATCH adapter result is expected '
          'because this observation intentionally makes no business submission. '
          'If generic repair workflow text requests a patch, this explicit read-only '
          'observation takes precedence. Finish naturally after the tools and final summary.')
    config=CodexConfig.from_environment(completion_policy='completion-aware',timeout_seconds=None,
        request_budget=None,agent_mode='single',experience_mode='aevora',model='gpt-5.6-terra',reasoning_effort='max')
    try:
        result=CodexAgentAdapter(config).execute(TaskInput('D',load_manifest('D').version,task,asdict(load_manifest('D'))),
            ExecutionContext(run.name,str(participant),constraints={'archive':str(run),'baseline':str(run/'workspace')}))
        metadata=result.runtime_metadata
        after=source_tree_sha256(snapshot_source_tree(participant))
        complete=metadata.get('trace_observations',{}).get('integrity',{}).get('status')=='COMPLETE'
        summary={'kind':'NEW_SESSION_READ_ONLY_EVIDENCE_OBSERVATION','run_id':run.name,
            'session_id':metadata.get('session_id'),'thread_id':metadata.get('thread_id'),
            'adapter_runtime_result':metadata.get('runtime_result'),'adapter_failure_kind':metadata.get('failure_kind'),
            'runtime_contract':'Repair Adapter NO_PATCH is retained; no Benchmark outcome is minted',
            'evaluation_result':'NOT_EXECUTED','submission':None,'source_before_sha256':before,'source_after_sha256':after,
            'source_unchanged':before==after,'native_turn_complete':complete,
            'session_observation_status':'COMPLETE' if complete and before==after and metadata.get('failure_kind')=='NO_PATCH' else 'INCOMPLETE',
            'updated_evidence_visibility':'UNVERIFIED_PENDING_INDEPENDENT_TRACE_REVIEW',
            'raw_mcp_events':'aevora_mcp_events.jsonl','mental_influence':'UNVERIFIED'}
        with (run/'observation_report.json').open('x') as output:json.dump(summary,output,indent=2);output.write('\n')
    finally:
        state=run/'codex-state'
        if state.exists():shutil.rmtree(state)
        seal_run(run)
    verify_freeze(gate)
    print(json.dumps(summary))
    return 0 if summary['session_observation_status']=='COMPLETE' else 1


if __name__=='__main__':raise SystemExit(main())
