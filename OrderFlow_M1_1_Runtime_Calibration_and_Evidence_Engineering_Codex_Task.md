# OrderFlow Incident Lab — M1.1 开发任务书

**主题：Long-Running Runtime Reliability · Difficulty Calibration · Evidence Engineering · Episode D-v02 Design**  
**性质：正式授权开发、动态验收与研究先导实验；不推进 B/C、D-v02 实现或经验治理核心。**  
**适用基线：M1 `m1-task-system-episode-d` 工作树中经验证的最终源码快照；以实际 SHA256 和验收记录为准，不以未提交的分支名作为真实性保证。**  
**优先目标：可靠、可解释、可复现；不以节省模型调用时间或增加 PASS 数字为目标。**

---

## 0. 为什么需要 M1.1

OrderFlow 已完成 Phase 1–3、Phase 3.5 和 M1，形成了真实的 Codex 原生 Multi-Agent、隔离 Participant、Submission Fidelity、独立 SQLite Oracle、Episode A 与 D-v01。M1 的 664 项开发者测试及 30 轮正反控制提供了较强工程证据。

但 M1 的三次真实 D-v01 Pilot，**原自动闭环为 1/3**：`TIMEOUT / PASS / TIMEOUT`。两个超时的原始补丁在停止后独立评测均为 `28/28 PASS`，不应反向改写为自动完成。我们目前能确认它们做出了正确代码，**尚不能断言既定时间内已完成原生协作、正式交付**。

本阶段需要同时回答：

1. 是否因为固定 wall-clock、Broker / CLI 超时、Provider 慢响应、429 以及原生协作收尾，使正常进行的挑战被过早终止？
2. D-v01 的**代码问题难度**与**运行时收尾成本**各有多大？是否存在任务天花板效应？
3. 怎样让审计证据仍完整可信，同时避免每次交付数 GB / 十万条目的 ZIP？
4. 下一独立 D 变体应怎样形成实质不同的证据条件 / 故障因果，而不只换参数？

**用户明确授权使用自己的 Gateway 进行必要的真实联网测试。不要为了省模型 Token 或赶进度设置一个人为很短的总时限。** 但模型可用不等于放弃身份隔离、进程资源限制、异常检测与人工停止能力。

---

## 1. 工作范围与保护原则

### 必须完成

- **R1：分层运行时诊断与可持续运行模式**。支持以真实完成条件而非固定 wall-clock 为终点，保存进度、错误与退出分类。
- **R2：体量可控的证据导出机制**。完整原始归档与轻量审计包分离，导出可校验、可追溯、可按需重放的审计资产。
- **R3：Episode D-v01 难度 / 协作开销先导校准**。真实单 Agent / 原生 Multi-Agent 对照，冻结任务输入、Evaluator 和模型，禁止修改得分以提升数据表现。
- **R4：Episode D-v02 的独立设计与质量审查**。只产出经评审的任务规格、独立因果假设与未来验收 Gate，本阶段**不实现 D-v02**。

### 严格不做

- 不开发 Episode B / C；不实现 D-v02 业务、隐藏测试、参考补丁；不修改 D-v01 当前私有真值来争取高分。
- 不开发 GraphSwarm、FalkorDB、MCP、WHEN/WHY/FEEDBACK 治理算法或 G0–G3 正式科学实验。
- 不重写 Codex 原生调度，不用 Python 角色扮演器代替原生 Subagent。
- 不覆盖 / 改写 M1 三次 Pilot、Phase 1–3.5 历史 Run、失败证据和冻结指纹；新运行一律独立 Run ID。
- 不将宿主密钥、授权 Token、完整私人认证文件送入 Participant、提示词、源码或导出证据。

如果某一项真实运行因外部服务限制无法完成，明确标记 `BLOCKED` / `PARTIAL` / `UNVERIFIED` 并提供原始依据，不能捏造完整 PASS。

---

## 2. R0 — 开发前基线检查与诊断设计（先做）

读完项目 `README.md`、`docs/ARCHITECTURE.md`、`docs/TASK_SYSTEM.md`（如存在）、`docs/TASK_RELATIONS.md`、M1 全部最终报告、Pilot 时间线、`M1_REMAINING_ISSUES.md`、Roadmap v1.0，并审查当前实际源码和 CLI。

重点逐一定位与记录：

