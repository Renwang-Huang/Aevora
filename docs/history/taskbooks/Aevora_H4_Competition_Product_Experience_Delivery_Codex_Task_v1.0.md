# Aevora H4 — Competition Product Experience & Delivery

> **版本**：v1.0 · **用途**：Codex 可直接执行的 H4 正式迭代任务书  
> **唯一目标**：将已经具备真实实现的 Aevora H1–H3 框架，打磨成**可使用、可理解、可验证、可交付**的优秀竞赛作品。  
> **实施顺序**：**H4-G0 真实证据与 Hero Scenario → G1 普通开发者接入 → G2 受控观察 API → G3 精简 Web Console → G4 差异化真实演示 → G5 竞赛发布与封存**。各 Gate 独立验收，严格控制范围。  
> **架构原则**：**MCP-first / Web-assisted**。Codex 等 Agent 通过 MCP 使用 Aevora；人类通过轻量 Web Console 理解、追溯、审核。Web 不成为第二套决策引擎。  
> **工程身份**：产品为 **Aevora**；**OrderFlow Incident Lab** 是独立 Benchmark，不是运行时必需依赖；**FalkorDB** 是实际经验与证据图的权威存储。历史 GraphSwarm 仅作为旧资料的来源名。  
> **工作范围**：围绕竞赛产品完成度做增量开发；不重写 H1–H3 历史，不启动新大型研究工程。

---

## 0. 本轮完成后，产品应该是什么样子

一个陌生开发者可以遵照公共 README，在全新环境启动 Aevora Core + FalkorDB，将其作为 MCP 工具接入**自己的普通 Codex 工程**，完成真实经验查询；另一个人在轻量 Web Console 中能够看到：

1. **发生了什么**：真实 Agent Session、工具调用、查询、Decision、可观察 Outcome 与状态；
2. **经验从哪里来**：候选 → 独立来源验证 → 有边界的 Host Review → Published Experience → 后续读取与修订；
3. **为什么这样判断**：实际 WHEN/WHY、支持/反驳证据、Scope/未知前提，以及真正影响输出的 FalkorDB 路径；
4. **反馈如何改变未来**：可信 Outcome 与未验证外部观察严格分层；历史 QuerySnapshot 保持不变，后续当前查询可以变化；
5. **哪些仍不能证明**：例如策略采纳、因果收益、外部公开测试的可信性与运行时隔离边界，都准确显示 UNKNOWN/PARTIAL/EXTERNAL_UNVERIFIED。

产品形态：

```text
                 普通 Codex / Agent Runtime
                           │
                     MCP / existing Broker
                           │
                  Existing Aevora Core
               WHEN · WHY · Candidate Lifecycle
               Trusted Feedback · Revision
                           │
                    FalkorDB Graph
                           │
                  Controlled Read/Host API
                           │
              Aevora Experience Console
            Activity / Explorer / Governance
                           │
                    审计/演示投影
      Live = 真实在线；Replay = 真实封存历史（显著标识）

   OrderFlow Incident Lab（独立的可信 Benchmark/Oracle）
        └── 只有受信任 Host Adapter 能生成 VerifiedOutcome
```

**最终成功标志不是 Dashboard 出现很多数据，而是完整可信的使用与可视化流程真实运行，并且任何关键 UI 声明都能回到实际代码/图查询/事件/收据。**

## 1. H3 基线、必须复用的模块与不可侵犯的历史

### 1.1 先核实本地代码与真实交付状态

正式编码前，**仅做一次短而精的源码/证据基线审计**，生成 `AEVORA_H4_BASELINE.md`（1–3 页），内容必须包含 Git HEAD/Tree/status、H3 Release/source epoch、当前工作树差异、可复用现有接口与主要改动点。不得只阅读汇总报告。优先从以下文件和实际代码定位：

