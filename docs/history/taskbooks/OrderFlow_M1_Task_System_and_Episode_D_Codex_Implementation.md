# OrderFlow Incident Lab — M1 Codex Implementation Task

**任务名称：Task System Design & Episode D — Multi-Worker Incident Benchmark**  
**基线：Phase 3.5 / Roadmap v1.0**  
**任务性质：正式开发 + 独立动态验收；不是单纯设计，也不是 Experience Governance 开发。**  
**最终交付：高标准任务体系规范 + 真正可执行的 Episode D + M1 原始验收证据。**

> 本轮的价值不是给 OrderFlow 增加一道“多进程测试”，而是确立可复用的任务设计方法，并用 Episode D 证明这套方法能承载真实的工程事故、合法的多种修复与跨环境策略适用性差异。

---

## 0. 开始前：读取基线并保护历史成果

在现有 `orderflow_incident_lab` 仓库内执行。先确认当前分支、工作树和提交；以**本机真实 Git 状态**为准，不假设文档描述的提交就是当前 HEAD。

必须优先阅读：

- `OrderFlow_Benchmark_Development_Roadmap_v1.0.md`（若位于 `benchmark_roadmap/`，在仓库内定位；本任务以其中 M1、M3/M4 的接口边界为准）
- `OrderFlow_Incident_Lab_Benchmark_Design_Spec_v1.0.md`
- `README.md`、`docs/ARCHITECTURE.md`、`docs/EPISODE_A.md`、`docs/EPISODE_REGISTRY.md`
- `PHASE3_5_VALIDATION_REPORT.md` 及对应可信验收归档
- `benchmark/registry.py`、`benchmark/runner.py`、`benchmark/manifest.py`、`benchmark/submission.py`
- `benchmark/episodes/episode_a.py`、`evaluator/worker.py`、`evaluator/suites.py`、`evaluator/oracle.py`
- `integrations/` 和现有 Codex Runtime/隔离配置

已知基线：Phase 3.5 报告为 **CONDITIONAL PASS**；历史开发者测试 **499/499 PASS**；三次联网挑战自动闭环 **2/3**，另一次超时补丁离线通过。提交保真已修复，但完全敌对环境安全、CPU/cgroup 和历史不可变性仍有限制。A 与 SMOKE 已实现；B/C/D 目前尚未实现；Experience 为 `DISABLED`。

基线校验要求：

1. 记录起始 Git commit、dirty files、Python/SQLite、Codex 配置标识、相关文件摘要；保留 Phase 3.5 原始报告与 Runs，禁止覆盖、删除或回填历史证据。
2. 在开发前执行一次可运行的现有核心回归；若环境不满足，记为 BLOCKED 并写明原因，**不得把未执行当作 PASS**。
3. 新建独立开发分支/工作区与新的 M1 验收归档。文档中曾出现核心冻结提交 `cee9bba`、文档提交 `beba4fb`，只把它们作为历史参考，必须以当前真实仓库状态核实。
4. 不允许将 Gateway 密钥、Codex 身份材料、隐藏测试或私有答案复制到 Participant 工作区、日志或 Git。

---

## 1. 本轮范围与成功定义

### 1.1 必须交付

**A. Task System Blueprint（任务体系规范）**

形成一套可复用、可落地的任务设计和准入规范，至少涵盖：

- 同一 OrderFlow Business World 中 A/B/C/D 的真实业务责任边界与跨模块不变量；
- Task Family、Scenario、Variant、Fault Mechanism、Execution Context、Evidence Condition、Experience Relation 的明确区分；
- Engineering Truth 与 Decision Reference 两种独立真值；
- Public / Private 数据和 Agent 可见信息的规则；
- 每个正式任务的交付包、版本/指纹、重置、难度校准与 Engineering / Research 双 Gate；
- 后续 A/B/C/D 变体的可复用接口，不提前实现 B/C。

**B. Episode D（首个高标准样板）**

