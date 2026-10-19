from audit import *
import json,csv,shutil,xml.etree.ElementTree as ET
r=json.loads((E/'TERMINAL_SOURCE_AND_HISTORY_RECEIPT.json').read_text());assert r['status']=='PASS_READONLY_SOURCE_HISTORY_FREEZE_AND_RESOURCE_AUDIT'
D=P/'docs/gen2/g20';freeze=json.loads((D/'CONTRACT_FREEZE_INDEX.json').read_text());assert all(sha(D/n)==v['sha256'] for n,v in freeze['files'].items())
cs=list(ET.parse(E/'checks/release-final/JUNIT.xml').getroot().iter('testcase'));assert len(cs)==59 and all(not list(c) for c in cs)
shutil.copyfile(W.parent/'Aevora_Gen2_G20_Final_Architecture_and_Contract_Freeze_Codex_Taskbook_2026-10-15.md',E/'TASKBOOK_AS_RECEIVED.md')
# Raw patch is architectural/docs only. Do not include old private implementation bodies in review bundle.
patch=subprocess.check_output(['git','--no-optional-locks','-C',str(P),'diff','--binary',C['base_head'],'HEAD']);(E/'G20_DESIGN_PATCH.diff').write_bytes(patch)
failures=[]
for p in sorted((E/'commands').glob('*/receipt.json')):
 d=json.loads(p.read_text())
 if d['exit_code']!=0:
  label=d['label'];expected=label in ['probe-r1-duplicate-rejected','probe-r1-mandatory-rejected']
  failures.append({'label':label,'exit_code':d['exit_code'],'classification':'EXPECTED_DATABASE_NEGATIVE_REJECTION' if expected else 'PRESERVED_INITIAL_FAILURE_OR_DRAFT_CHECK','receipt':str(p.relative_to(E)),'receipt_sha256':sha(p),'stdout_sha256':d['stdout_sha256'],'stderr_sha256':d['stderr_sha256']})
