# Aevora H1 — Experience Accountability Core：真实端到端闭环开发任务

> 版本：v1.1 · 状态：**正式开发授权任务** · 品牌名称：**Aevora**（GraphSwarm 为历史工作名）  
> 当前优先级：Aevora 经验治理核心（基于 FalkorDB）**高于** Benchmark 内容扩展  
> 本轮目标：完成 **FalkorDB → WHEN/WHY → 原生 Codex 真实调用 → OrderFlow 独立 Outcome → FEEDBACK → 后续查询变化** 的最小完整、可审计、可扩展闭环。  
> 阶段终点：H1 完成并验收后停止；之后再单独开展规模化任务、G0–G3 对照与完整研究评测。

## 0. 项目正式命名与兼容性契约（本次 v1.1 新增）

**正式项目与产品名称：Aevora。** 从本次开发开始，项目说明、README、架构图、CLI/服务显示名、MCP Server 身份、对外报告和演示统一使用 **Aevora**。`GraphSwarm` 只作为**历史工作名称**出现于已有源文件、Git 提交、旧文档和证据索引中，不再用它命名新增模块或作为现行产品称谓。

| 名称/层次 | 现在使用的名称 | 规则 |
|---|---|---|
| 产品 / 系统 | **Aevora** | 正式品牌，替代历史工作名 GraphSwarm |
| 核心引擎 | **Aevora Core / Aevora Experience Accountability Core** | WHEN、WHY、FEEDBACK、证据治理、版本与审计 |
| Agent 接入 | **Aevora MCP Interface** / **Aevora Agent Integration Layer** | 接入方式仍可为 MCP、API、SDK、HTTP；H1 先实现 MCP |
| 图谱及持久化 | **Aevora Experience Graph (powered by FalkorDB)** | **FalkorDB 是真实数据库品牌**，不更名、不改变核心图查询要求 |
| 独立工程 Benchmark | **OrderFlow Incident Lab（OrderFlow）** | 保留原名、原有仓库身份、任务 ID、评价真值和历史测试结果 |
| 开发阶段 | **Aevora H1** | G0–G5 Gate 与此前 H1 技术范围不变 |

**命名迁移原则：**

1. 新增核心包优先使用 Python 包/模块名 `aevora`，新服务名、MCP Server 名、CLI 入口和文档标题采用 Aevora；不得保留 `graphswarm` 作为新系统的主要入口。已经存在的代码须先审计再迁移，不能以品牌更名为由破坏可运行接口。
2. 下游 OrderFlow 的 `orderflow_*` 路径、Episode A/D 编号、Run ID、SHA256、签名、测试指纹、原始证据内容**一律不重命名、不改写**。若有历史 GraphSwarm 文件、旧架构说明或仓库路径，不删除、不批量重命名；通过兼容导入、显式迁移映射及文档别名保持可追溯。
3. 源码路径、配置键、数据库标签或 MCP 工具名称如需改名：先建立旧→新映射，检查现有消费者，必要时提供兼容层，并通过新旧接口回归测试；**不得为视觉统一强行重写历史数据或改动可信指纹**。
4. G0 首先运行 `rg -n -i 'graphswarm|aevora'`（或同等搜索）盘点命名影响；区分新输出必须修改的现行称谓与不可修改的历史出处。最终验收须另列 **Brand & Compatibility Gate**：新增项目资产统一 Aevora，历史来源保持真实，旧接口无无意回归。
5. 文中 `GraphSwarm_Agent_Interface_Architecture(1).md`、`GraphSwarm_H0_Preflight_and_Hackathon_Build_Codex_Task_v1.0.md` 等文件名是**需要按原文件名定位的历史材料**，不得机械替换导致无法检索。H0 的仅准备文档限制已明确失效。

## 1. 任务授权与唯一成功标准

**这是工程实现任务，不是赛前规划或文档审查。** 此前 `GraphSwarm_H0_Preflight_and_Hackathon_Build_Codex_Task_v1.0.md` 中仅允许准备文档、限制核心开发的执行门禁**不适用于本次 H1**。现在直接实现、部署、测试和集成所需代码；不因赛程安排阻断技术开发。保存真实开发历史和来源。

我们的作品不是“FalkorDB Memory MCP”，不是新的 Agent Orchestrator，也不是 OrderFlow Benchmark 的改名版本。

