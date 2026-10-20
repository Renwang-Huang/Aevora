from audit import *
import uuid
O=E/'audit_verification';findings=json.loads((O/'LITE_GITLEAKS.json').read_text());assert len(findings)==5 and all(x['RuleID']=='generic-api-key' and x['File'].endswith('commands/verified-safe-official-mcp-four-tools/stdout.log') for x in findings)
data=json.loads((E/'delivery_final/Audit-Lite/commands/verified-safe-official-mcp-four-tools/stdout.log').read_text());values={k:[] for k in ['scope_token','idempotency_key','candidate_key']}
def collect(x):
 if isinstance(x,dict):
  for k,v in x.items():
   if k in values:values[k].append(v)
   collect(v)
 elif isinstance(x,list):
  for v in x:collect(v)
collect(data)
expected=hashlib.sha256(json.dumps(['task.shared_state_kind','sqlite_file'],sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()
assert len(values['scope_token'])==3 and all(v==expected for v in values['scope_token'])
for k in ['idempotency_key','candidate_key']:
 assert len(values[k])==1 and all(uuid.UUID(v).hex==v for v in values[k])
assert data['source']=='OFFICIAL_MCP_SDK_NOT_MODEL' and data['candidate_published'] is False and data['unauthorized_extra_field']=='REJECTED'
write(O/'LITE_GITLEAKS_TRIAGE.json',dict(status='REVIEWED_NON_CREDENTIAL_IDENTIFIERS',scanner_exit=1,findings=5,known_secret_matches=0,items=[dict(field='scope_token',count=3,classification='PUBLIC_SCOPE_CONTENT_DIGEST',proof='All three equal the deterministic canonical SHA256 of the public task.shared_state_kind/sqlite_file scope; no keyed secret or authentication. Core demo_fixture.py line124 and graph_v2.py catalogue discovery use it only as an index selector.',value_not_printed=True),dict(field='idempotency_key',count=1,classification='CLIENT_TRANSACTION_UUID_NOT_AUTHORIZATION',proof='Public SDK test supplies uuid4().hex in an already authorized connection; V2Service authority comes from ReadGrant, not this identifier.',value_not_printed=True),dict(field='candidate_key',count=1,classification='CLIENT_PROPOSAL_UUID_NOT_AUTHORIZATION',proof='Public SDK test supplies uuid4().hex; actual result PROPOSED_UNTRUSTED/NOT_PUBLISHED. It cannot grant Host authority.',value_not_printed=True)],source_files={n:sha(P/n) for n in ['aevora_core/src/aevora/demo_fixture.py','aevora_core/src/aevora/graph_v2.py','aevora_core/src/aevora/mcp_v2.py','aevora_core/public_tests/check_live_mcp.py']},disposition='No finding suppressed and no archived bytes rewritten. Gitleaks raw exit1 retained. Public source/tree/history scans independently exit0; this finding concerns internal dynamic SDK evidence identifiers only.'))
print('5 scanner findings checked: deterministic public scope digest and client UUIDs; no credential.')
