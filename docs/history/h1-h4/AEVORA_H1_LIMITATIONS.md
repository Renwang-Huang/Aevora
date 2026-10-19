# Aevora H1 — 已确认限制与证据验收范围

## 审查版本与适用范围

本报告为 H1 的**封存前最终审查版本 5**。对应新归档：
`aevora_validation/20261011T051334Z-3e7fe273-3a17-4891-a6b2-4afb25376288`。
详细源码 SHA、现有证据 SHA、审查分类和待完成项目见
[STATIC_REVIEW_FINAL.json](aevora_validation/20261011T051334Z-3e7fe273-3a17-4891-a6b2-4afb25376288/STATIC_REVIEW_FINAL.json)。
版本 1 原件保持不变；本次新增核查见
[STATIC_REVIEW_DYNAMIC_ADDENDUM.json](aevora_validation/20261011T051334Z-3e7fe273-3a17-4891-a6b2-4afb25376288/STATIC_REVIEW_DYNAMIC_ADDENDUM.json)。
最终闭环及 post-live 源码修复的只读复核见
[STATIC_REVIEW_CLOSURE_ADDENDUM.json](aevora_validation/20261011T051334Z-3e7fe273-3a17-4891-a6b2-4afb25376288/STATIC_REVIEW_CLOSURE_ADDENDUM.json)。
最新 dispatch/preflight 与真实最终回归补充见
[STATIC_REVIEW_CLOSURE_ADDENDUM_V2.json](aevora_validation/20261011T051334Z-3e7fe273-3a17-4891-a6b2-4afb25376288/STATIC_REVIEW_CLOSURE_ADDENDUM_V2.json)。
所有先前审查原件均保留，没有将原 PENDING 或失败记录改写为事后 PASS。

审查直接读取了 37 份现有源码/配置/文档；其中 28 份属于当前
`release_admission_v2/LIVE_GATE.json` 的 Runtime source freeze，实际 SHA 全部匹配。
其余文档/接口源码也记录了实际 SHA，不冒称它们均包含在该 Runtime freeze 中。
本审查没有修改冻结源码、隐藏测试、参考补丁、历史报告或历史归档，也没有另起模型挑战。

真实 completion-aware Run `5089297e-39e7-4bd5-8b87-cbc7e21de022`
已自然结束并封存，Runtime 耗时约 1457.209 秒。补充审查独立验证其 536 个封存文件、
148 个原始 JSONL 行引用、28 项完整必要 JUnit 测试和 36 份一致的宿主 Oracle，
重新解析官方原生 rollout 得到 3 个执行、完成并回交结果的子 Agent。
版本 2 核查时，37 份已审源码/配置/文档的 SHA 再次全部匹配。
本次是对已有新动态证据的只读复核，没有重跑模型、候选业务、Evaluator、Docker 操作或图查询。
不同 Session 的只读观察、实际 demo closure 和最后完整回归均已完成。
最终回归实际命令退出 0，1214/1214 PASS、0 FAIL/ERROR/SKIP；本审查直接读取 JUnit，
并重新校验 closure 的 21 个文件、188 份批准的 frozen source snapshot 及两个 Run seal。
结论为 **CONDITIONAL PASS**：工程闭环已证实，同时保留 AOF/RDB、局部安全、
本地信任和非因果研究限制。
本报告在整个 Full Archive 封存前完成；最终 Full index/seal 与 Audit-Lite 的真实发布验收
由 Full 外的独立
[RELEASE_RECEIPT.json](aevora_validation/audit_exports/20261011T051334Z-3e7fe273-3a17-4891-a6b2-4afb25376288/RELEASE_RECEIPT.json)
负责，本审查不声称核验尚未生成的 ZIP。该链接的独立发布结果决定最终包的事实。

## 当前可核验结论

