from audit import *
import xml.etree.ElementTree as ET
# Actual final executable bytes match each accepted run; only review docs changed afterward.
checks=[]
for name in ['inherited-acceptance','gen2-acceptance-final']:
 epoch=json.loads((E/'05_regression'/name/'RUNTIME_SOURCE_EPOCH.json').read_text());before=epoch['before'];after=epoch['after'];assert before==after
 bad=[n for n,h in before.items() if sha(P/n)!=h]
 assert not bad;checks.append(dict(run=name,epoch_unchanged=True,current_paths=len(before),mismatches=bad))
epoch=json.loads((E/'05_graph_accepted/SOURCE_EPOCH.json').read_text())['files'];assert all(sha(P/n)==h for n,h in epoch.items())
selection=json.loads((E/'05_release/public-final-build/PUBLIC_SELECTION.json').read_text())['files'];bad=[]
for n,v in selection.items():
 if n in {'.gitignore','.dockerignore','README.md','LICENSE','THIRD_PARTY_NOTICES.md'}:continue
 if sha(P/n)!=v['source_sha256']:bad.append(n)
assert not bad
write(E/'reports/FINAL_EXECUTABLE_SOURCE_IDENTITY.json',dict(accepted_runtime_checks=checks,graph_source_files=len(epoch),graph_source_match=True,public_selection_source_match=True,public_source_files=len(selection),docs_only_final_commit=True,source=json.loads((E/'FINAL_SOURCE.json').read_text())))
# Frozen old source remains intact; report exact verified scope instead of claiming all old disk hashed.
old=Path('/home/PRIVATE_MAINTAINER/data_storage/aevora_validation_runs/G20-20261015T103947Z-f5d0781381')
assert record('terminal-g20-seal-check',['python3','-B',str(old/'full_verify.py'),str(old),'--expected-manifest-sha256','6f631e2bd982ec1ec79a2022f6a0d295665e7c935cdbf558e47526c826af6c32'],cwd=E)==0
print('FINAL_RUNTIME_SOURCE_IDENTITIES_MATCH')
