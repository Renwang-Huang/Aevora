# Aevora H1 — 实际 Decision / Native Trace 审计

## 1. 证据层次

挑战 Run `5089297e-39e7-4bd5-8b87-cbc7e21de022`；Lead `01a1298c-887d-7170-8c17-1c0cd0b16bc1`。原始 `codex_events.jsonl`、`aevora_mcp_events.jsonl` 和官方 native rollouts 在 sealed Run 中；派生 trace 单独存 `trace_audit/native_challenge/`。
Run seal SHA `1a89c94ebbe81df08e280c1e2150b341cfe7a70abf86bfe2efbbd7494c51bfff`；完整 file/line pins 见 [trace_audit/native_challenge/trace_audit.json](aevora_validation/20261011T051334Z-3e7fe273-3a17-4891-a6b2-4afb25376288/trace_audit/native_challenge/trace_audit.json) 与 [trace_audit/native_challenge/native_supplement.json](aevora_validation/20261011T051334Z-3e7fe273-3a17-4891-a6b2-4afb25376288/trace_audit/native_challenge/native_supplement.json)。
MCP host log不等于原生Agent身份证明；identity以官方typedCall/Session/parent/OwnTurn/receipt关联。原始 `exec --json` 未提供spawn，实际child来自原生rollouts。
本报告读取真实事件，不通过自然语言补写工具/child/完成事件。心理因果 **UNVERIFIED**；strategy attribution **UNKNOWN**。

## 2. 时间线（UTC，真实来源）

| 时间 | 事件 | 来源 |
|---|---|---|
| 06:00:35.971 | collector 开始（实际Runtime开始另见metadata） | g3-native-live-command-v2 receipt |
| 06:05:11.269706 | resolve returned / query `5699ade1…` | host response + exact official exec structuredContent |
| 06:05:35.827286 | resolve returned / query `0996f645…` | 同上 |
| 06:05:55.434 / .438 | 两条 bundle returned | host + native complete result |
| 06:06:29.517446 | record_decision，实际 VERIFY | Decision `33d8b213…`，独立调查要求 |
| 06:12:07.254898 | record_decision，实际 APPLY | Decision `7006a90b…`，Participant声明验证后采用原则 |
| 06:12:34.272 | 首个 official business FileChange lifecycle **start** | Lead原始210行 started_at_ms=1791699154272 |
| 06:12:34.348 | 上述 FileChange completed | 同一official FileChange |
| 06:12:34.354317 | host首次观察业务源码变化 | 非原子采样，只能作为上界 |
| 06:24:54.349423 | host提交接收 | execution trace5行 |
| 06:25:34.974 | collector完成/exit0 | command receipt；Runtime实际约1457.209s |
| 06:29:28.558 → 31.381 | trusted feedback入库与重复验证 | g4-actual-outcome-ingest |
| 06:30:36.015 → 36.229 | authenticated RDB SAVE | g4-rdb-explicit-save |
| 06:30:51.450 → 57.608 | stop / up --wait | 独立命令receipt |
| 06:31:53.790 → 06:41:29.775 | 新 observation完成 | 独立Session真实模型调用，无业务提交 |

成功工具调用在首个已观察的官方业务 FileChange start 前，满足**决策前工具可见性**；不能从时间先后证明心理因果。
`first_major_patch` 的语义、internal patch request call ID 未可靠暴露，标 **UNKNOWN**；不使用相邻exec的callID推定。

完整 Query IDs：

- `query:5089297e-39e7-4bd5-8b87-cbc7e21de022:0996f645-88fc-4195-934a-472eeca3b7d0`
- `query:5089297e-39e7-4bd5-8b87-cbc7e21de022:5699ade1-5749-4866-8add-e28d6c4c1453`

完整 Decision IDs：

- `decision:5089297e-39e7-4bd5-8b87-cbc7e21de022:33d8b213-6172-4ea3-934e-ef5d03a1f38d`
- `decision:5089297e-39e7-4bd5-8b87-cbc7e21de022:7006a90b-23d6-47a6-8f35-55a9c81ea422`

## 3. MCP 结果精度与错误

8次真实attempt，6 RETURNED +2 ERROR。全部8都有typed原生callID/arguments/thread join。
6个成功的完整结果均可精确对应官方 exec structured结果；其中bundle/decision的4个还与nativefullJSON精确一致。
两条成功resolve的native text wrapper不可完整解析（UNPARSEABLE_JSON），保留原始文本；完整可见性依赖官方exec精确引用，不修补或猜测遗漏字段。
两次输入错误真实保留，不报告为成功；broker outcome/admin能力不开放。
Cleanup真实activeConnections=0、SDKgroups=0、tokenrevoked/socketunlinked/handler/serverstopped，细节见原Runmetadata。

## 4. 三名原生子 Agent 自身证据