| 项目 | 审查结论 | 证据性质 |
|---|---|---|
| 默认 Experience 路径 | 保持 DISABLED；Aevora 需显式 opt-in | 当前源码 |
| Aevora 与 OrderFlow 身份 | `aevora-core` / `aevora` 为新增独立核心；OrderFlow 仍是独立 Benchmark | 当前元数据与 Brand Gate |
| Participant Outcome 权限 | 三个公开 MCP 工具不包含 Outcome、原始 Cypher 或管理员能力 | 当前 Broker/Server/Feedback 源码 |
| WHEN/WHY | 同一规则引擎查询真实图链；unknown、缺边和不相关证据不应自动获得 APPLY | 当前 Resolver 与已执行 G2 证据 |
| 工程评测 | 独立 OrderFlow Evaluator、Submission Fidelity、宿主 Oracle 保持独立 | 当前分层与已有回归 |
| 最后完整开发者回归 | 实际命令退出 0；JUnit 1214 PASS，0 FAIL/ERROR/SKIP | `H1_FINAL_RELEASE_JUNIT.xml`、146.1207 秒命令；本审查没有重跑测试 |
| 历史保护 | 根 Agent 再次重新哈希 90,800 历史文件 / 57 真值 / 44 原测试源码，856 原测试身份全保留 | `H1_FINAL_RELEASE_INTEGRITY.json` 与真实退出 0、29.4051 秒命令；本审查读取结果，没有再次独立扫描全部历史 |
| 在线数据库部署 | `appendonly no`，仅 loopback 16379，1 GiB/2 CPU/256 PID，状态 running | 本次只读 `docker inspect` |
| Native Runtime / Multi-Agent | PASS；原生 Lead 与 3 个 verified children，退出 0 | 已封存官方 rollout、重新执行只读 native parser |
| Episode D 工程结果 | PASS；28/28，pytest 退出 0，Oracle 36/36 一致 | 独立 JUnit、Report、原始 Oracle 文件与 Run seal |
| Submission Fidelity | PASS；原始 patch 与评测 tree 一致 | patch SHA、expected/applied tree SHA、封存记录 |
| 新 Outcome / Feedback | INGESTED；UNKNOWN attribution，仅 OBSERVED_OUTCOME | Trusted pins、幂等 receipt、真实公开多跳链 |
| 新反馈 RDB 持久化 | PASS，限定显式 SAVE 与正常 stop/up | 实际命令均退出 0，重启前后完整图状态与 public paths 相同 |
| 不同 Session 看到更新 | PASS，仅只读 observation；修复 Adapter 仍 ERROR / NO_PATCH | 官方 thread.started / session_meta、同字节 native / host MCP bundle、旧解析原件保留 |
| 最终 demo closure | PASS；原 v1 退出 2 保留，v2 实际退出 0 | `G5_FINAL_GATE.json`、pin V2、真实只读 verifier stdout |
| Full / Audit-Lite 发布验收 | 独立 release receipt 负责；不在本预封存审查中执行 | 外部 ZIP SHA、实际 export/verifiers/repeat/tamper/secret-scan 结果由上述链接报告 |

隔离核查采用实际 Linux namespace、native command 和候选进程的探针。
`g3-physical-probes-final/summary.json` 与
`g3-inherited-three-layers/summary.json` 明确 `model_calls=0`：它们是真实权限探针，
不是联网 Session 或原生子 Agent 证据。

## L01：FalkorDB AOF 重放故障与 RDB 持久化范围

这是本轮实际确认的数据库可靠性限制，不能写成无条件“持久化 PASS”。

1. 首次在线 release restart 的真实命令为
   `docker compose -f aevora_core/compose.yaml up -d --wait experience-graph`，
   归档 `g1-release-restart/command.json`，**CLI 退出 1**。
   当时观察到的 engine 139/函数栈未保存为原始崩溃日志，标记为
   `EARLIER_OBSERVATION_NOT_ARCHIVED / UNVERIFIED`。
   `FALKORDB_AOF_CRASH_AND_RECOVERY.log` 实际包含恢复 startup/RDB 内容，不能单凭其文件名
   当作首次 SIGSEGV 原始证据。