- `integrations/codex_agent.py`：`CodexConfig.timeout_seconds` 当前为正数且有 7200s 上限；`Popen.communicate(..., timeout=...)` 超时后杀进程组；`ResourceWatchdog` wall_seconds；真实是否具备安全暂停/终止。
- `benchmark/cli.py`：`run-codex --agent-timeout` 当前默认 900s、`--request-budget` 默认 160。
- `integrations/model_broker.py`：Broker `request_timeout` 上限 120s、上游 `opener.open()` 超时、SSE `read1()` 行为、HTTP 错误分类、429 / Retry-After 语义。
- `integrations/codex_agent.py` 的原生 CLI 配置：`stream_idle_timeout_ms=120000`、`request_max_retries=2`、`stream_max_retries=2`；先核对安装版本支持哪些配置，不可猜测未证实字段。
- Pilot collector / `m1_live_pilots.py`：目前 1200s Agent + 1380s collector，且 Gate 写死这组设置。
- 证据目录：实际占用、最大的 N 种文件 / 目录、重复内容占比、归档写入位置与清单校验方式。

先提交一份 `M1_1_BASELINE_AND_FAILURE_HYPOTHESES.md`：列出每个超时层、触发条件、原始错误证据、是否属业务失败，以及设计要改变的**最小源码位置**。不要先修改测试，再声称问题已定位。

---

## 3. R1 — 可持续运行：取消固定总时限，但不取消安全门禁

### 3.1 两种显式模式

在当前 CLI / `CodexAgentAdapter` 中实现兼容模式：

**`bounded`（兼容历史行为）**：允许设置总运行时长，旧 CLI 与验收脚本的语义保持兼容；原 TIMEOUT 记录仍准确。

**`completion-aware`（M1.1 新研究模式）**：**不因为经过 900/1200/7200 秒就强制结束仍正常工作的 Agent**。总 wall-clock 不作为自动失败阈值；完成判据为 Codex 官方 `turn.completed`、进程正常退出、实际补丁生成与独立提交评测。允许研究人员显式取消，并记录 `CANCELLED_BY_OPERATOR`，不能冒充 `TIMEOUT`、`PASS` 或 `FAIL`。

如果使用 `--agent-timeout none` / `--completion-policy completion-aware` 等 CLI 表达，请由实现者决定实际命名，保持向后兼容并在 `--help` 写清楚。不允许使用“很大的数字”假装无限制，也不能让 `ResourceWatchdog.wall_seconds` 继续隐式强制终止。

### 3.2 慢速中转响应 ≠ 卡死

不能把单一的“长时间没有 stdout”或“某次 SSE read 很慢”视为 Agent 死锁。至少区分：

- `ACTIVE_MODEL_REQUEST`：请求已发出，等待首字节或继续接收流；
- `SSE_STREAMING`：流有实质内容或可验证的增量传输；
- `RATE_LIMIT_BACKOFF`：真实 429，遵循有效的 `Retry-After` / 退避；
- `CHILD_AGENT_RUNNING`：已观测到原生子 Agent 的活跃工作；
- `LOCAL_TOOL_RUNNING`：本地工具执行；
- `WAITING_FOR_CHILD`：主 Agent 正等待真实子 Agent；
- `POSSIBLE_STALL`：缺少足够进度信号，只发出告警、不仅凭时长判失败；
- `UPSTREAM_ERROR`、`PROCESS_EXITED`、`RESOURCE_LIMIT_EXCEEDED`、`CANCELLED_BY_OPERATOR` 等明确终态。

区分**从发起到 HTTP 首响应、两段 SSE 数据间隔、完整响应时长、重试/退避、Agent 本地计算、协作等待、最终提交**。能准确观测则记录，不能准确归因标记 `UNAVAILABLE`，不得靠差值硬凑各阶段耗时。

Broker / CLI / collector 的短超时需做分层评审：慢速有效连接不应仅因 120 秒固定阈值被当作不可恢复失败；但连接断开、证书问题、永久 4xx、格式错误必须正确终止或按真实机制恢复。采用当前 Codex CLI 官方支持的超时 / 流恢复参数；**不允许修改上游 Codex 二进制，不关闭 TLS 验证，不伪造心跳、SSE 和官方完成事件**。如果 CLI 本身有不可调限制，记录可重现证据，并为该能力给出 `PARTIAL` 结论。

### 3.3 安全与负载控制继续存在

