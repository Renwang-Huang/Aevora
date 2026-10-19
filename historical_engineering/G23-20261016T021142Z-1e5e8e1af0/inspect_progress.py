from audit import *
import sys,time
label=sys.argv[1];d=E/'04_live'/label
if (d/'ORIGINAL_RUN_SUMMARY.json').exists():x=json.loads((d/'ORIGINAL_RUN_SUMMARY.json').read_text());x['test_results']={k:v for k,v in (x.get('test_results') or {}).items() if k!='tests'};print(json.dumps(x));raise SystemExit()
r=next((d/'runs').iterdir());p=r/'codex_events.pending';lines=p.read_text().splitlines() if p.exists() else []
print(json.dumps({'run':r.name,'events':len(lines),'event_age':time.time()-p.stat().st_mtime if p.exists() else None}))
for l in lines[-2:]:
 x=json.loads(l);item=x.get('item',{});print(json.dumps({'type':x.get('type'),'item_type':item.get('type'),'text':item.get('text','')[:800],'tool':item.get('tool'),'status':item.get('status')}))