2. 随后从保留的原 data volume **只读**复制 `appendonlydir` 到独立 tmpfs，使用同一固定
   image 启动隔离 postmortem。该新执行归档为
   `g1-retained-aof-isolated-replay/command.json`，**退出 139**，约 1.187 秒。
   stdout 实际包含 `signal: 11`、`GraphContext_GetSchemaByID` 和 `GRAPH.EFFECT`。
   容器使用 `--network none --read-only --memory 1g --cpus 2 --pids-limit 256`；
   原 volume 以 readonly 挂载，复制后回放，未挂载密钥、未重启正在服务真实 Agent 的数据库。
3. 新 postmortem stdout SHA256 为
   `a0a50858d2d6ce93ffb55b2d2481bf19bf0685ae47abd7ed97b47781ceb19a12`。
   这是**新故障复现**，不是补回首次遗失的原始日志，也不能倒填首次命令为退出 139。
4. 当前 profile 明确关闭 AOF。已有 RDB 恢复前后真实 `state` 与
   `actual_parameterized_paths` 完全相同，且恢复命令退出 0。
   接受范围是显式 authenticated `SAVE` 和 graceful stop/restart。
   **尚未保存的 crash tail、突然断电、自动故障恢复、零数据丢失保证仍为 UNVERIFIED。**
   新反馈写入后已实际执行 authenticated SAVE、container stop/up 和重新查询，均退出 0。
   补充审查直接比较 `G4_BEFORE_RESTART.json` 与 `G4_AFTER_RESTART.json` 的
   `graph_state` 和两条经验的完整 `public_paths`，完全相同；图为 60 nodes / 101 edges。
   该结果仍不解除上述未保存 crash tail 的限制。

