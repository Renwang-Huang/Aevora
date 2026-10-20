from audit import *
import shutil,json
D=P/'docs/gen2/g20'
def doc(n,t):
 p=D/n
 with p.open('x') as f:f.write(t.strip()+'\n')
head='**Contract candidate:** `aevora.gen2.contract/2.0.0-rc1` — **PROPOSED / NOT_IMPLEMENTED**. Only explicitly named source observations and synthetic probe results are TESTED. Maintainer design, not Participant input.\n\n'
def design(n,t):doc(n,head+t)
design('GRAPH_CYPHER_CONTRACTS.md','''# Graph v2 — Cypher 与读取成本合同

## 访问约束

只有 GraphRepository 的固定模板可以向真实数据库发送 Cypher。tenant/graph由Host registry映射，工具参数不能提供graph/tenant/Cypher。values走官方SDK params；labels/relations仅编译期allowlist，不拼接模型文本。`GRAPH.RO_QUERY`用于所有查询；`GRAPH.PROFILE`可能执行查询，禁止把不可信写语句当作只读profile。公开MCP不提供任意query工具。保留 GraphError/GraphUnavailable 区分，错误不回显输入或凭据。

原模型的payload_json不是可以随意绕开的可信源：native投影必须对照canonical payload+SHA，所有中间关联及必要完整集必须校验。新schema允许原生id/tenant/state/epoch/scope_key索引；不将原始策略文本向量检索当作证据裁决。

## 模板与结果

| ID | 输入（由Host bound） | 输出/语义 | 上界/超限 |
|---|---|---|---|
| Q00 | tenant,state,generation | TenantState epoch/authz_epoch/policy/schema | 恰一；缺失初始化错误，不静态fallback |
| Q01 | tenant,state | 已提交且公开的候选identity | LIMIT257，超过256即CAPACITY_EXCEEDED，不选前256装作完整 |
| Q02 | tenant,experience,epoch | 已提交revision/rule/premise及声明hash | 最多16有效revision、64premises/revision；读取上界+1检测 |
| Q03 | tenant,experience | SUPERSEDES与治理事件/commit/authority | 最大8hop、256events；循环/歧义VERIFY，不能最新时间胜出 |
| Q04 | tenant,state,experience | Revision→Evidence→Outcome→Context + Authority，原边类型/ID | 固定多跳，LIMIT513；最多512path，超过拒绝完整推荐 |
| Q05 | tenant,state,experience | 当前完整GovernanceEvent及target/authority/manifest | LIMIT257；未知scope保留potential，不过滤掉负例 |
| Q06 | tenant,run,query,request_key | Recommendation + 完整source hash的幂等审计记录 | 固定allowlist写；不提升证据epoch |
| Q07 | tenant,state,expectedepoch,candidate,headsha,manifest | 最终发布fence/COMMITS/不可变event/head/epoch | 单写query；恰一为成功，0为STALE_HEAD，不伪报成功 |
| Q08 | tenant,state,authz_epoch,query,session,experience | 发页前当前授权/epoch/lifecycle检查 | 不同返回STALE_SNAPSHOT/UNAUTHORIZED；权限丢失不返回旧page |

实际模板文件在cypher/。Q04和minimal Q07 query-shape有真实合成探针；**完整生产query、全部typed payload验证与authority/tenant服务均NOT_IMPLEMENTED**。探针返回路径集合，不运行拟议Core裁决，因此不能声称APPLY/VERIFY生产验收。

## 完整 final publication Q07（PROPOSED / NOT_EXECUTED）

前置：prepared candidate/revision/rule/evidence/manifest全部不可变且校验完，manifest列出精确边集、candidate/body/source/outcome摘要，拟下一epoch=expected+1。相同request_key先检查已有完成事件；body不同拒绝ImmutableConflict；相同返回原事件而非当前状态。

```cypher
MATCH (s:TenantState {id:$state,tenant_id:$tenant}),
      (c:Candidate {id:$candidate,tenant_id:$tenant}),
      (h:LifecycleHead {id:$head,tenant_id:$tenant}),
      (previous:CandidateEvent {id:$previous,tenant_id:$tenant}),
      (m:PublicationManifest {id:$manifest,tenant_id:$tenant})
WHERE s.epoch=$expected AND h.payload_sha256=$expected_head
  AND m.epoch=$next AND m.payload_sha256=$manifest_sha
CREATE (event:CandidateEvent {id:$event,tenant_id:$tenant,
        payload_json:$event_json,payload_sha256:$event_sha})
CREATE (c)-[:HAS_CANDIDATE_EVENT {id:$candidate_edge,tenant_id:$tenant}]->(event)
CREATE (event)-[:PREVIOUS_EVENT {id:$previous_edge,tenant_id:$tenant}]->(previous)
CREATE (s)-[:COMMITS {id:$commit_edge,tenant_id:$tenant}]->(m)
SET h.payload_json=$head_json,h.payload_sha256=$head_sha,s.epoch=$next
RETURN event.payload_sha256,s.epoch
```

为简洁展示仅列关键属性；G2-1/G2-2实现时必须给所有节点/边补齐共同字段和canonical payload/hash，不得直接复制缩写绕过MANDATORY。最终完整可执行模板、schema与异常rollback须一起冻结，不能宣称此文档是已运行事务。

## 一致读取协议

1. Q00获取E0/authz0/generation/policy；确认capability可读该tenant及profile。
2. Q01/Q02/Q03/Q04/Q05在同graph、受限模板里获取witness。只读取有实际TenantState→COMMITS→Manifest路径的语义事实。
3. 校验声明的完整节点/边集合、payload投影、Source/Authority、时效与scope；任何+1 overflow拒绝完整裁决。未关联Authority的结果不支持推荐。
4. Q00复读，E1≠E0重试一次；持续变动GRAPH_CHANGED。所有激活/撤回/可信事实变动必须在原子epoch fence内；telemetry不变更证据epoch。不是跨query的数据库快照事务。
5. 生成Recommendation与manifest、返回有界summary，记录**成功写出的真实页**。每次Bundle/cursor用Q08重新授权。历史snapshot只在read_history grant+显式REPLAY下可读。

## 预算与性能可证伪合同

每图默认100000nodes/300000edges为运行资源准入上界，不声称已压测。每query DB timeout5000ms（现有配置上限30000不变），读合计20MiB中间结果、每experience最多512paths、活跃16revisions/64premises/256governance events；最坏查询数≤2+5*256，不隐瞒N+1。完整resolve wall目标p95≤5s（64candidate/每项8path）、≤30s上界；**PERFORMANCE_NOT_RUN**，G2-1测量索引plan/真实时延/内存。超限明确CAPACITY_EXCEEDED；不能用超时当ABSTAIN或偷偷丢反证。若目标未达，优化批量查询/索引，不改变裁决和Oracle，变更预算需版本化重审。

wire继续真实SDK text+structured序列化≤196608bytes，broker MAX_MESSAGE_BYTES262144、depth16/node20000；page24576、document8MiB、cache32/16MiB、TTL900s。图中保留完整不可变历史，不全量内嵌重复paths到每个响应。所有category含count/hash/disclosed omissions、lossless continuation；无新数据库缓存真值。

## 探针范围与重放

独立network=none、无发布端口、合成数据、实际镜像digest和server/module版本见外部probes/。P1验证复合index/UNIQUE/MANDATORY readiness和真实拒绝；P2验证完整多跳、支持边cut/restore、tenant filter以及epoch CAS stale返回空。首次容器readiness失败保留，配置/资源修正使用新owned目录；日志与退出码决定实际状态。没有写任何旧图、没有创造真实OracleOutcome。

`Q07_epoch_fence_probe.cypher`明确为minimal语法探针，不替代生产权限、候选审查、完整manifest或恢复测试。无大图压测、生产图迁移或Gen2正式Agent运行。
''')
design('04_AGENT_LIFECYCLE_AND_TRUST_CONTRACT.md','''# G20-E — Agent、可信 Host 与生命周期合同

## 身份和事件不混用

`tenant_id`来自Host registry，`run_id`由Runner/ordinary trusted host创建，`session_id`是新native invocation的实际session，`native_thread_id`可有parent/child。Agent名/role仅说明文字；不能当身份。多次Single保持多个Session，没有SPAWNED边。每条归一化事件包含contract_version、event_id、kind、run/session/thread（无法观察null+UNAVAILABLE）、authority_class、observed_at、official_at(nullable)、source_ref(fileSHA/line/lineSHA/byte_scope)、payload及其canonicalSHA。见contracts/event.schema.json。

| 事件 | 谁能证明 | 必须保留的关联 / 禁止推断 |
|---|---|---|
| SessionStarted / NativeChildStarted | 官方thread.started；child自身session_meta和父typedcollab | 新session、父子UUID、sourceversion；共享PID/role文本不是child |
| TaskDelegated / ChildExecuted / ChildCompleted / ParentReceived | 原生typed调用+child自身新turn/action/final/task_complete+父structured回执 | 继承父历史去重；全文不可见UNAVAILABLE；无回执不能全称完成 |
| RetrievalComputed | Core实际Q witness与Recommendation | CONSIDERED只表示全候选集合，不代表每项已交付 |
| ResponseDelivered / BundleDelivered | broker实际完整响应/SDK/native tool completed | query/recommendationID、页与documentSHA、isError、connection/requestID；不声称用户阅读 |
| DecisionClaimRecorded | 实际record_decision请求/响应 | UNTRUSTED；精确引用recommendation/query/newID；Core verdict独立 |
| PatchObserved / SubmissionAccepted | 可信文件字节提取/Submission verifier | patchSHA、baseline/candidate trees、sourceepoch；仅文件变化不是正确修复 |
| OracleCompleted | 原独立Evaluator/授权ordinary verifier | 真实exit、JUnit必要身份、DBOracle、suite/source指纹；非Agent自述 |
| CandidateProposed | 官方typed+同Run MCP matched body | 原bodySHA不代写；可早于独立Oracle，不能早于其核验发布 |
| SourceVerified / ReviewApproved / PublicationCommitted | 原Host源码/Outcome验证、语义审查、fence | source/patch/outcome/candidate/scope/Head/epoch全关联；不可从Agent verdict创建 |
| FeedbackObserved / SubsequentRetrieval | Host真实独立结果+新Session实际调用 | adoption/strategy-causal仍独立未知；新经验必须明确Bundle/Decision/行动才称实例关联 |

## 原生Multi-Agent准入

复用 `CodexAgentAdapter` 和 `native_rollout_trace.analyze_native_rollouts`，pin官方CLI实际版本、help/features、protocol source SHA。当前安装0.162.1的已实现parser读取child自身session_meta的id/parent_thread_id/session_id、新turn归属和父collab_tool_call sender/receiver/tool/agents_states；新官方API文档字段不是该CLI字段，绝不混用。

正式 G2-3 至少两个不同真实child，分别有任务交付、自己执行、任务完成和父接收证据。任务正文加密则交付可证、语义UNAVAILABLE；若无法证明独立任务语义，不宣布完整multi验证。两个模型HTTP请求、三个Single或主Agent自述不能满足。共享编辑由原生Lead协调，最多一个业务patch owner，不写Python Planner。旧历史children证据只用于parser兼容测试，不算新Gen2协作。

MCP连接由子代理继承时，其peer PID/connection并不证明具体thread。只有官方typed mcp_tool_call与broker原始请求/回复唯一关联（request/item/bodySHA+实际时间+session+connection）才能增加BY_AGENT；重复相同参数或欠缺join key时保留UNAVAILABLE。不能用时间最近强行匹配。整体parent/child验证和单工具child归属单独报告，后者未知不伪造。

## 候选与Host状态机

保留现有内部`PROPOSED`状态，其信任语义为PROPOSED_UNTRUSTED。转移：PROPOSED→EVIDENCE_PENDING→ADMITTED_BOUNDED→PUBLISHING→PUBLISHED；审查可REJECTED，批准/发布可WITHDRAWN，发布可SUPERSEDED。REJECTED/WITHDRAWN不就地恢复；若需要复议创建明确新Candidate/Revision指向前驱。语义scope缩窄可批准，不可篡改原proposal或扩大声明；不明必要前提保持pending。

1. Broker绑定run/session/tenant，接受proposal exactschema，建立不可变body和原始请求引用。
2. Host `verify_source(candidate,SourceAnchor)` 检查同run实际typed proposal、native完成和Patch来源；SourceAnchor是服务配置，不是请求字段。
3. `verify_independent_outcome(anchor,report_ref)`走原只读pin verifier；独立Oracle源码、必要suite集合、实际DB审计、source/patch身份必须匹配。ordinary来源若没有注册独立verifier，只记录ExternalObservation，**不自动升格**。
4. `review(candidate,expected_head,scope,reason,host_grant)`语义审批与来源验证分离，scope不超出证据；需要PASS支持且匹配条件；FAIL可作为明确工件反证，ERROR/TIMEOUT仅运行事实。跨任务泛化、因果判断不自动认证。
5. prepare不可变manifest，finalCAS同query提交lifecycle完成、COMMITS与epoch；PUBLISHING不可读作当前推荐。崩溃后相同request_key验证并重试；错误保留原source。授权失效必须重新Host review，禁止绕过旧grant。
6. 反馈只关联实际snapshot/Query/Decision/Action，原observed结果不转成功计数分数；新推荐需要新source/审查，不能靠self-reinforcing observation增加支持。

Host facade是**PROPOSED**的本地受控Python/CLI接口，不是新增公开MCP：`verify_source`, `verify_outcome`, `review`, `publish`, `govern`, `attest_public_context`, `revoke_capability`。每方法先校验registered principal、capability、expiry、tenant、idempotency/body hash再访问repo。ReviewGrant字符串不是抗恶意Host的密码学凭据；OS/credential边界是根。需要跨Host部署时必须另行审查成熟签名/身份方案，不能把本地hash当签名。

## 跨Session S1→S2→S3

S1新原生会话调查/修复/提案（提案可在Oracle前）→独立判分→Host来源+语义核验→PUBLISHED revision R1；S2面对公开关键前提变化，真实resolve/BUNDLE/DECISION/行动或拒绝→独立判分，必要时自然新proposal/Host有界revision R2；S3全新初始fixture、不同native session，从正式图而非旧聊天/patch看到R2，明确bundle/decision/action→原Oracle→真实feedback。任一步未发生按缺口报告，不能Host冒名提案、人工补丁或重跑挑选成功。

## 失败与不可改写记录

Runtime、Integration、Evaluation、SourceVerification、Publication、Inheritance、CausalBenefit分别报告。真实CLI exit0/NO_PATCH仍Runtime完成、提交未达成；Oracle NOT_RUN不等FAIL/PASS。429/网络/provider/timeout/cancel保留failed attempt+stream partial，不能因后续完成洗掉。completion-aware None总时限/请求/Token/费用预算，有限并发4、现有idle/retry/cgroup/磁盘守卫和Host人工cancel继续。财务统计是观察值不是停止阈值；无法获取billing记UNAVAILABLE。

原始日志在Host只写归档；秘密仅Host外部0600/0700，Participant只得scope proxy，不可读取admin、旧run、Oracle或Reference。逐文件/逐行原hash→脱敏hash链；Full与Lite分层；封存terminal输出另边界解决自引用，不改旧结果。Hash链只能证明本地字节一致，不宣称外部可信时间或恶意admin不可改。
''')
design('MCP_COMPATIBILITY_AND_VERSIONING.md','''# 四工具兼容与版本冻结

## profile，不把新字段静默塞进旧schema

已实现server版本`aevora.mcp/1.2`+projection1.0，真实SDK1.26.0抽取schema归档。`contracts/legacy_mcp_v1_2.schemas.json`是本次真实list_tools结果，**SCHEMA_EXTRACTION_ONLY**；repository=None不执行tool/graph，不是假造live通过。

Gen2拟`aevora.mcp/2.0.0-rc1`。Host grant在SDK初始化之前明确`protocol_profile`/graph schema/tenant/run/session/capabilities；server实例在一个session内固定profile。不让Agent输入tenant、source_type、verified、outcome或Hostprincipal。profile1.2严格保持原参数、八字段Claims、原proposal约束及错误；profile2新增字段必须由版本schema支持。profile1.2不能偷偷读取schema2新事实，不匹配返回UNSUPPORTED_PROFILE。旧图没有epoch/tenant语义，不能冒充v2。

| tool | 1.2真实输入 | 2.0拟变化 / 理由 |
|---|---|---|
| resolve_experience | task_context严格八fields；可选cursor | 保留task_context和cursor；新增可选request_key用于重复请求幂等。Host profile携带typed phase context；Agent原Claims只审计，不建立前提。无第五工具 |
| build_evidence_bundle | experience_id、可选query_id/cursor，view=bundle或candidate | view可增recommendation以读取完整v2 witness，query_id仍绑定唯一candidate；返回epoch/documentSHA及scope。旧view保留，不将raw私人证据公开 |
| record_decision | decision对象含query/experience/kind/reason/steps/optionaldecision_id | v2要求recommendation_id+idempotency_key（同snapshot），可选action_intent；Claim只审计。更精确identity避免“字符串命中即采用” |
| propose_experience | 原CandidateProposal exactfields及opt-in capability | 外层proposal字段保留；v2 public fact vocabulary phase化task.*等，source_reference kinds增Recommendation/DeliveryReceipt；不允许callerVerifiedOutcome/Publish。新proposal使用v2合同，旧body不可自动改写 |

四个工具足以承载查询、细节、声明与提案；Host审批/撤回/Outcome永不变第五个公开工具。若未来确实需新工具，先ADR+schema兼容/权限负控，本G20不预批准。

## 输入、输出与错误规范

见contracts/mcp_v2.schema.json。SDK以strict JSON Schema/Pydantic同一来源生成并在pre-coercion检查；bool≠integer，extra=forbid；Claims≤8192UTF8bytes、proposal≤16384、reason≤4000chars且整体wire预算。空task_context合法，缺省只表示不声明。KNOWN只能由Host独立factreceipt建立，不以null补齐。正负示例文件可以被真Codex使用，无固定EpisodeID、指定experienceID或修复答案。

每响应含contract/profile/query/policy/source/evidenceepoch；Recommendation独立三态与reason_codes、witness completeness、matched/conflicting/unknown、scope/revision/authority、解释路径索引。没有结果是EMPTY/available候选[]，不是PASS或静态seed。

| 失败 | MCP/HTTP语义 | 可重试策略 |
|---|---|---|
| INVALID_INPUT / CONTEXT_CONFLICT | isError=true，安全code，不回显值 | Caller修正；不能默默coerce |
| UNAUTHORIZED / REVOKED | 统一不可见响应，避免枚举其他tenant资源 | 不重试，需Host授权 |
| GRAPH_UNAVAILABLE | isError=true；Console LIVE503 fallback=false | 有限退避；不调用旧Replay |
| GRAPH_CHANGED / STALE_SNAPSHOT | 明确当前epoch不匹配，不返回混合页 | 新resolve，最多一次透明重读 |
| GRAPH_INTEGRITY_ERROR | 缺声明边/sha/authority，不产APPLY | Host诊断，保留失败 |
| CAPACITY_EXCEEDED | 显式预算与安全上下文，非静默裁剪 | 请求新受限scope需Host许可；不扩大无限上限 |
| CURSOR_INVALID_OR_EXPIRED | 不泄露存在性；同一SDK连接/tenant/run/session/query/view/epoch绑定 | 从首tool重新查询 |
| NO_NEW_PATCH / ORACLE_NOT_RUN | Runtime/Submission报告，不塞入三态 | 不等任务失败或成功，保留原因 |

## Cursor与数据增长

继续用既有HMAC capability和lossless RFC6901页；缓存只存真实投影。绑定tenant+run+session+connection+profile+query+args/view+semantic epoch+authz_epoch+documentSHA。TTL900s不续命，和Agent无限completion-aware总时长无关。每页检查authority撤回、publication可见性、capability状态；不因immutable旧快照就绕过新权限。正常session不可使用过期语义推荐；read_history需要显式权限和REPLAY标签。失效不删除DB历史。

当前工具小响应保留形状；v2元数据是新profile的规范部分。wire测量真实SDK text+structured duplication和最坏RPC ID，跨SDK升级重新验正好262144边界、Unicode、depth/node、cache/graph变化。绝不把大响应拆成未声明丢反证的漂亮摘要。

## 兼容验收（PLANNED）

K01原四工具schema快照/Claims严格匹配；K02旧合法payload不变；K03原32+29新增测试身份保留；K04新profile+generation只读适配；K05错误profile拒绝不降级；K06故意嵌authority/tenant/Outcome拒绝；K07跨connection/run/session/tenant cursor拒绝；K08撤回/epoch改变旧cursor失效；K09完整重组SHA；K10空图/断库/overflow；K11普通project干净安装只公开包，不导Benchmark；K12 requiredMCP失败原生退出归档。G20只验证JSON合同及合成query语法，不把这些计划写成生产PASS。
''')
shutil.copyfile(E/'source_audit/V5C1_ACTUAL_MCP_SCHEMAS.json',D/'contracts/legacy_mcp_v1_2.schemas.json')
print('WROTE_GRAPH_AND_PROTOCOL')
