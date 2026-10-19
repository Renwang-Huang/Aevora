"""Host-only review of an actual sealed H3 engineering proposal.

No Agent body is edited, no reference patch is substituted, and no unsupported
premise is repaired by the reviewer. An unsupported candidate stays pending.
"""
from datetime import datetime,timedelta,timezone
from pathlib import Path
import argparse
import json
from scripts.aevora_h3_audit import archive,digest,write,now


def anchor_for(run):
    from aevora.orderflow_outcome_bridge import TrustAnchor
    A=archive()
    binding=run.parent.parent/'SOURCE_EPOCH.json'
    if binding.exists():
        value=json.loads(binding.read_text());source=A/value['source_epoch']
        if digest(source/'SOURCE_TRUST_MANIFEST.json')!=value['source_manifest_sha256']:
            raise ValueError('Original Run source binding changed')
    else:source=A/'g1'
    return TrustAnchor(archive_root=run,manifest_sha256=digest(run/'run_evidence_manifest.json'),
        allowed_reports={'evaluation_report.json':run.name},profile='current_live',
        manifest_relative_path='run_evidence_manifest.json',source_snapshot_relative_path='frozen_source_snapshot',
        source_archive_root=source,source_manifest_sha256=digest(source/'SOURCE_TRUST_MANIFEST.json'),
        source_manifest_relative_path='SOURCE_TRUST_MANIFEST.json')


def review(run,out,approval=None):
    from aevora.graph_repository import GraphRepository
    from aevora.admission import verify_orderflow_candidate
    from aevora.candidate import CandidateLifecycle,ReviewGrant
    repo=GraphRepository.from_environment();out.mkdir(parents=True,mode=0o700)
    approved=json.loads(approval.read_text()) if approval else {}
    try:
        life=CandidateLifecycle(repo)
        ids=[r[0] for r in repo.query('MATCH(c:Candidate {run_id:$run}) RETURN c.id ORDER BY c.id',{'run':run.name})]
        rows=[]
        for i,cid in enumerate(ids):
            destination=out/str(i);destination.mkdir()
            before=life.inspect(cid);write(destination/'BEFORE.json',before)
            grant=ReviewGrant('aevora-h3-host-reviewer',(datetime.now(timezone.utc)+timedelta(minutes=30)).isoformat())
            def move(state,key,reason,metadata=None):
                return life.transition(cid,state,expected_head_sha256=life.inspect(cid)['head_sha256'],
                    event_key=key,reason=reason,grant=grant,metadata=metadata)
            move('EVIDENCE_PENDING','host-open','Real proposal pending independently pinned source verification')
            row={'candidate_id':cid,'run_id':run.name,'causal_benefit':'UNKNOWN'}
            try:
                source=verify_orderflow_candidate(repo,cid,anchor_for(run),'evaluation_report.json')
                write(destination/'SOURCE_VERIFICATION.json',source)
                if (approved.get('candidate_id')!=cid or approved.get('body_sha256')!=before['candidate']['body_sha256']
                    or approved.get('submission_sha256')!=source['source']['submission_sha256']
                    or approved.get('semantic_review')!='BOUNDED_PLAUSIBLE_FROM_ACTUAL_PATCH'):
                    raise ValueError('Explicit Host patch/body review receipt required; candidate remains pending')
                write(destination/'HOST_APPROVAL.json',approved)
                move('ADMITTED_BOUNDED','host-admit','Independent submission passed in the verified factual scope; causal benefit UNKNOWN',
                     {'source_id':source['source']['id'],'scope':before['candidate']['body']['scope'],'strength':'BOUNDED_SUPPORT_NOT_CAUSAL'})
                published=life.publish(cid,expected_head_sha256=life.inspect(cid)['head_sha256'],event_key='host-publish',
                    reason='Host approves bounded factual support and a public conditional principle',grant=grant)
                write(destination/'PUBLICATION.json',published);row.update(state='PUBLISHED',experience_id=published['experience_id'])
            except Exception as e:
                row.update(state=life.inspect(cid)['head']['state'],error_type=type(e).__name__,
                           reason=str(e),review_result='NOT_ADMITTED; no body or assertion relaxed')
                write(destination/'REJECTION_OR_PENDING.json',row)
            write(destination/'AFTER.json',life.inspect(cid));rows.append(row)
        result={'status':'PASS' if any(r.get('state')=='PUBLISHED' for r in rows) else 'PARTIAL',
            'run_id':run.name,'candidate_count':len(rows),'candidates':rows,'recorded_at':now(),
            'scope':'Trusted source/admission gate; not causal benefit or general strategy validation'}
        write(out/'RESULT.json',result);print(json.dumps(result));return 0 if result['status']=='PASS' else 1
    finally:repo.close()


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--run',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--approval-file',type=Path)
    a=p.parse_args();raise SystemExit(review(a.run.absolute(),a.output.absolute(),a.approval_file))
