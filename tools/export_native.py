"""Trusted, offline FalkorDB logical export for the native importer.

Stop all writers first. This holds the shared repository's exclusive backend
barrier, preserves canonical bytes, checks source fingerprints before/after,
and exports no profile, credentials, grant, socket or runtime identity file.
"""
import argparse
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'aevora_core/src'))
from aevora.models import canonical_json,digest,validate_record,LIFECYCLE_SCHEMA_VERSION,QUERY_VERSION,LIFECYCLE_LABELS,LIFECYCLE_RELATIONSHIPS


def export(repo,output,contexts):
    from aevora.experience_resolver import ExperienceResolver
    from aevora.host_config import private_directory
    output=Path(output)
    if not output.is_absolute() or output.exists() or output.is_symlink():raise ValueError('Fresh absolute output required')
    private_directory(output.parent,create=True)
    os.mkdir(output,0o700)
    guard=repo._backend_guard._open()
    try:
        fcntl.flock(guard,fcntl.LOCK_EX|fcntl.LOCK_NB)
        before=repo.state_fingerprint()
        if repo.get_node('Schema',LIFECYCLE_SCHEMA_VERSION)!={'id':LIFECYCLE_SCHEMA_VERSION,'version':LIFECYCLE_SCHEMA_VERSION}:
            raise ValueError('Upgrade source schema explicitly before export')
        now=datetime.now(timezone.utc).isoformat()
        # The bounded read-only resolver is a source witness, never a new Query.
        witnesses=[{'context':c,'as_of':now,'expected':ExperienceResolver(repo).resolve(c,as_of=now,persist_snapshots=False)} for c in contexts]
        refs={};counts={};seen=set()
        for kind in ['nodes','edges']:
            seen=set()
            path=output/(kind+'.jsonl');sha=hashlib.sha256();size=count=0;after=''
            with path.open('xb') as f:
                os.chmod(path,0o600)
                while True:
                    if kind=='nodes':
                        rows=repo.query('MATCH (n) WHERE n.id>$after RETURN labels(n),n.id,n.payload_json,n.payload_sha256 ORDER BY n.id LIMIT 256',{'after':after})
                    else:
                        rows=repo.query('MATCH (s)-[r]->(t) WHERE r.id>$after RETURN r.id,type(r),labels(s),s.id,labels(t),t.id,r.payload_json,r.payload_sha256 ORDER BY r.id LIMIT 256',{'after':after})
                    if not rows:break
                    for row in rows:
                        if kind=='nodes':
                            labels,identity,payload,hash_value=row
                            if len(labels)!=1 or labels[0] not in LIFECYCLE_LABELS:raise ValueError('Ambiguous/unknown source label')
                            value=json.loads(payload);validate_record(labels[0],value)
                            entry={'label':labels[0],'id':identity,'payload_json':payload,'sha256':hash_value}
                        else:
                            identity,relation,sl,sid,tl,tid,payload,hash_value=row
                            if len(sl)!=1 or len(tl)!=1 or relation not in LIFECYCLE_RELATIONSHIPS or sl[0] not in LIFECYCLE_LABELS or tl[0] not in LIFECYCLE_LABELS:raise ValueError('Unknown source endpoints')
                            value=json.loads(payload)
                            if identity!='edge:'+digest([relation,sl[0],sid,tl[0],tid]):raise ValueError('Changed edge identity')
                            entry={'id':identity,'relation':relation,'source_label':sl[0],'source_id':sid,'target_label':tl[0],'target_id':tid,'payload_json':payload,'sha256':hash_value}
                        if identity in seen or identity<=after or value.get('id')!=identity or canonical_json(value)!=payload or digest(value)!=hash_value:raise ValueError('Duplicate or noncanonical source record')
                        seen.add(identity);after=identity;raw=(canonical_json(entry)+'\n').encode();sha.update(raw);f.write(raw);size+=len(raw);count+=1
                        if size>64*1024*1024 or count>(100000 if kind=='nodes' else 200000):raise ValueError('Export bound exceeded')
                    if len(rows)<256:break
                f.flush();os.fsync(f.fileno())
            refs[kind]={'path':path.name,'sha256':sha.hexdigest(),'bytes':size};counts[kind]=count
        path=output/'witnesses.json';raw=canonical_json({'cases':witnesses}).encode()
        if len(raw)>8*1024*1024:raise ValueError('Witness bound exceeded')
        with path.open('xb') as f:os.chmod(path,0o600);f.write(raw);f.flush();os.fsync(f.fileno())
        refs['witnesses']={'path':path.name,'sha256':hashlib.sha256(raw).hexdigest(),'bytes':len(raw)}
        if repo.state_fingerprint()!=before:raise ValueError('Source changed during export')
        manifest={'schema_version':'aevora.logical-transfer/1','logical_schema':LIFECYCLE_SCHEMA_VERSION,'query_version':QUERY_VERSION,'source_engine':'python-falkordb','created_at':now,'counts':counts,'files':refs,'source_state':before,'capabilities_included':False}
        raw=canonical_json(manifest).encode();path=output/'manifest.json'
        with path.open('xb') as f:os.chmod(path,0o600);f.write(raw);f.flush();os.fsync(f.fileno())
        return {'status':'EXPORTED','manifest_sha256':hashlib.sha256(raw).hexdigest(),'counts':counts,'source_changed':False,'next_step':'Import into a new native project and verify; old source remains unchanged.'}
    finally:os.close(guard)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--config',required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--contexts',type=Path,required=True,help='Approved list of public contexts; include representative known and unknown cases')
    args=p.parse_args()
    from aevora.host_config import prepare_environment
    from aevora.graph_repository import GraphRepository
    from aevora.models import normalize_context
    from tools.public_evidence.hero_verify import strict_json
    raw=args.contexts.read_bytes()
    if len(raw)>65536:raise ValueError('Context file too large')
    contexts=strict_json(raw)
    if not isinstance(contexts,list) or not 1<=len(contexts)<=32:raise ValueError('1..32 approved contexts required')
    contexts=[normalize_context(c) for c in contexts]
    prepare_environment(Path(args.config));repo=GraphRepository.from_environment()
    try:print(json.dumps(export(repo,args.output,contexts),sort_keys=True))
    finally:repo.close()


if __name__=='__main__':
    try:main()
    except Exception as e:
        print(json.dumps({'status':'FAILED','error_type':type(e).__name__,'next_step':'Preserve incomplete output and source. No automatic retry or cutover.'}),file=sys.stderr);raise SystemExit(2)
