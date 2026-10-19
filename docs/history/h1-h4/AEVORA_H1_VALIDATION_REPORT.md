# Aevora H1 工程验收报告

唯一任务书：`Aevora_H1_Experience_Accountability_EndToEnd_Codex_Task_v1.1.md`。
本轮实现、部署及实际验证已完成。**H1 Overall：CONDITIONAL PASS**。
完成真实闭环不解除已确认的数据库 AOF、共享内核隔离及本地证据权威限制。

## 1. 独立结论与边界

| 维度 | 结论 | 实际证据与范围 |
|---|---|---|
| FalkorDB Graph & Provenance | PASS | 真实数据库、约束、多跳 Cypher、历史四条可信链、幂等导入；持久化接受显式 RDB SAVE 与正常重启 |
| WHEN/WHY & Evidence | PASS | 同一 RLock 经验：单进程 APPLY、独立进程 ABSTAIN、未知 VERIFY；真实图边消融改变判断 |
| Native Codex MCP Integration | PASS | 新会话、三种实际工具、原生三名 child、补丁前真实调用、完整封存 |
| Trusted Feedback & Evolution | PASS | 独立 Outcome + 原始 seal/source pins；真实追加 Revision/OBSERVED_OUTCOME；幂等、冲突/伪造拒绝 |
| End-to-End A→D | PASS | 历史 A 来源入图 → 新 D 挑战 → 28/28 Hidden → 新反馈 → 不同真实会话读取更新证据 |
| Security / Leakage Boundary | PARTIAL | 声明路径/权限边界实际拒绝；完整恶意对抗、内核漏洞/侧信道、采样 CPU 不作保证 |
| Episode D Task Outcome | PASS | 未人工修补 Agent 提交；28/28 必要身份、pytest exit 0、Oracle 36/36 一致 |
| H1 Overall | CONDITIONAL PASS | 工程闭环成立；AOF 回放真实 SIGSEGV、RDB 非零丢失保证、全对抗隔离和外部存证仍有限 |

OrderFlow Incident Lab 仍是独立 Benchmark；Aevora 是独立经验问责核心；FalkorDB 是真实图数据库。
默认 Manual / Disabled 路径保留，只有显式 `--experience aevora` 开启集成。
本轮未实现 B/C、D-v02 业务、Dashboard、通用治理算法或 G0–G3 正式随机化实验。
单次任务通过**不能证明** Aevora 提高解题成功率、降低 token/成本或建立心理因果。

## 2. 新实现与既有成果复用

- `aevora_core/`：独立 `aevora-core` 0.1.0 / `aevora` 包，官方 FalkorDB SDK、真实 constraints、稳定 immutable IDs、参数化 Cypher、完整公开 evidence bundle。
- WHEN/WHY 从真实 Premise/Rule/Revision/Outcome/Context 图链计算三态；缺图、断库、未知前提不回退到固定答案。
- 官方 Python MCP SDK / FastMCP 服务显示名 **Aevora**。可信宿主 scoped UDS Broker：每 Run 短期授权、nonce/replay、UID、尺寸/并发限额和关闭撤销；只暴露 resolve/bundle/decision 三工具。
- Trusted Outcome Bridge 从批准的源/Run seal、实际 pytest/JUnit 必要集合、补丁 tree、宿主 Oracle/topology/recovery 核验事实；Participant 不可写 VerifiedOutcome。
- `integrations/aevora.py` 与现有 Participant/Runner/Codex Adapter 为薄集成；原生 Codex 负责协作，没有新增 Agent Orchestrator。
- `scripts/aevora_demo.py` 提供分阶段现成 argv、显式安全门禁下运行现有 collector、只读独立闭环复核；不自动重启图或虚构 Gate。
- `scripts/aevora_trace_audit.py` 仅对封存后原始官方事件做可追溯解析，不改运行结果。
- 修复了 G0 实际发现的取消发布竞态：`integrations/runtime_control.py` 原子发布。原 856 个测试身份、44 份旧测试字节、57 份任务真值及 90,800 个历史文件保留。

## 3. 实际环境与冻结版本

