# Aevora H2-G3 — Native E2E 验收

## 结论

**G3 关键功能 PASS；Agent 解题 2/2 PASS；公开测试的 Native Runtime 兼容性 PARTIAL。** 总体 H2 为 CONDITIONAL PASS，不能将集成成功、解题成功和治理因果收益合并。

本轮 Full：`aevora_validation/H2-20261011T082213Z-6bd12e96-82e1-4c87-b1df-67bc7fa74ae9/`（以下 A）。历史报告与原成绩不变；新结论来自本轮命令与原始字节。 `A/G3_GATE.json` 保存逐项实际文件 SHA。冻结源码 Commit `6a8e3d7831c27acb27703a7dba0a5d47d90fdbe0`，326 项源码在挑战前后保持一致。Suite/Oracle 1.1.1、36 项隐藏测试、8 项恢复窗口在首个 Participant 启动前冻结；历史35项/1.1.0 epoch未改判。

## 全部分母与原生协作

| Run | Thread | Runtime / Integration | Hidden | 原生子 Agent | 原始补丁 SHA256 |
|---|---|---|---:|---:|---|
| ea0b61f9-781d-43b2-99e6-6ff2b8b98234 | 01a12ad9-c65b-76b3-a709-b12ee6f02ded | PASS / PASS | 36/36 | 3 | 207a2c0504f1da1a74b729f3d79f687e0a4da6a39b3b9ad434d45531e1af8513 |
| ddfc2726-8d0d-4a4a-a37f-3ed99b2f64f2 | 01a12aee-390b-7aa1-b182-77366d3c0f1e | PASS / PASS | 36/36 | 3 | 879f88e696dbaab8c2a4a03bbefddd17b7ae954c104195ad0ab0b4340a79e18b |

两次全部开始的正式工程挑战均归档，没有筛去失败重试。各 Run 是全新 `codex exec --json` Session，不继承维护者对话；同一初始公开缺陷基线、不同最终补丁。两轮分别实际运行 1274.039 秒、1586.781 秒。原生 rollout 的 typed task delivery / tool / task complete / parent receipt证明每轮3名不同子 Agent 独立完成；CLI stdout未提供完整子 Agent身份，不把文字自述当证据。初始加密任务明文 UNAVAILABLE。原生原始 rollout 和 stdout均保留。

挑战01子 Agent：01a12ada-e118-7440-bb36-567c3b0fc072, 01a12adb-00a9-7163-8585-2d14d13d7e83, 01a12ae6-07b7-77f2-92e1-52a7dae89b8a。
挑战02子 Agent：01a12aee-df4f-7913-84d6-da1f1c1d0623, 01a12aef-05f5-7ee2-b57f-1ff88eb4efe9, 01a12afb-a1c7-7bb0-854c-f738ce735dc9。

两个原始 Participant→补丁→Candidate tree一致，独立宿主 Oracle/JUnit各36 PASS、0 FAIL/ERROR/skip，八窗口 COMPLETE；每轮399个原始 Oracle 文件和37项 Worker/Clock清理记录经独立复核。没有人工替换 Reference。独立两轮分母报告：`A/g3/independent-stopped-run-review/20261011T122527.647503Z-67b96346-5df4-4d05-acf4-ceb1202b651e/two_challenge_denominator/TWO_RUN_DENOMINATOR_REVIEW.json`。

## MCP、WHEN/WHY 与实际反馈

两轮原始 MCP 合计14次工具调用：9次成功、5次 resolve ERROR。挑战01为8/5/3，挑战02为6/4/2（调用/成功/错误）；错误完整保留。成功 resolve/bundle/decision 在可观测的首个文件变更完成及宿主首个补丁发现之前，精确 host/native逐行SHA可关联。最早写入请求时刻并非全可观察，宿主轮询不是实际首写时间。RLock不满足多 Worker前提→ABSTAIN；SQLite原则有支持→principle APPLY，整项 lease/authority操作覆盖不足→VERIFY。未按题号提供答案；Agent仍须调查当前权限失效。

真实 `verify_outcome` / Trusted Host `ingest_outcome` 接受两个36/36原始提交。两轮各新增两个 OBSERVED_OUTCOME Revision；图由37/40→48/65→59/89（节点/边，查询快照等是实际元数据）。重复导入前后相同。真实 Decision关联数量第一轮2、第二轮1。没有将 PASS 自动生成 SUPPORTS；Feedback 为 `outcome_observed_no_attribution`，归因 UNKNOWN。历史 natural_agent_run来源与本次 `MAINTAINER_SEEDED_HISTORICAL_CONTROLLED_CORPUS` 部署来源分开，未将治理 Fixture算自然工程成绩。

## 真冷恢复与新 Session 回读

实际 SAVE→RDB校验→全新独立 volume/17683 official FalkorDB冷启动，source/restored/source-after均59/89、同一图摘要。RDB SHA256 `f6d06ef9adc6e6373e22989163fd829bceb25e7e3dacd24bf36b1a80e8673532`；checkpoint SHA256 `185b28be4c18a5930ddeb66ad0cf45448bcb43baf643617908254549dbca7c42`。