- 保留 Participant 文件和网络隔离、每 Run Broker 鉴权、cgroup memory/pids 以及已有输出/CPU 资源观察。
- **总运行时长可以无限等待自然完成，不代表模型并发可以无限增加。** 保持并发受控，模型请求和资源用量持续可观察；请求预算应可配置、可明确声明为不设总量硬上限，但不能隐式绕过 Broker 身份和安全限制。允许配置告警阈值，不因纯用量计数在研究模式偷偷停止。
- 必须提供**可信宿主侧** `status` / `cancel`（或等价机制）；取消后完整终止进程组、子 Agent、Broker、Socket、cgroup，所有子进程都能清理；不可将取消误判为 Agent 模型能力不足。
- 支持进行中的**只读状态/证据快照**，包括当前 Run ID、状态、最近可信进度、子 Agent 完成情况、请求计数、Token（若有）、最近真实错误和补丁树摘要。仅在可安全读取且不扰乱 Participant 时生成；若流尚未最终封存，明确标记 `PARTIAL_SNAPSHOT`。
- 正式 Session **默认从头运行**。没有官方支持且验证通过的 resume 时，不能声称断线续跑；不能把新 Session 冒充同一轮恢复。

### 3.4 必需的动态测试

除原有回归之外，新增可控本地 Fake Gateway / SSE fixture：延迟首字节、缓慢但持续的 SSE、真实流空闲、429 + Retry-After、连接中断后重试、永久鉴权失败、子进程/子 Agent 长时间工作、用户取消、Collector 中断、异常进程退出。应确保：

- `completion-aware` 对“慢但最终完成”的响应判定成功，不触发总时长 TIMEOUT；
- 真正的网络/进程错误分门别类，拒绝无限重试永久错误；
- 正常完成、人工取消和故障退出均有明确证据与清理；
- `bounded` 仍可准确执行和报告现有 TIMEOUT，历史测试不被掩盖；
- 标准 Episode A / D 公私隔离与提交保真不回归。

**不要把 test fixture 简化为 sleep 一下然后打印 PASS。** 必须让模拟走过真正的 Broker / Codex Adapter 边界或可说明的等价真实执行路径；fixture 不能代替后续真实 Gateway 挑战。

---

## 4. R2 — Evidence Engineering：完整原始证据 + 轻量审计导出

### 4.1 不得以删证据换小包

原始 Run、失败记录、完整原生事件、JUnit、补丁、数据库验证、指纹与历史版本留在可信宿主的 Full Archive。创建独立的 **Audit Export**，用于用户上传给外部审查者。两个层级必须有清晰关联：

- **Full Evidence Archive**：本机完整、不可被本轮导出工具原地重写的原始证据。可以建立只读或内容寻址去重结构，但不能删除历史失败记录；涉及已有封存的迁移必须生成新索引、证明源文件不变。
- **Audit-Lite Bundle**：简明、可移植、脱敏、可验证的 ZIP / tar.zst（以实际环境成熟工具为准）。包括原始执行与得分结论所需的最小证据，不用把所有重复工作区、虚拟环境、重复数据库备份和全部历史 Run 都打包。
- **Replay Pack（可选、独立）**：若用户需要在外部环境重放，提供必要源码、固定依赖与操作指令。其权限等级单独明确：维护者私有 Oracle / Reference 只可进入受控维护者复现包，**绝不能出现在 Participant 公开包**。

### 4.2 Audit-Lite 必须包含的内容

- `README_AUDIT.md`：来源、版本、如何验证、能证明什么、不能证明什么；
- `MANIFEST.json`：原 Full Archive Run ID、模式、文件 SHA256、角色、来源相对路径、导出时刻、敏感性等级、原始文件是否随包提供；
- `RUN_INDEX.json`：每次尝试的实际状态（包含 FAIL/TIMEOUT/CANCELLED/ERROR）、模型/effort、版本指纹、真实使用的资源策略；
- 原始 Codex 事件流或能独立验证关键原始事件的**完整脱敏切片**，带原始文件 SHA、行范围、逐行 SHA 和明确缺失标记；
- 每次真实 Submission Diff、提交保真结果、代码树哈希；
- 评测报告、JUnit、可信 Oracle 结论与必要命令回执；
- 单/多 Agent 委派、工作、回传的时间线（证据引用可回到原始记录）；
- 关键失败原因和限度报告；
- `SHA256SUMS` 与**离线 verifier**，不依赖正在运行的模型、网络或本机个人路径。

