from audit import *
G=E.parent/'G23-20261016T021142Z-1e5e8e1af0';summary=json.loads((P/'console/web/gen2_history.json').read_text());out=E/'13_historical_review_final';out.mkdir(exist_ok=False);rows=[];cache={}
def refcheck(x):
 count=0
 if isinstance(x,dict):
  r=x.get('raw_reference')
  if isinstance(r,dict) and all(k in r for k in ['path','line','sha256']):
   p=Path(r['path']);assert p.is_relative_to(G) and p.is_file()
   if p not in cache:cache[p]=p.read_bytes().splitlines(keepends=True)
   assert hashlib.sha256(cache[p][r['line']-1]).hexdigest()==r['sha256'];count+=1
  for k,v in x.items():
   if k!='raw_reference':count+=refcheck(v)
 elif isinstance(x,list):
  for v in x:count+=refcheck(v)
 return count
for public in summary['runs']:
 root=G/'04_live'/public['label']/'runs'/public['run_id'];report=root/'evaluation_report.json';patch=root/'submission.diff';native=root/'native_rollout_summary.json';r=json.loads(report.read_text());n=json.loads(native.read_text());a=n['subagents']
 assert sha(report)==public['original_report_sha256'] and sha(patch)==public['patch_sha256']
 assert r['overall_status']=='PASS' and r['test_results']['passed']==r['test_results']['collected']==28 and not any(r['test_results'][k] for k in ['errors','failed','skipped'])
 assert a['verified_count']==a['completed_count']==a['parent_receipt_count']==3
 refs=refcheck(n);assert refs>0
 rows.append(dict(label=public['label'],run_id=public['run_id'],report_sha256=sha(report),patch_sha256=sha(patch),native_summary_sha256=sha(native),original_tests=28,verified_children=3,completed_children=3,parent_receipts=3,raw_line_hashes_rechecked=refs,source='HISTORICAL_READ_ONLY_NOT_NEW_EXECUTION'))
t=G/'04_live/S2/TRANSFER_VERIFICATION.json';transfer=json.loads(t.read_text());assert transfer['core_verdict']=='APPLY' and transfer['agent_decision']['decision']=='VERIFY'
pub_path=G/'04_live/S1_05/HOST_PUBLICATION.json';pub=json.loads(pub_path.read_text());assert sha(pub_path)==summary['s1_publication_sha256'] and pub['status']=='PUBLICATION_COMMITTED';assert pub['receipt']['kind']=='SourceVerification' and all(k in pub['receipt'] for k in ['manifest_id','new_head_sha256','prepared_sha256','epoch']);assert pub['receipt']==transfer['s1_q07_receipt']
write(out/'HISTORICAL_SUMMARY_RECEIPT.json',dict(status='PASS',at=now(),public_summary_sha256=sha(P/'console/web/gen2_history.json'),runs=rows,transfer_sha256=sha(t),core='APPLY',agent='VERIFY',s2_followup='HOST_APPROVED_FOLLOWUP_NOT_DIRECT_NATURAL_PUBLICATION',new_native_model_execution=False,causal_benefit='UNKNOWN',limits='This is a local read-only byte/field/link review. Raw private conversations and Oracle assertions are not exported publicly; no third-party attestation.'))
print(json.dumps(rows))