在 Phase 3.5 已有 Runner / Evaluator / Submission / Sandbox / Codex Adapter 上，真正实现 Episode D：多个**独立操作系统进程**以共享持久化 SQLite 为状态源，在扩容、并发、异常退出和恢复过程中出现可重现的库存一致性事故。

**C. Evidence-based Validation（真实验收）**

通过 Buggy、Reference、合法替代修复、已知错误修复、独立 Oracle、重复初始化、旧场景回归以及真实 Codex 盲测建立完整证据链。

### 1.2 明确不做

本轮**不实现** Episode B/C、GraphSwarm Core、FalkorDB、MCP、WHEN/WHY 决策引擎、经验反馈算法、G0–G3 正式对照与论文式统计显著性结论；不重新开发 Agent Orchestrator，不为抽象而大改现有 Runner，不建设云级集群或生产级支付系统。

Episode D 在本轮**允许提供供未来评测使用的受控经验素材和私有参考标签**，但不向 Codex Participant 自动灌入经验，也不实现经验治理机制。不要把离线人工策略可用性检查冒充实际 Agent 的经验继承效果。

---

## 2. 先完成高质量 Task System Design

**先写设计并完成自审，再编码 Episode D；不需要停下来等待人工二次批准，可在报告中保留设计决策。**

编写 `docs/TASK_SYSTEM_DESIGN.md`，至少包含：

1. **统一业务世界**：订单、库存、支付、事件、Worker 拓扑之间的关系；明确当前已经有的业务代码与未来 B/C 扩展边界，不虚构已实现服务。
2. **任务分类模型**：
   - `TaskFamily`：A Inventory / B Payment / C Event / D Distributed；
   - `TaskVariant`：真正不同的故障机理、部署条件或证据条件，不把改线程数当作新任务；
   - `FaultMechanism`：具体因果故障；
   - `ExecutionContext`：进程/线程数量、共享状态、持久化、崩溃/恢复；
   - `EvidenceCondition`：公开 Issue 能观察到的事实、未知信息、干扰信息；
   - `ExperienceRelation`：策略在环境中的适用、失效或证据不足，以及真实来源。
3. **两层真值**：
   - Engineering Truth：库存守恒、成功订单、预留账本、幂等、持久化/恢复等由宿主 Oracle 判定；
   - Decision Reference：某个具体历史策略在具体上下文中的适用性，由维护者私有审查资料记录，不得从任务结果倒推替代。
4. **Episode Package 合同**：Public Manifest/Issue/Test、Fixture、Fault Variant、Reset Recipe、Private Tests/Oracle、Buggy、Reference、Alternative Fixes、Known-Bad Mutants、指纹、重复性报告、私有策略标签、运行归档。
5. **任务关系说明**：A→D 的条件性正迁移与负迁移；未来 A→B、B→C 等只做设计占位，不宣称已验证。
6. **任务准入 Gate**：Engineering Quality Gate 和 Research Quality Gate，列可证伪的验收条件，不以测试数量或某次 PASS 替代。
7. **难度校准计划**：区分软件难度、诊断难度、经验判断难度；记录 Pilot 成功率、耗时、Tokens、独立 Trial，不把单次成功当稳定性结论。

文档需**明确标记 `CURRENT / IMPLEMENTED`、`PLANNED`、`REFERENCE-ONLY`**，避免将未来数据契约写成实际可用接口。

单独编写 `docs/TASK_ADMISSION_GATES.md`，给出逐项检查表，后续 B/C/Variant 可以复用；不要将评测标准硬编码到 Participant 可见文件。

---

## 3. Episode D：真实工程事故设计

### 3.1 场景与公开 Issue

OrderFlow 由原先单进程服务扩展为多个相互独立的 Worker，各 Worker 访问同一份持久化库存数据库。服务在扩容、并发下出现库存与订单/预留账本不一致的真实故障；部分请求伴随超时、重试或 Worker 退出。

