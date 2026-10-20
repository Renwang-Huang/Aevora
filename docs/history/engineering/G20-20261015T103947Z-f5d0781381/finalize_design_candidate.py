from audit import *
import csv,json
D=P/'docs/gen2/g20'
# Add the final freeze index prospectively, avoid a self-hash/content cycle in the contribution matrix.
source=list(csv.DictReader((D/'HACKATHON_CONTRIBUTION_MATRIX.csv').open()));retained=[r for r in source if r['classification']!='G20_NEW_DESIGN_CONTRACT_ASSET']
new_names=sorted({str(p.relative_to(P)) for p in D.rglob('*') if p.is_file()}|{'docs/gen2/g20/CONTRACT_FREEZE_INDEX.json'})
for n in new_names:
 retained.append({'path_or_module':n,'classification':'G20_NEW_DESIGN_CONTRACT_ASSET','content_sha256':'SEE_FROZEN_DESIGN_MANIFEST_NOT_SELF_HASHED_HERE','origin_evidence':'G20 actual write commands + CONTRACT_FREEZE_INDEX (explicit self exclusion) + final Git receipt','first_visible_commit':'SEE_EXTERNAL_G20_DESIGN_COMMIT_RECEIPT','first_visible_commit_time':'REAL_GIT_TIME_NOT_BACKDATED','last_touch_commit':'SEE_EXTERNAL_G20_DESIGN_COMMIT_RECEIPT','last_touch_commit_time':'REAL_GIT_TIME_NOT_BACKDATED','new_competition_claim':'NEW_ARCHITECTURE_CONTRACT_NOT_PRODUCTION_FUNCTION','license_or_release':'MAINTAINER_REVIEW_NOT_AUTO_PUBLIC_EXPORT','uncertainty':'Not proof of main FalkorDB implementation or organizer eligibility'})
for root in [E,D]:
 p=root/'HACKATHON_CONTRIBUTION_MATRIX.csv'
 with p.open('w',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(retained[0]));w.writeheader();w.writerows(retained)
write(E/'source_audit/FINAL_CONTRIBUTION_SCOPE.json',{'at':now(),'new_design_assets':len(new_names),'inherited_files':551,'matrix_rows':len(retained),'self_reference':'New assets use external freeze manifest/commit receipts; do not invent self SHA or authoring dates'})
# Last semantic prose alignment: no untyped after-facts as prerequisites, no authority-by-schema.
p=D/'04_AGENT_LIFECYCLE_AND_TRUST_CONTRACT.md';s=p.read_text();s+='\n## 有界生命周期与结果JSON\n\n`contracts/lifecycle_transition_catalog.json`与`lifecycle_event.schema.json`冻结状态/事件合同；`independent_outcome.schema.json`仅供已授权Host独立验证后产生，不能因一个对象结构合法就写VerifiedOutcome。`document_manifest.schema.json`统一QuerySnapshot/Publication record-set的inline或chunked形态。幂等的semantic request digest包含principal/candidate/action/expectedhead/epoch/source/scope/reason，不包含短期grant expiry或transport connection；首次执行仍检查有效grant，读取旧回执仍要当前read权限，重放不重新激活任何撤回状态。\n';p.write_text(s)
print('FINAL_DESIGN_SCOPE',len(new_names),'FILES')
