# Aevora Gen 1.5 — Repository Consolidation & Architecture Cleanup

**Codex 正式工程任务 v1.0**  
**阶段定位：第一代完成后的独立仓库整顿；第二代功能开发之前的工程基线整理。**  
**对象：本地完整维护者 Git 仓库及其关联的独立 Release/Worktree，不是只针对 H4 公开产品 ZIP。**  
**目标：在不丢失既有能力与可信证据的前提下，建立结构清晰、职责分明、可测试、可交付的 Aevora Gen 2 开发基线。**

> 重要：本指令根据已审查的 H1–H4 源码快照与验收证据制定，但本次尚未直接读取 Codex 所在机器的**完整最新本地仓库**。所有目录布局、历史文件归属、Git 状态与迁移细节，以 Codex 对实际本地文件的只读调查为准。不得将参考目录当作已经确认的本地事实。

## 0. 绝对边界：此轮是 Gen 1.5，不是 H5 或 Gen 2 功能迭代

1. **允许**：目录梳理、模块职责明确、代码去重、未使用入口的安全弃用、import/CLI 迁移、构建脚本整理、文档重组、开发命令整合、测试归档组织、维护者与公开产品分层。
2. **不允许**：重新实现 WHEN/WHY、改变证据或发布准入判断、重建 FalkorDB 图模型、替换 Agent Runtime、重写 OrderFlow Oracle、扩展 B/C、添加新 Agent 功能或把尚未验证的结果升级成 PASS。
3. **不得删除/覆盖**任何 H1–H4 已封存 Full/Lite、原始模型事件、私有 Oracle/Reference、历史验收报告、真实失败、原始执行收据、关联 SHA、源版本/Run ID。它们是历史事实，不是“清理垃圾”。
4. **不得执行** `git clean -fdx`、盲目的 `rm -rf`、整仓 reset、`git add .` 或其他可能波及未跟踪证据、工作树、数据卷、秘钥和历史文件的破坏性操作。
5. **不得上传/推送** GitHub 或其他远程；不得启动第二代开发、正式赛事提交或重新编造比赛演示。任何本地提交应在新建、隔离的整顿 worktree/branch 中进行，原维护者根工作区保持不被意外 stage。
6. 原私有任务真值/隐藏测试、Host/Gateway/DB 凭据及模型原始事件不能进入公共 wheel/sdist/source ZIP/Docker image/Console 静态资源。不能为了方便重构放松这一发布边界。
7. 这次工作应**真实整理工程结构**，不能只添加 `docs/`、改 README 或输出虚构的架构图就报告完成。

## 1. 冻结 Gen 1 基线（G0：Baseline & Inventory）

开始前，只读查明：

- 全部 Git worktree、branch、HEAD、index、dirty/untracked 状态及不同 Release 源码；对照 H4 已记录的本地最终源码 Commit `871572fc38d3110b10dc8f25097490109a2bb261` 和公共产品独立 Commit `00c43f53ce8d2c04af956d6b88c601efc17dfa7b`，但**不可假设它们是当前 root HEAD**。
- 真正的运行产品源码、Core、Console、Agent Integration、维护者 Orchestration/Benchmark、Evaluator、Private Truth、测试、一次性脚本、生成文件、缓存、日志、历史证据、外部依赖/数据卷分别在哪里。
- 文件规模和占用大头：Git tracked/untracked 与 evidence/artifact 在磁盘占用和数量上分别统计，不能将归档中数十万证据文件误当活动源码文件。
- 每个入口（CLI、MCP Server/Proxy/Broker、FalkorDB Repository、Console Server、Benchmark CLI、Host Validator、构建/发布脚本）的实际调用路径及运行依赖。
- 采用静态搜索 + Python import graph + packaging manifest + 运行命令 + 测试覆盖交叉判断，不因文件名含 `h1/h2/h3/h4/old/legacy` 就判为废弃。
- 有条件时收集 H4 当前基线的真正运行结果；无法运行的记录为 `ENVIRONMENT_BLOCKED`，保留对应原始 H4 JUnit 作不可替代的历史参照，而不是声称重跑通过。

**G0 必须形成**：`GEN1_5_REPOSITORY_INVENTORY.md`、`GEN1_5_DEPENDENCY_MAP.md`、`GEN1_5_BASELINE.json`、`GEN1_5_RISK_REGISTER.md`。所有文件数量/可删除项要有脚本或命令来源，不得按直觉估算。