- `AEVORA_H3_VALIDATION_REPORT.md`、`AEVORA_H3_LIMITATIONS.md`、`AEVORA_H3_TRACEABILITY_MATRIX.csv`、`FINAL_DELIVERY_RECEIPT.json`；正确的 `aevora-h3-audit-lite-v2.zip` 与 H3 Full Archive 的冻结/补充关系；
- `aevora_core/src/aevora/` 中的 `experience_resolver.py`、`graph_repository.py`、`governance.py`、`candidate.py`、`admission.py`、`feedback.py`、`mcp_server.py`、`mcp_broker.py`、`connection.py`、`models.py` 等**实际存在**的模块；
- `aevora_core/scripts/h3_demo.py`、`h3_verify.py`、`aevora_core/docs/H3_OBSERVABILITY.md`，已有 H3 Live/Replay 投影与独立验证逻辑；
- `integrations/` 下现有 Codex 接入路径、独立公共 Core Wheel/SDK 与可信 Host 的权限划分；
- OrderFlow 中的实际 `benchmark/` / `evaluator/`，只用于验证来源与 Benchmark；严禁将私有 Evaluator 迁入公共产品包。

**已有的受审计历史基线，不能算本轮重新跑的成绩**：

- H3 总体 `CONDITIONAL PASS`：G0 `PARTIAL`，G1–G4 限定范围 `PASS`。
- H3 最终开发者回归 `1714/1714 PASS`；继承 H2 的 `1655` 个测试身份。H4 新版本需真实重新执行可用测试并保留身份。
- 新自然来源 Run：`405c481e-ae7a-420d-8502-fb1d9ede02e6`；**3 名完整身份链的原生 Subagent**，Episode A **14/14 Hidden PASS**，可对应候选/Host Review/发布。
- 新 Session 阅读：`c4cd6c0e-fb38-465f-bee1-63d3d50374a6`，观察 PASS，但工程任务 `ERROR/NO_PATCH` 且 `NOT_EXECUTED`，不得描述为另一项修复成功。
- 普通 Receipt 工程 Governance Run：`c8a6a7ae-fb65-4b2d-98ea-0651eb939a7b`；Raw Memory Run：`f4406efc-d94d-4d21-b30f-d350248f3d4e`，**二者均 7/7 公开测试 PASS**、均为 `EXTERNAL_UNVERIFIED`；还有先前 `PROVIDER_FAILURE`，不得删除。
- H3 图谱必要性控制：真实 `VERIFIES` 支持边删除后，当前路径 `1 → 0`，当前决策 `APPLY → VERIFY`，恢复边后恢复；**这是维护者受控消融，不是新 Agent Outcome**。
- H3 原始时间线覆盖 6 个真实 Session、1042 条事件（依据封存记录），不能把多文件记录强排成一条具有未知因果方向的时间线。
- H3 Audit-Lite v2 SHA256：`c7d36870084a90b14e4fb11b8651a80d3bf5aef2e2a2b07690990826772aeeec`；Full/Lite/历史 Run/私有 Oracle/补丁/旧报告均不得覆盖或篡改。

### 1.2 必须维持的既有限制

- 原 D-v02 Native 的 6 个跨进程 UDS setup `EPERM` 未完全解决；当前安全的 in-process 业务契约验证不能冒充真实跨进程 Clock Transport 成功。
- AOF reload `SIGSEGV/139` 仍是 UNVERIFIED；只承诺上次完成 `SAVE` 的 RDB/checkpoint 恢复边界，不能承诺零 RPO。
- 共享 Linux 内核/Flatpak 24.08 EOL 与 Prompt Injection 防护证明均有明确边界。
- 外部普通工程的自测或模型自述不能升格为 `VerifiedOutcome`；策略实际采纳和增量因果贡献保持 UNKNOWN。
- 多步检查+图写入不自动具备全局原子事务语义；受限 Host 操作需保留重试、校验和并发冲突处置。
- 目前的 SHA/本地日志属于本地一致性审计，不是第三方不可变存证。

**本轮不要为追求全绿把 PARTIAL 擅自改成 PASS。**

## 2. H4-G0 — Hero Scenario & Evidence Contract（先有真实证据，再写 UI）

这是最重要的第一个 Gate。**G0 未闭合前禁止先开发华丽 UI 或填充假数据。**

### G0.1 冻结一条诚实的三幕式展示故事

```text
ACT I   An Experience Is Born
    真实新任务 → 原生 Agent / Patch → 独立评测 → Untrusted Proposal
    → Host Source Verification / Bounded Approval → PUBLISHED
    → 不同 Session 读取

ACT II  A Memory Is Challenged
    表面相似，关键事实不同或支持证据缺失
    → FalkorDB 支持/反驳图路径 → APPLY / VERIFY / ABSTAIN
    → 解释改变及“下一步该验证什么”

ACT III Knowledge Evolves
    可信反馈、候选撤回/修订或受控图谱证据变动
    → 当前 WHEN/WHY 变化、历史 QuerySnapshot 不变
    → 新 Session/新查询读取变化（有真实数据才能展示）
```