| 项目 | 实测 |
|---|---|
| checkout | dirty 分支 `m1-1-runtime-calibration-evidence`；HEAD `beba4fba73f2e59e0d5a7fb99aea332ad80ea2cf`，它不是本轮新源码的提交证明 |
| 运行时 source epoch | `release_admission_v2/frozen_source_snapshot`，manifest SHA `686d7a2b12f1fe710315d477e6f85f31334c6411ae2a25b05298c1d6aaf83f16` |
| Python / SQLite / pytest | 3.12.13 / 3.46.1 / 9.1.1；使用 `scripts/aevora-python`，宿主 Python3.10 不能直接执行部分工程入口 |
| Codex | 官方 CLI 0.162.1 + 同版本 Code Mode；真实 JSONL/native rollouts |
| 模型/effort | Gateway 响应与运行配置 `gpt-5.6-terra` / `max`；底层权重与费用 UNVERIFIED |
| completion-aware | `agent_timeout=None`、`request_budget=None`；连接/idle/retry/并发/资源有限，人工 cancel 保留 |
| FalkorDB | 4.20.4 image digest `adbddd418916c25618564ff8597a919b08bc76452ebeb74eb985c38d7281df62`；SDK 1.7.1 / redis 8.1.0 |
| MCP | official SDK 1.26.0；3 public tools / bounded scoped broker |
| 部署 | loopback 16379、authenticated、1 GiB/2 CPU/256 pids、持久 volume、当前 appendonly=no |

密钥保留宿主项目专用配置，未交给 Participant。Known-secret 扫描及 Audit-Lite 源码扫描的实际结果见最终外部 release receipt；扫描不能证明发现了所有未知敏感值。
运行时 source freeze 与后续审计解析修复属于不同 epoch；新解析器不能冒称是挑战时已经运行的版本。

## 4. Gate 与完整有效回归

| Gate | 结果 | 实件 |
|---|---|---|
| G0 | PASS | [G0_GATE.json](aevora_validation/20261011T051334Z-3e7fe273-3a17-4891-a6b2-4afb25376288/G0_GATE.json)；原 baseline 855 PASS / 1 FAIL，已归档并真实修复取消竞态 |
| G1 | PASS，RDB 范围 | [G1_RELEASE_GATE.json](aevora_validation/20261011T051334Z-3e7fe273-3a17-4891-a6b2-4afb25376288/G1_RELEASE_GATE.json)；AOF 失败另列，未删除故障文件 |
| G2 | PASS | [G2_GATE.json](aevora_validation/20261011T051334Z-3e7fe273-3a17-4891-a6b2-4afb25376288/G2_GATE.json)；同经验三态、真实 graph copies 边消融、断库拒绝 |
| G3 | PASS | [G3_GATE.json](aevora_validation/20261011T051334Z-3e7fe273-3a17-4891-a6b2-4afb25376288/G3_GATE.json)；原生 MCP/child/28 Hidden/Submission/cleanup |
| G4 | PASS，UNKNOWN 归因 | [G4_GATE.json](aevora_validation/20261011T051334Z-3e7fe273-3a17-4891-a6b2-4afb25376288/G4_GATE.json)；真实入库、负控、重启、新 Session 读取 |
| G5 | PASS，工程闭环范围 | [G5_FINAL_GATE.json](aevora_validation/20261011T051334Z-3e7fe273-3a17-4891-a6b2-4afb25376288/G5_FINAL_GATE.json)；独立 verify-existing，不宣称统计增益 |
| Brand & Compatibility | PASS | [BRAND_COMPATIBILITY_FINAL_RELEASE_GATE.json](aevora_validation/20261011T051334Z-3e7fe273-3a17-4891-a6b2-4afb25376288/BRAND_COMPATIBILITY_FINAL_RELEASE_GATE.json)；新 Aevora 命名，历史/旧接口保留 |

