# Aevora H3 — Experience Lifecycle & Competition Readiness

> **版本**：v1.0 · **状态**：正式开发任务（供 Codex 执行）  
> **基线**：Aevora H2 `CONDITIONAL PASS`；在 Codex 本机重新核对冻结 Commit、最终修复版本与当前工作树后执行。  
> **核心定位**：在现有 Aevora 框架内补全经验形成—准入—使用—反馈的**可审计产品生命周期**，并验证独立于 OrderFlow 的普通 Codex 接入。  
> **竞赛优先**：真实可运行、差异化价值可见、低摩擦部署、独立验证。不要把论文级显著性检验当作本轮交付要求。  
> **实施顺序**：H3-G0 → H3-G1 → H3-G2 → H3-G3 → H3-G4；各 Gate 独立验收。H3 完成后停止，不自动开展 H4。  
> **品牌**：现行项目 **Aevora**；GraphSwarm 仅是历史来源名。OrderFlow Incident Lab 与 FalkorDB 保持各自独立身份。

## 0. 唯一目标与明确禁区

H1 已经打通：真实 FalkorDB → WHEN/WHY → Codex MCP → OrderFlow 独立 Outcome → Trusted Feedback → 另一 Session。H2 已增加：冲突与版本治理、QuerySnapshot、D-v02、真实新场景挑战和冷恢复。**这些基础不能重建、降级或改写历史结果。**

本轮交付的关键新能力是：

```text
真实 Agent 执行任务，产生可观察策略与真实证据
           ↓
未受信任的候选经验（含来源、前提、策略原则、反例/未知）
           ↓
可信宿主验证来源、审查证据、决定有限作用域的准入/拒绝
           ↓
Aevora Experience Graph（FalkorDB、追加版本与审计）
           ↓
另一新 Agent Session 经 MCP 查询 WHEN/WHY，看到实际新经验
           ↓
实际决策/行动 → 可用的可信 Outcome 或明确的未验证反馈 → 再演化
```

加上第二条独立产品路径：

```text
一个不是 OrderFlow Participant 的普通 Codex 工程项目
    → 经最小配置接入 Aevora MCP → 获取有来源的建议和依据
    → 可以提交未验证候选/任务结果，但不得自证为 VerifiedOutcome
```

必须避免：

- 凭一次任务 `PASS` 就把策略标为“对 Agent 有因果增益”，或者自动发布为普遍适用的可靠经验；
- 把 `record_decision`、自述 `adopted=true`、测试 stdout、普通项目的自述 PASS 当作独立 Verified Outcome；
- 让参与者自报 `source_type=natural_agent_run`、`verified=true`，或自造 Run ID/哈希得到可信来源；
- 退化成 JSON/SQLite 静态检索替代 FalkorDB，或按照 Episode ID/策略关键字硬编码决策；
- 修改 OrderFlow Hidden Oracle、私有标签或参考补丁去迎合 Aevora；
- 将 Hidden 测试、参考答案、Graph 管理员口令、维护者全文证据、长期密钥暴露到普通 Agent/MCP；
- 开发新 Agent Orchestrator、生产级多租户 SaaS、复杂 Dashboard、完整 B/C 或多 Runtime SDK；
- 虚构 demo、原生 MCP 调用、补丁、Outcome、反馈归因或模型/费用事实。

## 1. 基线审计：先看真实工程树

使用真实本机工作树、独立冻结版本、H2 Audit-Lite、Git 与封存收据，不依赖单篇总结。优先审查：

- `AEVORA_H2_VALIDATION_REPORT.md`、`AEVORA_H2_LIMITATIONS.md`、`AEVORA_H2_DELIVERY_ACCEPTANCE_REPORT.md`、`AEVORA_H2_G3_NATIVE_E2E_REPORT.md`；H2 最终 Source/Run/Release Commit 的对应关系；
- `aevora_core/src/aevora/{models.py,graph_repository.py,experience_resolver.py,governance.py,feedback.py,mcp_server.py,mcp_broker.py,orderflow_outcome_bridge.py}`；
- `integrations/{aevora.py,experience.py,codex_agent.py}`，`benchmark/{runner.py,participant_sandbox.py,submission.py}`；
- `aevora_core/docs/{GRAPH_SCHEMA.md,H2_GOVERNANCE.md,TRUST_BOUNDARY.md,CODEX_INTEGRATION.md,H2_REBUILD.md}`；
- H2-G2 D-v02 的源码及独立 Oracle；H1/H2 Full 归档不得被更名、补写或覆盖。