对没装入轻量包的原始重证据，列出 `NOT_INCLUDED`、原相对路径/可引用 ID、内容哈希和它具体支持的声明。**不能声称 Audit-Lite 自己能验证未包含的原始字节**；只能验证包中内容及对原始归档的可追溯指针。

### 4.3 可移植与保密

- 通过压缩、稳定文件排序和内容寻址去重处理重复证据；输出内容大小要有真实明细与缩减比例。**目标是几 MB 到数十 MB 的常规审计包，而不是以固定尺寸牺牲必要证据。**
- 任何原生事件 / stderr / 环境快照必须先脱敏；保持可审计的事件类型、时间、身份关联和来源哈希。不可在 Markdown、Manifest、日志里写入实际密钥、认证令牌或其摘要。
- ZIP 应拒绝路径穿越、重复条目、意外 symlink、恶意覆盖和不受控嵌套引用。
- `export`、`verify`、`inspect` 命令具有明确成功 / 失败退出码；**导出不触碰冻结核心文件和既有历史归档**。
- 生成 M1 原始三次 Pilot 的 Audit-Lite 示例，必须同时保留 `TIMEOUT/PASS/TIMEOUT` 和两个 `postmortem` 原样补丁结果。

### 4.4 必需的测试

正常导出、离线复核、单字节篡改、文件缺失、伪造 JUnit 与 Manifest 不一致、错误 Run 引用、脱敏、路径穿越、重复文件、跨平台相对路径、多次确定性输出（时刻字段处理说明）、包含异常和超时的完整导出。产物失败不应触发重跑或重写历史实验。

---

## 5. R3 — Episode D-v01 难度与运行开销先导校准

### 5.1 先定义评测对象与分母

至少建立两种真实的执行条件：

- **S：Codex Single-Agent**。只有主 Agent 调查、修改和提交；不得只是写一个“不要用 Subagent”的提示，而实际仍启动子 Agent。必须通过可验证的官方配置/日志核查没有 Child。
- **M：Codex Native Multi-Agent**。延续真实原生委派与子 Agent 自身活动的证据链，不用模拟角色。

两组必须使用相同 Episode D-v01 冻结公开 Issue / Tests / 基线、同一 Gateway 模型与推理配置、同一隐藏 Suite、提交规则、隔离等级、明确记录的资源条件。仅改变是否允许原生协作及执行任务所需的相关提示。记录不可完全匹配的差异。

### 5.2 运行设计

在 R1/R2 的门禁通过之后，用 `completion-aware` 完成**至少 3 次全新 Single-Agent Session + 3 次全新 Native Multi-Agent Session**的先导校准。尽量采用交错顺序（如 S/M/M/S/S/M）并记录其他宿主负载；不要拿仅有一次成功的 M1 历史运行充当本阶段新样本。

- 不设任意的**总 wall-clock 自动超时**，允许中转站缓慢但持续地完成任务。
- 以真实终态、人工明确取消、真实资源/安全违规或不可恢复故障作为终止依据。
- 运行期间记录 liveness、真实请求错误和阶段性证据；研究人员如决定取消，记录理由和时间、保留分母，不重置成重试后的成功。
- 记录每次是否达到 `turn.completed`、是否自然产生提交、是否进入 Evaluator、实际隐藏测试结果；保留必要时的独立 postmortem，但不能把 postmortem 升级为原自动 PASS。
- 由于没有固定时间上限，时间不再作为此组试验的硬性 FAIL 判据；仍需要报告端到端完成时长、请求量、Token 和错误分布，以及长尾耗时。不可把这一组成绩与此前 1200 秒有界 Pilot 的自动成功率直接合并比较。
- 如果组间有不同不可恢复 Provider 错误，应单独标记 `PROVIDER_FAILURE`，不得自动当作软件解题失败；同样不能悄悄剔除失败 Run 改变分母。

### 5.3 校准报告要分开的指标