**关键反造假规则**：三幕**可以是同一产品的三个真实案例/子场景**，不要求来自一条跨 Case 的物理 Run。真实 Episode A 候选、旧 D 家族中的不适用规则、H3 graph-edge 消融若本来是不同 Rule/Session，必须清楚标注为不同案例；**不能为了故事流畅伪造跨 Rule 的继承链或统一时间线。**

先调查是否已有**同一条经验**能覆盖三幕。若没有，采用 `Case A: new experience lifecycle`、`Case B: conflicting premise`、`Case C: evidence evolution` 的诚实编排，界面显式显示每个案例的来源 ID。仅在必要时，才在隔离运行环境补跑**最小真实**新案例。

### G0.2 输出机器可校验的 Evidence Contract

新增 `docs/H4_HERO_SCENARIO.md` 和机器可读 `h4/hero_scenario_contract.json`（具体路径适配仓库），至少包含：

- 每幕 `case_id`、实际 `run_id`、`session_id`、`candidate_id`、`experience_id`、`rule_id`、`decision_id`、`query_snapshot_id`、`outcome_id`（不存在必须为 `null/UNAVAILABLE`，不得发明）；
- Source Commit/Tree、时间戳及可核对的 `artifact_path`、SHA256、关键 graph query ID/Cypher 与关系边 ID；
- 事实标签：`VERIFIED` / `SUPPORTING` / `EXTERNAL_UNVERIFIED` / `UNKNOWN`、`REPLAY` / `LIVE`；
- 将演示中每一句重要“因果/收益/Agent 采纳/图谱变化”话术映射到真实证据与允许的最强陈述；
- `NOT_INCLUDED` 清单：旧报告或图谱中不可提供的材料；
- 有效的脱敏 `PUBLIC` 数据投影，与 `MAINTAINER_ONLY` 来源清晰隔离。

构建独立验证器 `verify_h4_hero_contract`（命名可调整）：验证所有必填引用、哈希、图边端点、可见权限、时序和状态；故意篡改一条关系/Outcome/Run ID 必须失败。**不能只检查字段是否非空。**

### G0.3 先实现无 UI 演示原型

复用 H3 `h3_demo.py`/`h3_verify.py` 的真实公共观察接口，最小 CLI 输出三幕可追溯 JSON/文本；若缺少足够证据则标 `PARTIAL`/`NOT_AVAILABLE`，不得自动选择参考答案或注入固定 Decision。

**G0 PASS**：三幕可展示的信息与现实相符；可追溯证据契约、脱敏投影、独立验证与至少 3 个篡改负控通过；事实不可展示部分清楚列出；不要求三幕是同一原始 Run。

## 3. H4-G1 — Developer Onboarding（真正从零使用 Aevora）

H3 已证明独立安装/MCP 接入，本轮将该能力转化为**公共用户的短路径**，不要重造 MCP 或编写 Codex 特定编排器。

1. 给出可复现的干净环境启动方案：版本固定的 FalkorDB + 独立 Aevora Core，依赖、健康检查、持久化 RDB/SAVE 策略、退出/清理方法和诊断输出明确。优先复用现有 Docker Compose/CLI，允许必要薄封装；不得用全权限 Docker Socket 或挂载维护者家目录换方便。
2. 提供 `quickstart`（理想上 3–5 个清晰步骤，而不是强行追求单命令）：启动服务 → 生成/安装当前 Codex MCP 配置 → 运行示例普通代码仓 → 真实查询 WHEN/WHY → 进入 Console 观察。演示示例与 Benchmark Participant 无关。
3. 提供自动化检查：端口/图连接、MCP tools/list、`resolve_experience`、`build_evidence_bundle`、`record_decision`（需适当权限）、`propose_experience` 的真实协议行为；断库、无经验、过期 capability、Scope 撤销后的错误可解释、无越权。
4. 外部工程只允许形成未验证观察和待审核候选，不得通过“测试显示 7/7 PASS”自造可信 Outcome 或直接发布。
5. 将 `PUBLIC` 的部署/源码/Docs 与 `MAINTAINER_ONLY` 的 Hidden Oracle、私有 Label、Reference、密钥和证据分开；**Wheel、sdist、容器镜像、前端静态资源、浏览器响应**都做实际负面扫描。
6. 发布 `docs/QUICKSTART.md`、`docs/CODEX_MCP_SETUP.md`、`docs/TROUBLESHOOTING.md`，CI/自动验收脚本必须从**干净 checkout、空 Volume、新 Codex Session**按文档原样执行，不能依赖作者机器里的 `.env` 或旧临时状态。

