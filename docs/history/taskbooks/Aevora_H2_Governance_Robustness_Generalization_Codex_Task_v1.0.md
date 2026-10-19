# Aevora H2 — Experience Governance Robustness & Generalization

> **版本**：v1.0 · **状态**：下一轮正式开发任务指令 · **日期**：2026-10-11  
> **现行项目名称**：Aevora；GraphSwarm 仅为历史工作名  
> **依赖基线**：Aevora H1 v1.1，当前结论 **CONDITIONAL PASS**  
> **本轮性质**：真实工程实现、部署与验证；**不是**仅进行设计审查或撰写文档  
> **优先级**：H1 可复现性与安全/可靠性 → 经验治理鲁棒性 → 独立新场景 → 原生 Agent 端到端复验  
> **执行策略**：H2-G0 → G1 → G2 → G3；每个 Gate 独立验收、提交证据；完成 H2 后停止。

## 0. 任务授权与唯一目标

从现有本机工作树、已实现系统和真实历史证据出发，继续开发 **Aevora**，实现并检验 **Experience Governance Robustness & Generalization**。

**H1 已经证明**：真实 FalkorDB → WHEN/WHY → 原生 Codex MCP → 独立 OrderFlow Outcome → Trusted Feedback → 不同 Session 再查询的端到端闭环可以运行。本轮**不重新发明这个闭环**。

**H2 必须进一步证明**：

1. 该闭环在最终源码版本上能从干净环境重建、可控恢复，并守住关键授权与资料隔离边界。
2. WHEN/WHY/FEEDBACK 在证据缺失、证据冲突、版本更新、未知前提和不适用场景中，能产生由真实图谱支持的有据判断；不把任务 PASS 直接转化为经验因果收益。
3. Aevora 能面对 **H1 以外的真实挑战场景**运行，而不是在 Episode A/D-v01 的已知条件上过拟合。
4. 至少完成一次全新原生 Codex Challenge 的实际工具调用、独立评测、可信结果入图谱、另一全新 Session 再查询；所有失败和异常同样记账。

**严禁**：Mock FalkorDB 冒充真实图、静态 JSON/题号查表冒充治理、提前向 Participant 泄露参考补丁或 Hidden Oracle、事后补写 MCP 工具事件、人工替换 Agent 提交、将真实失败样本挑掉、将 UNKNOWN 归因编造为正向收益。

## 1. 冻结的历史基线与名称边界

### 1.1 必须先核查、不可随意改写的事实

以本机 Git、源码、真实命令和封存报告为最终权威；下列是现有**历史报告中的基线**，不是本轮重新跑出的结果：

- OrderFlow Phase 1–3、Phase 3.5、M1、M1.1 已完成历史验收；Episode A 14 项、D-v01 28 项隐藏测试。
- H1 总结论为 **CONDITIONAL PASS**；FalkorDB/WHEN/WHY/Codex MCP/Trusted Feedback/A→D 闭环具备成功运行记录，Security 为 **PARTIAL**。
- H1 最终开发测试报告为 **1214/1214 PASS**；原 856 个测试身份和历史任务真值保留。
- 原生 H1 D Challenge Run `5089297e-39e7-4bd5-8b87-cbc7e21de022`：报告称 3 名 Codex 原生子 Agent 完成，Agent 原始提交通过 28/28 Hidden、宿主 DB Oracle 36/36；原始提交 SHA256 为 `274117054125ab84424d024bab6e2cae4ffbcae18d1e4f8066e014a08866d9a6`。
- 不同只读 Session Run `4a141343-0714-4992-a0cf-119b61cff121`：报告称读取到了新的 `OBSERVED_OUTCOME`；Adapter 的 `ERROR/NO_PATCH` 与 `NOT_EXECUTED` 事实必须保留。
- H1 的 AOF 保留数据隔离回放曾发生 **SIGSEGV / exit 139**，因此现有可信结论仅限于已经验证的 RDB SAVE 与正常重启路径；断电、未快照尾部恢复仍 **UNVERIFIED**。
- 原生联网闭环后存在 Broker 清理与复现入口的**后续修复版本**，其测试成绩不可冒充原始联网挑战的成绩。
- H1 Full Archive、Audit-Lite、原始事件、Run IDs、旧证据及 SHA256 原封保留。H1 Audit-Lite SHA256：`d38db23087f702b5f5320428b5e622a56de7aa2eacad25ad4ed8373e0bc4708e`。

