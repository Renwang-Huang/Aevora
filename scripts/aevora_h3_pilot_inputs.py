"""Freeze original public experience text and an independent project baseline.

No model/Oracle call, strategy recommendation or fabricated task outcome.
Both pilot conditions consume this pre-run corpus and the same business bytes.
"""
import json
from scripts.aevora_h3_audit import archive,write,digest,now
from scripts.aevora_h3_external import project,baseline_git,ordinary_test


def main(label):
    from aevora.graph_repository import GraphRepository
    from aevora.models import public_record
    from integrations.aevora import public_runtime_context
    from benchmark.submission import snapshot_source_tree,source_tree_sha256
    A=archive();out=A/'g2'/label;out.mkdir(parents=True,mode=0o700)
    manifest=project(out/'project');baseline_git(out/'project',out);(out/'public-tests').mkdir()
    actual=ordinary_test(out/'project',out/'public-tests')
    files=snapshot_source_tree(out/'project');tree=source_tree_sha256(files)
    repo=GraphRepository.from_environment()
    try:
        rows=[]
        for eid in repo.experience_ids():
            e=public_record('Experience',repo.get_node('Experience',eid))
            # Original public text and declared premises, without a precomputed
            # WHEN verdict, repair instruction or private test/answer content.
            premises=repo.premise_paths(eid)
            rows.append({'experience':e,'declared_premise_paths':premises})
        (A/'g3').mkdir(exist_ok=True)
        write(A/'g3/PILOT_PUBLIC_CORPUS.json',{'status':'FROZEN_BEFORE_BOTH_NATIVE_CONDITIONS','raw_experiences':rows,
            'context':public_runtime_context(manifest),'baseline_tree_sha256':tree,'public_manifest_sha256':digest(out/'project/public.json'),
            'classification':'Historical controlled corpus plus verified new H3 natural candidate; no causal claim',
            'source_graph':repo.graph_name,'at':now(),'fairness':'Exploratory single paired pilot; tool protocol/time overhead differ; no statistical or causal inference.'})
        write(out/'RESULT.json',{'status':'PASS','baseline_test_command_exit':actual['exit_code'],'baseline_tree_sha256':tree,
            'test_authority':'EXTERNAL_UNVERIFIED','preinstalled_correct_strategy':False,'experience_count':len(rows),'at':now()})
        print(json.dumps({'status':'PASS','baseline_test_exit':actual['exit_code'],'experience_count':len(rows),'tree':tree}));return 0
    finally:repo.close()


if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--label',required=True)
    raise SystemExit(main(p.parse_args().label))