**G1 PASS**：非 OrderFlow 的用户路径能在干净部署成功；真实 MCP 与真实 FalkorDB，且负控通过；README 中不存在必须依赖维护者私有目录的隐藏步骤。若真实 Codex Provider 不可用，单独标 `BLOCKED`，不能以 Mock 伪造 Live PASS（其它离线安装/协议检查可以独立通过）。

## 4. H4-G2 — Experience Observatory API（统一权威数据接口）

必须**先做后端受控投影，再连接 Web UI**。优先复用 Core 已有服务/查询模型，避免第二套业务逻辑。

### G2.1 最小只读资源

建议能提供下列资源语义（具体 HTTP 路由以现有框架和源码命名为准）：

| 资源 | 最低字段 / 来源 |
|---|---|
| `Sessions & Activity` | Run/Session、模式、来源、原始事件指针、可观察时间、状态 |
| `Decisions` | Decision、WHEN、WHY、关键前提、UNKNOWN、QuerySnapshot |
| `Experiences` | Published/Candidate/Withdrawn、来源、Bounded Scope、规则、Revision |
| `Evidence Graph` | 实际 FalkorDB 节点/边 ID、类型、来源、证据状态、可显示子图 |
| `Governance Timeline` | proposal/review/approval/rejection/publication/withdrawal/feedback |
| `Outcomes` | 可信 Oracle / 未验证外部观察严格分开、验证级别、关联实际 Run |
| `System Health` | DB/MCP 连接及可明确验证的状态，保留故障与不可用字段 |

同一个 Experience/Decision 的 WHEN/WHY **必须来自现有 Aevora Core 的权威查询结果**，禁止前端或聚合 API 自己重新判定 APPLY/VERIFY/ABSTAIN。

### G2.2 Live 与 Replay 的边界

- `LIVE`：读取真实运行中的 Core/Graph/MCP 受控事件；数据不可用就显示 `UNAVAILABLE`，不得降级成预置数组或快照假装实时。
- `REPLAY`：读取经过脱敏、独立可验证的**历史封存**投影；显著呈现 `REPLAY · archive / captured_at / SHA`，不伪装实时模型执行或实时 FalkorDB 写入。
- Replay 支持时间线逐事件查看、图谱历史快照与 provenance 跳转；不得在 Replay 模式调用实际审批、写图或重复导入 Outcome。
- 时间信息保留原始 UTC 与缺失状态，多 Session/多文件仅能展示已有部分顺序，不能推断缺失的跨流因果边。

### G2.3 安全与权限

- 普通 Viewer：只可读取 PUBLIC allowlist 字段和必要的脱敏证据投影；不得接触 Raw MCP payload、完整日志、数据库口令、受限候选/私有业务事实。
- Host/Maintainer：如提供审核/撤回操作，必须经过后端显式身份/capability 校验、CSRF/来源/输入限制、操作审计和幂等/版本并发控制；**浏览器不可直接获得 FalkorDB 管理员凭据**。不具备安全鉴权能力时**宁愿先做只读 Console**，将审批保持在已有可信 Host CLI。
- 默认监听 loopback；不开放匿名公网写入；前端不能任意执行 Cypher、任意路径读文件、运行脚本或写入证据归档。
- 限制图查询深度/结果规模/超时/分页，谨防大图拖垮 Demo；故障要有明确错误状态，不以缓存显示虚假成功。

**G2 PASS**：真实 Core/Graph/Archive 至少能生成三幕所需投影；权限负控、断库、空图、畸形输入、超大查询/泄露扫描实际通过；Replay/Live 在 API 响应中可机器区分。

## 5. H4-G3 — 精简 Web Experience Console（三页，而非通用大后台）

UI 设计目标：**专业、克制、可信、可讲述**。以清晰的信息层级服务竞赛展示，而非堆炫目图表。

### 5.1 页面结构

**Page A：Activity & Decisions（默认首页）**