**已知历史结果（不是 H3 当前测试成绩）：**

- H2 真实工程挑战两次、各 `36/36` Hidden PASS；各自三名原生子 Agent；两次补丁各有不同 SHA，可信反馈及冷恢复新 Session 查询有原始归档。
- H2 冻结后 `1625/1625` 开发者回归；导出器修复后的最终版本 `1655/1655`，**该最终修复版本并未再执行真实联网挑战**。
- H2 AOF 回放存在 `SIGSEGV / exit 139`；RDB 仅确认最后完成的 SAVE/checkpoint 及对应 RPO，不承诺零损失。
- D-v02 Native Sandbox 原 6 项公开 UDS 测试在 `.bind()` 遇到 EPERM；共享内核敌对隔离仍 PARTIAL；底层运行时存在 EOL 问题。
- 历史原始 Run、源码身份、测试身份和封存证据不变；本轮的任何新增测试成绩必须按 H3 实际版本重新报告。

**基线 Gate 产物：**`AEVORA_H3_BASELINE.md`：Git status、H2 live/release/export-fix 版本、当前工作树与冻结版本差异、可复用接口、已知限制、H3 新功能边界及实现计划。不要因根 README 陈旧就认定 H2 未完成，也不能因为 H2 报告写 PASS 就省略代码核查。

## 2. H3-G0：可用性与交付边界加固（短而硬）

### G0.1 已知 Native 公开测试兼容性

对 D-v02 Participant 内的 6 项 UDS/Clock 公开测试 `.bind()` EPERM 进行真实定位：明确宿主与 Native Sandbox 的 namespace、cgroup、socket、路径和能力差异。**优先提供不扩大 Participant 权限的修复**；不得为了让测试 PASS 放开私有文件、`CAP_SYS_ADMIN`、Docker Socket 或任意 Host IPC。若当前平台无法安全修复，给出独立可执行的等价公开测试入口、保留原 EPERM，并将 Native 兼容性标记 PARTIAL，而不能抹去或跳过失败。

### G0.2 发布与文档边界

- 更新根 `README.md` 与 `aevora_core/README.md`：以 H2 实际源码与已验收能力为准，纠正“D-v02 未实现”等过时叙述；明确 H3 未完成前的状态。历史文档不批量改名。
- 审计根 `pyproject.toml`、Wheel/sdist 与发布包数据：不能把 `evaluator/private_manifests/`、`private_labels/`、`reference_patches/`、Hidden Oracle、内部凭据误打进普通用户/Agent 分发包。若现有内部分发必须保留，建立显式 `MAINTAINER_ONLY` vs `PUBLIC/AGENT` 构建边界和相应自动化检查。
- 保持已证实的 RDB checkpoint、健康检查和重建路径；AOF 139 不在 H3 无限制修复。记录运行时 EOL 风险及可实施的升级策略，不为赶 PASS 虚报已升级。
- 从干净 checkout 验证最小部署/查询，保留当前 Commit、依赖、来源指纹；所有破坏性实验在隔离 Volume/端口运行。

**G0 验收：**有修复前后动态复现与权限差分、分发包私有资料的负面扫描、干净安装/基本查询、A/D/D-v02 有效回归及明确的残余限制。不能安全解决的项为 PARTIAL，不阻断与之安全隔离的 H3-G1/G2 实现。

## 3. H3-G1：Experience Candidate → Trusted Admission → Published Experience

### G1.1 增量数据模型和状态机

优先复用已有 `GraphRepository`、`ExperienceRevision`、`Evidence`、`QuerySnapshot`、`Feedback`、`governance.py` 及 Schema 1.1。新增必要的候选、准入和发布记录，不重造同名核心；最终设计以真实现有代码为准。

建议最小状态流（名称可调整但语义不得丢失）：

```text
PROPOSED (不可信候选)
  ├─ REJECTED (拒绝，理由、来源保持)
  └─ EVIDENCE_PENDING (资料不足，不能直接推荐)
          ├─ REJECTED
          └─ ADMITTED_BOUNDED (可信宿主准入，明确作用域与强度)
                    ├─ PUBLISHED (可供相应条件下检索)
                    └─ WITHDRAWN / SUPERSEDED (追加事件；历史仍可追踪)
```

**可信准入与“证明有用”是两种不同判断。**