官方 [FalkorDB #2201](https://github.com/FalkorDB/FalkorDB/issues/2201) 报告了相关
`GRAPH.EFFECT` AOF 重放崩溃，但触发条件为 failed LOAD CSV，栈为
`Graph_GetRelationMatrix`。它支持“已存在此类上游风险”的判断，**不能证明本次的精确根因相同**。
后续应在单独授权的可靠性阶段评估上游修复/版本以及完整重启、故障、导入/删除图工作负载；
本轮没有擅自升级数据库或删除故障 AOF。

## L02–L04：本地信任、原子性与事实来源

- **本地维护者是信任根。** Trusted Bridge 校验预先批准的 manifest/source pins、
  完整必要 JUnit 身份、实际退出状态、patch-derived tree、Evaluator/Suite 指纹及宿主
  Oracle/topology/recovery 记录。它不能证明维护者身份、原始进程或机器来自第三方可信执行。
  GraphRepository 的管理员/宿主 API 仍是可信能力；直接持有这些权限的维护者可以构造或修改图数据。
- **多步 append 不是整体 ACID 事务。** 每个节点/边具备稳定身份、冲突拒绝及幂等性，
  但进程中断可能留下部分链。完整链与 completion AuditEvent 以及相同事实重试用于恢复，
  不提供分布式原子性。真正数据库管理权限下的删除也不受应用 append-only 约束。
- **H1 的 Context 是经过授权的初始公开环境能力。** SQLite atomic-write capability
  不表示候选代码已经正确实现事务；单进程共享对象能力不表示候选当前锁覆盖范围正确。
  公共拓扑到语义事实的映射只覆盖当前批准的 A/D 环境，没有任意 deployment 自动发现能力。
  Participant 自述不能把 unknown 改成可信事实并提升到 APPLY。

这些界限遵循 [官方 FalkorDB SDK](https://github.com/FalkorDB/falkordb-py) 与
[真实 constraint lifecycle](https://docs.falkordb.com/commands/graph.constraint-create) 的能力，
并将 [SLSA artifact verification](https://slsa.dev/spec/v1.2/verifying-artifacts) 的
本地一致性检查与真实性/身份保证区分开。

## L05：未知归因与研究结论

Query exposure、Participant Decision、自述 adoption、真实补丁、独立工程 Outcome
是不同的事实。当前反馈只追加 `OBSERVED_OUTCOME`、新 Revision 和
`outcome_observed_no_attribution`，保持 **UNKNOWN attribution**。
已封存的 D Run 通过 Trusted Bridge 入库，图从 49 nodes / 74 edges 变为
60 nodes / 101 edges；两条新 Revision 均关联该 Run，未自动生成 SUPPORT 或反例。
错误 seal 的宿主控制调用退出 2；真实 immutable Outcome 的合成冲突写入被拒绝且原件保留。
这些是可信宿主 CLI/API 的负向控制，不能冒称为 Participant 权限攻击验证。

当前系统没有实现从一次 PASS 自动更新可靠性、把失败自动判为该经验的反例，或者证明 Agent
确实按某条经验进行了内心推理。查询时间早于修改、声明使用、代码策略相似都不能独立建立因果。
单次闭环和有限样本也不能证明 Aevora 提高成功率、降低成本或优于另一个系统。

## L06–L07：隔离与 Agent 身份的范围

实际探针验证的范围包括：维护者/隐藏/reference/private 路径、长效项目密钥、其他 Run、
graph TCP、native business-command 中的 MCP socket 访问被拒绝；公开业务源码仍可访问。
Outer native Runtime 被明确授权访问当前 Run 的 socket，完成模型/MCP 连接。

这不是 VM 隔离、共享内核漏洞证明、全量 side-channel 防护或恶意宿主防护。
资源 CPU/output 检测包含采样窗口；既有 SQLite observer 对未支持的提交路径仍需声明覆盖范围。
请求/并发/消息/JSON/文件/数据库等待具有限额，不能把有限探针推广为所有攻击路径已经验证。
模型请求经过授权 Gateway；底层 provider、模型权重、实际费用与外部数据处理无法由本机标签证明。

Broker 的 kernel peer UID 与短期 bearer 证明当前 **Run 能力**，不是每个独立子 Agent 的
不可伪造身份。相同 Run 的 native children 可以共享 Query。
Broker `connection_id` 不等于 Codex thread ID。原生子 Agent 必须通过官方 typed spawn、
自身执行记录、完成及 parent receipt 核验；MCP 日志、角色配置或自然语言声明都不够。
本次封存 Run 的上述链均已核验。原始 task-delivery 正文处于 encrypted channel，仍为
`UNAVAILABLE_ENCRYPTED_TASK_CHANNEL`；独立活动来自三份自身命令、final、completion 和
parent receipt，不声称已经解密原始委派文本。
实现复用 [官方 MCP SDK](https://github.com/modelcontextprotocol/python-sdk) 与
[安装版本 Codex 配置 schema](https://github.com/openai/codex/blob/rust-v0.162.1/codex-rs/core/config.schema.json)，
没有自建 Agent Orchestrator。

## L08–L09：证据与脱敏边界

Full Archive 保留本机完整新证据；Audit-Lite 是 **MAINTAINER_AUDIT**，不能成为 Participant
输入。胶囊有有限文件、条目、总字节与 JSONL 行映射预算。已知 credential pattern 不能发现
所有任意字符串密钥；collector 必须安全提供已知 in-memory secret values，且 Runtime
首先不能把长效密钥交给 Participant。base64 只是编码，不能免除内容扫描。

原始 source SHA 与脱敏/portable export SHA 分开。被变换的原始字节以及 omitted 原件，
从轻量包独立审查时保持 **UNVERIFIED**。`NOT_INCLUDED` 是原件指针，不是提供了原件。
Capsule 类别齐全与本地 checksum PASS 不能升级成 Gate/任务 PASS。

本次 native MCP 留下 8 次实际 attempt：6 次返回、2 次错误，错误原样保留。
8 次 native call ID / arguments 均匹配；其中两次成功 `resolve_experience` 的原生
text wrapper 无法完整解析，`exact_native_result_match=false`。其完整 structured result
由 `codex_events.jsonl` 中官方执行事件的精确引用核验，原始 wrapper 未改写。
因此不能说 8 次完整 native result bytes 全部相同。六次成功返回发生在第一项官方
业务 FileChange 的 `started_at_ms` 之前；这不是外层 patch request ID、
“首次重要补丁”的语义判断或内心因果证明，后三者仍 UNKNOWN / UNVERIFIED。

Verifier 不提取 ZIP、不执行包内代码、不运行模型/候选代码、不访问图服务。
但是攻击者可以同时替换包与自己的 verifier/checksum，因此需要独立渠道的可信 verifier
及外部 bundle SHA。Bundled 旧 stdlib verifier只验证 Benchmark 一致性；Aevora capsule
还需可信安装的 `verify_exported_capsule()`。本预封存审查不验证未来包的 bytes：实际完整
Full seal、ZIP SHA、两类 verifier、重复导出、tamper 拒绝及 known-secret 扫描由
Full 外 `audit_exports/.../RELEASE_RECEIPT.json` 单独执行和报告。

## L10–L13：历史兼容和目前没有实现的能力

- 两条 H1 经验及其 Rule/Premise 由维护者整理，尚无一般自动经验提取/规则演化。
  自然 atomic 策略的 origin Run/patch 与维护者四次 A/D 历史重放明确区分。
  Import 重新验证既有 bytes，本身不重新跑 hidden suite，也不产生新 Session。
- Unknown topology 是 applicability fixture，不是已实现或评测的 D-v02 工程任务。
- 新 verifier SHA 可能与相同 stable Run 的旧 immutable Outcome 冲突。
  本轮保留 prototype graph、使用显式 release namespace；没有一般
  VerificationRevision migration、active-rule selection 或 feedback evolution。
- 当前保留 Disabled/manual 接口和 OrderFlow 的元数据。只在可读 workspace 中核查了
  GraphSwarm 历史来源；未找到的旧 architecture/H0 或未安装 governance 包不能声称已经审查兼容。
- `current_live` trust profile只证明授权结束 Run 的独立工程证据符合契约，
  不单独证明 fresh Session、native MCP 模型调用或多 Agent。这些需要独立 G3/G5 原始记录。

本轮没有实现 B/C、D-v02 业务、通用跨 Runtime 全量 SDK、多租户商业安全平台或正式 G0–G3 实验。

## L14：运行收集和只读新 Session 的判分

Collector 退出 0 表示完成收集；必须读取内部 CLI/Runtime/Evaluation 的真实状态，不能视作任务 PASS。
completion-aware 允许没有任意总 wall-clock/request 上限，仍保留连接/idle/retry、并发、资源与人工取消。
当前没有断电/SIGKILL 后的完整自动 resume。

只读新 Session 观察不提交补丁，可以正常结束并保留 repair Adapter 的 `NO_PATCH`。
应分别报告 observation 是否完成、真实图更新是否可见、Adapter 原始状态与
Evaluation `NOT_EXECUTED`，不能为了展示成功伪造 patch 或 mint 工程 Outcome。

实际只读 observation Run 为 `4a141343-0714-4992-a0cf-119b61cff121`。
本审查静态读取 109 份原件的 seal，全部文件 SHA 匹配；collector / 官方 CLI 退出 0，
原始 metadata 仍是 `Runtime ERROR / NO_PATCH`、`session_id=UNAVAILABLE`，
`evaluation_result=NOT_EXECUTED`，源码前后 tree SHA 相同，没有 Submission 或新工程 Outcome。
官方 `thread.started` 与本 Session 的 `session_meta.id` 独立一致为
`01a129a9-2b51-7771-aee5-f47aa995ce72`，与挑战 Lead 不同。

原 v1 trace audit 的 `INCOMPLETE`、`UNAVAILABLE` 和错误原样保留。v1.1 postprocessor
仅在内存中将准确的 repository-relative metadata path 转为该封存 Run 下的绝对路径：
要求 canonical spelling、位于该 Run 的 native archive、无 symlink、record SHA 与 seal SHA
及实际 bytes 三者相同，没有 basename/suffix 搜索、身份补写或原件变更。
`trace_audit/new_session_resolved/trace_audit.json` SHA 为
`cfdbaa682dc34a7c86a1db22a41a03b9c1f259b52fcb46f808f1b2c363c22a0a`，
原 v1 审查仍为 `79efe142751a1345f1be651953e2abbce832b6834629ba92ac913e1372c221d8`。

本次只读比对了 native rollout line 100 与 host MCP line 33：两个真实
`build_evidence_bundle` result 完整相同，都包含先前封存挑战的 `OBSERVED_OUTCOME`
路径。该路径 canonical SHA 为
`c95c2814765b515e6a2f104355f73b4bac12f0af937fef6555fc985ddddeeb4e`；
这是跨 Session 更新可见性证据，不表示又一次 Episode D 解题成功。
派生报告列出的重复 path matches 来自多个 typed 输出引用，不能按 24 次独立 observation
计算样本量。以上是对已存在动态原件的静态阅读，本审查没有启动新的 Session 或重新执行 parser。

## L15：联网后发现并修复的 owner-close 时序问题

`H1_FINAL_ACCEPTED_JUNIT.xml` 原件为 **1173 PASS / 1 FAIL**，失败为原始 EOF 断言的
`ConnectionResetError: [Errno 104]`，没有改写。其后清理断言未执行，不能仅从该 traceback
推断 SDK/资源泄漏。Linux v6.8 的
[`unix_release_sock`](https://github.com/torvalds/linux/blob/v6.8/net/unix/af_unix.c)
确实在 stream receive queue 未读空时给 peer `ECONNRESET`；归档内真实 kernel matrix
和受控官方 SDK probe 支持该时序解释。原 EOF 测试单独十次 PASS 也不能消除整套测试中的失败。

post-live 修复只在 owner 已撤销的 handler-finally 中 `SHUT_RDWR`、改为 nonblocking、
最多读取四个 64 KiB chunk / 262,144 bytes 并丢弃后关闭。残留 bytes 不 parse、不 forward、
不写日志；原测试文件是新测试文件的 exact byte prefix，原 EOF/cleanup 断言保留。
实际 old/fixed 受控结果为 RESET / EOF；两者 SDK 与连接归零、token 撤销、socket 删除；
只 forward `initialize`，pending ping 未 forward。新版本丢弃 96 bytes / 两次读取。
39 项 broker 测试通过，修复后的原 EOF 与受控测试连续十轮、每轮两项，共 20 PASS。
最终整体 1202 PASS 来自该新源码 epoch，不覆盖原 1173/1 FAIL。

固定 old broker SHA `98a7b56442aa012555c723f6caf4b3871bf96b0ad852eb4b2a7bbd0e0d313f2f`
仍是两次已封存模型 Run 的真实来源；新 broker SHA 为
`1026f28623ffcbec3e2739004e817c16178fef3659968d01ba925bb2ff1fd4e4`。
新源码没有再次模型挑战，本轮不向它倒填先前 Runtime 成绩。
超出有限 discard budget 的恶意未读队列仍可能在撤销后 RESET；不提供无限输入 EOF 保证。
最初 nested-launcher probe 未运行 pytest 的失败同样保留，不能计入十轮有效结果。

## L16：demo dispatch 的后续 source epoch 与真实 preflight 范围

发现 demo 从可信 launcher 内再次调用 shell wrapper 不合适后，只修复该入口的 dispatch。
授权、批准的 Gate/source pins、graph namespace 和唯一 trial 检查仍在 dispatch 之前。
宿主分支继续使用原 trusted wrapper；已经位于可信 wrapper 内的分支要求固定 mount markers、
Python 3.12、必要文件为普通、非空、可读且工具可执行，随后经 `sys.executable` 调用既有 collector。
没有新增 Agent Orchestrator、wall timeout 或读取 credential 内容的步骤。

实际 dispatch JUnit 为 **73/73 PASS**；前一版 61 个 demo 测试身份全部保留，
原函数、decorator 和断言 AST 没有改写，新增十二个 inside/guard/capability 用例。
record-only fixture 清除宿主真实 mount markers，明确原 host 契约的合成测试环境；
它不能取代下面真实 preflight 的证据。
真实 capability preflight 退出 0：Python 3.12.13、四项固定能力可用、outer enable flag
为 UNAVAILABLE，明确 `model_called=false`、`credential_contents_read=false`。
真实 old-gate source guard **退出 2**，指出 `Frozen source changed: aevora_core/src/aevora/mcp_broker.py`，
未创建 trial、未调用模型。此结果证明旧冻结版本在启动前拒绝新源码，不能写成新模型成功或
有效新 admission 的完整交接成功。

当前 demo SHA 为 `051821f1497d4ca02fab22e950cd3fe6d2aeb2b8d5efd8acc423943cbf1b2bc7`，
属于原联网 Run 之后的 source epoch；当前源码没有新联网挑战。
先前 188 份批准 snapshot 的 pins 只证明旧冻结运行版本，**不证明新 dispatch 是原 live 版本**。
`demo-real-closure-verification-release` 实际退出 0、stdout SHA
`c7b07cf2436b1b0498f4d8cd555a0b1c124507d1b87c137457fa664214f86589`
重新确认既有闭环，本身不发模型、图或业务调用。
最后完整 JUnit 为 1214/1214；先前 1202 PASS 和 1173 PASS / 1 FAIL 的所有原件均保留。

## 动态验收进度与剩余项目

| 项目 | 本版本状态 | 完成后所需实际证据 |
|---|---|---|
| Run `5089297e-39e7-4bd5-8b87-cbc7e21de022` 自然结束及清理 | PASS | Runtime 退出 0；SDK/连接归零、token 撤销、socket 删除、state 清理、536 文件 seal |
| 官方 MCP 模型调用和至少两个 native children | PASS，带上述 wrapper / encrypted-task 限制 | 3 个 verified children；3 个公开工具真实返回；官方原始引用匹配 |
| Episode D independent Outcome | PASS | 28/28 必要 JUnit 测试、36/36 Oracle；原始 patch SHA `274117054125ab84424d024bab6e2cae4ffbcae18d1e4f8066e014a08866d9a6` |
| Trusted current Outcome / Feedback | PASS，observed only | 授权 source/seal pins、拒绝/幂等/宿主冲突控制、两条新 Revision/OBSERVED_OUTCOME |
| 新 feedback 的 RDB SAVE/restart | PASS，范围限定 | 停写后显式 SAVE，stop/up 退出 0，重启前后图与所有 public paths 完全相同 |
| 不同 Session 看到更新 | PASS，仅 observation | 新 Session/thread independently joined；sealed host/native bundle 包含相同新 revision/evidence/Outcome；原始 NO_PATCH/NOT_EXECUTED 不改 |
| 最终完整回归 / demo closure | PASS，原失败与 source epochs 独立保留 | 1214/1214；最新 demo release exit 0；21 closure / 188 原live批准源码 / 两个 Run seal 再校验 |
| 后续 demo dispatch / preflight | 73 契约 PASS；metadata probe exit 0、source guard 正常拒绝 exit 2 | 不称为模型成功；无当前 source epoch 的新模型挑战 |
| 历史与独立真值保护 | PASS，真实根 Agent 再扫描 | 90,800 / 57 / 44 原件不变，856 测试身份保留；本审查读取命令与报告 |
| Final Full seal / Audit-Lite | Full 外独立发布门禁负责 | 见上述 RELEASE_RECEIPT；本预封存审查不宣称未来 ZIP 校验结果 |

完成这些项目也不解除本报告中的非因果、局部隔离、RDB crash-tail 和本地信任界限。
结论为 **CONDITIONAL PASS**，不会把未知因果、无限 adversarial 安全或 crash tail 改为 PASS。
H1 完成后停止；进一步可靠性升级或研究实验须另行授权。