优先阅读并定位实际文件：

- `Aevora_H1_Experience_Accountability_EndToEnd_Codex_Task_v1.1.md`、`Aevora_Project_Context_Handoff_2026-10-11.md`（能找到则读，若缺失注明）。
- `orderflow_incident_lab/AEVORA_H1_VALIDATION_REPORT.md`
- `orderflow_incident_lab/AEVORA_H1_DECISION_TRACE_REPORT.md`
- `orderflow_incident_lab/AEVORA_H1_LIMITATIONS.md`
- `orderflow_incident_lab/AEVORA_H1_TRACEABILITY_MATRIX.csv`
- `orderflow_incident_lab/aevora_validation/audit_exports/.../AEVORA_H1_RELEASE_REPORT.md` 与对应真实 Full Archive / Audit-Lite。
- 现有 `aevora/` 源码、Graph Schema、MCP 配置、OrderFlow Runner/Adapter/Evaluator、D-v02 静态规范和历史路线图。

如果文件位置与上述不同，**搜索本机真实路径**，不要假装文件存在；如不可获取，报告缺口及影响。

### 1.2 不变的职责边界

| 层次 | 固定职责 | 本轮禁区 |
|---|---|---|
| Codex Native Multi-Agent | 独立调查、策略选择、提交真实补丁 | 不自研替代 Planner/Orchestrator |
| Aevora Agent Integration Layer | MCP 查询、证据展示、Decision 记录；可信桥接 | 不向 Participant 提供管理员 Cypher 或可信 Outcome 写入权 |
| Aevora Core | WHEN/WHY、Provenance、反馈、Revision/Conflict 治理 | 不按 Episode ID 写死答案 |
| FalkorDB | 真实持久化图谱、多跳查询与证据路径 | 不退化为 JSON 查表或可视化摆设 |
| OrderFlow Incident Lab | 独立业务任务、Runner、Sandbox、Submission、Hidden Oracle | 不为提高 Aevora 成绩篡改原有真值 |

新增正式资产统一采用 **Aevora** / `aevora` / `AEVORA_`，但不能批量改写历史 GraphSwarm 路径、证据及哈希。OrderFlow/FalkorDB 保持独立命名。

## 2. H2-G0 — H1 Release Hardening、可复现与安全

**目标**：使 H1 条件通过后的源码成为可独立复现、可恢复、可审计的 H2 基线；不把历史联网成功错误计入后续修复版。

### G0.1 版本与兼容性封存

1. 只读审查工作树状态、分支、Commit、dirty diff、依赖、Docker 镜像 digest/版本、Codex CLI、MCP 实现、Provider/Gateway 配置和图谱 Schema/版本；记录 `H1-live` 与 `H1-post-live-fix` 的源码边界。
2. 在不覆盖已有状态的前提下建立 H2 隔离工作分支/工作树；为可复现源码生成明确的 Commit/Tag 或 source tree hash。若缺失历史 Commit，明确说明，不伪造历史 Tag。
3. 新增变更保持 OrderFlow A/D-v01 的旧接口、原始 856 身份、历史真值、Run 与 SHA256 不变。不得 force-push；不得提交密钥、原始敏感日志及数据库管理员口令。
4. 提供从干净 checkout（或全新可验证工作树）到服务启动、Schema 检查、回归测试、最小真实查询的可执行复现入口；不能依赖维护者个人缓存或现存容器的隐性状态。

