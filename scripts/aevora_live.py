#!/usr/bin/env python3
"""Aevora H1 serial native challenge collector, reusing OrderFlow lifecycle.

This is not an Agent scheduler. Codex owns delegation; collection has no total
wall deadline. Only public Episode task inputs reach the fresh Participant.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.m11_calibration import collect_trial, tls_probe, verify_freeze


def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    with path.open('x') as output:
        json.dump(value, output, indent=2, sort_keys=True); output.write('\n')


def freeze(archive, gate_files, regression):
    evidence = {}
    for relative in gate_files:
        path = archive/relative
        data = json.loads(path.read_text())
        if data.get('status', data.get('mandatory_boundary_result')) != 'PASS':
            raise ValueError('Mandatory admission gate did not pass: '+relative)
        evidence[relative] = sha(path)
    command = json.loads((archive/regression).read_text())
    if command.get('exit_code') != 0: raise ValueError('Mandatory current regression did not pass')
    evidence[regression] = sha(archive/regression)
    source_directory = archive/'frozen_source_snapshot'
    source_directory.mkdir(exist_ok=False)
    sources = {}
    for name in ('app','benchmark','evaluator','integrations','scripts','tests','aevora_core/src','aevora_core/scripts','aevora_core/tests'):
        for path in sorted((ROOT/name).rglob('*')):
            if path.is_file() and not path.is_symlink() and '__pycache__' not in path.parts and path.suffix in ('.py','.json','.diff'):
                relative = path.relative_to(ROOT).as_posix()
                target = source_directory/relative; target.parent.mkdir(parents=True,exist_ok=True)
                shutil.copyfile(path,target); sources[relative] = sha(path)
    for relative in ('scripts/aevora-python','scripts/python312','aevora_core/compose.yaml','aevora_core/pyproject.toml','aevora_core/requirements.lock.txt','pyproject.toml'):
        target=source_directory/relative; target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(ROOT/relative,target); sources[relative] = sha(ROOT/relative)
    write(archive/'SOURCE_TRUST_MANIFEST.json',{'files':{'frozen_source_snapshot/'+name:digest for name,digest in sources.items()},
        'created_at':datetime.now(timezone.utc).isoformat(),'scope':'Maintainer local pinned code authority; not third-party authentication'})
    write(archive/'LIVE_GATE.json',{'status':'PASS','gate':'G3_NATIVE_ADMISSION','checks':evidence,
        'frozen_source_sha256':sources,'source_manifest_sha256':sha(archive/'SOURCE_TRUST_MANIFEST.json'),
        'provider':'gateway','model':'gpt-5.6-terra','reasoning_effort':'max','experience':'aevora',
        'completion_policy':'completion-aware','agent_timeout':None,'request_budget':None,
        'parallel_trials':1,'maximum_model_concurrency':4})
    print(json.dumps({'status':'PASS','source_files':len(sources),'gate':str(archive/'LIVE_GATE.json')}))


def run(archive, label):
    if not label.isidentifier(): raise ValueError('Use a simple unique trial label')
    gate=json.loads((archive/'LIVE_GATE.json').read_text())
    if gate.get('status')!='PASS': raise ValueError('No accepted gate')
    for relative,digest in gate['checks'].items():
        if sha(archive/relative)!=digest: raise ValueError('Admission evidence changed')
    if sha(archive/'SOURCE_TRUST_MANIFEST.json')!=gate['source_manifest_sha256']: raise ValueError('Source authority changed')
    verify_freeze(gate)
    if sys.version_info < (3,12) or not os.environ.get('ORDERFLOW_CODEX_BINARY') or not os.environ.get('ORDERFLOW_GATEWAY_SECRET_PATH'):
        raise ValueError('Run this collector through ORDERFLOW_ENABLE_CODEX=1 scripts/aevora-python (Python 3.12 trusted environment)')
    live=archive/'live';live.mkdir(exist_ok=True)
    directory=live/label
    # Already inside the trusted launcher; never nest a host Flatpak wrapper.
    command=[sys.executable,'-m','benchmark.cli','--runs-root',str(live/'runs'),
        'run-codex','--episode','D','--variant','v01','--provider','gateway','--model','gpt-5.6-terra',
        '--reasoning-effort','max','--completion-policy','completion-aware','--agent-timeout','none',
        '--request-budget','none','--agent-mode','multi','--experience','aevora']
    connection=tls_probe('https://api.renwang-huang.top/v1')
    receipt,report=collect_trial(directory,command,live/'runs')
    write(directory/'verified_tls.json',connection)
    verify_freeze(gate)
    write(directory/'summary.json',{'receipt':receipt,'run_id':report.get('run_id'),
        'runtime_result':report.get('runtime_result','UNAVAILABLE'),
        'evaluation_result':report.get('overall_status','UNAVAILABLE'),
        'scope':'Single actual native challenge; not statistical or causal superiority evidence'})
    print(json.dumps(receipt))
    return 0


def main():
    parser=argparse.ArgumentParser(description=__doc__);sub=parser.add_subparsers(dest='operation',required=True)
    f=sub.add_parser('freeze');f.add_argument('archive',type=Path);f.add_argument('--gate-file',action='append',required=True);f.add_argument('--regression',required=True)
    r=sub.add_parser('run');r.add_argument('archive',type=Path);r.add_argument('--trial',required=True)
    args=parser.parse_args()
    if args.operation=='freeze': freeze(args.archive.absolute(),args.gate_file,args.regression);return 0
    return run(args.archive.absolute(),args.trial)


if __name__=='__main__':raise SystemExit(main())
