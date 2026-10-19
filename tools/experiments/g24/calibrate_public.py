"""Fresh model-free G24 fixture calibration, never a Pilot/Formal causal result."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--instances', type=Path, default=Path(__file__).with_name('public_instances.json'))
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--instance', action='append', help='Explicit instance IDs; default all public fixtures')
    a = p.parse_args()
    from tools.paths import fresh_external_output
    from tools.experiments.g24.instances import bind, build
    from benchmark.runner import BenchmarkRunner
    output = fresh_external_output(a.output, ROOT)
    output.mkdir(parents=True)
    instances = json.loads(a.instances.read_text())
    rows = []
    for instance in instances:
        if a.instance and instance['id'] not in a.instance:
            continue
        if set(instance) != {'id','episode','fault','journal','busy_timeout'}:
            raise ValueError('Explicit public instance fields required')
        if instance['id'] not in {'public-A-lock','public-D-flock','public-DV02-local'}:
            raise ValueError('Unregistered public instance; supply a separately reviewed experiment runner')
        with bind(instance):
            runner = BenchmarkRunner(output / instance['id'] / 'runs')
            reference = build(output / instance['id'] / 'reference', instance, implementation='reference')
            for label, source, expected in [('buggy', None, 'FAIL'), ('reference', reference, 'PASS')]:
                report = runner.evaluate(instance['episode'], source)
                rows.append({'instance': instance, 'strategy': label, 'run_id': report['run_id'],
                             'expected': expected, 'observed': report['overall_status'],
                             'status': 'PASS' if report['overall_status'] == expected else 'FAIL'})
    if not rows:
        raise ValueError('No selected public instances')
    result = {'status': 'PASS' if all(r['status']=='PASS' for r in rows) else 'FAIL',
              'classification': 'FRESH_OFFLINE_FIXTURE_CALIBRATION_NOT_G24_PILOT_OR_FORMAL',
              'instance_file_sha256': hashlib.sha256(a.instances.read_bytes()).hexdigest(),
              'model_execution': False, 'rows': rows}
    (output/'RESULT.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))
    return 0 if result['status']=='PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