**核心定义**：一种使 Agent 群体有依据地继承经验（WHEN）、解释经验为什么可信（WHY）、用可信任务结果对经验使用负责（FEEDBACK）并持续更新适用边界的 Experience Accountability Layer。

本轮必须提供三种证据：

1. **图谱证据**：FalkorDB 中存在真实来源、情景、策略、支持/反例、决策及结果之间的图关系；实际 Cypher 关系查询影响决策结果。
2. **Agent 证据**：全新 Codex Session 在关键策略决策与代码提交前，确实通过工具读取经验建议；工具调用和实际策略选择有独立、可追溯的关联。
3. **反馈证据**：只有可信 OrderFlow Evaluator 的真实结果能够登记为 Verified Outcome；反馈作为新事实保留并影响后续查询，历史不被覆盖。

**严禁**以 mock 图数据库、静态 JSON 查表、提示词内写死正解、回放维护者答案或事后补写 MCP 调用替代真实闭环。若真实集成受阻，诚实报告 BLOCKED/PARTIAL，保留成功的分段成果。

## 2. 当前基线与工程职责（编码前核查）

以**实际本机工作树、Git commit、源文件、Run 产物**为准，而非阶段文字摘要。阅读：

- `OrderFlow_Benchmark_Development_Roadmap_v1.0.md`；`GraphSwarm_Agent_Interface_Architecture(1).md`；现有 Proposal/Technical Architecture（如存在）。
- OrderFlow `README.md`、`docs/ARCHITECTURE.md`、`docs/EPISODE_A.md`、`docs/EPISODE_D*.md` 和 Task System 规范。
- `PHASE3_5_VALIDATION_REPORT.md`、`M1_EPISODE_D_VALIDATION_REPORT.md`、`M1_1_VALIDATION_REPORT.md`、`M1_1_DIFFICULTY_CALIBRATION_REPORT.md`。
- Runner / Registry / Participant / Codex Adapter / MCP 配置或可扩展接口 / `integrations/experience.py` / Oracle / Audit-Lite Exporter 的真实实现。
- 早期 FalkorDB 图蒸馏、关系检索、规则经验原型（如果存在），注明原型身份、代码位置及可复用范围，不将静态原型声称为新的生产实现。

已知的、待在本机复核的状态：Phase 1–3 完成了 Runner、Episode A 和真实 Codex；Phase 3.5 解决提交保真；M1 实现 D-v01 的 2/4 独立 Worker 与恢复；M1.1 引入 completion-aware 和 Audit-Lite，六次校准 5/6 自动闭环。B/C、D-v02 业务实现尚无完成证据。**Experience Adapter 至此仍为 DISABLED**。

**职责边界**：

| 子系统 | 唯一职责 | 禁止事项 |
|---|---|---|
| Codex Native Runtime | 调查、决策、修改与提交 | 不由我们重造 Planner/Orchestrator |
| Experience Interface (MCP 首先) | 经验查询、证据展示、决策登记 | 不直接决定隐藏评测结果 |
| Experience Core | WHEN、WHY、经验版本与反馈治理 | 不按 Episode ID 硬编码答案 |
| FalkorDB | 持久化图关系和实际 Cypher 证据查询 | 不退化为普通键值缓存或装饰性可视化 |
| OrderFlow | 任务、隔离、Submission、Hidden Oracle、Verified Outcome | 不内嵌 Aevora 的决策规则，不为系统改变真值 |

优先新建**独立的 Aevora 经验治理核心包/仓库**，通过薄 Adapter 连接 OrderFlow，不在 `evaluator/` 中实现治理算法；已有原始任务和隐藏测试不能为迎合新系统而修改。

## 3. 总体集成结构（按此方向实现，不要求照抄目录）

```text
Codex Main Agent + Native Subagents
            |
     Experience MCP Client
            |
  Per-run, least-privilege bridge
            |
   Aevora Experience Accountability Core
      ├─ Experience Resolver (WHEN)
      ├─ Evidence Bundle Builder (WHY)
      ├─ Decision / Adoption Trace
      ├─ Trusted Outcome Ingestor
      └─ Feedback / Revision Engine
            |
        FalkorDB

OrderFlow Runner / Hidden Evaluator
            |
  Trusted Verified Outcome Adapter
            +----> Outcome Ingestor
```