- Session/Run 列表、真实事件时间线、MCP 工具与执行阶段、Status；
- 选中某次 Decision 后显示 WHEN/WHY、适用前提、关键 Evidence、Outcome（或 UNKNOWN/NOT_EXECUTED）、可追溯 Source；
- 清楚标识当前 `LIVE/REPLAY`、`VERIFIED/EXTERNAL_UNVERIFIED`、运行失败/撤销/无提交，不因 UI 情绪化隐藏错误。

**Page B：Experience Explorer（最重点打磨）**

- Published Experience / Candidate、规则前提与例外、适用作用域、Revision、现行状态；
- 以可聚焦的子图展示真实 `Agent/Run → Decision → Evidence → Rule/Experience → Revision/Outcome` 中**实际存在的关系**，不要为了视觉完整性补齐不存在的节点/边；
- 点击图中节点/边能查看可见的属性、来源 Run/Query ID、真正使用过的 Cypher 或审核事件；
- 标准展示 ACT II：支持路径 / 缺失支持 / 反驳条件导致的决策变化，并解释具体哪个前提缺失；
- 需要放缩、布局稳定、超大图采样/折叠及列表替代，无大面积重叠或只靠节点颜色区分。

**Page C：Governance Timeline（生命周期与追责）**

- Candidate 提议 → 来源验证 → Host Review（限定结论）→ PUBLISHED/REJECTED/WITHDRAWN → 后续检索/修订；
- 可并排比较历史 QuerySnapshot 与当前 Query，显示证据/Rule Revision 的差异；
- 区分 `Trusted Outcome` 与 `ExternalObservation`；
- 若开放管理动作，必须遵守 G2 授权约束；若未通过写入权限安全门禁，则展示只读审计与管理 CLI 引导，不允许做假按钮。

### 5.2 交互验收与视觉质量

- 应有全局 Case/Run/Session 选择与时间模式标识，三页选择对象保持一致；支持具体 Run/Experience 的可复制 Deep Link；
- 页面必须有 Loading、Empty、Disconnected、Forbidden、Partial、UNKNOWN 六类真实状态，网络断开后不得冒充历史缓存为 Live；
- 响应式桌面优先，兼容典型笔记本显示、浏览器缩放/长 ID、键盘导航与可读对比度；不使用会让评委迷失的复杂动效；
- 所有文本、图表、关键状态均有与机器可查证据一致的来源；演示模式**不得切换为合成数据但使用真实案例名称**；
- `UI_COMPONENT_EVIDENCE_MATRIX` 记录每个关键 UI 元素来源 API 字段/图谱查询/档案与状态语义；
- 对实际界面做截图检查及实际浏览器点击流程（若本地浏览器权限受限，记录 BLOCKED 和可复核替代，不声称视觉已检验）。

**技术选型**：优先使用与现有 Python/Core 兼容的薄后端 + 轻量前端；可选 React/TypeScript 等，但不要无理由引入重量级微服务/多租户平台/第二数据库。前端工具链有锁定版本和可重复构建。**先保证行为正确，再打磨专业度。**

**G3 PASS**：3 页真实端到端工作；三幕至少各有可点击的证据链；能够从 UI 追溯到真正的 Run/Query/Graph/Outcome；空/断库和权限错误仍正确；没有无效按钮、伪造实时信息或隐藏错误。

## 6. H4-G4 — Differentiation Demo（用真实机制赢，不靠宣传话术）

此 Gate 与 G0-G3 有关，但独立验收**核心差异是否能被别人理解**。

### 6.1 最小演示脚本

提供一个可重复执行的 `h4 demo` 或独立 Demo Runner，包含：

1. **真实历史**：加载经独立校验的 Replay 档案 / 独立临时 FalkorDB 恢复副本，打开 ACT I 的自然来源候选及限域审核；
2. **证据冲突或支持缺失**：真实查询 Act II，展示 APPLY / VERIFY / ABSTAIN 的合理变化，附 Cypher、实际边 ID 和返回值；
3. **演化**：通过已有可信历史 Observation/Revision/Withdrawal 或**标注为维护者控制实验**的图谱干预，展示现行判断发生变化，历史决策记录不被改写；
4. **真实普通 Agent**：在非 OrderFlow 工程里运行 Codex + MCP，Console 的 LIVE 实际更新（如果网络/Provider 故障，如实记录并有可信 Replay 保底）；
5. **受限对照**：提供已真实运行的 Raw Memory 与 Governance 两组的原始结果和差异，明确**两组都 7/7 PASS**，不得编造 Raw 失败、Token 降低或“提高成功率”。

