"""Real isolated graph + real owned Oracle cases, never a fake verified result."""
import os,uuid,json
from pathlib import Path
import pytest
from aevora.graph_repository import GraphRepository
from aevora.contracts import *
from aevora.orderflow_outcome_bridge import TrustAnchor
from aevora_maintainer.host_v2 import TrustedHost

@pytest.fixture
def v2():
    main=GraphRepository.from_environment();kw=main._client.connection.connection_pool.connection_kwargs;main.close()
    name='aevora_v2_g22_test_'+uuid.uuid4().hex
    r=GraphRepository(host='127.0.0.1',port=kw['port'],password=kw['password'],graph_name=name)
    v=r.v2(TenantBinding('tenant-g22',name),TrustRegistry());v.initialize()
    yield v
    root=os.environ.get('AEVORA_G22_ARTIFACT_ROOT')
    if root:
        out=Path(root)/'graphs';out.mkdir(parents=True,exist_ok=True)
        nodes=r.query('MATCH(n) RETURN labels(n),properties(n) ORDER BY n.id')
        edges=r.query('MATCH(a)-[e]->(b) RETURN a.id,type(e),properties(e),b.id ORDER BY e.id')
        (out/(name+'.json')).write_text(json.dumps(dict(nodes=nodes,edges=edges,sha256=digest([nodes,edges])),sort_keys=True))
    r.close()

@pytest.fixture
def host(v2,tmp_path):
    cases_path=Path(os.environ['AEVORA_G22_CASES'])
    cases=json.loads(cases_path.read_text());case=cases['cases'][0]
    anchor=TrustAnchor(archive_root=Path(case['root']),manifest_sha256=case['manifest_sha256'],
                       allowed_reports={'evaluation_report.json':case['run_id']},profile='current_live',
                       manifest_relative_path='HOST_RUN_MANIFEST.json',source_snapshot_relative_path='frozen_source_snapshot',
                       source_archive_root=Path(cases['source_root']),source_manifest_sha256=cases['source_manifest_sha256'],
                       source_manifest_relative_path='SOURCE_MANIFEST.json')
    pin_root=(Path(os.environ['AEVORA_G22_ARTIFACT_ROOT'])/'private_host_pins'/v2.binding.graph_name if os.environ.get('AEVORA_G22_ARTIFACT_ROOT') else tmp_path/'pins')
    grant=TrustedHost.bootstrap(v2,pin_root,principal='maintainer-g22',allowed_scope={'task.shared_state_kind':['sqlite_file']})
    h=TrustedHost(v2,pin_root,grant)
    verifier=h.register_orderflow(anchor,case['evaluator_sha'],case['suite_sha'])
    h.case=case;h.anchor=anchor;h.verifier=verifier
    return h