必须先验证当前 Codex CLI 对 MCP（stdio 或 streamable HTTP）、项目配置、原生工具事件和现有隔离网络策略的**实际支持方式**；选择符合当前环境的最小可靠接入。不能因为 MCP 需要连接而取消 Participant 文件隔离，不能把 FalkorDB 管理员口令、Gateway 长期密钥、隐藏测试或参考补丁交给 Participant。

## 4. G1：真正的 FalkorDB 经验图谱与证据存取

使用真实 FalkorDB 服务及官方受支持的 Python Client。固定经验证的镜像/依赖版本，提供 Compose/启动、Health Check、最小 Schema 初始化、幂等种子导入和容器重启后持久化验证。优先使用参数化 Cypher，验证版本所支持的语法；不要仅编写未执行的查询示例。

建议的初始概念实体（允许在有证据的设计审查后合并）：`Agent`, `Task`, `Context`, `Experience`, `ExperienceRevision`, `Decision`, `Evidence`, `VerifiedOutcome`, `Rule`。

**强制的数据约束：**

- 每条经验拥有稳定 ID、来源类型、来源 Run/Report 引用、受支持的适用前提、反例、创建与版本信息。
- 严格区分 `natural_agent_run`、`maintainer_seed`、`synthetic_or_test_fixture`。不能把维护者 RLock 对照经验伪装成真实 Agent 自创经验。
- `Outcome` 包含 `run_id`、`submission_digest`、`evaluator_fingerprint`、`test_suite_fingerprint`、验证身份/来源及实际 Verdict；可信索引须可追到 OrderFlow 的真实归档。
- 历史 Evidence/Outcome 不可覆盖。新反馈追加事件、新版本/修正关系；保留反例及原来支持它的上下文。
- `Decision` 应将推荐、Agent 是否查询、是否声称采纳、可观察行动分开记录，不能由查询自动推断采纳，更不能从成功自动推断经验起了作用。
- 与 Agent 共享的是**公开或脱敏的经验证据摘要**。不得暴露私有 Manifest、隐藏测试断言、完整参考补丁和独立适用性私有标签。

最少建立两条**来源真实、带引用**的策略：

1. Phase 3 已有真实 Codex 修复：数据库条件原子更新、适用条件以及已验证的 A 和 D-v01 运行报告（只记录实际有的关联，不凭空合并不同 Run）。
2. 维护者受控 RLock 方案：单进程条件下已通过 A；跨独立 Worker 并不提供同步保证，已有 D-v01 的实际错误/失效证据须以真实评测记录为准。

实现并实际执行三类查询：**正向支持链**、**跨环境冲突/反例链**、**包含未知前提的候选证据链**。证明多跳关系（而不是固定词汇匹配）影响下游判断。服务被断开时必须显式失败/不可用，不得秘密回退到写死的经验建议。

**Gate G1：** 空库初始化、重复导入幂等、独立 Cypher 路径查询、容器重启保持数据、来源/版本追踪与断库失败测试均通过。

## 5. G2：WHEN / WHY 决策与证据机制

构建与 Episode 名称无关的决策规则。输入为**Agent 可获得或授权采集的真实当前上下文**，如 `concurrency_scope`、`worker_count_known`、`shared_state_kind`、`synchronization_scope`、`transaction_guarantees`、`observed_failure_mode`，同时保留未知值，不把缺失字段自动当作 false。

返回 `APPLY / VERIFY / ABSTAIN`，每条候选经验至少包含：

- 可引用的 Evidence Bundle：相关任务、成功结果、反例、前提、来源、图谱路径与检索快照版本；
- 判断依据：哪些已证实的前提匹配、哪些发生明确冲突、哪些事实未知；
- 结论范围：建议是否值得借鉴，而非承诺原始补丁可直接复制；
- 可审计的决策版本与规则/查询版本；
- 在证据不足时明确建议需要验证的事实，不得虚构 confidence 或伪造完整因果证明。

决策含义：`APPLY` = 在**已证明的相关前提范围内**建议采用经验原则；`VERIFY` = 关键条件未知或证据冲突，需要调查；`ABSTAIN` = 已确认的重要适用前提违背，或有足够反证，拒绝直接套用。避免把 `APPLY` 设计成“Agent 必须复制历史补丁”。