公开 Issue **只能提供可观察症状、业务约束和必要诊断方式**。禁止在 Participant 可见标题、Manifest、TASK、公开测试和提示中直接出现“RLock 无法跨进程”“使用数据库原子更新”“负迁移标准答案”等根因或私有标签。当前 D 的公开 `research_role` 等字段应检查是否泄漏研究预期，必要时改为中性、真实的任务描述。确保维护者研究资料留在可信宿主侧。

### 3.2 故障必须真实且有独立机制

必须构建真正可能发生在扩容场景的状态竞争，例如：单 Worker 内曾依赖局部互斥保护的读-改-写操作，在多个不同 PID 的 Worker 之间无法形成互斥；不同 Worker 根据过期库存计算并写入不正确状态。

但**不能仅把 Episode A 的旧测试换为 `multiprocessing` 并称为 D**；应说明 D 的不同环境前提、失效机制、故障传播路径和新的恢复约束。

错误结果必须由实际业务代码、SQLite 事务边界和真实并发交错产生。禁止伪造库存、故意修改断言、直接抛异常制造 FAIL 或为了叙事禁止合法修复。

### 3.3 真实多进程执行拓扑

当前 `evaluator/worker.py` 的 `ThreadPoolExecutor` 只证明单 Worker 多线程。D 需要由**可信 Evaluator/Supervisor** 调度不少于 2 个真正独立 OS Worker Process（至少验证 2 和 4 Worker），每个进程装载候选业务代码，访问**同一份实际 SQLite 数据库文件**，Worker 之间没有共享的 Python `RLock` 对象。

实施要求：

- 尽量扩展现有通用 RPC 与 Episode Registry，允许多个受限 Candidate Worker 共享受控数据库；不要把预期答案写入 Worker，也不要在可信宿主中直接 import Candidate 业务模块。
- 由可信宿主控制启动、同步、异常退出、重新启动和结果收集；保留各 PID、数据库文件身份、操作区间与退出状态的可核验证据。不能由单个服务进程轮流代理请求冒充多进程。
- 并发竞争需要受控调度/跨进程同步点及有界时间门禁，不能只依赖 `sleep()`、运气或主机负载；**同步点不得强迫正确的事务/锁方案死锁**，更不能向 Candidate 暴露 Hidden Oracle。必要时使用独立的进程间同步控制通道，但不能让它参与业务一致性判定。
- SQLite `busy`、回滚、WAL、事务锁等待及连接生命周期都要根据业务语义处理。不能将正确方案偶发的环境锁争用混淆成业务不变量错误；应分别报告工具/环境失败与业务失败。
- 可靠清理全部子进程、连接、临时文件和 FD；一次评测失败不得污染下一 Run。
- 不改变已验证的 Participant 私有文件、网络、Broker 认证与提交保真边界。若 Sandbox、Candidate 挂载共享数据库方式有变化，必须重新执行对应隔离回归。

### 3.4 业务真值及反作弊

最少要求在共享数据库下验证：

- 库存守恒：初始化库存 = 可用库存 + 有效预留/消耗（按项目已有账本语义精确定义）；
- 订单与预留账本一一对应且无重复/丢失；
- 同一订单 ID 的重试具备明确且可审计的幂等行为；
- 多 Worker 正在**实际执行有效写入**，禁止通过仅启一个 Worker、拒绝大多数请求、关闭并发或写死库存结果来骗取 PASS；
- Worker 异常退出、重启与后续请求不破坏持久化不变量；
- 全部符合公开 API / 业务语义，不能强制只接受作者指定的修复技巧。

可信数据库 Oracle 必须在 Candidate 之外直接查询 SQLite 原始状态；不要仅调用候选 `audit()`。独立验证成功响应和持久化提交一致；候选异常、进程被杀、评测错误、超时应分别归类。

### 3.5 参考正确修复与多种策略

至少提供：