| 角色 | Session | Lead spawn line | Child任务/活动/完成 line | Lead接收line |
|---|---|---:|---|---:|
| Investigator | `01a1298e-8a19-7e41-9718-ed6c8eedf4b3` | 55 | 16 / 24 / 121 | 175 |
| Test Engineer | `01a1298e-c399-75d2-9913-2c6d3d0a5b4d` | 61 | 17 / 23 / 130 | 185 |
| Reviewer | `01a12999-32f1-7563-acd0-bf9777e1b22a` | 239 | 18 / 24 / 171 | 346 |

每份raw reference均保留完整文件路径、行号、包含原换行的SHA；排除child继承parenthistory后核查自己的Turn/工具/完成/parentreceipt。
原始任务投递正文位于加密通道：**UNAVAILABLE_ENCRYPTED_TASK_CHANNEL**。不宣称已解密；可核验的是实际身份、独立活动、final和回交。
维护者开发subagents不计入这些Participantchild。

## 5. 新会话与后处理 epoch

新 Run `4a141343-0714-4992-a0cf-119b61cff121`；真实 official thread/nativeSession `01a129a9-2b51-7771-aee5-f47aa995ce72`，与挑战Lead不同。
新会话在没有 Outcome ID 提示的公开只读任务下，真实 `resolve`/`build_evidence_bundle` 返回包含本次Outcome的updatedpaths。
精确bundlejoin：host33行SHA `c25767a3c4583c39c53da04b185bd54fb99c4ffcb7ef6b5d9552cf0e581cc6a2` ↔ native100行SHA `5b71dd47b2e352ab98492fab02970ca06b6f072f3a03006a78d7cef175e7a11e`；actual atomic OBSERVED_OUTCOME path SHA `c95c2814765b515e6a2f104355f73b4bac12f0af937fef6555fc985ddddeeb4e`。
该链保留 Outcome `orderflow:5089297e-39e7-4bd5-8b87-cbc7e21de022` / 28PASS / UNKNOWN；锁经验也新增observation，未因此获support。

原 Runtime `session_id=UNAVAILABLE`、ERROR/NO_PATCH、CLIexit0、evaluation NOT_EXECUTED 完整保留。
原v1audit **INCOMPLETE**：metadata collector使用repo-relativefullprefix，旧parser当作Runrelative追加。v1报告SHA `79efe142751a1345f1be651953e2abbce832b6834629ba92ac913e1372c221d8` 未变。
新增v1.1仅对精确位于本sealedRun/artifacts/native_rollouts的路径做in-memory projection，校验全Runseal、metadata和fileSHA，拒绝crossRun/链接/穿越/非canonical/不符。原nativeparser/Runtime未改，原始文件未改。
新audit [trace_audit/new_session_resolved/trace_audit.json](aevora_validation/20261011T051334Z-3e7fe273-3a17-4891-a6b2-4afb25376288/trace_audit/new_session_resolved/trace_audit.json) SHA `cfdbaa682dc34a7c86a1db22a41a03b9c1f259b52fcb46f808f1b2c363c22a0a`：native/exec COMPLETE；标POST_RUNTIME_DERIVATION_ONLY。
新增demo以sealed唯一官方thread.started + native session_meta +原metadata.thread_id + observation_report.thread_id一致性核验身份，保留session_id不可用，而非补写身份。

## 6. 可信反馈与归因

QueryExposure ≠ DecisionClaim ≠ ObservedAction ≠ VerifiedOutcome ≠ causalFeedback。
本次真实入库仅追加 OBSERVED_OUTCOME、两个ExperienceRevision和`outcome_observed_no_attribution`；UNKNOWN attribution、UNVERIFIED adoption、causal_claim NONE。
补丁SHA `274117054125ab84424d024bab6e2cae4ffbcae18d1e4f8066e014a08866d9a6`；独立candidate tree `b5ee7acaa3819e8124889938d011594245e61d5ec31fda57c5250621d1fecbaa`；隐藏结果PASS28/28，Oracle36/36。
这些证明工程产物与客观结果，不能证明某经验促成修复、Agent内心推理、治理算法整体提升或统计显著性。

Token usage见 [OFFICIAL_USAGE_SUMMARY.json](aevora_validation/20261011T051334Z-3e7fe273-3a17-4891-a6b2-4afb25376288/OFFICIAL_USAGE_SUMMARY.json)：D官方native80条按response去重的input=2,322,703、output=48,217；官方exec主Turn累计input=1,426,800、output=20,155。新观察Session的officialTurn input=343,874、output=15,429。不同口径不相加；cached/reasoning是嵌套字段，不能重复计入total。这些是可观测官方字段，不从自然语言估算缺失值；未响应Provider重试、账单与内部路由仍UNVERIFIED。
完整匿名化原始MCP trace通过Aevora capsule导出；原始完整native来自Full，Lite包含已选择的官方raw及未包含指针。Lite脱敏后的sourceSHA仅指向Full，exportSHA验证实际包含字节。