如果确实需要展示 **Agent 行动因为治理建议而改变**，且旧证据无法证明，请设计并真实运行**一个最小的新成对工程场景**，与预注册输入/约束、隔离环境和独立 Outcome 对照：

- 不得写死模型回答、强行提示正确策略、不按 Episode 名称挑结果；
- 先核对两个条件的任务快照、提示信息、可用工具、权限、模型路由、提交物和 Outcome 是否可比较；
- 失败也保留。如果最终没有可比较的行动差异，改成只展示已验证的“治理建议随证据变化”，不要输出成功率收益说辞；
- **禁止为了 Demo 在旧独立 Hidden Oracle 上改真值或给 Agent 暴露参考补丁**。

### 6.2 同屏可解释性（可以是 Replay，不可装作 Live）

作品最终需能让评委在有限时间理解以下三个问题：

- **WHEN**：为什么当前任务需要 / 不需要检索与使用这条经验？
- **WHY**：哪条证据支持或阻止使用，FalkorDB 中的哪些实际边参与判断？
- **FEEDBACK & ACCOUNTABILITY**：谁提出了经验、谁/什么可信宿主审核了它、结果能支持什么、为什么发生版本变化、无法证明什么？

提供**有证据指针的演示讲述稿**（2–4 分钟的建议叙事），各个画面有明确操作步骤和正常/故障备用演示路径。讲述稿不能比事实声明等级更强。

**G4 PASS**：在全新 Replay 读端真实重放成功、图谱必要性可复核、普通 Live（若 Provider 可用）明确状态、对照如实；主展示流程在现场操作中不会依赖私有维护者口令或手工修改数据库隐藏真值。

## 7. H4-G5 — Competition Release / Final Delivery（完整作品，而非维护者审计包）

### 7.1 可公开的产品工程

- 明确 Public Release 与 Maintainer Audit/Private Benchmark 的边界；公开的产品运行路径只能依赖许可公开的 Aevora Core、Web、示例图谱/脱敏数据和运行工具，不能带 Hidden Tests、Oracle、私有 Reference、真实凭据/密钥。
- 提供可复现的 `README.md`、架构图（最好 Mermaid/SVG）、公开 Graph Schema、关键 Cypher、MCP 工具说明、端到端 Quickstart、Demo/Replay 说明、Known Limitations、License、AI 工具使用披露和清晰的项目来源说明。
- 官方最新要求应由 Codex 在交付时核对官方页面和**本项目适用的提交规则**，写出 Requirement → Deliverable 映射；不要根据旧提示硬编码赛道、截止时间或竞赛资格声明。
- 发布分为 `Core runtime`、`Console runtime`、`public example/replay`、`maintainer-only validation`，防止把 Audit-Lite MAINTAINER_AUDIT 误当普通 Participant/公共素材。

### 7.2 一次真实的陌生用户全流程演练

从干净 checkout/新 Volume 开始，按公开 README 原样执行：

```text
Clone/Install → Start FalkorDB/Core → MCP configure →
Ordinary Codex project → Real WHEN/WHY query →
Console LIVE/REPLAY → Experience Explorer →
Governance Timeline → Proof/Verifier → Cleanup
```

同时实际演练：断网/Provider 错误、断数据库、空图、无候选、撤销过期能力、未授权审批尝试、Archive 篡改拒绝。无能力证明的自动化结果标记 `BLOCKED`，不得合并到 PASS。

### 7.3 完成发布收据与审计