最新完整开发者回归：**1214/1214 PASS，0 FAIL/ERROR/SKIP**；实际 command exit 0。
JUnit SHA `03d84b7faa1f33b0feb766121801d4a930a87ad32cf8067332d234a0bc2ac824`；[H1_FINAL_RELEASE_JUNIT.xml](aevora_validation/20261011T051334Z-3e7fe273-3a17-4891-a6b2-4afb25376288/H1_FINAL_RELEASE_JUNIT.xml)。
[H1_FINAL_RELEASE_INTEGRITY.json](aevora_validation/20261011T051334Z-3e7fe273-3a17-4891-a6b2-4afb25376288/H1_FINAL_RELEASE_INTEGRITY.json) 核对旧 856 个测试身份全部保留、44 份旧测试字节、57 份任务真值和 90,800 个历史文件未变。
先前 1102/1102、1154/1154，以及最后修复前 **1173 PASS/1 FAIL** 全保留，是不同源码 epoch 的成绩，不能混用。owner-close reset 在 Linux6.8 上由 unread queue 确定性复现；旧 Broker 实际撤销资源正确，但未满足原 EOF 断言。新版本仅在 owner 已 stopped 时 SHUT_RDWR 后有限非阻塞 discard（4×64KiB），不解析/转发/日志内容。原 EOF/cleanup 断言每字节不改，39 Broker tests 与修复后10轮×2项均通过。联网两 Session 仍归旧 broker98a7… epoch；当前1026f286…的清理修复是 post-live 工程补丁，没有再运行模型。见 `post_live_close_fix/EPOCH_BEFORE.json`、`EPOCH_AFTER.json`、`DIAGNOSIS_AND_VALIDATION.md`。

已有 CLI 生命周期也实际新执行：SMOKE Buggy FAIL / Reference PASS；A Buggy FAIL / Reference PASS（14 necessary）；D Buggy FAIL / Reference PASS / 合法 flock PASS（28 necessary）；B/C NOT_IMPLEMENTED；invalid ERROR / timeout TIMEOUT；validate/prepare/report/reset 正常。
证据在 `inherited-cli-replay/`。这些是新的离线 Run，不改旧历史成绩。

## 5. 两个真实联网 Session

| 项目 | D native challenge | 新 read-only observation |
|---|---|---|
| Run ID | `5089297e-39e7-4bd5-8b87-cbc7e21de022` | `4a141343-0714-4992-a0cf-119b61cff121` |
| 官方 thread | `01a1298c-887d-7170-8c17-1c0cd0b16bc1` | `01a129a9-2b51-7771-aee5-f47aa995ce72` |
| collector exit | 0 | 0 |
| Runtime | PASS，约 1457.209s | 原 Adapter ERROR/NO_PATCH；CLI 正常完成，原结果保留 |
| 任务评测 | PASS 28/28、Oracle 36/36 | NOT_EXECUTED，无提交；本轮任务为只读证据观察 |
| 原生子 Agent | 3 verified/completed/received | single；只验证新会话重新读取，无需假装多 Agent |
| Run seal SHA | `1a89c94ebbe81df08e280c1e2150b341cfe7a70abf86bfe2efbbd7494c51bfff` | `1d04a2b1c70d5bb8daa8203954d98c0b2e9b2c20b09bb37513864ba533826c72` |

D 原始补丁 SHA：`274117054125ab84424d024bab6e2cae4ffbcae18d1e4f8066e014a08866d9a6`。
提交 tree SHA：`b5ee7acaa3819e8124889938d011594245e61d5ec31fda57c5250621d1fecbaa`。
宿主 Evaluator report SHA：`a810889e8a459447211c9add0f07cdb6bbab85cc99f694313d5d93b98e1606a4`。公开测试 diff 独立归档，不能替代隐藏 suite。
MCP 三种工具均实际到达；8 次 attempt = 6 成功 + 2 输入错误，错误保留。成功调用在首个 official business FileChange start 之前；详情见 Decision Trace 报告。

Trusted Outcome `orderflow:5089297e-39e7-4bd5-8b87-cbc7e21de022` 入库，实际图由 49 nodes/74 edges 变为 60/101；两条经验追加 OBSERVED_OUTCOME/Revision。完整重复导入一致且图不变。
显式 SAVE、container stop/up、重新读取均退出 0，完整图状态和 public paths 相同。
新会话真实 tool completed 的路径与 host raw response 完全匹配，包含同 Outcome ID、28 PASS、UNKNOWN attribution。
原 observation `session_id=UNAVAILABLE` 没被补写；使用封存官方 `thread.started` + native `session_meta` 精确一致作独立身份派生。

## 6. 实际执行命令与退出状态

每个下列链接保存**完整 argv、cwd、UTC、elapsed、exit、stdout/stderr SHA**，不是文档示例或假日志。

