**Contract candidate:** `aevora.gen2.contract/2.0.0-rc1` — **PROPOSED / NOT_IMPLEMENTED**. Only explicitly named source observations and synthetic probe results are TESTED. Maintainer design, not Participant input.

# 四工具兼容与版本冻结

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

## 时间格式的显式断言

JSON Schema的format可能仅为annotation，不能假设安装jsonschema就一定校验date-time。本次设计检查真实发现该依赖缺口；生产必须复用现有parse_timestamp并规范为UTC、明确验证timezone/日历，不依赖可缺少的RFC3339可选包。G20检查使用Python标准datetime显式检查；原始失败JUnit保留。schema是结构合同，不是authority或payloadSHA存在性的证明。

已注册fact value类型冻结在fact.schema.json的RegisteredFactValueTypes：task.worker_count为1..4096的严格integer（不是bool），task.worker_count_known为严格boolean，其余已注册事实为≤512字符的公开语义label。supported_operation_set是声明的operation-group label，不把任意文本当集合解析。KNOWN的phase/key/value类型和独立来源必须同时匹配。v2提案scope/必要/排除条件的allowed-values逐key使用同一类型，不能以bool代count或将artifact_after塞进前提。扩展registry是版本化合同变更。

旧Host17项公开facts的词汇全部有显式v2映射：除authority_validation按明确phase保留为artifact_before/after，其他均task.*；新增evaluation.test_suite_fingerprint只作独立结果来源。旧flat记录不会自动重标，导入adapter须保留legacy语义或重新取得独立phase事实。