- Candidate 包含：稳定 ID、不可变候选正文/摘要哈希、策略原则、必要前提、已知不适用条件、适用作用域、未知字段、来源引用（Run/Query/Decision/Observed Action/Submission/Outcome，如果实际存在）、提出者与时间、候选 schema 版本。
- 溯源分开：`natural_agent_run`（由真实宿主运行证据确认）、`maintainer_seed`、`synthetic_or_test_fixture`、未验证外部来源。Agent 提议不能改变宿主核定类型。
- **VerifiedOutcome 证明一次工程提交通过独立测试，不自动证明某条原则带来了增量收益。** 候选可以得到“具备真实来源且在某个受限环境存在支持证据”的准入，不得自动升级为“普遍可靠/促进成功”。必要前提未知时保持待验证。
- 使用 H2 已有规范化查询/Revision/`SUPERSEDES`/事实 Scope 机制；旧 Experience、Decision、Snapshot、Outcome、证据边不覆盖或删除。拒绝/撤回/重复导入及冲突发布都留可追踪审计事件。
- **所有新经验的发布必须是可信宿主独立批准或受明确可审计、可拒绝的规则门禁控制**；即使支持受信任的程序化审核，也不能让 Participant 通过自己的 MCP 工具获得发布权。

### G1.2 Agent 侧接口与可信宿主边界

可在现有 MCP 工具中新增最小 `propose_experience(...)`，但其请求**永远是未受信任的提议**；对于现有 MCP 工具的版本与行为保持兼容。可信宿主的 `review/admit/publish/reject/withdraw` 使用独立、最小授权的 Host CLI/API，**不得作为同一 Participant 能调用的特权 MCP 工具**。

- 源运行与 Agent 身份由 Host 的 per-run capability/原生事件核定，不能相信请求里自填的 `run_id` / `verified=true`。
- 不可信内容须经输入长度/数量限制、字段类型、引用关系、Cypher 参数化、路径 allowlist、敏感词/路径脱敏和 prompt-injection 处理；拒绝跨 Run 冒充和重放。
- 未完成审核的候选，不得通过标准 `resolve_experience` 被当作已发布经验。可在维护者审计视图中明确显示候选状态，不悄悄删除。
- 对相同 Candidate ID 的幂等操作应返回可重放的确定结论；同 ID 不同内容拒绝并留审计；竞争准入、撤回后发布、版本分叉、过期审阅授权必须 fail closed。
- 原 Agent 源证据可长期追溯，但普通 MCP 只返回公开可用、脱敏且有作用域约束的证据摘要。

### G1.3 最低真实场景

1. 从**有实际来源引用**的一次 Codex 工程运行（可用 H2 已封存的真实源作为初始集成样本，但不得篡改历史、不能冒充 H3 新自然 Session）提炼候选策略，完成候选/证据关联、可信审核、有限作用域发布，并由**不同的新 Session** 实际查询到。至少一次真正的新 H3 Codex Session 要能调用 `propose_experience`，若调用受阻须如实记录该 Gate 为 PARTIAL，不能补写事件。
2. 构造一个可审查的无证据、错误作用域或仅有自述 PASS 的候选，确保拒绝/保持 PENDING，不进入公开建议链。Fixture 必须明显标注，不能计入自然 Agent 的经验产量。
3. 修改/撤回支持证据，或发布显式冲突 Revision，证明后续 WHEN/WHY 输出变化；旧 QuerySnapshot、候选与决策记录保持可回放。
4. 重启实际 FalkorDB/恢复受控 checkpoint 后，候选—审核—发布—撤回各状态和引用均可追踪；断库不可静默回退静态建议。

**G1 验收：**真实 FalkorDB 写入、来源/授权校验、拒绝和冲突边界、真实新 Agent 候选事件、审核/发布、另一 Session 检索的可复核链路。若仅通过脚本直接写入预制 Experience 或只验证 mock schema，不得认定 G1 PASS。

## 4. H3-G2：普通 Codex 项目接入（不依赖 OrderFlow Runner）

**目标：**Aevora 不仅是 OrderFlow 的外挂；真正普通的工程项目可经稳定 MCP 工具使用经验，同时保持来源和可信评测边界。

### G2.1 最小稳定用户路径

提供可从干净目录运行的最小体验，例如：

```text
install / start core → connect Codex MCP → resolve and inspect evidence
  → record decision / propose candidate → inspect provenance and status
```