| command receipt | exit | elapsed seconds |
|---|---:|---:|
| [g0-developer-baseline/command.json](aevora_validation/20261011T051334Z-3e7fe273-3a17-4891-a6b2-4afb25376288/g0-developer-baseline/command.json) | `1` | 125.856 |
| [g0-cancel-deterministic-before/command.json](aevora_validation/20261011T051334Z-3e7fe273-3a17-4891-a6b2-4afb25376288/g0-cancel-deterministic-before/command.json) | `1` | 0.569 |
| [g0-developer-accepted/command.json](aevora_validation/20261011T051334Z-3e7fe273-3a17-4891-a6b2-4afb25376288/g0-developer-accepted/command.json) | `0` | 124.838 |
| [g1-dependencies/command.json](aevora_validation/20261011T051334Z-3e7fe273-3a17-4891-a6b2-4afb25376288/g1-dependencies/command.json) | `0` | 113.236 |
| [g1-release-import-history/command.json](aevora_validation/20261011T051334Z-3e7fe273-3a17-4891-a6b2-4afb25376288/g1-release-import-history/command.json) | `0` | 7.922 |
| [g1-release-disconnected/command.json](aevora_validation/20261011T051334Z-3e7fe273-3a17-4891-a6b2-4afb25376288/g1-release-disconnected/command.json) | `1` | 0.169 |
| [g2-decision-ablations-serial/command.json](aevora_validation/20261011T051334Z-3e7fe273-3a17-4891-a6b2-4afb25376288/g2-decision-ablations-serial/command.json) | `0` | 0.447 |
| [g3-full-regression-final/command.json](aevora_validation/20261011T051334Z-3e7fe273-3a17-4891-a6b2-4afb25376288/g3-full-regression-final/command.json) | `0` | 143.620 |
| [inherited-cli-regression/command.json](aevora_validation/20261011T051334Z-3e7fe273-3a17-4891-a6b2-4afb25376288/inherited-cli-regression/command.json) | `0` | 174.879 |
| [g3-physical-isolation-final/command.json](aevora_validation/20261011T051334Z-3e7fe273-3a17-4891-a6b2-4afb25376288/g3-physical-isolation-final/command.json) | `0` | 1.185 |
| [g3-native-live-command-v2/command.json](aevora_validation/20261011T051334Z-3e7fe273-3a17-4891-a6b2-4afb25376288/g3-native-live-command-v2/command.json) | `0` | 1499.003 |
| [g4-actual-outcome-ingest/command.json](aevora_validation/20261011T051334Z-3e7fe273-3a17-4891-a6b2-4afb25376288/g4-actual-outcome-ingest/command.json) | `0` | 2.935 |
| [g4-rdb-explicit-save/command.json](aevora_validation/20261011T051334Z-3e7fe273-3a17-4891-a6b2-4afb25376288/g4-rdb-explicit-save/command.json) | `0` | 0.213 |
| [g4-graceful-container-stop/command.json](aevora_validation/20261011T051334Z-3e7fe273-3a17-4891-a6b2-4afb25376288/g4-graceful-container-stop/command.json) | `0` | 0.356 |
| [g4-container-rdb-restart/command.json](aevora_validation/20261011T051334Z-3e7fe273-3a17-4891-a6b2-4afb25376288/g4-container-rdb-restart/command.json) | `0` | 5.801 |
| [g4-rdb-postrestart-snapshot/command.json](aevora_validation/20261011T051334Z-3e7fe273-3a17-4891-a6b2-4afb25376288/g4-rdb-postrestart-snapshot/command.json) | `0` | 0.192 |
| [g4-forged-seal-rejection/command.json](aevora_validation/20261011T051334Z-3e7fe273-3a17-4891-a6b2-4afb25376288/g4-forged-seal-rejection/command.json) | `2` | 0.243 |
| [g4-actual-immutable-conflict-audit/command.json](aevora_validation/20261011T051334Z-3e7fe273-3a17-4891-a6b2-4afb25376288/g4-actual-immutable-conflict-audit/command.json) | `0` | 0.197 |
| [g4-new-session-command/command.json](aevora_validation/20261011T051334Z-3e7fe273-3a17-4891-a6b2-4afb25376288/g4-new-session-command/command.json) | `0` | 575.984 |
| [g4-new-session-trace-postprocess-resolved/command.json](aevora_validation/20261011T051334Z-3e7fe273-3a17-4891-a6b2-4afb25376288/g4-new-session-trace-postprocess-resolved/command.json) | `0` | 0.377 |
| [demo-real-closure-verification-release/command.json](aevora_validation/20261011T051334Z-3e7fe273-3a17-4891-a6b2-4afb25376288/demo-real-closure-verification-release/command.json) | `0` | 1.115 |
| [h1-final-release-regression/command.json](aevora_validation/20261011T051334Z-3e7fe273-3a17-4891-a6b2-4afb25376288/h1-final-release-regression/command.json) | `0` | 146.121 |
| [h1-final-release-integrity/command.json](aevora_validation/20261011T051334Z-3e7fe273-3a17-4891-a6b2-4afb25376288/h1-final-release-integrity/command.json) | `0` | 29.405 |
| [g1-retained-aof-isolated-replay/command.json](aevora_validation/20261011T051334Z-3e7fe273-3a17-4891-a6b2-4afb25376288/g1-retained-aof-isolated-replay/command.json) | `139` | 1.187 |
| [demo-launcher-dispatch-command/command.json](aevora_validation/20261011T051334Z-3e7fe273-3a17-4891-a6b2-4afb25376288/demo-launcher-dispatch-command/command.json) | `0` | 1.637 |
| [demo-trusted-capability-preflight/command.json](aevora_validation/20261011T051334Z-3e7fe273-3a17-4891-a6b2-4afb25376288/demo-trusted-capability-preflight/command.json) | `0` | 0.084 |
| [demo-live-source-guard-preflight/command.json](aevora_validation/20261011T051334Z-3e7fe273-3a17-4891-a6b2-4afb25376288/demo-live-source-guard-preflight/command.json) | `2` | 0.104 |