| 指标 | 要求 |
|---|---|
| Task Correctness | 实际提交的 Hidden Tests、DB Oracle、恢复窗口完整性 |
| Runtime Completion | 是否真实完成 Session、完成所需墙钟时间 |
| Collaboration Closure | Child 启动、活动、回传、主 Agent 接收、是否因等待挂起 |
| Patch Readiness | 首次观察到有效补丁的时间；**无法证明其当时已通过隐藏测试则标记 UNVERIFIED** |
| Provider Performance | 请求首响应、流式耗时、429、重试、失败分布、不可归因的等待 |
| Resource Cost | 模型 Token（去重/防重复合计）、上游请求、峰值占用；实际货币账单若无证据则 UNAVAILABLE |
| Difficulty Signal | 成功率粗分布、修复路径差异、错误策略、公开信息泄露、疑似 ceiling effect |

**六次属于先导校准，不足以宣称统计显著性、Single/Multi 哪个一般更强，或任何经验治理收益。** 报告须提出后续正式实验的样本量和难度修订所需证据，而非臆造精确显著性。

### 5.4 运行 Gate

每次联网前证明原始源码与私有 Suite 指纹一致、公开输入未泄露答案、Gateway TLS 正常、Broker 隔离与 Operator Cancel 有效、Audit-Lite 导出可行、无无关重型运行挤占宿主资源；每次执行后验证进程清理和原始证据封存。若任何强制安全门禁失败，不得为满足 6 次数字而关闭隔离硬跑。

---

## 6. R4 — Episode D-v02 规格（只设计、审查，不编码）

在研究现有 D-v01 的公开 Issue、Buggy/Reference、28 项 Hidden Tests 以及三次真实 Agent 修复后，提出至少 **2 个实质不同的 v02 候选事故**，并选 1 个推荐方案形成完整规格。每个候选回答：

1. 新因果机制是什么？为什么不是简单将 Worker 数从 2 改成 8、增加 SQL 查询或换随机种子？
2. 与 A / D-v01 的历史策略关系是什么：何时正迁移、何时负迁移、何时证据不足需要调查？
3. 业务系统中有哪些真实可观测症状、信息缺口和排查途径？不能为了制造 VERIFY 而人为隐藏工程师原本可以合理查到的必要事实。
4. 哪些任务条件对 Participant 公开，哪些只在可信 Maintainer Private Gold Label 中？如何防止任务描述直接泄露根因？
5. 有哪些参考修复路径及合法替代方案？哪些错误策略和规避型补丁应该被拒绝？
6. Hidden Oracle 如何与具体候选实现解耦、又能覆盖 crash/retry / ledger / concurrency 等必要业务真值？
7. 哪些机制会导致 ceiling/floor effect？如何校准难度并收集独立证据？
8. 未来如何用相同任务进行纯无经验、普通 Memory、经验治理的公平比较（这里只写 Benchmark 协议，不开发治理）？

给出统一的 Task Card（Fault Mechanism、Execution Context、Evidence Condition、Experience Relation）、Public Issue 草案、Private Gold 条件结构、Reference vs Wrong Controls 设计、Oracle 设计、预期验收 Gate、风险与取舍。

**不可改写已验收 D-v01，也不把 v02 的设计状态伪装成已实现任务。**

---

## 7. 强制回归、失败规范与独立审计

在既有测试上做增量验证：

1. 保留 M1 当前 664 项测试的有效测试身份和断言，不因兼容修改删除或弱化它们；允许新增测试。涉及默认运行语义变动，写兼容性说明并验证旧模式。
2. 直接运行真实 `scripts/orderflow` 生命周期验证 Episode A、D 的 Buggy / Reference / alternative，确认既有 Oracle 与冻结 Suite 不变；B/C 保持 `NOT_IMPLEMENTED`。
3. 校验 Codex 的隔离、秘密不泄漏、Submission Fidelity、资源清理、真实 JSONL 解析；继续对 `CANCELLED`、`UPSTREAM_ERROR`、`RESOURCE_ERROR`、`NO_PATCH` 与实际任务 FAIL 分门别类。
4. 用测试覆盖异常停止后再次执行时的干净状态，避免资源泄漏、残留 Broker 或 Run 污染；必须证明并行状态索引不会错认别的 Run。
5. Export/Verify 不能自行证明历史真实性；每项关键声明要有原始证据与 SHA、实际运行命令/退出码，且由独立的 verifier 校验内容一致性。
6. 所有新实验用不可复用的新 Run ID；绝不因重试或人工提取而覆盖旧 Run。
7. 若不同实现路径出现 `RECOVERY_EVIDENCE_UNVERIFIED`，保留它是**观测证据不足**，不得偷偷升级为业务 FAIL 或 PASS；并在兼容性报告中列明通道边界。

