"""Actual observation repeatability, independent validation and byte negative control."""
import json
import shutil
from scripts.aevora_h3_audit import archive,record,write,digest,ROOT,now


def main():
    A=archive();first=A/'g4/demo';second=A/'g4/demo-replay-02'
    m1=json.loads((first/'MANIFEST.json').read_text());m2=json.loads((second/'MANIFEST.json').read_text())
    static=[name for name in m1['files'] if name!='WHEN_WHY.json']
    assert set(m1['files'])==set(m2['files'])
    assert all(m1['files'][name]==m2['files'][name] for name in static)
    times=[]
    def qualified(path):
        view=json.loads(path.read_text())
        for context in view.values():
            for candidate in context['candidates']:
                projection=candidate.get('governance_projection')
                if projection is not None:
                    # Record every real time before excluding this declared
                    # live projection clock from the semantic comparison.
                    times.append({'file':str(path.relative_to(A)),'experience_id':candidate['experience_id'],'as_of':projection.pop('as_of')})
        return view
    semantic1=qualified(first/'WHEN_WHY.json');semantic2=qualified(second/'WHEN_WHY.json')
    assert semantic1==semantic2
    assert record(A,'g4-independent-demo-replay-verify',['python3','-I',str(ROOT/'aevora_core/scripts/h3_verify.py'),str(second),'--manifest-sha256',digest(second/'MANIFEST.json')])==0
    bad=A/'g4/demo-byte-tamper';shutil.copytree(first,bad)
    p=bad/'TIMELINE.json';p.write_bytes(p.read_bytes()+b' ')
    code=record(A,'g4-independent-demo-byte-tamper',['python3','-I',str(ROOT/'aevora_core/scripts/h3_verify.py'),str(bad),'--manifest-sha256',digest(first/'MANIFEST.json')]);assert code==1
    assert all(digest(first/name)==h for name,h in m1['files'].items())
    write(A/'g4/DEMO_REPEATABILITY.json',{'status':'PASS','at':now(),'byte_identical_files':static,'WHEN_WHY_semantics_identical':True,'actual_projection_times':times,
        'manifest_observation_timestamps_different':m1['observed_at']!=m2['observed_at'],'byte_tamper_verifier_exit':code,'original_unchanged':True,
        'qualification':'Read-only replay; WHEN/WHY contains actual governance_projection.as_of timestamps, retained in originals, excluded only from explicitly qualified semantic comparison.'})
    print(json.dumps({'status':'PASS','byte_identical_files':len(static),'semantic_WHEN_WHY_equal':True,'tamper_rejected':code}));return 0


if __name__=='__main__':raise SystemExit(main())