**G0 基线锚点（须验证对应版本与原始证据，不可盲信）**：H4 1802/1802 开发者测试，继承 H3 1714 身份；原有 H4 原生外部修复 7/7、`EXTERNAL_UNVERIFIED`/0 VerifiedOutcome；D-v02 Buggy 28 PASS/8 FAIL、Reference 36/36 PASS；G0–G5 的真实 Hero/Web/Core/CLI 契约；H4 记录的 215589 历史文件、79 历史测试源码、39 私有真值、25 旧报告和 Full 20310 文件封存验证。**数字不是任意新版本天然应有的断言，应按来源和测试命令对应其真实冻结 epoch。**

## 2. 先冻结架构分层与迁移蓝图（G1：Ownership & Architecture Blueprint）

以模块职责和依赖方向为主，不以阶段名称作为长期业务目录边界。将仓库文件逻辑划为以下六类，并给每一项指定唯一 owner：

1. **Product Runtime (PUBLIC)**：Aevora Core、ExperienceResolver、Evidence Bundle、Governance、Candidate Lifecycle、Trusted Feedback、GraphRepository、MCP Server/Client/Proxy/Broker；任何必须保留在 Host 的组件单独标记 Trust Boundary。
2. **Experience Console (PUBLIC)**：前端、只读 Observatory API、Live/Replay 读取接口、公共投影、局部 Graph UI；不得把读取/UI 代码混入核心治理引擎。
3. **Integrations & Developer UX (PUBLIC)**：Codex MCP 快速接入、核心 CLI、bootstrap、普通项目示例、配置样例；独立于 Benchmark Runner。
4. **OrderFlow Benchmark / Maintainer (PRIVATE/CONTROLLED)**：Runner、独立 Evaluator/Hidden Oracle、Reference、Fixture、可信 Outcome Adapter、隔离和维护者实验脚本；不得自动成为公共产品依赖或打包资产。
5. **Validation / Dev Tools (SCOPE-BOUND)**：当前有效的单元/集成/安全负控、CLI/浏览器合同、Benchmark 验证、发布检查工具；淘汰/迁移历史脚本时留下原始证据与映射。
6. **History / Evidence / Generated (IMMUTABLE/IGNORED)**：Full/Lite、旧报告/Raw Rollout/日志/DB 备份、构建 dist、缓存、浏览器 traces、临时 worktrees；保留证据的物理位置和哈希记录，不让它们污染主开发目录/公共制品。

**期望的依赖方向**：Console / Integrations → Core 的受控接口 → FalkorDB；Benchmark 维护者适配器 → Core 的可信接口，但 Core 的运行时安装不依赖 Benchmark/Evaluator/Hidden Oracle。公共 Replay 是明确的、带签名/哈希校验的发布资产，不能冒充 Live。

参考目录（**仅供比较，不能直接按此强行搬迁**）：

```text
<repo>/
  README.md
  docs/                      # 当前统一架构、快速开始、可信边界、竞赛说明
  packages/                  # 或保留已稳定的 aevora_core/ 命名
    aevora-core/
    aevora-console/
  integrations/              # Codex MCP、普通项目接入
  examples/                  # 可直接运行的公开样例
  benchmark/                 # OrderFlow 维护者系统（严格非公开构建边界）
  tests/                     # 按 Core/Console/Integration/Benchmark/Release 分类
  tools/                     # 仍在使用的可复核构建、测试、审计工具
  evidence/README.md         # 只放不含敏感内容的存储约定/哈希索引指针
  .gitignore
```

**路径可以不同，职责必须明确。** 不能为了看起来像 Monorepo 而产生无价值路径 churn，破坏 Python distribution、CLI 或消费者 import；允许保持现有 `aevora_core/`、`console/` 等真正稳定的现有包根。以一张迁移映射列出 `old path → new path → reason → import/release/test impact → rollback`。

重点核查真实存在的阶段痕迹：公开 `h4/` 包含长期要运行的 Hero/Replay/部署逻辑；Core 文档内混合 H1/H2/H3 的历史与当前规范；Console 通过同步脚本带入公共验证工具；各阶段旧 CLI/报告和根级脚本长期共存。逐项核对语义后给出 `KEEP / MERGE / MOVE / DEPRECATE / IMMUTABLE` 判定，**绝不可因名称认定重复实现**。

**G1 产物**：`GEN1_5_TARGET_ARCHITECTURE.md`、`GEN1_5_MIGRATION_MATRIX.csv`、`GEN1_5_DEPRECATION_REGISTER.csv`、`GEN1_5_DEPENDENCY_RULES.md`。在提交大量路径迁移之前用已有测试验证迁移地图的完整性。

## 3. 执行可回滚的分层重构（G2：Repository Consolidation）