- **Buggy**：单进程场景可能表现正常，但跨进程竞争真实失败；
- **Reference**：依赖共享持久化状态的正确原子一致性方案，例如合适的 SQL 条件更新/事务；
- **Alternative Valid Fix**：**机制不同**、但同样满足业务约束的正确实现，例如合理的 `BEGIN IMMEDIATE` 事务保护与安全重试；不能只做语法变化；
- **Known-Bad Mutant 1**：仅依赖进程内 `RLock` 的修复，能够显示其旧环境成功边界和 D 中的跨进程不足；
- **Known-Bad Mutant 2+**：至少另一种具有现实意义的错误策略（如分离检查与更新、异常恢复时遗漏持久状态等），必须由 Oracle 识别。

参考修复与替代修复可使用不同并发控制机制；评测不得要求提交保留特定锁/函数实现，不得通过人为性能门槛排斥本来正确且满足公开 SLA 的方案。

特别注意**真实来源**：A 中 `RLock` 成功属于维护者验证的替代修复证据；此前 Codex 真正自主完成的 A 修复主要采用数据库条件原子更新。禁止把 RLock 称为真实 Codex Agent 自主发现的策略。保留源 Run/测试报告/来源性质及对应环境限制。

---

## 4. 为未来经验评测准备私有参考，不实现治理系统

交付一份版本化且只在维护者可信侧存在的 `evaluator/private_labels/episode_d_applicability.json`（可依现有结构调整路径），至少包括：

- 原子 DB 更新策略，在受控共享 DB 语义及特定假设下的适用边界；
- 单进程 RLock 策略，在单进程共享对象前提下的成功证据、在独立进程拓扑下的失败证据；
- 拓扑或共享状态证据不足时 `VERIFY` 的信息条件（可以先是设计级受控标签，不强制本轮实现第三个正式 Episode 变体）；
- 适用性决策标签、依据、证据引用、标签版本、审查者标记、`natural / maintainer_seed / synthetic` 来源。

这些标签属于 **Benchmark 私有参考数据**，不是 `ExperienceAdapter`，也不是 GraphSwarm 算法。绝不向 Agent 泄漏“答案”。本轮只验证对应策略在各环境中确实有不同可观察结果；不报告任何真实 Experience Governance 的提升。

编写 `docs/EPISODE_D.md`（公开任务描述与维护者设计分析应拆开文件；发布到 Participant 的文档必须严格受限）及 `docs/TASK_RELATIONS.md`（维护者侧关系设计）。

---

## 5. 接入现有执行框架，保持向后兼容

- 在现有 Episode Registry 注册 D，并接入独立 Fixture、Public Tests、Private Suite、Oracle、Reset、Report/Fingerprints；原则上不增加 `if episode == "D"` 的核心 Runner 特例，拓扑差异通过可复用的执行策略/注册信息承载。
- 实现 D 的 `prepare/evaluate/reset/report`，`run-codex --episode D` 在完成安全检查后实际可调用；保留 Manual Submission 路径。
- D 必须复用 Phase 3.5 的 **Baseline / Patch / Expected / Applied SHA256 与逐文件提交保真验证**；错误提交必须在进入 Hidden Evaluator 前拒绝。
- 所有场景互不污染；SMOKE 与 A 完整保留，B/C 继续 `PLANNED / NOT_IMPLEMENTED`；Experience 继续 `DISABLED`。
- D 的 Manifest、Private Manifest、Suite、Fixture 等版本必须按真实改动更新，不可复用旧 Episode 或旧报告指纹。
- 注意历史 499 项测试中可能含有“D 未实现”的合法旧断言：D 转为已实现后应**明确记录语义迁移**，保留原测试文件与历史归档；可按版本更新相关当前态断言并提供新测试，不得偷偷删除测试、批量跳过或降低 A/SMOKE/Phase 3.5 的覆盖标准。最终报告需提供旧测试身份和行为迁移表，不得机械要求过时的 `D=NOT_IMPLEMENTED` 断言仍然成立。

---

## 6. 分层验收矩阵：任何一个 Gate 都不能靠口头 PASS

### Gate A — 任务体系设计质量

`TASK_SYSTEM_DESIGN.md` 和任务准入规范经过自审；明确区分任务家族、故障变体、执行上下文、公开证据、私有真值和迁移关系。D 的私有参考可以用真实证据支持，不能在 Participant 包中泄漏。