要求数据驱动而非题号驱动。测试中使用**相同的 Experience 和策略**，只改变执行环境/已知事实，至少验证：

- 单进程锁 → 已证明共享对象的单进程多线程环境：可得到有条件 `APPLY`；
- 相同锁 → 多个独立 OS Worker 且无跨进程同步：`ABSTAIN`；
- 相同锁 → 部署拓扑未知：`VERIFY`；
- 原子事务策略 → A/D 已证实的相关约束：能引用支持证据，但不能把它夸大为所有数据库或所有业务的通用万能修复。

**重要：** 第三个“未知拓扑”可先是受控 *decision test fixture*，只能证明决策引擎对未知事实作出正确处理，不得声称 D-v02 已通过真实工程任务验证。

**Gate G2：** 同条经验三态由上下文证据决定；实际 FalkorDB 查询结构驱动判断；去除支持/添加真实反例后输出可解释地变化；无私有参考数据泄露；错误/空图不能无条件 APPLY。

## 6. G3：真实 MCP 与 Codex 决策前接入

以历史架构文档 `GraphSwarm_Agent_Interface_Architecture(1).md` 为参考，构建 **Aevora MCP Interface** 的最小受支持工具：

- `resolve_experience(task_context)` — 候选及 APPLY/VERIFY/ABSTAIN、依据、未知条件；
- `build_evidence_bundle(experience_id)` — 公开可展示的支持/反例与证据路径；
- `record_decision(decision)` — 不可信 Agent 的策略选择或采纳声明，带时间/关联；
- `submit_outcome` **仅可信 Runner/Host Adapter 可调用**，不可作为 Participant 可伪造 `verified=true` 的通用工具暴露。

如果为了协议完整性提供 Participant 可见的 `submit_outcome`，仅能提交未验证的自述，并与可信 VerifiedOutcome 不同类型、不同行权，不能进入可信反馈链。

建立稳定关联：`run_id`、`agent_thread_id`（如可见）、`experience_id`、`query_id`、`decision_id`、`submission_digest`、`outcome_id`。原始日志保存为原始数据；后处理解析不得虚构原生事件。无法观察的“经验是否真的改变思考”标记 `UNVERIFIED`。

**安全审查重点**：现有 Participant 网络与 Model Broker 的限制不可被 MCP 打开。优先可信宿主代理 + 每 Run 短期授权 + 只允许经验查询/登记；拒绝从 Participant 发任意 Cypher 或操作可信反馈、跨 Run 历史、数据库管理。验证连接、断连、重放攻击、越权和清理。不要把 Redis/FalkorDB admin 凭据挂载进 Agent 工作区。

至少运行一次真实、全新、隔离的 Codex Native Multi-Agent Session：

1. Agent 获取 Episode D-v01 的合法公开任务材料，**不额外提前提供答案或适用性私有标签**。
2. MCP 原始工具调用发生于策略选择及主要修复提交前；记录原始请求/响应、查询时序和 Agent 的真实决定。
3. 继续沿用 completion-aware，允许慢 Gateway 自然完成；保留取消、资源和 Provider 故障分类。
4. Agent 生成真实提交，并走现有 OrderFlow Submission Fidelity 与 28 项 Hidden Evaluator。
5. 不以“Episode D PASS”为本阶段唯一条件，区分 **工具集成成功** 与 **任务解题成功**，完整记录失败情形。

**Gate G3：** 可核验原生工具调用、真实 Session 与子 Agent、私有路径拒绝、补丁保真、独立 Outcome；用文本声称“我用过经验”不能代替原始工具事件。

## 7. G4：可信 Feedback Evolution 与跨 Session 持久性

实现独立于 Agent 自述的可信 `Outcome Ingestor`。它应从授权的 OrderFlow 报告源读取 Run/Submission/Evaluator 证据并交叉核对摘要与身份，避免调用者自行指定 `PASS`、`verified=true` 等字段伪装可信结果。重复导入同一 `outcome_id` 应幂等；相同 ID 但内容冲突必须拒绝并留审计记录。

反馈处理需要区分：

- 工程任务成功/失败（Verified Outcome）；
- 推荐或记录的经验（Query/Decision）；
- Agent 自述采用（Untrusted Adoption Claim）；
- 可观察的代码/工具行为（Observed Action）；
- 经验的可适用性反证/新增支持（Feedback），不得默认由最终 PASS 推导“某经验促进成功”。