- 保留每 Gate 的真实命令（argv/UTC/退出码/stdout-stderr SHA）、源码 Commit/Tree Hash、公共产物哈希、测试/JUnit、UI 实际截图或浏览器验证记录、Graph SDK/Cypher、MCP events、Run 与 Query IDs；
- 真实新版本完整回归必须覆盖现有的 **1714** 个历史测试身份，以及新增 Core/API/UI/安全/部署断言；缺失/skip/error 明确报告，禁止为了通过删除旧测试或放宽旧 Oracle；
- 适度封存 **H4 Full Archive + 可公开的 Demo Replay/Artifact + H4 Audit-Lite/Reviewer Supplement**。全量历史不可变；脱敏资料缺失写 `NOT_INCLUDED`；独立哈希与篡改负控；一次确定性导出能力核实；
- H4 Live 真实联网运行的源码时代/模型与 Provider 信息按原始记录报告；不将封存后文档/UI 修补版本倒归给之前的 Live Run；
- 检查发布仓库、Wheel/sdist、Docker Image、前端 build、网络 API 都不会泄漏私有评测与宿主授权；本地哈希不称为外部第三方证明；
- 录制/提供可录制的完整 Demo 操作步骤与视频脚本；如当前环境无法实际产出视频，交付 `DEMO_RECORDING_GUIDE.md`，不要标记“视频已完成”。

**G5 PASS**：公共产品路径可复现，Contest Requirements Checklist 有真实引用来源与逐项映射，关键 Demo 不依赖 Hidden Oracle，公开产物通过安全扫描与功能测试，所有剩余风险诚实列出。

## 8. 竞赛最重要的优先级与拒绝范围

### P0 — 必须完成

1. 可追溯 Hero Scenario 与 Evidence Contract（**优先于 UI**）；
2. 无 OrderFlow 依赖的普通开发者真实接入；
3. 真图谱、真 Decision、真 Review 的可信观察接口；
4. 三页小而精的 Console，重要 UI 元素有事实来源；
5. APPLY/VERIFY/ABSTAIN 的实际证据差异 + 真实反馈/修订故事；
6. 公共运行包、文档、演示以及基本安全/复现验收。

### P1 — 只有在 P0 可靠后才做

- 更精美的局部图谱布局、筛选/对比、Deep Link、键盘效率及动画微交互；
- 只读审核历史对比与多 Session 时间线搜索；
- 精简的公开 Host Approval 页面（仅当权限、CSRF、幂等和图并发门禁全部成熟时）。

### 明确禁止作为 H4 硬任务

- 重写 Aevora Core、FalkorDB Repository、MCP Broker、真实 Agent Runtime 或引入自己的 Orchestrator；
- 一次性开发全部 Episode B/C、跨所有 Agent Runtime 的 SDK、生产级多租户 SaaS/公网管理员控制台；
- 研究论文级随机统计研究、成功率显著性结论、模型权重/费用和因果收益推断；
- 花大量时间做三维全图/炫技数据大屏、堆 KPI/测试数量、先把前端做完再找证据；
- 把维护者 Replay 当在线实时推理，或为 Demo 人工编造 Agent 的行为与真假关系。

## 9. 建议文件布局与最小交付清单

目录以实际仓库为准；**不得为匹配建议布局而大规模移动已稳定源码**。

```text
orderflow_incident_lab/
├── aevora_core/                         # Existing authority Core; minimal additive API
│   ├── src/aevora/...                    # Existing Resolver, Graph, Candidate, Feedback, MCP
│   ├── ...                                # Existing install/serve/checkpoint
│   └── docs/...
├── console/                               # 新增，精简前端与所需薄 API（如有）
│   ├── ...
│   └── README.md
├── docs/
│   ├── H4_HERO_SCENARIO.md
│   ├── QUICKSTART.md
│   ├── CODEX_MCP_SETUP.md
│   ├── TROUBLESHOOTING.md
│   ├── GRAPH_MODEL_AND_CYPHER.md
│   ├── DEMO_WALKTHROUGH.md
│   └── COMPETITION_REQUIREMENTS_CHECKLIST.md
├── h4/hero_scenario_contract.json         # machine-verifiable; not fake causality
├── tests/                                  # 现有 + additive API/UI/negative controls
├── AEVORA_H4_BASELINE.md
├── AEVORA_H4_G0_HERO_EVIDENCE_REPORT.md
├── AEVORA_H4_G1_ONBOARDING_REPORT.md
├── AEVORA_H4_G2_OBSERVATORY_API_REPORT.md
├── AEVORA_H4_G3_CONSOLE_REPORT.md
├── AEVORA_H4_G4_DIFFERENTIATION_DEMO_REPORT.md
├── AEVORA_H4_G5_RELEASE_REPORT.md
├── AEVORA_H4_VALIDATION_REPORT.md
├── AEVORA_H4_LIMITATIONS.md
├── AEVORA_H4_TRACEABILITY_MATRIX.csv
└── aevora_validation/...                 # H4 new archives only, no H1-H3 overwrite
```