### G0.2 数据可靠性与恢复

1. **保留现有已验证 RDB 路径**；先在隔离副本中重现实测 AOF 问题，固定触发条件/版本/栈及失败记录；若需要，查验上游已支持的修复版本，但**不得让修 AOF 的工作无期限阻塞 H2**。
2. 提供明确的 RDB checkpoint/backup/restore 流程：快照标识、图谱版本、文件哈希、备份原子化或一致性边界、恢复后的证据链/节点关系核验。备份应避免把敏感内容放入 Agent 工作区。
3. 在隔离环境做故障注入：正常 SAVE→重启、快照后新增未保存反馈→异常停止→恢复、损坏备份拒绝、重复恢复/重复 Outcome、恢复后新 Session 查询。明确说明 checkpoint 之外尾部数据可能丢失时的状态、审计与 RPO 边界；**禁止声称未验证的零数据丢失或断电可靠性**。
4. 不允许在实验中破坏生产/主机上当前唯一的 FalkorDB 数据卷；为所有破坏性测试使用隔离 Compose project、临时 Volume 和独立端口。

### G0.3 授权、隔离及故障关闭

1. 实际检验 per-run 最小授权、过期/撤销、跨 Run 重放、越权调用、错误身份、工具断连、FalkorDB 断连、恶意上下文/提示注入文本、不可信 `record_decision` 与可信 `VerifiedOutcome` 隔离。
2. Participant 不得读管理员凭据、完整历史私有文件、隐藏测试、参考补丁、Graph 管理接口或任意 Cypher；拒绝访问必须有原始事件与负面测试。
3. 核对 Gateway/Broker 生命周期和清理路径，分类 `ERROR / TIMEOUT / CANCELLED / PROVIDER_ERROR / NO_PATCH`，避免假 PASS；仍采用 **completion-aware**，不得因任意固定总 wall-clock 超时中止正常活跃的慢 Gateway，保留资源、取消和不可恢复错误防护。
4. 共享内核安全隔离若不能得到敌对级证明，明确保留 **PARTIAL**，不因常规单元测试而升级为无条件 PASS。

**Gate H2-G0 PASS 的最低证据**：干净环境重建步骤真实执行；最终源代码版本至少完成真实 FalkorDB/MCP 基线复现与核心回归；隔离 RDB 恢复/失效测试可复核；授权/越权/重放/断连均有记录；任何 AOF 或共享内核剩余限制逐项列出。若计划外部真实新 Codex 试验，可在 G3 集中执行，但不能在 G0 将旧联网 Run 当作最终版本的新 Run。

## 3. H2-G1 — Advanced Experience Governance

**目标**：在真实 FalkorDB 上拓展经验判断的鲁棒性，重点治理 **Evidence Conflict / Missing Premises / Revision / Provenance / Staleness**；不以更复杂的硬编码替代真实图谱决策。

### G1.1 基于现有核心增量设计，不无理由推倒重来

- 先审计 H1 `ExperienceRevision`、Evidence、WHEN/WHY、Feedback、Snapshot/Decision ID 与图谱 Schema 的既有能力。能复用则复用；对无法表达的新需求提出最小增量模型和迁移。
- 严格区分已知 `true`、已知 `false`、**unknown/not_observed**、证据缺失与证据彼此冲突；不得把 unknown 当 false，也不得单凭新证据“较新”就直接作因果优先级判决。
- 来源类型必须保留 `natural_agent_run`、`maintainer_seed`、`synthetic_or_test_fixture`；不得将受控 Fixture 计入自然 Agent 结果。
- Revision 必须追加而非覆盖，保留生效条件、来源、支持/反例、决策版本、查询快照/版本和前后关联；必要时补充 Supersedes/Conflicts/Scope 等关系，版本与 Schema 变更要有可执行迁移和反向兼容验证。

### G1.2 必测情形（同一引擎，依赖真实图谱与当前事实）

