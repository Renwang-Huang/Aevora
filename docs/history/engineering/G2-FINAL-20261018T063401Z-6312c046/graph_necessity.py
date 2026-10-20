from audit import *
import urllib.request,urllib.error
out=E/'11_graph_necessity';out.mkdir(exist_ok=False)
url='http://127.0.0.1:19064/api/journey?context=threads&stage=before'
def read():
 try:
  with urllib.request.urlopen(url,timeout=8) as r:return r.status,json.load(r)
 except urllib.error.HTTPError as r:return r.code,json.load(r)
code,before=read();assert code==200 and before['recommendation']['core_verdict']=='APPLY';write(out/'before.json',before)
container='aevora-final-6312c046-graph-1'
save="from aevora.graph_repository import GraphRepository;r=GraphRepository.from_environment();assert r._client.connection.save() is True;r.close();print('Explicit owned RDB SAVE complete')"
assert record('necessity-explicit-save',['docker','exec','aevora-final-6312c046-console-1','python','-c',save])==0
try:
 assert record('necessity-owned-graph-stop',['docker','stop',container])==0
 code,missing=read();write(out/'disconnected.json',dict(http_status=code,body=missing));assert code==503 and missing['fallback'] is False
finally:
 assert record('necessity-owned-graph-start',['docker','start',container])==0
for _ in range(30):
 try:
  code,after=read()
  if code==200:break
 except OSError:pass
 time.sleep(1)
else:raise RuntimeError('Owned graph failed normal restart')
assert code==200 and after['recommendation']['core_verdict']=='APPLY';assert before['graph']==after['graph'];write(out/'after.json',after)
write(out/'FALKORDB_NECESSITY_RECEIPT.json',dict(status='PASS',at=now(),normal_saved_restart=True,disconnected_http=503,replay_fallback=False,persisted_graph_projection_equal=True,model_execution=False,crash_test=False,root_cause139='UNVERIFIED',before_sha256=sha(out/'before.json'),after_sha256=sha(out/'after.json')))
print('Real owned graph disconnect/restart: PASS; no replay fallback')