只在完成所有能真实执行的测试后宣布 PASS。因环境限制无法执行的检查标记 `UNVERIFIED` 或 `BLOCKED`，不得用文档宣称通过。

---

## 8. 开发组织、交付物与里程碑 Gate

建议按 **R0 → R1 → R2 → R3 → R4** 顺序推进，但可使用 Codex 原生 Subagent 并行进行独立代码审查、Archive 分析和 D-v02 设计。**不要让子 Agent 同时修改同一共享源码**，主 Agent 负责整合与真实验收。每个 Gate 完成后将结果写入单独的阶段记录，后一个 Gate 不能掩盖前一个 Gate 的失败。

### 必须交付

- `M1_1_BASELINE_AND_FAILURE_HYPOTHESES.md`：实测超时层、原始 Pilot 时间线及改动范围；
- `docs/LONG_RUNNING_CODEX_POLICY.md`：两种运行策略、慢响应识别、Operator Cancel、风险与兼容性；
- 可运行的 completion-aware Runtime、Broker/collector 相应改动及自动测试；
- `docs/EVIDENCE_EXPORT_POLICY.md`：Full / Audit-Lite / Replay 权限与保留策略；
- `scripts/...` 下适当的导出与离线核验入口（名称由项目架构决定），相关单元与端到端测试；
- 至少一份基于 **M1 三次原始 Pilot** 的 Audit-Lite 包以及大小对比、离线校验结果；
- `M1_1_DIFFICULTY_CALIBRATION_REPORT.md`：六次新 Session 的真实原始状态、请求与用量、任务与协作评价；
- `docs/EPISODE_D_V02_DESIGN.md` 与独立自审意见（至少两候选、一个推荐）；
- `M1_1_VALIDATION_REPORT.md`、`M1_1_REMAINING_ISSUES.md`、`M1_1_EVIDENCE_INDEX.json`：命令、退出码、SHA、动态结果、前后指纹、未完成条件。

### Gate 定义

| Gate | PASS 含义 | 不得混淆 |
|---|---|---|
| R0 | 基线、限制与原始失败确有证据 | 不是开发完成 |
| R1 | 无总 wall-clock 的自然完成模式真实运行，慢流不被武断杀死，取消/故障可正确清理 | 不代表不会发生 Gateway 故障 |
| R2 | 轻量包可以独立校验其所含证据，并能指向未提供的完整归档；体积明显下降 | 不能将不在包内的文件称为已独立验证 |
| R3 | S/M 各 ≥3 个真实新 Session、条件有据可比、原始成绩完整保留 | 不代表六次已具统计显著性 |
| R4 | D-v02 设计经工程与研究双 Gate 评审，尚未实现 | 不能将设计 PASS 当 Episode 运行 PASS |

### 最终总体状态

- **PASS**：R1/R2 的动态 Gate 通过，R3 的实际运行和报告完成，R4 有合格设计与可追溯意见，旧回归保持；限本阶段已声明的安全与统计范围。
- **CONDITIONAL PASS**：核心运行机制真实实现，但部分正式实验、兼容性或隔离门禁尚存在明确的未验证边界；不得隐瞒。
- **FAIL**：提交/评测可信度回归、私有信息泄漏、篡改历史数据、用伪造运行或参考补丁冒充盲测。

全部完成后**停止在 M1.1**。禁止自发进入 D-v02 编码、Episode B/C、GraphSwarm 或正式 G0–G3 实验。

---

## 9. 给主 Agent 的执行要求

这是认真提升 Benchmark 质量的工程任务，不是追求一个漂亮的 PASS 表格：

- **先找到并验证失败层，再改策略。** 不要直接把 1200 秒改成 7200 秒就宣布解决问题。
- **尊重慢速 Gateway。** 有真实工作和响应证据时应允许它完成，不要仅凭 wall-clock 杀死任务。
- **可观察、可取消、可清理。** 没有固定截止时间仍应有明确的可信运行状态和故障处理。
- **以证据而不是体量取胜。** 保留 Full Archive，输出真正便于别人阅读和核查的 Lite 包。
- **困难要来自工程决策。** 难度校准要拆开软件正确性与 Agent 协作开销，不用耗时长来证明题目难。
- **不得越界开发。** 严格停止在 M1.1。