### Gate B — 多进程故障真实性

- 2 Worker 与 4 Worker 均能证明不同 PID 同时请求**同一数据库**，有真实写入；提供可信宿主侧 PID、操作时间和共享 DB 身份日志。
- Buggy 在独立初始化下至少 **10/10 稳定 FAIL**，失败确因业务不变量不满足；不能只用异常/启动失败冒充缺陷。
- 增加 Worker 崩溃/重启、请求重试、竞争交错、多商品或不同库存规模等独立测试；故障诱发机制可受控复现，不能只靠长时间随机施压。

### Gate C — 多解正确性与评测判别力

- Reference 至少 **10/10 PASS**；Alternate Valid Fix 至少 **10/10 PASS**；在 2/4 Worker 和关键恢复条件下均满足业务不变量。
- 进程内锁-only 及至少另一种错误策略在对应错误暴露条件下被可靠检出，记录失败原因和真实状态证据。
- 独立 Oracle 直接验证库存、订单与持久化账本；JUnit 测试集合完整性、必要测试数、版本指纹与测试退出码均一致。
- 人为降低并发、拒绝合理请求、改写测试/Oracle、硬编码检测样例等明显绕过策略应被识别，而不是 PASS。

### Gate D — 原有框架不回归

- 执行完整当前开发者回归，正确披露 PASS/FAIL/ERROR/SKIP 数；不得把历史 499 项“D=PLANNED”行为变化掩盖为无关失败。
- A：Buggy 必须 FAIL；Reference 和已验证替代修复必须 PASS；SMOKE 原行为不变。
- Phase 3.5 的 Submission Fidelity、Broker、隔离、网络与资源门禁有可追溯回归；新增多进程候选拓扑不得开辟未受控文件/网络路径。
- B/C 继续 NOT_IMPLEMENTED；若工作树原有无关变更，予以保护并在报告单独说明。

### Gate E — 真正 Agent 盲测及难度先导校准

经过私有答案泄漏检查后，使用**独立新 Session** 的真实 Codex 原生 Multi-Agent 挑战 Episode D，记录模型/Provider、思考强度、预算、提示输入摘要、Subagent 证据、Patch/Tree SHA256、Evaluator Outcome。

建议先执行 **3 次独立 Pilot**，在现有用户已授权的 Gateway 与预算门禁下进行；如模型或认证实际不可用，按 BLOCKED 如实汇报，不伪造联网成绩。

- 目标是测量 D 的可解性、运行时间、成本与任务判别力，而**不是要求 Codex 三次都必须修好**。
- 报告 Runtime 结果、自动闭环结果、隐藏测试结果分别计算；TIMEOUT 后离线复测不能改写原 Run。
- 如果新 Codex 三次非常轻松通过，记录可能的天花板效应；如果全部失败，检查任务描述、环境可解性与预算是否合理。不要为了刻意降低通过率而破坏真实性或临时更改同一组正式冻结测试。
- 这是先导校准，**不能**将 3 次 Pilot 宣称为统计有效的成功率比较或证明多 Agent 优越。

### Gate F — 研究边界真实性

- 正向适用与负迁移证据都来自可复核的策略实际运行；信息不足标签有明确证据条件。
- 能独立报告 `Engineering Outcome` 与 `Strategy Applicability Reference`；两者不混分。
- Experience 始终 `DISABLED`；未执行 G0/G1/G2/G3 治理实验，不声称经验治理改善了 Agent 决策。

---

## 7. 应保留的验收命令形态

以下是**目标行为示意**，具体有效参数先根据当前 CLI 帮助核对；不允许把示例命令直接当作已验证执行结果。

```bash
# 旧场景回归
scripts/orderflow evaluate --episode A
scripts/orderflow evaluate --episode A --submission evaluator/reference_patches/A-v01.diff

# 新 D：Buggy 预期 FAIL，Reference 预期 PASS
scripts/orderflow evaluate --episode D
scripts/orderflow evaluate --episode D --submission evaluator/reference_patches/D-v01.diff

# 真实 Participant 盲测（需通过隔离和 Secret 门禁）
scripts/orderflow run-codex --episode D --agent-timeout 1200
```