1. **正例**：满足全部重要前提且可追溯支持链，给出有条件 `APPLY`。
2. **显式反例**：已确认违反必要前提，或适用范围有确凿反例，给出有证据的 `ABSTAIN`。
3. **关键信息未知**：输出 `VERIFY`，指出必须调查的事实；不得编造 confidence。
4. **冲突证据**：支持与反例指向不同上下文或同一上下文；保留双方路径，不得按固定检索顺序静默选一个。根据可核验条件分层判断，无法分辨时 `VERIFY`/`ABSTAIN`，且说明规则。
5. **版本演化与过期**：新增证据/修订、历史事实失效或证据被标注撤回时，原始来源保留；当前 Snapshot 的结论能正确变化，旧 Snapshot 可追溯。
6. **跨作用域差异**：单进程共享锁、多独立 Worker、拓扑未知、事务保证未知，不能将 A/D 已证实的 RDB 原则泛化成任意数据库/业务的万能修复。
7. **负面与故障情况**：空图、断库、被删除关键关系、错误来源、非可信新 Outcome、重复/冲突导入、恶意 Evidence 文本、候选证据不足；不可静默 `APPLY`。
8. **非题号泛化**：使用一个不含 A/D 字样的新任务上下文，证据和前提同构时仍输出等价结果；只改变无关 Episode ID 不应改变结论。

### G1.3 真实验证要求

- 每类决策至少保留实际执行的参数化 Cypher/关联查询、图关系路径、查询快照、匹配/冲突/未知前提与可解释 Output。
- 对图边做消融/替换、添加反例、增加修订、变动可观察上下文；输出应因有效条件变化而变化，而不是只验证响应 JSON 的形状。
- 使用基于独立 Fixture 的确定性单元测试**和**真实 FalkorDB 集成测试；Fixture 结果只能证明决策规则，不能冒充独立工程任务成功。
- Trusted Feedback 区分 `VerifiedOutcome`、推荐、查询、Agent 声称采纳、可观察行动和真正归因；新证据缺少因果链时继续保留 `UNKNOWN` 或 `outcome_observed_no_attribution`。
- 不要单靠经验 PASS 次数设计“可信分数”，避免过拟合两条历史策略。若引入任何加权规则，必须有明确解释、反例及敏感性测试；非必要不做。

**Gate H2-G1 PASS 的最低证据**：同一 Resolver 在独立上下文下产生可审计的三态及冲突处理；真实 Cypher 关系变动影响决策；Revision 前后结果、原始来源及反例可回溯；不可信反馈无法成为 Verified；原 H1 A/D 行为和历史证据不回归。

## 4. H2-G2 — 独立新场景：优先 OrderFlow D-v02

**目标**：建设至少一个 H1 已验证挑战之外的新动态业务场景，以检验治理在新的适用条件下是否仍可信。**优先使用历史已静态设计的 D-v02（Lease/Authority 优先）**，但所有业务条件必须以仓库中的真实 D-v02 规范为准；不得自行臆造其已经实现或已经通过评测。

### G2.1 先做真值与设计核查

1. 定位并完整阅读 D-v02 的原始设计、Task System 规范、历史优选 Lease/Authority 与备选 WAL Backup/Generation 的具体要求。给出已冻结/未确定项和建议的最小可验证实现边界。
2. D-v02 必须与 D-v01 在某些关键工程前提上产生实质差异，能够检验 H1 策略迁移边界；不能仅将 D-v01 变量改名并增加几条测试。
3. **先完成独立 Task Specification、公共任务包、私有 Hidden Oracle、Reference、Buggy、挑战登记与指纹封存，然后再让新 Participant 挑战**。不得按照 Agent 后续表现倒推修改 Oracle 来制造 PASS。
4. 若原静态规范与现有系统存在矛盾，先记录设计裁决与追溯，不通过暗改已有任务真值解决。

### G2.2 业务、Oracle 与测试