反馈必须在 FalkorDB 中追加，并更新 ExperienceRevision 的可解释证据边界，保留原有证据。展示至少一次由**真实独立评价**产生的新支持/反例被持久化；不同的新 Session 对同一经验查询时能观察到证据变化。如果本轮实际 Outcome 没有足够因果证据，不要自动把经验改判为可靠或不可靠；可以增加 `outcome_observed_no_attribution` 状态并保持 UNKNOWN。

**Gate G4：** 未授权或伪造 Outcome 不能成为 Verified；真实 Outcome 导入、幂等、冲突拒绝、更新前后图谱差异、容器重启和新 Session 再查询均有真实证据。

## 8. G5：最小但完整的研究演示与消融检查

建立**可在同机重复运行**的演示脚本，不依赖手工剪辑日志或将预设答案复制到 Agent Prompt：

```text
A 的历史来源和证据 → FalkorDB 图谱
  → D 的真实任务上下文 / 经验候选
  → WHEN/WHY（含适用与不适用策略、必要时 VERIFY）
  → Codex 工具查询 → 决策声明 → 代码提交
  → OrderFlow Hidden Oracle → Trusted Feedback
  → 新 Session 读取更新后的图谱证据
```

至少覆盖以下三类验证：

- **图谱必要性**：禁用 FalkorDB、移除相关图边或换成无关联数据时，证据链和判断不应照常工作；不能仅从 Episode 名称给出预设答案。
- **经验条件对照**：同一 RLock 策略在单进程、跨进程、未知拓扑情景给出不同有据判断；同一策略来源及证据可被独立复核。
- **真实 Agent 闭环**：有 MCP 原始调用和独立 Evaluator Outcome，Feedback 在新会话中可见；成功与失败均如实归档。

**可以额外做非常有限的 G2 Raw Memory vs G3 Governance smoke/pilot，但不能将其伪装为公平、统计显著的正式消融。** 下一轮才建设完整 G0–G3 随机化对照、多任务分布和统计验证。

**Gate G5：** 一条真实全链路可按说明重复运行，关键数据由 FalkorDB 与 OrderFlow 真实产生，具有独立检验脚本；证明不了增量收益时如实报告而不是宣称 Aevora 提升通过率。

## 9. 工程组织方式、测试与开发节奏

不要一次性在单个巨大的改动中同时实现所有 Gate。采用：

- **G0：基线核查**（只读审查与新工作树/模块边界）；
- **G1：Graph Store + Schema + 历史证据导入**；
- **G2：WHEN/WHY + Evidence Bundle**；
- **G3：MCP + Codex 真实连接**；
- **G4：Trusted Feedback + Revision**；
- **G5：真实 A→D 闭环和演示验收**。

每个 Gate 结束时都要留下可运行命令、开发者测试、实际数据库/工具响应、失败记录和简短阶段报告，先修复当前 Gate 再继续下一项。允许使用 Codex 原生 Subagent 并行审查 schema、接口安全、评测信任边界，但避免多 Agent 同时修改相同文件。

**原有回归**：确保 OrderFlow A 14 项、D 28 项和有效开发者测试在已批准修改范围内不回归；如未在本轮完整执行 856 项，必须说明为何、列出执行了哪些项，不能声称全部 PASS。历史 M1/M1.1 产物不可被改写。

**运行时间**：不要用任意固定的总 wall-clock 时间杀死正在正常处理慢速 Gateway 的 Agent；仍须有显式取消、不可恢复错误、Provider 失败分类、活性观察和资源限制。不要把 `max` / 模型字符串标签写成可验证的模型权重事实。

**证据工程**：Full Archive 本机保留，新增输出 Audit-Lite；轻量包**必须包含**核心源码变更清单、Graph Schema、可执行 Cypher、完整 Gate 报告、测试 JUnit、匿名化原始 MCP Tool Trace、关键 Outcome、SHA/NOT_INCLUDED 清单。不能再出现关键设计正文缺失却声称外部能独立审查的情况。

## 10. 建议交付结构（可依据仓库现状合理调整）

