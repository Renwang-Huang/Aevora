#!/usr/bin/env python3
"""Offline real Runner/Oracle reproduction. No model calls and no hidden-test claim."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True, help='Fresh directory outside the source checkout')
    parser.add_argument('--episodes', nargs='+', choices=['SMOKE-001','A','D','D-V02'], default=['SMOKE-001','A','D','D-V02'])
    args = parser.parse_args(argv)
    from tools.paths import fresh_external_output
    from benchmark.runner import BenchmarkRunner
    from benchmark.h2_cli import register_h2
    from benchmark.episodes.episode_d_v02 import build_episode_d_v02
    register_h2()
    output = fresh_external_output(args.output, ROOT)
    output.mkdir(parents=True)
    runner = BenchmarkRunner(output / 'runs')
    checks = []
    patches = {
        'SMOKE-001': 'SMOKE-001-current.diff',
        'A': 'A-v01.diff', 'D': 'D-v01.diff',
        'D-V02': 'D-V02-reference.diff',
    }
    for episode, patch in patches.items():
        if episode not in args.episodes:
            continue
        if episode in {'D','D-V02'}:
            from benchmark.resources import CgroupScope, CANDIDATE_LIMITS, SecurityGateError
            try:
                scope = CgroupScope.create(CANDIDATE_LIMITS)
                scope.close()
            except SecurityGateError:
                checks.append({'episode':episode,'status':'SKIP','observed':'SKIP','reason':'Delegated cgroup v2 memory/pids required; no fallback'})
                continue
        for strategy, expected in [('buggy', 'FAIL'), ('reference', 'PASS')]:
            source = ROOT / 'evaluator/reference_patches' / patch if strategy == 'reference' else None
            report = runner.evaluate(episode, source)
            (output / (episode + '-' + strategy + '.json')).write_text(json.dumps(report, indent=2) + '\n')
            tests = report.get('test_results') or {}
            check = {'episode': episode, 'strategy': strategy, 'expected': expected,
                     'observed': report['overall_status'], 'run_id': report['run_id'],
                     'tests': {k: tests.get(k) for k in ('collected', 'passed', 'failed', 'errors', 'skipped')},
                     'model_execution': False, 'evaluation_visibility': 'PUBLIC_HISTORICAL_NOT_BLIND',
                     'status': 'PASS' if report['overall_status'] == expected else 'FAIL'}
            checks.append(check)
    for episode in ['B', 'C']:
        report = runner.prepare(episode)
        checks.append({'episode': episode, 'expected': 'NOT_IMPLEMENTED',
                       'observed': report['overall_status'], 'status': 'PASS' if report['overall_status'] == 'NOT_IMPLEMENTED' else 'FAIL'})
    result = {'status': ('FAIL' if any(c['status']=='FAIL' for c in checks) else 'SKIP' if any(c['status']=='SKIP' for c in checks) else 'PASS'),
              'generated_at': datetime.now(timezone.utc).isoformat(), 'checks': checks,
              'model_execution': False, 'future_blind_evaluation': False,
              'interpretation': 'Expected buggy FAILs test the real public evaluator; this is not an Agent result or causal performance experiment.'}
    (output / 'RESULT.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))
    return 0 if result['status'] == 'PASS' else 77 if result['status']=='SKIP' else 1


if __name__ == '__main__':
    raise SystemExit(main())