具体 CLI/配置名称以 Codex 本机当前支持方式为准，禁止写未验证的复制即用命令。提供项目级最小权限配置、Server Health、凭据外部加载、连接/断连报错、示例环境变量和卸载/清理。独立使用时不可要求运行 OrderFlow Registry、其 Sandbox 或访问其私有 Oracle。

### G2.2 实际普通项目验证

- 选择一个**非 OrderFlow** 的小而真实、具有自己的版本控制和测试的 Python 工程项目；它不能是临时空目录或复制自 Benchmark 的任务/参考补丁。可使用受控公开/自建维护者示例，但必须明确它的来源、任务和是否预置正确策略；不能把简单 Hello World 冒充复杂实际部署。
- 在全新 Codex Session 中，真实连接 Aevora MCP，完成至少一次 `resolve_experience`、`build_evidence_bundle` 和真实决策/行动的可追踪调用（若 Agent 不调用，保留实际事实）；读取公开经验而不接触内部 Oracle。
- 证明连接的身份与工作目录隔离、正常断连/重连、空图/断库情况、授权撤销、最小安装/卸载路径；尽可能让另一个独立新 Session 复现查询。
- 普通工程项目自运行的测试结果仅作为 `EXTERNAL_UNVERIFIED` 或类似未验证 Outcome/Observation，除非存在独立可信评测机制且确实有完整可审计来源。**没有 OrderFlow 的隐藏评测不等于不能使用 Aevora，也不等于可以伪造 VerifiedOutcome。**
- 不要求每个外部普通项目都能自动发布经验；查询可用、候选入口可用、无可信 Oracle 时能安全停在待验证状态就是合格能力。

**G2 验收：**干净项目端到端安装/连接/查询、原生 MCP 工具事件、权限负控、普通项目不会获得隐藏评测资料或管理员凭据；外部结果没有被伪装为 Verified。不得仅以已有 OrderFlow 的 MCP 测试取代。

## 5. H3-G3：核心差异价值的有限真实对照

本 Gate 是竞赛的**可信价值展示检查**，不是论文式统计研究，也不是预置答案的戏剧化演示。

建立至少三类可复现情景：

- **正迁移**：前提有真实支持链，WHEN/WHY 给出有限作用域 APPLY；公开证据链与适用条件可核查。
- **负迁移拒绝**：一个语义上相关、但实际先决条件冲突的经验被拒绝或要求调查，例如进程内锁在独立 Worker 环境；不可依赖 Episode 名称判断。
- **新经验演化**：前一轮真实提交形成候选，通过审核后新 Session 能获得更新信息；新的反例/撤回事件也能够影响后续查询。

强制完成：

1. FalkorDB 图必要性对照：移除或更换关键 Evidence/Revision 边、断库以及恢复后，WHEN/WHY 的变化或失效须来自**真实 Cypher 图查询**。
2. 有限 `Raw Memory vs Aevora Governance` pilot：同一原始经验、相同可见上下文及尽可能相近的 Agent 任务条件；Raw Memory 仅提供无治理的经验文本，Governance 提供实际 WHEN/WHY/证据链。禁止把“RLock 错误、必须选原子事务”等答案直接写入任何 Pilot Prompt。
3. 如进行原生 Agent pilot，保留所有尝试、真实补丁、评测与资源状态；区分策略推荐差异、决策与任务完成，不得以一个成功案例推断成功率提升或因果效应。
4. 证据样本必须标识来源：历史自然 Run、受控维护者来源、模拟决策 Fixture、H3 新自然 Session。对比条件若不公平则在报告中记为探索性演示，不宣传为严格科学对照。

**G3 验收：**三类证据情景、图必要性验证、至少一个诚实 Raw Memory 对比（即使结论为无明显差异也能通过诚实性审查），没有事后篡改上下文或隐藏评价；不要求统计显著性。

## 6. H3-G4：可观察性、审计导出与竞赛演示基础

**只做小而完整的产品观察面，不在 H3 开发大型 Dashboard。** 推荐先实现稳定的 read-only JSON/CLI 导出，必要时附带轻量静态 HTML/本地 Viewer（不得以页面代替真实数据库）。

应能按 Run/Query/Candidate/Experience 的真实引用展示：

- 任务上下文（public、脱敏）及候选经验；
- WHEN `APPLY / VERIFY / ABSTAIN` 与 WHY 支持/反例/未知前提及图谱路径；
- 未受信任的 propose/record_decision 与可观察代码/工具行为的区别；
- Candidate 审查轨迹、发布/拒绝理由、ExperienceRevision 变化；
- VerifiedOutcome 的权威来源/非 Verified 外部 Observation 的身份差异；
- 新 Session 读取反馈前后的差异和 Snapshot 版本。