- 用与现有 OrderFlow 一致的 Runner、Submission Fidelity、sandbox 隔离、Reset、Run Registry、Original-vs-Postmortem 记录方式实现；对原 Episode A、D-v01 不做无必要的改写。
- 提供真实可触发的缺陷、受控环境变化和独立 Oracle；评估正确性、进程/Worker 失效或恢复行为、数据一致性与合法替代解法，具体断言以已确认的业务规范为准。
- 设计合法解法不止一种的验收，避免隐藏测试强迫 Participant 复制维护者参考补丁；对预期无效的典型策略做负面验证。
- 对 Buggy、Reference 和至少一个有代表性的无效策略反复运行（默认各 **至少 10 次**；若环境成本或规范要求不同，报告独立理由、次数和全部结果），建立独立判别力和不稳定性报告。
- 保持 Participant 只获得合法公开任务材料；Hidden Oracle、Reference Patch、适用性标签、维护者经验真值不得进入受挑战 Agent 工作区、Prompt 或其工具响应。
- D-v02 属于 **D 任务家族内部的新变体**。若本轮没有 B/C 等跨家族动态任务，不得宣称已实现跨所有故障家族的泛化；若 D-v02 的独立性不足，H2-G2 报告 PARTIAL，不为了完整叙事强行标 PASS。

**Gate H2-G2 PASS 的最低证据**：独立可执行 D-v02 Challenge、封存的私有 Oracle/公开材料边界、有效 Buggy/Reference/无效实现判别、反复运行与环境重置、旧 Episode A/D-v01 回归无破坏。

## 5. H2-G3 — 新场景原生 Codex + Trusted Feedback 端到端复验

**目标**：在 G0 最终版本和 G1 实际图谱治理机制上，让真实新 Session 面对 G2 新任务，形成工具调用、实际代码变更、独立 Outcome、反馈演化和另一 Session 再检索的完整链条。

### G3.1 实际 Challenge 协议

1. 先冻结 Challenge 公共输入、Hidden Oracle Fingerprint、Source Commit、图谱基线版本、策略候选、上下文可见边界和运行配置；隔离 Agent 不可看到设计者私有答案或此前挑战的 Solution。
2. 新建真正独立的 Codex Native Multi-Agent Session，使用当前受支持的真实 MCP，至少包含决策前 `resolve_experience` / `build_evidence_bundle`，以及可追踪的 `record_decision`（如真实 Agent 未调用，应如实记录）。禁止在 Prompt 中直接预设最优策略答案或适用性标签。
3. 原始 MCP request/response、native tool events、子 Agent 事件、Query/Decision/Snapshot ID、时间戳和主要代码修改事件必须能够独立对齐；经验查询不等于声称采纳，声称采纳不等于可证明的因果收益。
4. 使用 completion-aware 等待正常活跃任务，不设置任意硬墙钟 kill；保留取消、资源防护和 Provider 故障分类。所有开始的 Run（包括 ERROR/NO_PATCH/TIMEOUT）必须进入分母和原始归档。
5. Agent 原始提交必须经 OrderFlow Submission Fidelity 及**新场景独立 Hidden Oracle**，由可信 Host Adapter 导入真实 Outcome，拒绝 Participant 伪造 Verified 结果；Outcome 即使 FAIL 也须按类型正确反馈。
6. 在不同真实 Session 再查询同一经验/上下文，证明新增 Outcome/Revision 可观察，并验证支持、冲突或 UNKNOWN 的合理解释。图谱断开、关键证据边消融时不能悄悄给出同样完整结论。
7. 完成 **至少一次完整真实 Challenge 链** 和 **一次不同 Session 的回读**。若资源与运行环境允许，再做一个独立新 Session Challenge 作为复现检查；任何额外尝试都应全部报告，不筛选成功样本。

### G3.2 最小有限对照（不是正式科学消融）