`AEVORA_H4_TRACEABILITY_MATRIX.csv` 每条至少包含：

`gate,requirement,source_function_or_frontend_component,actual_command_or_browser_step,run_session_candidate_query_reference,evidence_path,sha256,status,limitation`。

## 10. Gate 验收、质量约束和何时停止

### 10.1 分类与否决门槛

- 每个 Gate 独立使用 `PASS` / `PARTIAL` / `FAIL` / `BLOCKED`，并写明实际证据、运行环境与不满足项。
- **H4 Full PASS** 的先决条件：G0–G5 的 P0 都存在真实动态验收；公共发布包无私有资料泄露，Core/Graph/MCP/Console/Replay 均有可重复运行证据；没有伪造可信 Outcome、Replay-Live 混淆和历史篡改。
- **H4 CONDITIONAL PASS**：产品主体验与关键证据真实成立，但仍保留已知且可明确隔离的运行时/安全或部分上线能力限制；真实 Demo 路径不能因关键未解决事项必然失败。
- **FAIL**：FalkorDB 不再影响真实决策；伪造经验关联、Agent 采纳或隐藏 Raw 结果；公开泄漏私有 Oracle/Host secret；靠虚构 Mock/固定字符串冒充真实 Live；破坏 H1–H3 历史。
- **BLOCKED/PARTIAL**：有可重复明确环境阻碍时，保留失败、上下文与替代 Demo，不强行升格 PASS。

### 10.2 实现约束

1. 先按 G0 只读真实源码/证据并输出短审计，接着**按 Gate 直接执行，不停留在写计划**；每个 Gate 实际完成、测试并记录，再进入下一个。
2. 不把“报告有 PASS”替代原始事件、实际图查询、真实浏览器截图和真实普通项目 Codex 调用；没有 Provider 凭据时保留 UNKNOWN/BLOCKED。
3. H3 G0 的 UDS EPERM / AOF139 / EOL / shared-kernel 安全限制**只做会直接阻断公共 Quickstart/Contest Demo 的定向修复**；如不可安全修复则隔离、标注和降级流程，不无限期纠缠生产级难题。
4. **Host/Viewer/Agent 权限必须分层**，保护 source verification、host approval、VerifiedOutcome、private graph、秘密与运维能力。展示服务默认 loopback 最小权限。
5. 全过程保持 source epoch、测试身份、原生时间线与历史失败真实；不要改旧 Oracle、私有 manifest、reference、旧 Full/Lite；新测试不能通过损害旧测试获得 PASS。
6. Console 的图谱、时间线、Decision 可以使用真实只读公共投影，**不要为了可观测性去扩大 Agent Runtime 对维护者系统的可见性**。
7. 优先选一个“最小但完整”的可部署作品，避免 H4 演变成无限期工程；达到 G5 P0 验收后停止，不自动开始 H5 或开发未批准的扩张目标。

### 10.3 Codex 第一轮执行摘要要求

首先向我输出不超过两页的：

- **H3 source baseline**：当前实际源码/版本/可重用 API 与已知限制；
- **Hero truth table**：3 幕各自已有真实证据、当前缺失项，是否可合并成一个案例（不能就显式 Case A/B/C）；
- **Implementation footprint**：会修改/新增哪些文件、公共构建会不会带出私有数据、UI/Host 权限如何隔离；
- **Gate plan**：按 G0→G5 顺序的实际验收命令与停止条件。

随后开始实现 G0；不是只输出一堆待办或要求用户反复确认。若发现本任务书某条案例关系与真实源码冲突，**以真实原始证据为准，明确记录修正并继续执行**，不能悄悄补造不存在的 Source/Outcome。

---

## 最终产品叙事（用于内部验收）

> **Aevora 不只是让 Agent 记住过去。它让多个 Agent 能够根据可核查的证据，判断经验何时适用、为何可信，并对实际反馈负责，从而持续改进可共享的经验。**

H4 不需要声称“统计证明 Agent 成功率提高”。它需要用真实工程、FalkorDB 的决策必要性、可解释的经验治理以及低摩擦的用户路径，展示这是一个完整且具有差异化的**竞赛作品**。

**完成 H4-G5 后停止，交付可供用户评审的代码、Console、真实 Demo、公开文档、H4 验收报告和按版本封存的证据。**