如为 D 添加 `--variant`、并发拓扑或其他参数，应提供可发现的 `--help`、合法参数校验、默认值与稳定 JSON Report；不以专有脚本替代正常 CLI 生命周期。

---

## 8. 交付结构、证据归档与报告

最终至少交付：

1. `docs/TASK_SYSTEM_DESIGN.md` — 顶层任务体系，当前/规划严格区分。
2. `docs/TASK_ADMISSION_GATES.md` — Engineering / Research 双门禁与审查表。
3. `docs/EPISODE_D.md` — 设计说明、事故语义、并发拓扑、公开/私有边界（公开版 Issue 独立存储）。
4. `docs/TASK_RELATIONS.md` — A→D 经验关系与未来家族关系说明，注明经验来源。
5. D 的 Public Manifest/Issue/Public Tests 与独立 Private Suite、Oracle、Fixture、Fault、Reference、Alternative、Known-Bad Mutants。
6. 通用多 Worker 可信调度扩展及与原 Registry/Runner/CLI/Codex Adapter 的接入。
7. `scripts/reproduce_episode_d.py`（或等价可复现入口）、新开发者/集成测试。
8. 版本化的私有 `episode_d_applicability` 参考与真实来源引用。
9. `M1_EPISODE_D_VALIDATION_REPORT.md`、`M1_TASK_SYSTEM_DESIGN_REVIEW.md`、独立归档的结构化数据：命令、退出码、Run ID、JUnit、Oracle、PID/共享 DB/并发证据、10 轮正反与替代修复、三次 Pilot 的原始 Codex 事件及报告、指纹、已知限制。

不得覆盖 Phase 1–3.5 的历史 Runs 或假装旧记录在新代码下重新运行过；新增结果有新 Run ID、版本和哈希。密钥只在可信宿主持有，日志归档前脱敏。

报告结论应拆分为：

- `Task System Design`: PASS / CONDITIONAL PASS / FAIL
- `Episode D Engineering Gate`: PASS / CONDITIONAL PASS / FAIL
- `Episode D Research Gate`: PASS / CONDITIONAL PASS / FAIL
- `Agent Pilot`: 实际结果和不确定性（不强制成功）
- `Phase M1 Overall`: PASS / CONDITIONAL PASS / FAIL

**最重要的完成标准：Episode D 是一次真实且可解的工程事故；旧环境的成功策略在新环境中的适用性具有可验证差异；评测对合法多解公平、对错误方案敏感；并且这一切是在没有经验治理层的情况下由独立 Benchmark 提供的。**

---

## 9. Codex 开发方法与终止条件

- 可以使用 Codex 原生 Subagent 分工审查架构、多进程复现、Oracle、评测强度和隔离安全；主 Agent 负责最终集成。不得伪造 Subagent 或把开发 Agent 的成果混入 Participant 盲测证据。
- 每完成一个功能组立即跑对应最小真实测试，最终跑全部有效回归与独立重复验证；按最小可信改动修复，不做不必要的全仓重构。
- 如果 Runner 的现有架构不能安全支撑多 Worker，可以进行必要、可复用的拓扑抽象；必须说明为何改动不可避免、影响哪些旧接口和如何回归验证。
- 遇到重大设计冲突，不要降低 Gate；记录风险、失败命令和原始日志，采取最小合理实现或标记 CONDITIONAL/FAIL。
- 完成 M1 后停止：**不继续实现 Episode B/C、GraphSwarm Core、FalkorDB、经验治理算法或 G0–G3 正式研究。**

请最终反馈：真正交付的模块、关键设计决定、实际测试统计、Buggy/Reference/Alternatives/Mutants 重复结果、3 次 Codex 盲测的真实结果、剩余边界及所有核心证据路径。
