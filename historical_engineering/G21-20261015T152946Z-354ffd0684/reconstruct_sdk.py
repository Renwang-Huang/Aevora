"""Independent stdlib replay of actual delivered SDK pages; no product imports."""
from pathlib import Path
import json,hashlib,sys
E=Path(__file__).resolve().parent
ROOT=Path(sys.argv[1]).resolve();rows=[]
def digest(v):return hashlib.sha256(json.dumps(v,sort_keys=True,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode()).hexdigest()
def reconstruct(entries):
 root=None
 for row in entries:
  parts=[s.replace('~1','/').replace('~0','~') for s in row['pointer'].split('/')[1:]]
  value={} if row.get('container')=='object' else [None]*row['length'] if row.get('container')=='array' else row.get('value')
  if not parts:
   if 'string_offset' in row:
    assert row['string_offset']==len(root or '');root=(root or '')+value
   else:root=value
   continue
  parent=root
  for part in parts[:-1]:parent=parent[int(part)] if isinstance(parent,list) else parent[part]
  key=int(parts[-1]) if isinstance(parent,list) else parts[-1]
  if 'string_offset' in row:
   old=parent[key] if isinstance(parent,list) else parent.get(key);assert row['string_offset']==len(old or '');value=(old or '')+value
  parent[key]=value
 return root
for f in ROOT.rglob('events-*.jsonl'):
 events=[json.loads(l) for l in f.read_text().splitlines()];delivered={e.get('delivered_sha256') for e in events if e['category']=='V2_RESPONSE_DELIVERED'};groups={}
 for e in events:
  if e['category']!='JSONRPC' or e.get('direction')!='OFFICIAL_SDK_TO_PARTICIPANT' or e['archived_message_sha256'] not in delivered:continue
  value=json.loads(e['raw_json']).get('result',{}).get('structuredContent',{})
  if 'entries' in value and 'document_sha256' in value:
   groups.setdefault((e['connection_id'],value['document_sha256']),[]).append(value)
 for (connection,expected),pages in groups.items():
  complete=pages[0]['offset']==0 and not pages[-1]['has_more']
  if not complete:rows.append(dict(file=str(f.relative_to(E)),connection=connection,status='INCOMPLETE_INTENTIONAL_NEGATIVE',pages=len(pages)));continue
  entries=[]
  for p in pages:assert p['offset']==len(entries);entries+=p['entries']
  assert len(entries)==pages[0]['total_items'];value=reconstruct(entries);assert digest(value)==expected
  rows.append(dict(file=str(f.relative_to(E)),connection=connection,status='VERIFIED_LOSSLESS',pages=len(pages),entries=len(entries),sha256=expected,core_verdict=value['recommendation']['core_verdict'],counterexamples=len(value['recommendation']['contradiction_ids'])))
assert any(r['status']=='VERIFIED_LOSSLESS' for r in rows)
(E/'reports/INDEPENDENT_SDK_REASSEMBLY.json').write_text(json.dumps(rows,indent=2));print(json.dumps(rows))