最低要求：一个能**从新干净部署或受控原始数据重放执行**的 `H3-demo` 和一个 `H3-verify` 脚本/CLI，自动产生自足的事件时间线、Evidence Bundle、关系图数据和独立验证结果，不需要人工剪辑日志或临时改 Prompt。支持导出脱敏的竞赛评审包，但绝不能包含私有 Oracle、参考补丁、维护者密钥、跨 Run 私有证据。保留失败、UNKNOWN 和 NOT_INCLUDED 清单。

**G4 验收：**从真实 Run/Graph/Report 的读取结果生成的时间线与决策图数据，与原始事件和 SHA 一致；能复核至少一条候选被审核、一个外部 Codex 接入、一个负迁移情景和一次真实 Outcome 的演化。无前端 UI 不影响本 Gate PASS；若有 UI 必须能关联真实图数据。

## 7. 共通可靠性、测试、运行与证据标准

1. **真实源码优先。** 若本任务书对接口的建议与工作树实际冲突，按当前实现做最小相容扩展；记录旧→新变更映射，不擅自删除稳定公共工具。已有 MCP 工具 `resolve_experience`、`build_evidence_bundle`、`record_decision` 的安全与含义不能退化。
2. 每个 Gate 提交独立报告与源码 Commit/Tree Hash；包含：起始版本、修改文件、真实命令和退出码、真实图/Tool/Oracle 响应、JUnit、负控、异常、剩余限制、Gate `PASS/PARTIAL/FAIL/BLOCKED`。
3. **最后完整回归**必须覆盖当次可用测试集、H2 原有 1655 个测试身份和旧 A/D-v01/D-v02 的有效回归；注明平台依赖的 skipped/blocked。不能把以前的 1655/1655 当作本轮新结果，也不能靠删除旧断言获得通过率。
4. H3 必须真正连接 FalkorDB，包含 fresh graph、幂等、断库、隔离 Volume SAVE/restore、对关系边的动态干预；单元 Mock 不能替代真实图查询和新 Session 原生 MCP 事件。
5. MCP 管理与可信发布权只在 Host；执行期的 per-run Capability 仍受限。跨 Session 复用的是有作用域的公开知识，**不是**跨 Session 授权重放。即使发布候选后重启也不能让旧会话的授权自动复活。
6. 继续使用 completion-aware；不能以任意固定总 wall-clock 时间杀死仍然活跃的慢 Gateway，保留人工取消、有限资源与连接故障处理。保留 `ERROR/TIMEOUT/CANCELLED/NO_PATCH/PROVIDER_ERROR` 分项、真实失败及相应分母。
7. 查询路径必须实际依赖 FalkorDB；不得用固定字符串决策或静态缓存代替。处理并发审核、失联、Snapshot 时序、重放/撤回边界时不能默默覆盖历史证据；无法提供原子一致性证明则明确写限制。
8. 保留 H1/H2 Full 与 Audit-Lite 原封版本，以及 H2 两次原生 Run 的 patch hash、原测试身份、私有真值、Git 证据。H3 若重跑必须生成**新的 Run ID**，旧结果不得追溯升级。
9. 本地 Full Archive 保留，面向云端审查的 **H3 Audit-Lite** 包含核心变更源码与 Graph Schema/Cypher、Gate/JUnit、匿名化 MCP 原始事件、候选/审核/发布/撤回 Trace、Graph 快照、外部项目接入收据、关键 Outcome、Run/Source/Archive SHA 与 `NOT_INCLUDED`。候选和 public Graph 数据必须脱敏；私有 Oracle/Reference 与维护者秘密不可写入公开 Lite。
10. 实际 Secret 值及独立哈希不写入交付材料；校验 Lite 重导出确定性、独立校验和字节篡改拒绝。只有可由现有工具真实确认的事实可标 PASS，单独记录不可证明的模型权重、费用、因果效果及安全边界。

## 8. 建议工程改动位置（非强制目录重构）

优先考虑在已有 `aevora_core/src/aevora/` 添加或扩展：