- 在独立 worktree 进行小粒度可回滚变更，依次清理活动源码的入口、命名、重复业务实现、生成镜像/副本所有权、开发脚本，再梳理文档和历史资产展示。
- 明确一个 Core 的业务逻辑权威实现；不同 adapter 可以存在，但不可通过拷贝形成独立治理决策来源。
- 合并确证重复的代码；仅重定位仍在使用的功能；对旧 import/CLI 选择兼容 shim 或迁移文档，并测其行为。**业务数据与历史图关系的 ID 不应因为文件路径移动而改变。**
- 对验证器与公共 Replay 资产确认唯一可追溯源，必要的供应链复制必须能由脚本确定性再生成并做源哈希校验，不可手工维持两套不一致逻辑。
- 弃用/移除候选必须满足：无生产运行调用者、无仍有效的测试/发布调用者、非历史证据、非复现所必需、可明确恢复。对于存在歧义的文件，保留并标记待审而非冒险删除。
- 构建输出、运行临时物、数据卷、浏览器录像和历史证据不能混进源码包或被 `git add .` 误带入。大规模 evidence 只加索引/指针或文档；不得擅自移动原始 archive 目录并造成原始哈希/路径失效。
- 规范当前业务命名为 Aevora，旧 GraphSwarm/阶段性名称在不可变历史与追溯文档中保留，不改写来源历史。
- 文档应建立 `CURRENT` 产品指南与 `HISTORY/ARCHIVE` 历史规范的可辨认边界；不要删掉过去版本，只避免把过时文档当当前事实。

每个可回滚切片都必须执行对应测试和构建检查，并留下 Commit/Tree、文件迁移清单、前后对比、失败/修复记录。失败时停在该子步骤修复；不允许通过删除失败测试、减少检查或 `skip` 伪造 PASS。

## 4. 单一开发与发布入口（G3：Build, Test & Release Ergonomics）

目标是让 Gen 2 开发者在干净 worktree 中明确知道如何执行：

- Core 安装/开发环境初始化；
- Console 前后端构建与启动；
- 本地 FalkorDB 初始化/冷恢复与健康检查；
- Codex MCP 注册和普通项目接入；
- Developer unit/integration、Benchmark/Evaluator（维护者环境）、Public/Private separation、Console browser、HeroVerifier、release packaging；
- Replay 与 Live 的独立入口和失败表现；
- 最小公开产品构建及私有材料泄漏扫描。

如整合 `make`/`just`/Python entrypoint，须评估已有工具并尽量复用，不能仅为了形式引入过度复杂的新任务编排。公开用户使用指南和维护者运维指南必须分开，尤其是不得泄露私有 Oracle、Reference、模型密钥、DB 密码与内部 Full Archive。

检查 wheel/sdist/source ZIP/Docker/前端 bundle 实际文件树和 import，执行干净环境安装与启动验证；公共包不需要 OrderFlow 才能启动、查询空图并挂载 MCP/Console。

**G3 产物**：统一 `DEVELOPMENT.md`、受控命令入口、`PUBLIC_RELEASE_BOUNDARY.md`、发布扫描收据。

## 5. 保留行为与安全语义的验证（G4：Behavior Preservation & Regression）

**必须验证：**

1. H4 原 1802 个回归测试身份完整继承；迁移引起模块路径/`classname` 改变时提供明确的旧/新 ID 映射与语义等价证据。新增必要的 migration/packaging 测试，但不以增加测试数量作为完成度指标。
2. Core 关键行为：WHEN/WHY 的 APPLY/VERIFY/ABSTAIN、未知事实/反证处理、Version/Scope/Withdrawal、QuerySnapshot 与 Revision，拒绝从单次任务 PASS 推断策略因果收益。
3. Candidate Lifecycle 的 Agent/Host 信任分离、独立 Source/Outcome、发布/撤回及新 Session 查询；外部公开测试仍只能生成 `EXTERNAL_UNVERIFIED`，不能制造 VerifiedOutcome。
4. MCP 身份/权限/边界、SDK 实际调用、合法空图、Replay≠Live、越权拒绝/数据最小暴露；真实私有 Oracle/参考补丁不进入任何 PUBLIC release artifact。
5. 实际 FalkorDB 与独立 OrderFlow 的最小闭环，D-v02 Buggy 28/8、Reference 36/36、既有 CLI 正反和负控；与 H4 相应基础环境一致，若环境不可满足，报告 `BLOCKED` 并不可标为 PASS。
6. Console 三页数据投影、基本浏览器交互、空图/断库/Gateway401/断网、公共 Hero Replay、由真实图关系决定判断的演示控件及独立 HeroVerifier。
7. 使用 H4 的 SOURCE/Run ID/manifest 基线核对历史归档只读，核对权限/工具/构建/容器中敏感资产不得泄漏。需要时执行 diff 证明 old/new 标准化 Core 公共输出等价，忽略时间/临时路径须明确说明原因。
8. UDS EPERM、AOF reload139、共享 kernel/EOL、未保存崩溃尾部和统计因果 UNKNOWN 等历史限制不能因为重构而“自动通过”。记录是否实际复现/依然未验证。

