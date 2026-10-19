from audit import *
import csv,shutil
D=P/'docs/gen2/g20'
def doc(name,text):
 q=D/name
 if q.exists():raise RuntimeError('Existing design file:'+name)
 q.write_text(text.strip()+'\n')
header='**Freeze candidate:** `aevora.gen2.contract/2.0.0-rc1`. **Status: PROPOSED / NOT_IMPLEMENTED**, except individually identified AS-IS source and TESTED design probes. This directory is MAINTAINER_DESIGN_REVIEW, not Participant input or an automatically approved public export. G20 does not authorize G2-1.\n\n'
def design(n,text):doc(n,header+text)
baseline=json.loads((E/'BASELINE_RECEIPT.json').read_text())
doc('00_BASELINE_AND_AUTHORITY.md',f'''# G20-A — 基线、来源与验证级别

本阶段任务书为 `Aevora_Gen2_G20_Final_Architecture_and_Contract_Freeze_Codex_Taskbook_2026-10-15.md`，SHA256 `{baseline['input_task_sha256']}`。本轮创建时间来自真实 UTC 记录，绝不回填 Git 时间。G20 只提交架构与合同；不实现 G2-1。

| 权威 | 本次现场结果 | 证据 |
|---|---|---|
| Gen1 frozen | HEAD `{baseline['main_head']}`，Tree `{baseline['main_tree']}`，clean，547 路径逐一 SHA256 匹配 | 外部 BASELINE_RECEIPT.json |
| V5C→V5C.1 | `f016a825be67c0d30c8dcdb7f6b046c26d65ca95` 是 `{C['base_head']}` 的祖先，冻结基线也是前者祖先 | merge-base 实际退出0 |
| 技术起点 | `{C['base_head']}` / `{C['base_tree']}`，clean，551 个源路径匹配 | 真实 cat/show/rev-parse + 原源文件 Manifest |
| 新工作树 | `{P}`，分支 `{C['branch']}` | 新 bare clone --no-hardlinks；无 alternates；fsck |
| 新 Evidence | `{E}` | COMMAND_LOG.jsonl、逐命令 argv/stdout/stderr/exit |
| 1897 历史回归 | 原始 JUnit SHA `{baseline['historical1897_junit_sha256']}`，实际解析1897，原样历史通过 | historical_receipts；**NOT_RERUN_IN_G20** |

独立对象库属于本轮，不调用旧 registry 的 worktree add。旧 archive、原 Oracle、参考补丁和原生成绩不改。本轮 Python/SDK/SQLite/Node/Codex 仅必要 read-only probes；真实值见 source_audit/ACTUAL_READONLY_RUNTIME.json 和 commands。新 CLI feature 读取第一次因临时 CODEX_HOME 目录不存在而退出1，使用存在的临时目录后退出0，保留失败。无模型请求。

独立 V5C.1 审查文件未在限定工作目录中找到，不能声称已读。使用已封存 V5C.1 Final Report/Receipt 和当前逐文件源码复核；用户已给出的旧 V5 补充审查不能冒充新的 V5C.1 独立结论。主要风险延续：AOF139、Clock UDS EPERM、共享内核 PARTIAL、因果收益 UNKNOWN。本阶段真实 Native Multi-Agent 为 NOT_RUN。

当前维护者入口为 DEVELOPMENT.md / tools/dev.py；Product/Maintainer 工作区只改变视图，不提供安全隔离。GitHub 旧公开子集不作为源码权威；不 push、合并或改变可见性。
''')
design('01_AS_IS_ARCHITECTURE_AUDIT.md','''# G20-B — 源码 AS-IS 审计

## 实际调用与可信边界（IMPLEMENTED；本次 STATIC_AUDIT）

```mermaid
flowchart LR
  U[Public Participant code + Issue] --> N[Official codex exec / native children]
  N --> PX[mcp_proxy per Run capability]
  PX --> B[Trusted MCPBroker: peer credentials / limits / raw logs]
  B --> S[Official SDK + ExperienceService]
  S --> R[ExperienceResolver + governance.project]
  R --> GB[build_evidence_bundle]
  GB --> DB[GraphRepository / real FalkorDB]
  R --> Q[Immutable QuerySnapshot + Query]
  Q --> P[PublicProjection: bounded wire + lossless pages]
  P --> N
  N --> DI[Untrusted Decision / Candidate]
  N --> PATCH[Actual app diff]
  PATCH --> RUN[Private Runner / Submission validation]
  RUN --> OR[Independent Evaluator + SQLite Oracle]
  OR --> TV[TrustAnchor + verify_outcome]
  TV --> H[Host source verification / review / publication / feedback]
  H --> DB
  DB --> UI[Read-only Console LIVE]
  ARCH[Separately pinned sanitized archive] --> REPLAY[Explicit REPLAY]
```

## 已实现，不重建

| 源码与符号 | 实际语义 / 原证据入口 |
|---|---|
| graph_repository.py::initialize/put_node/put_edge | 真实 FalkorDB；异步 UNIQUE/MANDATORY 等待 OPERATIONAL；payload SHA/同ID冲突拒绝；多条 query 并非全局事务 |
| experience_resolver.py::ExperienceResolver.resolve/_resolve_one | 枚举最多256经验；基于实际多跳支持/反例、必要前提、作用域、治理与时间给三态；QuerySnapshot 精确回放；无 Episode 分支 |
| evidence_bundle.py::build_evidence_bundle | Rule→Premise、Revision→Evidence→VerifiedOutcome→Context→Task；allowlist；分开 support/counter/observed |
| governance.py::project | 显式 SUPERSEDES、作用域、validity、withdraw/expire/restrict；冲突保守 VERIFY；不存在已证因果分数 |
| candidate.py::CandidateLifecycle | PROPOSED→EVIDENCE_PENDING→ADMITTED_BOUNDED→PUBLISHING→PUBLISHED 等；原子单 query head fence；构建阶段可重试、发布前不可见 |
| admission.py::verify_orderflow_candidate | 同 Run、已封存 typed 原生提案+MCP request/reply+Patch+独立 Outcome；语义审批独立于来源校验 |
| feedback.py::ingest_outcome | 真 Outcome、实际 Query/Decision 边与快照；OBSERVED_OUTCOME 不等于 SUPPORTED_BY，不推断采用/因果 |
| mcp_server.py::ExperienceService / create_server | VERSION aevora.mcp/1.2；三基础工具加 opt-in propose；Host facts 与 Participant claims 分离；agent_thread_id 仍 UNAVAILABLE |
| mcp_projection.py::PublicProjection | WIRE196608 / broker262144；RFC6901；HMAC connection/run/document scope；900s 不延长游标；缓存32文档/16MiB、detail8MiB |
| integrations/codex_agent.py / gateway_broker.py | 官方CLI、真实 Gateway、completion-aware None 总时限/请求限额、独立 Runtime/Evaluation/Integration；原生协调由 Codex 拥有 |
| integrations/native_rollout_trace.py::analyze_native_rollouts | pinned rust-v0.162.1；子自身 session_meta/parent/session + 新 turn、任务交付、执行、final/task_complete/父回执；不从正文造 Agent |
| benchmark/submission.py + evaluator/runner.py | 提交保真、隔离候选、完整必要测试身份、JUnit/退出码；宿主直接审 SQLite；独立于公开 Core |
| orderflow_outcome_bridge.py::TrustAnchor/verify_outcome | 只读授权归档、fd/no-follow、源/报告/补丁/JUnit/Oracle pin；ordinary observation 默认 EXTERNAL_UNVERIFIED |
| console/src/.../server.py::create_app | loopback + read-only API，8资源；LIVE/REPLAY 区分，断库不 fallback；三页已有 |
| tools/dev.py / public_release.py::chosen/build | 一个成熟命令入口；显式 public allowlist；Core/Console 无需 Benchmark 安装；工作区不是沙箱 |

具体行号/字节 SHA 与原测试归属由 SOURCE_ENTRYPOINT_MAP.csv、SYMBOL_AND_IMPORT_INDEX.json 固定，避免文档行号漂移。

## 实际缺口，不能把规划当成已有产品

1. 模型已有 Agent/Decision/ObservedAction 标签，**没有完整 Session/Run/Recommendation/DeliveryReceipt 的正式图合同**。MCP connection/peer PID 不是 native child identity。CONSIDERED 是完整 resolver 候选，不证明某页被交付。
2. 主查询仍从 experience_ids 枚举，在 Python 内做规则/治理比较；多数业务属性位于 payload_json，缺少受控原生索引投影与一体化、带成本上界的 v2 witness 查询。
3. 没有部署级 tenant selector/tenant-wide epoch/授权代次合同；单个图名称和 run token 并不自动形成完整多租户产品。旧 snapshot replay 不保证语义撤回后不可读取历史；Gen2 明确区分当前推荐权限与历史阅读权限。
4. 既有 Context 是可信平面 facts。当前环境、修复后工件属性与验证后置条件缺少正式 phase。V5C.1 Core VERIFY / Agent APPLY 的差异保留；不能重标旧事实来改善历史成绩。
5. 宿主来源验证保留旧 source_epoch 字符标签，实际源字节另 pin；Gen2 事件应使用真实 build/contract/source digest，旧 label 只作 legacy provenance。
6. Console LIVE 仍有 H4 case-a/b/c 和演示默认经验 selector；这属于已有展示契约，不能当作通用图裁决逻辑。Gen2 增量替换为有来源的 Recommendation/Run 查询，保留旧 Replay。
7. 有界 wire 已解决事故，但图遍历/中间结果/查询数尚需完整预算及 overflow 不产生肯定裁决的合同。Graph admin/共享内核攻击不在已证明隔离范围。

本轮未重跑1897，也未新验证 native协作或 Host在线闭环；历史 evidence 与今天的 STATIC_AUDIT 分列。
''')
design('02_GEN2_FINAL_ARCHITECTURE.md','''# G20-C — 最终产品架构

## 产品承诺与复用

Aevora 对**有明确范围的策略经验**提供 WHEN/WHY、可信观察反馈和可核查传递链；不替 Agent 写补丁、不替独立 Oracle 判分、不以经验命中率保证解题。Gen2 完整实现全部闭环，不将冲突治理、Host、真实多 Agent、ordinary项目接入或发布推到假设的 Gen3。

```mermaid
flowchart TB
  subgraph Untrusted[Participant boundary]
    CODEX[Official native lead + real child threads]
    APP[Public workspace / commands]
  end
  subgraph Trusted[Trusted service boundary]
    CAP[Run/session scoped existing broker]
    AUTH[Tenant registry / capability / epoch]
    SERVICE[Existing four-tool service + v2 schema profile]
    GRAPH[GraphRepository v2 witness queries / payload checks]
    ARB[Deterministic WHEN + WHY arbitration]
    HOST[Existing verifier + review + fenced publication]
    TRACE[Native source normalization / delivery and action evidence]
  end
  CODEX --> CAP --> AUTH --> SERVICE --> GRAPH
  GRAPH <--> FDB[(FalkorDB: per-tenant evidence graph)]
  GRAPH --> ARB --> SERVICE
  CODEX --> APP --> DIFF[Trusted byte-faithful extraction]
  DIFF --> ORACLE[Separate OrderFlow Evaluator]
  ORACLE --> HOST --> GRAPH
  CAP --> TRACE
  CODEX --> TRACE
  TRACE --> GRAPH
  GRAPH --> OBS[Existing readonly Observatory projection]
```

## 模块责任与冻结接口

| 责任 / 拟扩展源码 | 输入→输出及持久化 | 幂等 / 失败 / 权限 |
|---|---|---|
| TenantBinding（新 contracts.py + 原 broker/connect） | OS-authenticated registry capability→tenant graph/profile/run/session；不接受工具传 tenant/graph | capability_id+authz_epoch；撤销立即拒绝；无 Caller Host角色 |
| Graph witness（原 graph_repository.py / 新 graph_queries.py） | AuthorizedContext+read_epoch→完整 bounded premises/support/counter/governance witnesses+hash | 所有读取绑定tenant、generation、epoch；超限/断库显式错误；无备用静态库 |
| WHEN（原 experience_resolver.py 增量） | 可信 task facts+necessary/hard exclusions→三态；Agent claims 仅审计 | query/request_key+context digest；未知永不升格已知；严格 bool≠int |
| WHY（原 evidence_bundle/governance + 新 arbitration.py） | 实际 paths、scope、authority、validity、revision→Recommendation + reasons/conflicts/witnesses | policy/graph/context hashes；没有全局成功分数；缺边或不完整不 APPLY |
| Host（原 admission/candidate/feedback） | Pin完整独立 outcome/source→review/commit/restrict/withdraw | manifest+candidate+expected_head/epoch；单query最终fence；准备失败不可见，保留失败，可重试 |
| Accountability（原 trace + 新 integration归一化） | 原始 typed Native/MCP/Patch/Oracle→分级 ToolEvent/DeliveryReceipt/Action links | source file+line hash；重复稳定ID；身份不能观测为 UNAVAILABLE；不从文本推断父子 |
| Runtime（原 CodexAgentAdapter） | Public Task→真实 official session/children→Patch | 全新session；completion-aware；None总预算；资源、重试、cancel；三层结果独立 |
| Product（原 Console/projection） | Authorized public graph/receipt→三页 bounded readonly view | LIVE从数据库；REPLAY单独pin；失联清空LIVE，无旧数据回退；不增加Host写权限 |

所有“新”模块在本轮 **PROPOSED**；不新建 Router、Planner/Coder Python orchestration、第二套 DB 或测试框架。Core 无 OrderFlow 导入依赖；OrderFlow bridge 以现有延迟、授权 adapter 接入。

## WHEN / WHY 的确定性优先级

1. 授权失败、断库、损坏、查询/文档超限：**ERROR，不生成看似完整推荐**。规则声明缺失/快照混读可恢复则最多 VERIFY，必须 integrity=INCOMPLETE；不能输出 APPLY。
2. Host明确撤回/过期/必要前提违反/已知硬排除：ABSTAIN。完整性不足时不伪造违反理由；输出VERIFY或显式错误，保留独立可证明的硬排除。
3. 同一适用域有完整权威支持和权威业务反证：VERIFY，枚举所有冲突 witness，标 REQUIRE_HOST_REVIEW；两经验不同scope可并存，不合并。
4. 匹配权威业务反证、无矛盾正控：ABSTAIN；基础设施 ERROR/TIMEOUT 不是策略反证。授权真实性不等于因果归属，反证必须有策略/工件/适用域关联证明。
5. 必要或 material task 前提 UNKNOWN/MISSING/NOT_OBSERVED、潜在反证、并行未决修订：VERIFY并列独立核验步骤。
6. 只有全部必要task前提已知匹配、无硬否决、完整当前域支持、无未解反证/修订冲突才APPLY，含义是有界推荐原则，**不是当前补丁已正确**。

取消任何“分数足够高覆盖前提不符”的设计。候选稳定ID排序只为分页，不是策略优先级；多个合法APPLY保留，由Agent选取并解释。Core verdict、Agent claim、Host outcome永不覆盖彼此。

## Fact phase（新增必需机制）

Context保留 `task`（环境/语义/目标）、`artifact_before`、`artifact_after`、`evaluation` 四 phase。事实必须有 authority、availability、source digest、observed_at。WHEN仅比较 rule 声明的**task必要前提**；修复后属性为独立验证的 evidence/postcondition，不偷换成目标已经具备的条件。若经验必须依赖初始实现属性，明确 rule 使用 artifact_before，并要求当前同phase已知。Agent观察不能自行变Host pin。

旧平面 Context 在兼容 profile 下保持原语义/UNKNOWN；**不自动重分类历史authority_validation**。新的phase化事实只有新Host注册/验证流程可以产生，需单独正反测试。此机制使修复原则可迁移而不要求目标已修好，但不规避必要前提缺失。

## 一致性与故障语义

每租户一物理图，TenantState 包含 schema/policy/generation/epoch/authz_epoch。准备的不可变记录和manifest不激活；最终 publication/governance fence 在**一条写query**关联 COMMITS、更新必要head与epoch。普通审计telemetry不提升证据epoch。查询开始/结束读epoch一致方可签发Recommendation；变化最多重新获取一次，持续竞争 GRAPH_CHANGED，不能混合结果。此协议依赖所有可信写者遵守fence；恶意DB管理员不在保证内。

缓存只保留授权的投影快照，绝不成为决策真值。每页检查当前capability/authz_epoch/graph epoch/lifecycle；撤销或语义变化返回STALE_SNAPSHOT，普通会话不得继续读旧推荐。合法历史审计需单独read_history grant、显式REPLAY及原epoch显示。

## 可证伪产品验收

缺支持边→不再APPLY；完整复原→相同context/policy恢复原裁决；同域权威反证→VERIFY/ABSTAIN；异域成功不覆盖；撤销后旧cursor拒绝；断库无结果fallback；原生两个不同child自身活动/回传可核；newID完整Bundle+Decision+action+独立Outcome关联可审。真实成绩失败照录。容量/时延合同见Graph与Gate计划，不以测试数替代这些属性。
''')
design('03_EXPERIENCE_GRAPH_V2_SCHEMA.md','''# G20-D — Experience Evidence Graph v2 Schema

## 版本与迁移

拟版本 `aevora.graph/2.0.0-rc1`，query/policy分别`aevora.witness/2.0.0-rc1`、`aevora.whenwhy/2.0.0-rc1`。v1.0/1.1/1.2真实目录见 source_audit/AS_IS_*。既有 initialize 检查**精确约束集合**，不能往旧图直接加标签再声称向后兼容。Gen2新owned图采用新catalog，按租户显式导入；旧图/历史schema保持只读。

导入是新图中的`legacy_alias`映射，保留原ID、原schema、原payload SHA/sourceManifest；新ID明确tenant namespace。不改原始payload、不自动提升Source authority、不把OBSERVED_OUTCOME变支持，不让未分phase旧facts绕过验证。输出逐文件/节点/边diff、数量与恢复收据。切换仅由Host配置，不由Agent选择graph。

## 节点目录（原名优先复用）

| 标签 | 冻结语义 | 归属 / 新旧 |
|---|---|---|
| Experience | 策略稳定身份，标题不是可执行指令 | Host发布；EXISTING |
| ExperienceRevision / Rule / Premise | 不可变声明、显式scope/validity/supersedes；必要前提与typed phase | EXISTING增量 |
| Evidence / VerifiedOutcome / Context / Task | 完整支持/反证/观察路径、独立结果与phase化事实 | EXISTING增量；仅Host可创可信结果 |
| Candidate / CandidateEvent / LifecycleHead / SourceVerification | 原提案与CAS事件链、来源审批；Head是唯一可变cache | EXISTING复用 |
| GovernanceEvent / AuditEvent / Feedback | 撤回/限制/到期/冲突处理与独立观察；无因果自动归属 | EXISTING增量 |
| Agent | 本次native线程身份，不是人名/人格；source runtime及版本 | EXISTING正式化 |
| Query / QuerySnapshot / Decision / ObservedAction | 查询epoch、不可变裁决、未可信Agent决定、实际Patch | EXISTING正式化；Decision仍名不变 |
| ExternalObservation / Schema | 未认证外部结果/明确schema | EXISTING |
| TenantState | generation/semantic epoch/authz_epoch，Host registry独占 | NEW |
| Authority | verifier/Host principal注册与key/version/source pin，不是Agent自填字符串 | NEW |
| PublicationManifest | 声明待激活revision/edges/hash/authority/expectedepoch | NEW |
| Run / Session | Benchmark/ordinary run与真实独立session分开，source identity/hash | NEW |
| ToolEvent / DeliveryReceipt | 原始请求/响应来源；实际已完成交付的页/bytes/摘要 | NEW |
| Recommendation | 指向query/context/policy/epoch/path hashes的Core裁决 | NEW DERIVED |

不新增名为IndependentOutcome的重复结果表；VerifiedOutcome承担该语义。反例沿COUNTEREXAMPLE路径，Conflict是推导assessment，不因一句自然语言建立可信CONTRADICTS事实。

## 共同字段与强制校验

每个不可变节点：`id,tenant_id,record_version,kind,payload_json,payload_sha256,created_at,source_type,authority_ref,visibility`。id=`kind:SHA256(canonical([tenant,source_namespace,stable_key]))`，最长240ASCII；原native UUID作为字段保留。payload采用现有有限JSON规范，拒绝NaN/重复key/非UTF8。typed索引投影必须逐项等于payload；否则 GRAPH_INTEGRITY_ERROR。只有TenantState及原LifecycleHead是明示可变指针，旧值由不可变事件保存。

native投影列按标签固定：tenant_id/id/experience_id/revision_id/run_id/session_id/native_thread_id/epoch/state/kind/verdict/valid_from/valid_until/payload_sha256，不从Agent任意键创建列。空值不能表示已知；fact `{availability:MISSING|UNKNOWN|NOT_OBSERVED|KNOWN,phase,key,value,authority_ref,source_refs}`；非KNOWN时value=null，KNOWN必须有授权独立来源。artifact事实不能填task槽。

每label UNIQUE(id)+MANDATORY共同字段，tenant每图隔离且额外断言tenant一致。合成复合UNIQUE(tenant_id,id)只验证引擎能力；生产以tenant独占物理图+namespace ID为主。每relation id=SHA256(type+typed endpoints+tenant)并声明payloadhash；拒绝跨tenant/缺endpoint/多重语义歧义，关系UNIQUE若未部署验证则应用单queryMERGE+manifest比对，不假装DB约束保证所有端点语义。

## 关系、方向与权限

| 来源→关系→目标 | 性质 | 基数/权限 |
|---|---|---|
| Experience→HAS_REVISION→Revision→USES_RULE→Rule→REQUIRES→Premise | 事实声明 | 已激活revision的rule恰一；premise列表与immutable声明完全相同 |
| Revision→SUPPORTED_BY/COUNTEREXAMPLE/OBSERVED_OUTCOME→Evidence→VERIFIES→Outcome→IN_CONTEXT→Context→FOR_TASK→Task | 事实观察 | 完整path；支持PASS/反例业务FAIL、同域且有策略工件关联；仅Observation不自动支持 |
| Outcome→ATTESTED_BY→Authority | NEW授权来源 | 注册独立verifier且精确Outcome digest；未认证External不得连 |
| Revision→PUBLISHED_BY→PublicationManifest←COMMITS←TenantState | NEW激活事实 | staging无COMMITS不可见；finalfence和epoch同query |
| Revision→SUPERSEDES→旧Revision | 有scope的显式取代 | 同Experience、无环、最大8hop；未知scope不任意选最新 |
| GovernanceEvent→GOVERNS→Evidence/Revision；GovernanceEvent→PUBLISHED_BY→Manifest | Host治理事实 | 同tenant、已提交、有效时间、scope；撤回只影响当前选择不删历史 |
| Session→HAS_AGENT→Agent；Agent→SPAWNED→Agent | NEW/正式化观测 | official自身metadata与父typed事件匹配，不能靠sharedRun推定 |
| Run→HAS_SESSION→Session；ToolEvent→IN_SESSION→Session；ToolEvent→BY_AGENT→Agent | 观测 | BY_AGENT仅精确可验证映射；未知保留UNAVAILABLE，不乱连 |
| Query→CONSIDERED→Experience；Query→AT_SNAPSHOT→Snapshot | 原候选/快照 | 不等于送达；Query→PRODUCED→Recommendation为派生 |
| ToolEvent→DELIVERED→DeliveryReceipt→OF_RECOMMENDATION→Recommendation | NEW交付事实 | broker完整frame写出/成功响应；用户阅读/采纳仍未知 |
| Decision→RESPONDS_TO→Query；Decision→CITES→Recommendation；Decision→DECIDED→Experience | 原claim+新准确引用 | 同run/session/授权scope；claimedAPPLY不改变Core |
| Outcome→OBSERVED_ACTION→Action；Decision→CORRELATED_ACTION→Action | 原事实/新派生 | Patch/tree/source hash；correlation不是mental causation |
| Feedback→FROM_OUTCOME→Outcome；Feedback→RESPONDS_TO→Decision；Experience→HAS_FEEDBACK→Feedback | 可信结果观察 | source/epoch准确；相关Query全候选可观察、不得反推全部已采用 |

Computed conflicts/Recommendation/CORRELATED_ACTION边以`authority=DERIVED`和policy/sourcehash标注；可重算，不能反向作为独立证据。Source和Authority不是Owner自填trust标签，创建面在Host权限内。

## 完整性、有效性和撤销传播

PublicationManifest不可变列出revision/rule/premise/support/counter/governance必要typed边ID及hash（分块Merkle式manifest可选增强，首版有界完整列表）。读者校验实际reached集合，不把漏掉counter当作无counter。原始删边→INCOMPLETE/VERIFY，不能从丢失负证据获得APPLY。合法撤回以已提交GovernanceEvent解释inactive，重新裁决；历史auditor可按旧epoch只读查看，当前普通cursor失效。

authority撤销触发authz_epoch/semanticepoch，依赖该Authority的当前支持不可用；重新verify之前不推荐。SourceVerification在发布前、读结果在发页前检查当前权限。visibility字段不能被工具输入直接设为PUBLIC，Host public projection/tenant grant共同决定可见性。

多条Cypher不声称全局事务：staging幂等写，单query finalCAS；并发失败记录conflict，不新增可见publication。异常恢复从PUBLISHING检查完整manifest并使用相同request id重试，不篡改旧记录。图谱断库明确Unavailable，空图EMPTY，超限CAPACITY_EXCEEDED；保留原262144wire。语义完整性验证不可被展示分页替代。
''')
print('WROTE_A_TO_D_ARCHITECTURE')