```text
candidate.py / admission.py       # 候选与可信准入；具体命名审计后决定
models.py                          # 来源类型、候选与准入状态
schema / graph_repository.py       # FalkorDB Candidate/Review/Published 关系
experience_resolver.py             # 仅检索已发布且作用域合规的经验
mcp_server.py                      # Participant 可提议，不可可信发布
feedback.py                        # 可信 Outcome 仍与策略贡献分离
scripts/aevora_*                    # trusted-review CLI、external connect、demo/verify
integrations/                     # 普通 Codex 使用最小 adapter
```

对 OrderFlow 只添加**薄的可信来源适配器**（如必要），不要在其 `evaluator/` 编写 Aevora 的准入治理算法。真实演示不应依赖修改原任务真值。

## 9. 交付清单与验收矩阵

建议保留以下内容（实际路径在 G0 明确）：

```text
AEVORA_H3_BASELINE.md
AEVORA_H3_G0_READINESS_REPORT.md
AEVORA_H3_G1_EXPERIENCE_LIFECYCLE_REPORT.md
AEVORA_H3_G2_EXTERNAL_CODEX_INTEGRATION_REPORT.md
AEVORA_H3_G3_VALUE_CONTROLS_REPORT.md
AEVORA_H3_G4_OBSERVABILITY_REPORT.md
AEVORA_H3_VALIDATION_REPORT.md
AEVORA_H3_LIMITATIONS.md
AEVORA_H3_TRACEABILITY_MATRIX.csv
AEVORA_H3_RELEASE_REPORT.md
H3 Full Archive + H3 Audit-Lite + SHA256 + NOT_INCLUDED
```

`TRACEABILITY_MATRIX` 要做到 **需求 → 源码函数/行 → 命令 → 原始 Run/Query/Candidate ID → Evidence 文件 → Gate Verdict**；失败与 `PARTIAL` 同样要能追溯。

最终 `AEVORA_H3_VALIDATION_REPORT.md` 必须分别报告：

| 维度 | 通过的实际必要证据 |
|---|---|
| Release / Security / Known Limits | 新源码可部署、分发隔离、Native 已知问题诚实处置 |
| Candidate Lifecycle | 真实 Agent 提议；真实来源核查；Host 审核发布/拒绝；持久化及撤回可审计 |
| Core Governance | 实际图谱驱动适用性，未发布候选不混入 WHEN；历史 Revision/Snapshot 保留 |
| External Codex MCP | 不依赖 OrderFlow Runner 的普通项目完成真实工具查询与行动 |
| Trusted Outcome | 无私有 Oracle 时不伪造 Verified；可信来源可闭环回填 |
| Value Controls | 正向/负向/演化场景和图谱必要性；Raw Memory pilot 原样记载 |
| Reproducibility & Audit | 完整新回归、Full/Lite、源码指纹、可执行复现链 |

**H3 Overall PASS**：G1、G2、G3、G4 的真实功能证据全部具备，G0 已知 P0 风险不因开发新增安全回归；所有关键操作有独立复核路径。  
**H3 CONDITIONAL PASS**：核心生命周期和外部真实接入成立，但已知可控平台限制或部分 G0/G3 边界仍未关闭；限制必须明确，不伪造升级。  
**H3 FAIL / PARTIAL / BLOCKED**：不能真实形成候选→可信准入→新 Session 使用，或没有普通工程接入，或泄漏私有结果/伪造可信反馈；其它 Gate 可以独立报告成绩。

## 10. 执行节奏与停止规则

- **先只读 G0**：输出 1–2 页的基线与模块复用/缺口清单，随后按本任务书**直接继续实现**，不因等待讨论而停在文档。
- G1 是本轮核心；优先让最小真实候选生命周期成立，再补边界与负控，不要先开发大 UI。
- G2 必须是非 OrderFlow 的实际工程项目，不能通过原 Benchmark 改名实现。
- G3 只做能反映机制价值的有限真实对照，避免吞没整轮开发时间。
- G4 优先稳定的观察与导出数据，复杂页面留给 H4。
- 每个 Gate 通过/受阻先在独立报告中落地，再进入下一 Gate；资源与可信系统约束阻断时诚实报告，不伪造测试结果。
- **完成 H3 后停止**。不自动建设 H4 Dashboard、不开展大规模正式 G0–G3 随机对照、不开发完整 B/C，也不私自改动比赛提交/赛程安排。

---

**H3 最终成功标志：** 一个真正新的经验可以从 Agent 的可观察工程行为出发，在可信证据约束下成为有边界的可查询知识；另一个独立 Agent 能在普通工程项目中使用它；审查者能看到真实图关系、判断依据与反馈演化，同时不把未经证明的因果收益宣传为事实。