**没有真实 FalkorDB 或原生 Codex 可用时，不能把 Mock 通过记作实机 PASS。** 应分列 `STATIC_PASS`、`UNIT_PASS`、`INTEGRATION_PASS`、`NATIVE_PASS`、`BLOCKED`、`KNOWN_LIMIT`。原真实挑战可以维持 H4 历史证据，不必为了纯仓库重构重新付费跑多轮模型，但必须检查该运行链没有断链，并尽可能做一次最小实际 SDK/MCP/FalkorDB 验证。

## 6. 整洁性与第二代可开发基线（G5：Gen 2 Readiness Handoff）

- 新的隔离开发 worktree 为干净 Git 状态，无未解释的未跟踪文件；保留所有应交付源码与配置；避免把历史证据和运行产物纳入 Git。
- 新开发者阅读当前 README 和 DEVELOPMENT.md 即可理解仓库目录、可信边界、如何开发 Core/Console、如何运行验证；目录内有清晰模块 ownership。
- “减少文件数/代码行数”**不是验收目标**；只有减少无效复杂性、提高可维护性、复现性和边界清晰度才是目标。
- 公开产品重新构建并验证包内容；维护者 Benchmark 和隐藏真值仍可独立运行、不外泄。
- `GEN1_5_GEN2_HANDOFF.md` 明确：新的 canonical module map、Public APIs、环境构建命令、Repo ownership、待办风险、历史证据索引、后续 Gen 2 可安全修改的模块与不可触碰的可信契约。
- 形成独立的 Gen 1.5 发布源 Commit/Tree，并保留源路径至新路径的可审计迁移映射。仅本地提交，不推送外部。

## 7. Gate 顺序与硬性停止条件

| Gate | 类型 | 必须达成的能力 | 达成后才能做什么 |
|---|---|---|---|
| G0 | 冻结 / 只读盘点 | 真实仓库状态、源版本、文件类别与风险清单 | 可以提出具体移动/去重计划 |
| G1 | 设计 / 迁移映射 | 所有关键入口、依赖方向与 Trust Boundary 有 owner | 可以动活动源码 |
| G2 | 可回滚重构 | 清除确认的重复/过时结构，不改变业务契约 | 可以合并日常入口 |
| G3 | 开发/发布入口 | 干净安装、统一命令、Public/Private 检查 | 可以做全回归 |
| G4 | 实际等价验收 | 1802 历史测试身份证据、Core/MCP/Console/Benchmark 行为及负控 | 可以封存新基线 |
| G5 | Gen 2 交接 | 干净 worktree、迁移与证据报告、可重建产品 | **停止 Gen 1.5** |

**任何以下情况必须标注 CONDITIONAL/BLOCKED 而不能假报完成：** 源与证据版本无法对齐、历史证据被修改、私有 Oracle 泄漏、核心决策语义变化、无法复现公共产品构建、真实集成测试无法在当前环境执行、未知文件被盲删或终端声称“修复”却没对应代码/运行证据。

## 8. 最终交付物

1. `GEN1_5_REPOSITORY_INVENTORY.md`（含 Git/文件/脚本/依赖清单）
2. `GEN1_5_TARGET_ARCHITECTURE.md` 和清晰的 Current Architecture 图
3. `GEN1_5_MIGRATION_MATRIX.csv`、`GEN1_5_DEPRECATION_REGISTER.csv`
4. `GEN1_5_DEPENDENCY_RULES.md` 和 `PUBLIC_RELEASE_BOUNDARY.md`
5. `GEN1_5_VALIDATION_REPORT.md`、测试身份映射、构建/安全/回归证据
6. `GEN1_5_GEN2_HANDOFF.md`（下一代开发基线）
7. 本地独立 Git Commit/Tree + Clean Worktree State + 用于外部审阅的小型审计包（当前源代码 + 关键命令/测试/映射，不包含私有真值、原始模型密钥或大体积历史 Full）
8. 完整变更/限制清单，注明仍未解决的 AOF139、UDS、共享内核和任何真实环境 BLOCKED。

## 9. Codex 启动时应执行的第一步

先对**完整本地维护者仓库**作只读 G0 调查，报告当前真实 Git/Worktree 和目录分布、活动源码入口/重复候选/历史证据分层、可能影响 Public/Private 包边界的内容；然后给出 G1 的明确迁移表。以此为准开展可回滚整理并进入 G2–G5。用户已授权完成本轮仓库整顿，不需要反复索取相同确认；但发现可能破坏封存证据、不可恢复数据、真实安全边界的操作时，应停止此子步骤，保留原件并给出可替代方案。

**最后停在 Gen 1.5，不自动开始 Gen 2 功能开发。**