核心真实命令：

```sh
# archive 为本报告的独立新 Aevora Full 路径；recorder 实际 argv 见上述实件。
scripts/aevora-python -m pytest -q tests aevora_core/tests --junitxml=<accepted-junit>
ORDERFLOW_ENABLE_CODEX=1 scripts/aevora-python scripts/aevora_live.py run <archive>/release_admission_v2 --trial native_challenge
scripts/aevora-python aevora_core/scripts/ingest_orderflow_outcome.py --run-dir <sealed-D-run> --run-id 5089297e-39e7-4bd5-8b87-cbc7e21de022 --run-seal-sha256 <preapproved-seal> --source-archive <archive>/release_admission_v2 --source-manifest-relative-path SOURCE_TRUST_MANIFEST.json --source-manifest-sha256 <preapproved-source> --source-snapshot-relative-path frozen_source_snapshot --output <new-receipt>
docker compose -f aevora_core/compose.yaml stop experience-graph
docker compose -f aevora_core/compose.yaml up -d --wait experience-graph
scripts/aevora-python scripts/aevora_demo.py verify-existing --archive <archive> --index-reference CLOSURE_INDEX_V2.json --index-sha256 82631e9fa7f2ab03dba4b4b99be58d2258fd44182aa4312b4822782db55295c7
```

带占位符的是上述真实 argv 的可阅读摘要；**执行事实以 command.json 的精确值为准**。
`plan/stages` 只打印现成命令，不自动授权挑战、发布 Gate 或执行重启。

## 7. 失败记录与纠正纪律

完整 [COMMAND_INDEX.json](aevora_validation/20261011T051334Z-3e7fe273-3a17-4891-a6b2-4afb25376288/COMMAND_INDEX.json) 包含所有已归档 receipt，包括失败；没有删除或改写失败。