- 做有限的图谱必要性验证与负迁移案例：可在相同上下文下比较原始经验文本与治理判断的差别，但**不要求本轮完成统计显著 G0–G3 实验组比较**。
- 不可改变隐藏答案来适配 Aevora；不可声称一次成功证明 Aevora 提高通过率。若新任务失败但工具、评价与可信反馈仍真实完成，分别判定 **集成闭环结果** 与 **Agent 解题结果**，不得混同。

**Gate H2-G3 PASS 的最低证据**：全新 Session 决策前原始 MCP 调用、真实 Agent 提交/失败事实、独立 D-v02 Outcome、可信入库、前后证据差异、新 Session 真实回读、无私有真值泄漏。若 Agent 未解题成功而闭环完整，可以报告集成 PASS / Solving FAIL，H2 总体是否 CONDITIONALLY PASS 依据其他 Gate 与风险如实裁定。

## 6. 全局回归、可复现与可审计要求

1. **强制保留** H1 封存证据、原始 Run ID、原 856 个测试身份、现有 1214 项测试基线和 A/D-v01 任务真值。做冻结前后树/指纹清单；新增测试不能借删除/重命名旧测试制造通过率。
2. 每个 Gate 结束执行其开发者测试和适当的 A 14 / D-v01 28 回归；最终在本机实际运行完整可用测试集。**不得把 H1 的 1214/1214 写成本轮新结果**；任何 skipped、xfail、部分集都要单独列明。
3. 每个 Gate 必须输出：源代码位置、命令、环境版本/Commit、原始数据库/工具/评测响应、真实成功与失败、负面/对抗测试结果、JUnit、Gate Verdict 和限制。新增 H2 的需求→源码→命令→Run/Query ID→Evidence 文件一一关联。
4. Full Archive 存本机；新增 **Audit-Lite** 需包含：设计与核心源码/变更清单、Graph Schema/关键 Cypher、测试 JUnit、G0–G3 全部报告、匿名化 MCP 原始事件、独立 Outcome、Source/Run Fingerprint、SHA256/NOT_INCLUDED、复现与安全说明。禁止将私有隐藏测试源码和凭据导出给 Participant；维护者 Audit-Lite 与 Participant 可见物需分开。
5. 审计包哈希/自校验不等于第三方不可变存证。必要内容 `NOT_INCLUDED` 不得宣传为独立可见并已审计。保留 Exporter/Verifier 的篡改拒绝与重复导出确定性检查。
6. 公开任务上下文与内部私有评测分离。恶意文本应作为不可信数据处理，禁止越过 Cypher/Prompt/Tool 信任边界。独立部署与多进程故障注入必须避免修改用户当前生产数据。
7. 如某 Gate 不能完成，先诊断并修复合理范围内的问题，确实受阻则输出 `BLOCKED` / `PARTIAL` 与原始证据，不伪造继续推进的 PASS。可以保留已完成 Gate，但不能隐藏阻断。

## 7. 建议交付清单（文件路径以真实仓库结构为准）

以下为建议命名；先审计现有结构，再在其上增量实施：

```text
AEVORA_H2_EXECUTION_PLAN.md
AEVORA_H2_G0_RELEASE_RELIABILITY_REPORT.md
AEVORA_H2_G1_GOVERNANCE_ROBUSTNESS_REPORT.md
AEVORA_H2_G2_DV02_BENCHMARK_REPORT.md
AEVORA_H2_G3_NATIVE_E2E_REPORT.md
AEVORA_H2_VALIDATION_REPORT.md
AEVORA_H2_LIMITATIONS.md
AEVORA_H2_TRACEABILITY_MATRIX.csv
AEVORA_H2_RELEASE_REPORT.md

aevora/                       # 尽量沿用现有实现，非强制重构目录
  core/                       # WHEN/WHY/Revision/Provenance 的必要增量
  interfaces/                 # 原有 MCP 的安全与兼容加固
  integrations/               # OrderFlow 可信 Outcome 桥接
  scripts/                    # backup/restore、replay、e2e 工具
  tests/                      # 数据驱动负面案例、FalkorDB 集成、安全测试

orderflow_incident_lab/        # 独立 Benchmark
  ...                         # 按既有规范实现 D-v02 与 Oracle；保留 A、D-v01
  aevora_validation/          # H2 原始证据与新 Audit-Lite
```

