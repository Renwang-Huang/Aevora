from audit import *
from tools.experiments.g24.instances import build,bind
from benchmark.runner import BenchmarkRunner
from benchmark.submission import snapshot_source_tree,source_tree_sha256
blocks=json.loads((E/'01_protocol/TASKS_DRAFT.json').read_text());out=E/'02_calibration';out.mkdir(exist_ok=True);rows=[]
for instance in blocks:
 for impl in ['buggy','reference']+(['flock'] if instance['episode'] in ['D','D-V02'] else []):
  label=instance['block']+'-'+impl;w=build(out/'submissions'/label,instance,implementation=impl)
  with bind(instance):r=BenchmarkRunner(out/'runs').evaluate(instance['episode'],w)
  row=dict(label=label,instance=instance,implementation=impl,run_id=r['run_id'],status=r['overall_status'],test_results=r['test_results'],errors=r['execution_errors'],submission_tree=source_tree_sha256(snapshot_source_tree(w)),report_sha=sha(out/'runs'/r['run_id']/'evaluation_report.json'))
  rows.append(row);write(out/'RESULTS.json',rows)
  print(label,row['status'],flush=True)
expected=all(r['status']==('FAIL' if r['implementation']=='buggy' else 'PASS') for r in rows)
write(out/'GATE.json',dict(status='PASS' if expected else 'BLOCKED_CALIBRATION',count=len(rows),original_hidden_oracle_unchanged=True))
raise SystemExit(0 if expected else 1)