- G0 baseline 1 FAIL：实际 cancellation publication race；定向回归修复前 FAIL、修复后 PASS，再重复旧路径 50 次 PASS。
- FalkorDB 起始 container CMD/auth 与 mandatory constraint SDK 兼容问题真实修复；官方 SDK/实际 schema validation 为依据。
- AOF release restart CLI exit 1；首次函数栈缺原始证据，不倒填。后来的只读隔离 AOF replay **exit139/SIGSEGV** 为新动态证据。
- 并行 graph copy 在 pids256 下失败；改为序列消融，无扩大生产 pids。
- 初次完整回归 1036 PASS/2 FAIL，真实修复 graph Context provenance namespace 与 capsule 收集问题后 1102 PASS。
- Host3.10 collector StrEnum failure 发生在 Run/model 创建之前；新 v2 source freeze 后用可信 Python3.12 运行。它不算新挑战成绩。
- MCP 两次真实输入错误、Gateway stream/client/server 中断保留；在 completion-aware 中正常自然结束，没有静默降级 max 或用总时间杀死健康运行。
- Native `resolve` text wrapper 两条不可完整解析；完整成功结果由 official exec structured result 精确引用核验，未截断/修补 native 文本。
- 新 observation metadata 记录 repo-relative archive path，引起 v1 后处理 INCOMPLETE；原报告保留。v1.1 用完整 Run seal + exact within-Run path + file SHA 在内存中投影，拒绝跨 Run/链接/穿越/不符。
- 新只读 observer 正常无 patch，被 repair Adapter 标 ERROR/NO_PATCH；不改该真实成绩。审计用 sealed official identity 修复新增 demo 的观察兼容性。
- 新 demo 最初只识别直接 SAVE/restart argv，真实 SDK SAVE + stop/up 被拒绝；保留 exit2。后续增加显式 pinned probe/stop/chronology 控制，不把字符串检查简单放宽。
- 新 demo 可信 launcher 内重复调用 launcher 的入口问题已修复：实际 Python3.12、固定 maintainer mounts 和官方 tools 可用性决定 direct existing collector dispatch，缺能力拒绝。73/73契约通过，原61身份保留；真实非模型 capability preflight exit0，旧冻结source guard exit2且模型调用0。该入口修改是 post-live，不冒称两次联网挑战运行过新源码。
- 最后修复前完整回归1173 PASS/1 FAIL：owner close遇到合法kernel ECONNRESET；确定性旧/new SDK probe分别reset/EOF但均完整撤销，修复有限discard而非放宽原断言。原测试10次独立PASS不能消除全回归失败；修复后额外20PASS及最终完整回归另归新epoch。
- 最终 capsule 收集首次 exit1：选入了实际为空的 source-guard stderr，严格非空资产校验拒绝。改选实际包含错误的完整 stdout，不改变非空断言；旧失败receipt、零字节日志及第一批 public copies/manifest全部保留。
- 某些合成测试初次 recorder argv /诊断字段错误及嵌套launcher ENOENT有独立失败receipt；未运行pytest的10个launch失败不计为close测试。修复仅在H1新模块/新增工具/追加测试，既有业务和隐藏断言未放宽。

## 8. 历史、新动态、静态与合成证据区分

历史：四条 A/D 对照源及 Phase3 自然 Agent patch，仅重新读取已封存文件；旧 M1 TIMEOUT/PASS/TIMEOUT 不变。
本次动态：真实图、三态/边消融、隔离权限、全部回归/CLI、新 D native challenge、真实 trusted ingest/RDB restart、新 observation。
静态：架构/身份/信任边界/37 源码只读审查；不能替代执行。审查 addenda 为独立后续产物，旧件不变。
合成：negative Outcome write、scoped socket/假凭据、契约测试等明确 SYNTHETIC，不能当作自然 Agent outcome。
无法证明：底层模型权重/费用、心理因果、正式治理增益、共享内核完全对抗、外部不可变存证、AOF精确上游根因、unsaved crash tail。均 **UNVERIFIED**。

## 9. Full / Audit-Lite 与停止边界

Full：`aevora_validation/20261011T051334Z-3e7fe273-3a17-4891-a6b2-4afb25376288/`；最终 manifest/checksums 后不再写入。
Audit-Lite：`aevora_validation/audit_exports/20261011T051334Z-3e7fe273-3a17-4891-a6b2-4afb25376288/aevora-h1-audit-lite.zip`；实测 ZIP SHA、size、独立 verify、capsule verify、同 timestamp 重导出、篡改拒绝和源保真在 **Full 外**的 `RELEASE_RECEIPT.json`。
当前源码和原始 MCP/设计正文、Schema、Cypher、全部 Gate、JUnit、关键 Outcome、Source Change 通过显式 Aevora capsule 收入 Lite。保留 NOT_INCLUDED 指针；私有隐藏测试/参考补丁/私有 Manifest/DB/凭据不导出。
外部可信 stdlib verifier 和 ZIP SHA 必须由独立渠道取得；包内自校验不能认证来源，旧 verifier 不验证 Aevora capsule 语义。
相同系统/压缩库/固定时间的确定性不是跨机器压缩库保证。

本轮到 **Aevora H1** 停止。后续应单独授权数据库 AOF 修复与故障恢复、更强隔离/外部证据权威、任务分布与正式随机化研究；当前未执行这些项目。