write(E/'FAILURE_LEDGER.json',{'at':now(),'records':failures,'interpretations':{'g20-a-native-features':'Fresh CODEX_HOME path absent; temp existing dir retry0. No auth/model session started.','g20-d-synthetic-graph-probe':'First owned container failed readiness; removed safely. Full root cause UNVERIFIED because first container logs were not captured. Retried new owned directory with known explicit redis-server entrypoint/resources, actual query probe succeeds.','g20-design-contract-checks':'Real dependency issue: jsonschema FormatChecker lacked optional date-time checker; added explicit stdlib calendar/timezone check without weakening old assertion. Original1FAIL40PASS retained.','g20-design-contract-checks-final':'After adding examples, negative test selected last positional case. Changed to explicit case name; original50PASS1FAIL retained.','g20-design-contract-checks-freeze-candidate':'ADR header counter matched a level3 supplement; exact level2 regex preserves required13 primary ADRs. Original53PASS1FAIL retained.','g20-design-diff-check':'CSV default CRLF flagged whitespace. First commit was created despite exit2; retained, follow-up LF normalization; no amend/reset. Strict final full diff check0.'},'source_product_or_oracle_assertions_weakened':False,'original1897_scores_replaced':False})
risks='''# G20 风险、未决事项与验证等级

## 必须保留的事实边界

- **G2-1..G2-6：NOT_IMPLEMENTED / NOT_RUN。** 当前只冻结候选合同、59项设计检查及两类合成query/constraint shape。没有新Gen2原生Agent/协作、真实独立Oracle或可信发布闭环。
- **1897 inherited regression：HISTORICAL_PASS / NOT_RERUN_G20。** 已重新解析原始JUnit并核SHA、源551/冻结547；不能算今天新59项里的业务测试。
- **生产完整Q07、权限租户隔离、snapshot分块、epoch读一致性与大图性能：PROPOSED_NOT_EXECUTED。** MinimalCAS和tenant WHERE探针不证明这些已实现。
- **比赛资格：ELIGIBILITY_UNCERTAIN。** 旧私有主要Core的可复用范围需主办方确认。真实提交日期不等首次研发日期，V5C.1赛期修复也不自动等于Gen2主要原创。
- **V5C.1独立新审查附件：UNAVAILABLE。** 未找到相应独立review，未声称已读取；真实源码、封存Final Report/Receipt和原1897JUnit已核验。
- **历史残余限制：UNCHANGED。** AOF reload139未修/未复验；RDB SAVE/graceful restart不是断电尾部持久性；原生Clock UDS EPERM；共享内核隔离PARTIAL；Provider内部weights/一般因果收益UNKNOWN。
- **探针范围：SYNTHETIC_ONLY。** network=none无端口、实际FalkorDB；其中PASS/FAIL形状节点是明确合成fixture，不是真Agent/Oracle结果，未导入任何历史或生产图。第一启动失败root cause未获日志证据，保留UNVERIFIED；成功重试没有改旧图。
- **时延/容量指标：TARGET_NOT_MEASURED。** 后续必须实测真实Qplan/byte/path/timeout，不把固定hop/limit误当线性成本。

## 待独立审查的架构选择

1. 批准显式v2 profile+新tenant图、原schema1.x只读兼容，还是要求更严格旧数据接入边界？当前候选选择保留来源别名、禁止自动重标事实。
2. 接受task/artifact_before/artifact_after/evaluation分phase与19-key初始registry？artifact_after不能作为目标必要前提、旧unknown保持unknown。
3. 接受无全局置信分数、权威同域反证/冲突优先、保留多候选与VERIFY？明确这可能比文本相似系统保守。
4. 接受单query activation fence+epoch乐观读一致性及共享内核残余威胁模型？这不是全局多statement事务或敌对管理员安全。
5. Native每次tool归属证据不足保持UNAVAILABLE；正式Multi必须至少两child自身执行+回传，不能为了完整图连猜测BY_AGENT。
6. 对Graph/Raw/NoMemory的60Run预注册主cohort与小样本结论边界，后续可在看结果前审改协议，但不能结果驱动替换失败/扩样。
7. 由用户向主办方确认旧Core/Benchmark/Runtime底座复用与新主要FalkorDB机制的作品边界。本轮没有向外发送消息，未自行认证合规。

上述是审查需要评价的候选选择，不是让Agent在本轮开始生产编码的许可。停止等待用户与独立审查，不自动G2-1、不push、不合并冻结基线、不清理历史。
'''
write(E/'RISKS_AND_OPEN_DECISIONS.md',risks)
qcount=len(list((D/'cypher').glob('*.cypher')));scount=len(list((D/'contracts').glob('*.schema.json')))
report=f'''# Aevora Gen 2 / G2-0 — Final Architecture & Contract Freeze Review

## 1. G20_STATUS

**G20_READY_FOR_REVIEW** — 架构与工程合同冻结候选。**不代表Gen2实现PASS、不代表比赛资格认证、不授权G2-1。** 当前生产新增0、真实模型挑战0；原生多Agent新验证NOT_RUN，符合计划阶段边界。

| Gate | 本轮实际状态 | 可核查收据 |
|---|---|---|
| G20-A | VERIFIED_BASELINE_AND_OWNED_WORKTREE | BASELINE_RECEIPT + terminal source/history +真实Git/CLI/help/schema |
| G20-B | COMPLETE_STATIC_SOURCE_AUDIT | 30个真实路径/符号映射、AST/import/hash索引、AS-IS→delta |
| G20-C | FROZEN_ARCHITECTURE_CANDIDATE | responsibility/trust flow +13ADR，旧Core/Runtime/Oracle复用 |
| G20-D | FROZEN_GRAPH_QUERY_CONTRACT; TWO_SYNTHETIC_FAMILIES_TESTED | v2catalog/{qcount}模板、epoch/constraints/multi-hop/cutrestore探针；生产Q07 NOT_RUN |
| G20-E | FROZEN_TYPED_PROTOCOL_AND_TRUST_CONTRACT | 四工具profile/Host/lifecycle/phase/schema；{scount}JSONschemas；59设计检查 |
| G20-F | COMPLETE_PREREGISTRABLE_DESIGN; AGENT_EXPERIMENTS_NOT_RUN | 四幕/14必要场景/60Run matched三arm/干预/完整分母 |
| G20-G | COMPLETE_DEPENDENCIES_PROVENANCE_RELEASE_PLAN | G2-1..6、逐文件来源、public/private、AI披露/eligibility风险 |

## 2. 源码权威与真实Git状态

- Frozen main `{r['main_head']}` / Tree `{r['main_tree']}`，**clean，547指纹逐一匹配**。
- V5C.1 技术起点 `{C['base_head']}` / `{C['base_tree']}`，**clean，551源路径匹配**；冻结→V5C→V5C.1祖先关系实际验证。
- Worktree `{P}`；branch `{r['new_branch']}`；独立bare `{r['independent_common_git']}`。无alternates，23份匹配对象内容一致但inode不同；未修改旧registry。
- **最终设计提交 `{r['new_head']}`；Tree `{r['new_tree']}`**；parent `{r['new_parent']}`；工作树clean。
- 相对V5C.1仅增加 `docs/gen2/g20/` **49资产**，生产Core/Runner/Evaluator/app/旧测试和Oracle/Reference源码0修改。三份本地新提交保留完整历史，第一版CSVstyle失败未amend/reset；最终严格diff--check退出0。
- 原V5C.1封存Full **28596普通文件+2544links** 的内容/模式/mtime/链接目标重新核验全部一致；外部terminal manifest的84文件也一致。没有push、baseline merge或历史cleanup。

## 3. 最终架构一页摘要

继续使用官方Codex Native Runtime与现有Adapter/Broker，公开Core不依赖OrderFlow。GraphRepository真实FalkorDB承担多跳witness/authority/版本/治理激活；Core deterministic WHEN/WHY从完整受限图证据裁决，Agent独立行动，可信Host从独立原Oracle核验source/outcome再审批发布，Console只投影实际图和原始receipt。

新增机制：Host固定tenant/profile；显式task与artifact/evaluation事实phase；native indexed projections+完整manifest/authority路径；单query COMMITS/head/epoch fence；Recommendation/DeliveryReceipt/Run/Session正式身份；QuerySnapshot与Publication大listing的有界分块；authz/semantic epoch游标失效。复用已有Revision/SUPERSEDES/governance、Candidate生命周期、Trusted Feedback、四工具、SDK有界RFC6901、Submission保真、独立Oracle、三页与Full/Lite。不造第二套Agent orchestration/新数据库。

Core verdict/Agent untrusted claim/Host independent outcome分开；KNOWN不来自Agent；APPLY不等已修好，CONSIDERED不等交付/采用，关联不等因果。硬排除/必要前提、unknown、反证/scope/时效/完整性优先，没有成功次数分数覆盖前提。不改旧authority_validation得到好看裁决。

## 4. 图谱与协议冻结版本、主要ADR

候选schema `aevora.graph/2.0.0-rc1`，MCP `aevora.mcp/2.0.0-rc1`，policy `aevora.whenwhy/2.0.0-rc1`；1.2+projection1.0原schema单独快照，不静默降级。

主要决策：显式revision保留；反证为真实scope内观察、冲突动态推导；不设全局信心分数；每tenant新owned图、旧记录不改；staging+原子最终fence/双读epoch而非虚构全局事务；四工具版本profile、Host权限不上放；原生父子和单工具归属分别证明；阶段化事实与有界snapshot/manifest分块。13ADR均含源码依据、替代/成本、兼容、验收与回退。

Production v2 factory/CAS/tenant授权/分块/时延尚未实现或正式动态测试。合成探针验证P1复合UNIQUE/MANDATORY readiness+真实拒绝（exit1），P2同queryepoch首次成功/stale空、固定多跳2rows→支持边cut1row→restore2rows、cross-tenant0rows。fixture中的PASS/FAIL/Authority只是合成形状，不是真Agent/Oracle，不认证产品trust。成功探针实际image digest固定，server/module版本见原始INFO/MODULE；两个owned probe容器均回收，无端口或旧volume。

## 5. Hero、场景与实际验证级别

四幕：A自然有界经验→Host审批；B关键前提改变/冲突的审慎判断；freshC继承受信revision并有真实native lead+2child与独立工程结果；隔离图干预/恢复对裁决与可见行动的影响。14类正反独立判据、逐层Evidence Contract、Graph/Raw/NoMemory+干预预注册均完成设计，**实际新模型运行NOT_RUN**，不把V5C.1两Single变成新Multi或新Hero。

本轮真实执行：原始1897JUnit解析/hash和source547/551；真实CLI0.162.1 version/help/features；官方SDK1.26.0四工具schema抽取（不执行tool）；实际Python3.12.14/SQLite3.51.3/Node版本；**59/59设计合同检查，0fail/error/skip**，真实pytest退出0；ownedFalkorDB两族合成probe。原1897测试没有重跑，仍是历史通过；没有Gen2新独立业务Outcome或可信反馈成绩。

## 6. G2-1 可执行首批与回滚

models增加独立v2catalog；新contracts/graph_queries/arbitration增量读取完整witness/phase/authority/epoch；原resolver/evidence_bundle/governance复用；原mcp_server/projection增加显式profile与当前授权失效，保留262144限制；有界snapshot/manifest loader；新独立tests覆盖T01–06/10/11/13。先真实DB/API垂直切片、再G2-2 Host治理、G2-3新Native协作、G2-4对照、G2-5Console、G2-6全回归/发布。每Gate来源pin、独立验收、错误首轮保留。失败切回原profile/owned registry，留存新图和失败，不动旧baseline/Oracle。

## 7. 参赛、发布与来源

官方rules/FAQ本轮实际读取并有HTTP/browser原文来源收据：[Rules](https://www.wemakedevs.org/hackathons/falkordb/rules)、[FAQ](https://www.wemakedevs.org/hackathons/falkordb)。FalkorDB需为核心决策依赖，交付公开源码/图模型/Cypher/视频/运行说明和AI披露。旧主要Core私有研发与赛期新增的边界 **ELIGIBILITY_UNCERTAIN**，需主办方确认。真实commit时间不能代替首次研发证明。本轮全551继承文件、49新设计资产、8规划实现项、4第三方来源分别列出；不是把今天提交旧Core当新作品。GitHub发布仍暂停。

## 8. 实际命令、Diff与审计收据

完整实际argv/UTC/elapsed/退出/stdout/stderr/hash在 `COMMAND_LOG.jsonl` 及commands/*/receipt.json，源码每符号定位在SOURCE_ENTRYPOINT_MAP.csv，完整设计diff在G20_DESIGN_PATCH.diff。

关键命令（隔离wrapper完整挂载/环境以收据为准）：

```sh
python3 audit.py g20-a-baseline-and-static-index python3 baseline_audit.py
python3 audit.py g20-primary-source-snapshots python3 fetch_primary.py
python3 audit.py g20-d-synthetic-graph-probe-retry1 python3 graph_probe_retry1.py
python3 readonly_runtime.py g20-final-contract-acceptance \\
  {BASE.parents[0]}/venv/bin/python -m pytest -q \\
  docs/gen2/g20/test_design_contracts.py \\
  --junitxml={E}/checks/release-final/JUNIT.xml -p no:cacheprovider
python3 audit.py g20-terminal-integrity-check python3 terminal_readonly_audit.py
```

上述全部退出0，最后设计测试59PASS。首次失败保留：CODEX_HOME不存在；首容器readiness失败/rootcause未证；缺可选date-time checker导致真实1FAIL40PASS；扩展示例后位置索引取错1FAIL50PASS；ADR子标题计数错误1FAIL53PASS；CSV CRLF whitespace exit2及未停在首docscommit的过程缺陷。修正源码仅本轮design/checker，保留每份原JUnit、diff、receipt与先前commit，不删除断言或洗旧分数。

合同index SHA256 `{r['freeze_index_sha256']}`；最终source/history收据 `TERMINAL_SOURCE_AND_HISTORY_RECEIPT.json`。本轮总交付manifest在 `DELIVERY_MANIFEST_SHA256.txt`；审查包/独立stdlib verifier在deliverables，终态receipt将记录实际ZIP SHA/数量及解包/篡改结果。该收据只能在实际打包验后生成，不预写PASS。新包是MAINTAINER_REVIEW，不是public release或Participant输入。

## 9. 重大阻断、未执行与停止

架构合同不存在阻止提交独立审查的工程阻断；生产实现、真实性、安全、性能仍按G2-1..6逐项动态验收。资格边界/新独立review附件/历史AOF与UDS/共享内核/因果未知全部见RISKS_AND_OPEN_DECISIONS.md。建议独立审查重点评价tenant/epoch/fact-phase/authority/manifest完整性与对照公平性，不凭59项检查接受产品已完成。

**STOP AT G2-0。等待独立审查与用户明确批准后才G2-1。** 不Push，不合并冻结baseline，不实现Gen2生产代码，不清理归档。
'''
write(E/'G20_FINAL_REVIEW_REPORT.md',report)
write(E/'G20_GATE_RESULTS.json',{'at':now(),'G20_STATUS':'G20_READY_FOR_REVIEW','scope':'ARCHITECTURE_AND_CONTRACT_FREEZE_ONLY','source_commit':r['new_head'],'source_tree':r['new_tree'],'design_assets':49,'design_contract_tests':59,'inherited1897_status':'HISTORICAL_PASS_NOT_RERUN','new_native_multi_agent':'NOT_RUN','new_agent_challenges':0,'gen2_production_implementation':'NOT_IMPLEMENTED','graph_probe':'REAL_SYNTHETIC_QUERY_CONSTRAINT_SHAPES_ONLY','eligibility':'ELIGIBILITY_UNCERTAIN','G2_1_authorized':False,'stopped_at':'G2-0_PENDING_REVIEW'})
print('G20_FINAL_REVIEW_WRITTEN',r['new_head'])