```text
aevora/                         # 正式项目名；独立核心包/仓库（按实际工作树适配）
  core/
    models.py
    graph_repository.py
    experience_resolver.py
    evidence_bundle.py
    feedback_engine.py
  interfaces/
    mcp_server.py
  integrations/
    orderflow_outcome_bridge.py
    codex_bridge.py
  scripts/
    init_graph.py
    import_verified_history.py
    demo_a_to_d.py
  tests/
    test_graph_provenance.py
    test_applicability.py
    test_mcp_boundaries.py
    test_trusted_feedback.py
    test_e2e.py
  docs/
    ARCHITECTURE.md
    GRAPH_SCHEMA.md
    QUERY_COOKBOOK.md
    WHEN_WHY_FEEDBACK.md
    CODEX_INTEGRATION.md
    TRUST_BOUNDARY.md
  evidence_review/               # Full 本地保存，Lite 导出
  pyproject.toml
  compose.yaml
  README.md

AEVORA_H1_VALIDATION_REPORT.md
AEVORA_H1_DECISION_TRACE_REPORT.md
AEVORA_H1_LIMITATIONS.md
```

并提供一份 `AEVORA_H1_TRACEABILITY_MATRIX.csv`，把需求 → 源码位置 → 实际命令 → Run/Query ID → 证据文件 → Gate 结论逐项关联起来。

## 11. 完成判定与停止边界

报告独立给出：

| 维度 | 必须报告的实际状态 |
|---|---|
| FalkorDB Graph & Provenance | PASS / PARTIAL / FAIL |
| WHEN/WHY & Evidence | PASS / PARTIAL / FAIL |
| Native Codex MCP Integration | PASS / PARTIAL / FAIL |
| Trusted Feedback & Evolution | PASS / PARTIAL / FAIL |
| End-to-End A→D | PASS / PARTIAL / FAIL |
| Security / Leakage Boundary | PASS / PARTIAL / FAIL |
| H1 Overall | PASS / CONDITIONAL PASS / FAIL |

H1 **PASS** 必须实际证明：真实 FalkorDB 图谱参与判断；三态有可核验依据；真实 Codex 决策前调用；真实提交被 OrderFlow 评测；可信 Outcome 实际更新关系证据；新会话能重新查询；没有私有答案泄露。任何一环未真实运行，整体不得标记 PASS。

**本轮不开发**：OrderFlow B/C、D-v02 业务实现；完整 G0–G3 科学实验；跨 Runtime 全量 SDK；大规模可视化 Dashboard；自研 Agent Orchestrator；商业级多租户平台。它们属于后续 H2/H3 的独立质量阶段，不是 H1 是否闭环成立的借口。

最后必须提交：实测命令、版本与 Commit、通过和失败结果、Raw Evidence、Audit-Lite、残余风险与下一轮建议。**H1 完成后停止，不自动进入后续研究实验。**

---

## Aevora 命名与迁移专项验收（新增）

- [ ] 新增仓库说明、项目元数据、服务启动信息、MCP Server 显示名、CLI 帮助文字及对外交付报告均使用 **Aevora**。
- [ ] 新的模块建议为 `aevora`，新的配置前缀优先 `AEVORA_`；不强制重命名既有稳定接口，但新增映射与兼容测试。
- [ ] `OrderFlow Incident Lab`、`FalkorDB`、`Codex` 保持各自原名和职责，不写成 Aevora 的同义词。
- [ ] 历史 `GraphSwarm` 仅作为此前工作名、原文档引用或旧代码溯源标记出现；新增正式描述不得继续宣传旧名。
- [ ] 原始 Run IDs、哈希、历史评测与证据索引未因更名受到修改；新增提交必须提供更名影响清单。
- [ ] 兼容性 Gate 不得替代 G1–G5 实际功能验收，改名本身不是技术完成证据。

---

## 官方技术参考（实现时核对当前版本）

- FalkorDB Python Client：https://github.com/FalkorDB/falkordb-py
- FalkorDB Docker：https://hub.docker.com/r/falkordb/falkordb
- FalkorDB Graph Query 与参数化查询：https://falkordb.github.io/docs-staging/commands/graph.query/
- Codex MCP 配置：https://developers.openai.com/learn/docs-mcp

以上参考只证明这些接口或配置方式存在；实际可用参数、运行环境与事件字段必须由本机实测确认。
