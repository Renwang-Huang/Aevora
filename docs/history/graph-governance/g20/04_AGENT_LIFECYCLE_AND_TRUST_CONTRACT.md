**Contract candidate:** `aevora.gen2.contract/2.0.0-rc1` — **PROPOSED / NOT_IMPLEMENTED**. Only explicitly named source observations and synthetic probe results are TESTED. Maintainer design, not Participant input.

# G20-E — Agent、可信 Host 与生命周期合同

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

## 有界生命周期与结果JSON

`contracts/lifecycle_transition_catalog.json`与`lifecycle_event.schema.json`冻结状态/事件合同；`independent_outcome.schema.json`仅供已授权Host独立验证后产生，不能因一个对象结构合法就写VerifiedOutcome。`document_manifest.schema.json`统一QuerySnapshot/Publication record-set的inline或chunked形态。幂等的semantic request digest包含principal/candidate/action/expectedhead/epoch/source/scope/reason，不包含短期grant expiry或transport connection；首次执行仍检查有效grant，读取旧回执仍要当前read权限，重放不重新激活任何撤回状态。