新只读 Run `ca0a17cb-1f0a-43ab-b1fc-7ef0b03321ec` / Thread `01a12b0d-d04d-7271-b5ac-c4c8ea8b9206` 实际连接冷恢复17683，534.097秒外层命令退出0、Codex退出0。原适配成绩 **ERROR / NO_PATCH**，Evaluation **NOT_EXECUTED**，生命周期原报告 PREPARED，均保留；不能把观察完成写成解题PASS。单 Agent observation 与两次多 Agent工程挑战分母分开。

实际 host MCP和官方 typed completed MCP响应中，出现第二次工程Outcome的两个完整 Experience→Revision→Evidence→VERIFIES路径，raw逐行SHA和对应实际Outcome字段匹配。审计24项匹配是跨多个证据源的重复匹配，不是24个独立Outcome。Observation原报告的 pending字段不改写，另附 `A/g3/trace-cold-readback/trace_audit.json` 的实际 `OBSERVED_IN_HOST_AND_TYPED_NATIVE_OUTPUT` 结论和419项独立冷恢复闭合复核。只读会话没有补丁，没有产生新 VerifiedOutcome。

独立冷目标已实际 down、未用-v；证据卷保留，H1与H2source仍RUNNING。目标 inspect退出1是正确的No such object负面结果。恢复后查询自然新增元数据，不能宣称读回后图永远保持59/89。

## 有限图必要性对照

九项真实控制全部按预期完成：GRAPH.COPY隔离副本中撤去关键VERIFIES，SQLite原则 APPLY→VERIFY；独立 relay实际断开后MCP请求 ERROR，没有缓存完整结论。缺少前提、冲突事实和断库不静默APPLY。主体受控图不变。140条实际SDK命令、36帧MCP及副本清理可复核。这是有限必要性验证，**不是统计消融，不证明提高通过率或因果收益**。

## Runtime、公开测试和安全限制

请求实际使用 gpt-5.6-terra/max，无静默降级；模型权重、服务端实际路由/内部推理计算 UNVERIFIED。completion-aware无任意总墙钟截止，模型并发4、挑战串行、2GiB/768pids、有限连接/idle/retry、取消入口保留。实际Gateway 500/502/503/524、连接中断/timeout、RUN_CONCURRENCY_LIMIT与原重试均归档，并未挑掉。

**确认的兼容性缺陷**：原公开6项 unittest的 DiagnosticClock Unix Socket `.bind()` 在原生 command sandbox被EPERM拒绝，全部setup ERROR；每轮原始失败退出1保留。新Agent测试以可注入内存Clock独立验证，不能冒充原6项通过或原UDS路径可用。独立 Hidden Evaluator拥有可信UDS、36项通过。这里没有为挑戦修改公开测试、冻结Oracle或沙箱。下一版本应增加明确公开Clock注入契约并独立保留真实UDS集成检查；本次仅记录限制。

实际新Archive扫描91,829普通单链接文件、4,460,709,620B，当前项目2项真实凭据匹配0，未输出值或哈希。318特殊/链接、6硬链接未读；未知任意凭据、清除后临时capability原值、VM/共享内核敌对证明 UNVERIFIED/PARTIAL。41个私有路径的实际读拒绝来源于先行三层安全门禁；正式挑战实际额外3个路径metadata ENOENT不伪装成41个读探针。Per-run capability不等于per-child身份。

## 实际命令与退出

| 命令 | A中的完整收据 | 退出 / 秒 |
|---|---|---:|
| `aevora-h2-python -m scripts.aevora_h2_native run A --trial challenge_01` | g3-native-challenge-01/command.json | 0 / 1314.623889 |
| 同上独立第2轮 | g3-native-challenge-02/command.json | 0 / 1627.468972 |
| `aevora-h2-python -m scripts.aevora_h2_graph_e2e ingest ...`，两轮 | g3-trusted-ingest-challenge-01/command.json；02 | 0 / 2.899965；2.897983 |
| `python3 -I -B scripts/aevora_h2_g3_recovery.py run A ...` | h2-g3-real-rdb-live-outcome-recovery/command.json | 0 / 5.7528 |
| `aevora-h2-python -m scripts.aevora_h2_native observe ...`，独立17683 | g3-native-new-session-cold-readback/command.json | 0 / 534.096531 |
| 档案only trace审查 / independent closure | g3-trace-audit-cold-readback/command.json；h2-g3-rdb-native-readback-cleanup-closure-v2/command.json | 0 / 0.53188；0.3714 |

命令中的省略参数不是复现命令；精确 argv、环境路径、UTC、stdout/stderr SHA以收据为准。最简入口见 H2_REPLAY_README 和公开Usage。没有成本理由省略必要挑战。停止在H2。