需要提供**最简复制执行命令**，可复现每个 Gate 的核心验证和独立端到端流程；自动化脚本不应该代替原始事件的保留。

## 8. H2 完成判定

最终报告逐项给出，不能只报总体 PASS：

| 维度 | 状态 |
|---|---|
| G0 Source & Clean-Rebuild Reproducibility | PASS / PARTIAL / FAIL / BLOCKED |
| G0 Persistence & Recovery | PASS / PARTIAL / FAIL / BLOCKED |
| G0 Security & Isolation | PASS / PARTIAL / FAIL / BLOCKED |
| G1 Evidence Conflict & Revision Governance | PASS / PARTIAL / FAIL / BLOCKED |
| G2 D-v02 Independent Benchmark | PASS / PARTIAL / FAIL / BLOCKED |
| G3 Codex MCP & New Scenario End-to-End | PASS / PARTIAL / FAIL / BLOCKED |
| Historical Non-Regression & Audit Integrity | PASS / PARTIAL / FAIL / BLOCKED |
| H2 Overall | PASS / CONDITIONAL PASS / FAIL / BLOCKED |

**H2 PASS** 需要 G0–G3 关键功能在当前源码上有真实可复现证据；新场景真实闭环、可信反馈、可解释适用性和原有回归均成立，未发生重大安全泄漏或历史证据破坏。仍存在已知 AOF/共享内核限制时，必须依据风险评估判定 CONDITIONAL PASS，而非自动升级。**任务解题 PASS 不等于治理增量收益 PASS**；若缺少严谨对照，治理效益始终 `UNVERIFIED`。

以下**明确不属于 H2 的硬性任务**：完整 Episode B/C、全故障家族覆盖、正式统计显著 G0–G3 实验组消融、Claude/AutoGen 全 Runtime 扩展、大型 Dashboard、自研 Agent Orchestrator、生产级多租户和无条件断电零损失承诺。

**H2 完成并提交报告后立即停止，不自动进入 H3**。如有下一阶段建议，列入 `AEVORA_H2_LIMITATIONS.md` 和最终摘要供维护者审查，不能提前编码。

## 9. 给 Codex 的执行方式与首次回复约束

1. 先审计现有仓库与 H1 已交付资产，输出**不超过一页的 H2 实施计划**：现状、拟复用模块、Gate 顺序、会影响既有接口的风险、首个可执行测试命令。
2. 随后**直接实施代码、部署和真实测试**，无需仅因为任务较大而停止在计划阶段，不需要再次请求授权；每个 Gate 单独 Commit（如仓库支持）并附证据。
3. 可以调用 Codex 原生 Subagents 并行审查数据库可靠性、治理规则、Benchmark/Oracle 和安全边界；避免多 Agent 同时编辑相同文件。保证主 Agent 负责最终集成及事实核验。
4. 不因实现失败删掉困难测试或降低 Oracle 判别力。不得通过修改评价真值、回放维护者答案、Mock 工具记录或事后篡改评测结果通过 Gate。
5. 结束时给出简洁结果摘要：Gate 判定、真实命令与 Commit、测试分母、Run ID、提交哈希、审计包路径及哈希、未知和失败事项、停止确认。

---

### 一句话的执行原则

**在 H1 已真实跑通的基础上，把 Aevora 从“已知场景可用的经验治理闭环”推进为“可复现、能处理冲突与未知证据、能跨新工程场景进行可信反馈的经验治理系统”；只认真实环境、原生 Agent、独立 Oracle 与可核验原始证据。**
