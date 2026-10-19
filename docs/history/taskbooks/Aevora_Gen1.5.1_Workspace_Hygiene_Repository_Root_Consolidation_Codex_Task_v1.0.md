# Aevora Gen 1.5.1 — Workspace Hygiene & Repository Root Consolidation

**Codex 正式工程任务书 v1.0**  
**任务属性：Gen 1.5 之后、Gen 2 功能开发之前的一次有界收尾；不是 H5，也不是 Gen 2 功能迭代。**  
**核心目标：识别真实结构性技术债，提供清晰的日常开发视图，并且在不破坏第一代源码行为、私有边界和封存证据的前提下，消除已经得到证明的根目录/入口混乱。**

> 用户已授权本轮独立仓库精修；无需对每个普通改动反复请求确认。任何涉及不可逆删除、历史证据物理迁移、数据库卷操作、远程推送或权限边界弱化的动作不在授权范围内，应立即停止相关子步骤并报告。

## 0. 执行总纲：先调查，再判断，最后只做必要修改

当前 VS Code 看到的目录繁杂，并不等价于架构有缺陷。将问题分成三个不同层次，分别取证与处理：

| 层次 | 需要回答的问题 | 合适手段 | 不允许的伪解决 |
|---|---|---|---|
| **Architecture debt** | 是否有重复权威实现、循环/反向依赖、过时入口仍参与实际运行？ | 调用图、import graph、测试/发布契约、必要时小幅重构 | 只给代码换名字、移动目录，未减少耦合 |
| **Repository hygiene** | 活动源码、历史只读证据、生成产物、环境文件是否混作同类？ | 分类、当前与历史索引、输出路径约束、清理有证明的临时产物 | 为了视觉整洁搬运数十万份不可变证据 |
| **VS Code developer UX** | 为什么初次打开工程不能迅速定位产品/测试/维护者模块？ | 明确的 `.code-workspace`、限定的隐藏/搜索/监听配置、入口文档 | 把所有有争议目录 `files.exclude` 隐藏并声称仓库已清理 |

### 本轮最低价值交付

1. 新人可按说明打开**专用 Aevora 产品开发工作区**，只看到当前应编辑的模块与文档；需要时可切换到**维护者全量工作区**查看 Benchmark、Evaluator、私有工具。仓库文件并不因视图切换而迁移。
2. 所有当前重要根目录都有真实用途解释；过时、生成、历史或待弃用项目有明确类别和 Owner。
3. 在调用证据充分时，消除少量确实无效的重复入口或阶段性耦合；如果没有可安全删除的内容，允许**零代码删除**，禁止为了凑重构成果制造 churn。
4. 原 Gen 1.5 成果与可信边界保持，生成干净可追溯的本地新 Commit，并提供 Gen 2 可直接接手的工作区与运行指南。

## 1. 真实基线与不可变边界（必须先核对）

### 1.1 已知锚点，不可替代实际本地检查

- Gen 1.5 候选基线 Commit：`47bd9101126f5b5fb8d8dc7cec88f0dfe3712c93`；Tree：`b6d6e4aa2552a2fd6e999e4fa7310ac3e440a63d`。
- 上一轮隔离 worktree 路径曾为 `<MAINTAINER_HOME>/data_storage/humble_workspace/aevora_gen1_5`，但**不假定目前仍在、仍干净或仍是当前 root HEAD**。
- Gen 1.5 的原始维护者仓库盘点为约 307,833 个普通文件，冻结当时筛出 501 个活动源码文件；大多数普通文件是历史证据、缓存/环境和运行工件，而非活动源码。
- Gen 1.5 已有标准 `tools/dev.py`、Make、`DEVELOPMENT.md`、Owner/dependency/migration/deprecation 记录和分层公共打包边界；历史阶段脚本仍有实际调用者，**不得因其命名包含 H1–H4、M1 或 phase 而删除**。
- 最近记录的全量开发者回归为 **1820/1820 PASS**，含 H4 的 **1802 个继承测试身份**；D-v02 Buggy `28 PASS / 8 FAIL`，Reference `36/36 PASS`；Chromium 17 个交互检查；真值与历史证据保护范围以原始收据为准。严禁将旧测试结果冒充本轮重跑。
- 现有已知风险：AOF reload139、原生 D-v02 UDS EPERM、共享内核/EOL、RDB 未保存尾部、Oversized UDS 请求偶发 BrokenPipe/413 竞态、当前 Codex 0.162.1 新真实联网 Session 未验证、Agent 采纳/因果收益 UNKNOWN。整理仓库不能宣称自动解决。

### 1.2 第一代架构稳定区，默认保留

| 真实模块/路径（须确认） | Gen 1.5 已定义职责 | 本轮默认处理 |
|---|---|---|
| `aevora_core/` | 公共 Core、WHEN/WHY、治理、候选生命周期、MCP、GraphRepository | **KEEP**：稳定包根，非必要不迁移 |
| `console/` | Experience Console、只读 Observatory、Live/Replay | **KEEP**：稳定包根，非必要不迁移 |
| `h4/` | 当前仍有效的 Hero、Replay、部署工具及公共兼容资源 | **ACTIVE/COMPAT**：不可仅因阶段名删除 |
| `tools/public_evidence/` | HeroVerifier 与 Disclosure Policy **唯一编辑源** | **CANONICAL**：生成副本必须确定性检查 |
| `tools/`、`scripts/` | 当前开发/发布入口及仍有调用者的阶段复现适配器 | **AUDIT**：先用真实调用证据判定 |
| `app/`、`benchmark/`、`evaluator/`、`integrations/`、`aevora_maintainer/` | OrderFlow/私有维护者、独立 Oracle、Host 集成 | **PRIVATE/CONTROLLED**：不合并到公开 Core |
| `src/`、`tests/` | 可能包含原业务实现与有效回归 | **AUDIT**：检查依赖和代码所有权 |
| `aevora_validation/`、`runs/`、`m1_validation/`、`m1_1_validation/`、`phase3_5_validation/`、`evidence/`、`evidence_review/` | 需要按实际内容进一步细分的历史证据、验证与运行资产 | **PRESERVE**：禁止按目录名批量物理移动 |
| `.venv/`、`.pytest_cache/`、`*.egg-info`、`dist/`、`node_modules/` | 本地环境/缓存/生成物（实际检查 tracked 状态） | **VIEW FILTER / IGNORE**，不要触碰有效记录 |

### 1.3 Git 与信任的硬约束

1. **不要直接在原维护者 root 或现有 Gen 1.5 交接 worktree 中大规模修改。** 首先用 `git worktree list --porcelain`、`git status --porcelain=v2 --branch`、`git rev-parse HEAD`、`git rev-parse HEAD^{tree}` 对所有涉及 worktree 做只读快照；记录 index/dirty/untracked 及差异清单。截图中分支 `*` 或 Git 数字提示不是事实证据。
2. 在可用且验证一致的 Gen 1.5 Commit 上创建**新的**隔离 worktree 和专用 branch（例如 `aevora-gen1-5-1-workspace-20261014`）；若 source Commit 或基线有歧义，停止相关写操作并报告差异，不凭猜测挑选版本。
3. 不允许 `git clean -fdx`、大范围 `rm -rf`、全局 `reset --hard`、无选择 `git add .`、不受控 `mv` 历史封存目录；每次仅 stage 指名文件，单一可回滚小切片提交。
4. H1–H4、Gen 1.5 Full/Lite、私有 Oracle/Reference、Raw Agent 事件、Graph/RDB/AOF、失效记录、运行凭据和原始 SHA 指纹保持原样。任何标记为 sealed 的路径不得作为默认生成输出。
5. 原有 Public Core 独立安装不得导入 Benchmark/Evaluator；普通 Agent 不能取得 Host 出版权限。外部项目的自测不能自动生成 VerifiedOutcome；Replay 不能冒充 LIVE。
6. 不上传/推送任何远程 Git，不启动 Gen 2 功能开发、不创建新的大规模 Benchmark、不新增付费模型挑战，除非已有严格合同需要额外真实运行且用户另行授权。

## 2. G0 — Residual Debt & Root Inventory（只读调查）

从实际 Gen 1.5 源码及上轮报告读取：

- `GEN1_5_GEN2_HANDOFF.md`、`GEN1_5_REPOSITORY_INVENTORY.md`、`GEN1_5_MIGRATION_MATRIX.csv`、`GEN1_5_APPLIED_MIGRATIONS.csv`、`GEN1_5_DEPRECATION_REGISTER.csv`、`GEN1_5_DEPENDENCY_RULES.md`、`GEN1_5_RISK_REGISTER.md`、`DEVELOPMENT.md` 与 `PUBLIC_RELEASE_BOUNDARY.md`。
- 根目录**所有第一层目录及可见顶层文件**：分类 `ACTIVE_PRODUCT`、`ACTIVE_MAINTAINER`、`ACTIVE_TEST`、`DOC_CURRENT`、`HISTORY_IMMUTABLE`、`GENERATED`、`ENVIRONMENT`、`COMPATIBILITY`、`UNKNOWN`。一类文件可能包含混合内容，目录不得简单整体判定。
- 基于源文件清单（原冻结 501 + Gen 1.5 变化）的源代码审计：import/call graph、CLI 入口、构建/测试依赖、symlink、运行配置、文档引用。对疑似重复、循环依赖、隐藏相互调用生成 `path → actual callers → package/release impact → proof → risk` 证据表。
- 盘点 Git tracked/untracked/ignored；特别确认 `.venv/`、`.pytest_cache/`、egg-info、`node_modules/` 和大型 evidence 仅属于工作区噪声，还是存在被版本管理和构建错误包含的真实问题。
- 判断目前源代码的 public/private allowlist、生成资源同步过程、受保护输出路径以及 `.gitignore` 与 VS Code view/search 设置是否存在矛盾。

**注意性能和安全**：优先使用已有 501 文件 ownership 清单、Git 已追踪树和阶段性边界索引；避免对 20 GiB 历史档案无差别执行 `rg --hidden -uuu`、跨卷 glob、遍历 symlink、删除/移动或重新压缩。允许对涉及变更的证据指纹做增量复核；总体旧归档指纹采用上次封存收据作为历史参照，不能声称此次逐字节重查了 236011 文件，除非真的执行。

**G0 产物**：
- `GEN1_5_1_ROOT_CLASSIFICATION.csv`（path/category/owner/actual-role/active-callers/source-of-truth/recommendation/confidence）
- `GEN1_5_1_DEBT_AUDIT.md`（真实架构债 vs 根目录混放 vs 仅 UI 噪声；精确源码/测试依据）
- `GEN1_5_1_BASELINE.json`（各 worktree 的实际 Git 指纹、上轮 Commit/Tree、重要不可变路径、测试基线）

**G0 准入 Gate**：没有 callsite、import graph、packaging 或执行契约支持的目录一律不能归类为“死代码可删”。

## 3. G1 — Minimal Change Plan（冻结有界修改方案）

对每一个候选给出实际判定，不允许模糊的“待优化”直接进入修改：

| 判定 | 用途 | 允许动作 |
|---|---|---|
| `KEEP_ACTIVE` | 当前稳定且必要 | 保留；可补职责说明 |
| `KEEP_COMPAT` | 旧 import/CLI、测试、第三方调用仍存在 | 保留 shim + 文档，明确权威实现 |
| `KEEP_IMMUTABLE` | 历史归档、真值、原始成绩/失败 | 原路径只读，绝不重写 |
| `GENERATED_IGNORE` | 缓存、可重建构建输出 | 规范新输出位置、忽略/隐藏；不可删封存产物 |
| `VIEW_ONLY` | 不妨碍运行但干扰 VS Code 展示 | 通过专用 workspace 解决，不动磁盘文件 |
| `REFACTOR_TARGET` | 有重复实现、反向依赖或冲突权威入口的**确切证据** | 最小等价变更、可回滚、测试 |
| `UNRESOLVED` | 现有证据无法判断 | 保留并列入后续风险，不擅自删除 |

每个计划中的真实代码变更须有 `old/new path or symbol → why → actual caller → expected benefit → tests → rollback`；如收益仅是“名字看着更统一”，优先不改。**优先修复真实架构债，而不是让每个根目录名字都符合新的设计图。**

**G1 产物**：`GEN1_5_1_ACTION_PLAN.csv`、`GEN1_5_1_SCOPE_FREEZE.md`；冻结哪些目录和文件是明确的“非目标”。

## 4. G2 — Workspace UX First（优先改善日常 VS Code 使用）

用户最直接的痛点：打开 `aevora_gen1_5` 时，Explorer 第一层看到大量历史目录，难以判断真正活动源码。

### 4.1 创建至少两种可打开的 VS Code 工作区

**Product Dev View**：显示 Aevora Core、Console、公开集成/部署、当前 Docs、必要开发工具和相关 Tests；不混入 Benchmark 私有资产。使用稳定的相对路径和清晰的可见命名，例如 `Core`、`Console`、`Public UX`、`Current Docs`、`Dev Tools`、`Public Tests`。**以实际目录结构为准**，不得为了创建工作区副本代码，也不得把 maintainer-only `integrations/` 误当公共入口。Product Dev View 并不等于公共发布包；只有经 source allowlist 验证的内容才可对外发布。

**Maintainer Dev View**：在 Product Dev View 的基础上展示 `app/`、`benchmark/`、`evaluator/`、`integrations/`、`aevora_maintainer/`、维护者测试/工具与当前证据索引。这是受信任本地工作视图，**绝不自动分享该文件树或把它纳入公共制品**。

文件名参考 `Aevora.Product.code-workspace`、`Aevora.Maintainer.code-workspace`；也可用项目现有命名，但两个入口应一眼区分。`.code-workspace` 使用相对路径，避免写死个人绝对路径、凭据、数据库端口或历史卷位置。不要因为 `.code-workspace` 指定子目录便误以为其是独立 Git 仓库；核验 Sources/Terminal/debug/Tests 等工作流在多根工作区中的真实行为及 repo SCM 发现方式。

### 4.2 过滤策略有界而真实

- 针对 `.venv`、`.pytest_cache`、`__pycache__`、`node_modules`、Build `dist`/`build`、临时 `*.egg-info` 等确认可再生、无必要编辑价值的路径设置合理的 `files.exclude`、`search.exclude`、`files.watcherExclude`。
- 需要隐藏封存证据时，**优先通过不把归档目录添加到日常 multi-root Workspace**；不要在全局 `.gitignore` 乱改历史 tracked/ignored 规则，更不要通过过滤将真实核心源码/测试/错误藏起来。
- 保留“全量仓库检查”的入口或清晰说明，允许维护者随时访问原始 Root，而不是只能通过漂亮工作区看到经过选择的文件。
- `.gitignore`、`.dockerignore`、workspace view rules、公共打包 allowlist 是四种不同边界；必须分别检查、解释，不能把其等同或交叉借用作为安全证明。

### 4.3 真实用户验收

- 使用当前本机 VS Code/CLI 能力验证 `.code-workspace` 配置可解析、folder 路径存在且指向正确源目录、SCM/任务/搜索/终端命令至少有明确可复现的验证结果；无法 GUI 自动点击时注明 `VISUAL_UNVERIFIED` 并交付用户本机手动操作步骤，不伪称截图已经验证。
- 提供 `WORKSPACE_GUIDE.md` 或 `docs/current/WORKSPACE.md`：如何选择 Product/Maintainer、如何进入全量仓库、如何显示/定位被过滤的历史文件、如何运行开发命令。
- 输出一张“日常应看到什么、为什么这些目录不是垃圾”的清单；若可获取原生截图则可附，**不要伪造截图**。

**G2 产物**：两份可打开工作区配置、受控 VS Code 设置、Workspace Guide、配置/实际用户检查收据。

## 5. G3 — Root Consolidation & Verified Debt Removal（只改确切问题）

G3 不要求必须移动任何根目录；按 G1 清单执行**少量、必要、可证明收益**的变更。优先次序：

1. 当前 README / DEVELOPMENT / Owner Map 的入口一致性：新开发者不用阅读旧阶段报告才能判断修改位置。把“当前运行入口”“历史复现入口”“受控发布入口”分别说清楚。
2. 现有活动产物的生成输出规范：临时运行、构建、浏览器截图、JUnit、重新导出的证据必须去受控的**新输出根目录**，不得落入封存 Full/Lite 或回写第一代数据目录；检查 symlink 和路径祖先约束。
3. 对确证不合理的 `scripts/`、`app/`、`src/`、`h4/` 重复入口执行最小修正。已有关联测试和包装依赖的阶段名保留兼容；`tools/public_evidence/` 仍为 HeroVerifier 的唯一编辑源，生成副本字节严格校验。
4. 若确有 tracked 生成文件或者公共包误带维护者资产，先证明构建/版本边界问题，再改变构建配置。不要将公开 Core/Console 与 Benchmark/Evaluator 合并为一个包。
5. 若没有足够收益证据，G3 可以只更新文档和文件所有权标识，并如实记录 `NO_SAFE_STRUCTURAL_MIGRATION`，仍可验收。

禁止重写 WHEN/WHY、Experience Candidate、Trusted Feedback、FalkorDB 图模型、MCP Agent 权限、Hero Replay 契约或独立 OrderFlow Oracle。根文件变更不应导致已有用户的 `pip install`、MCP tool schema、CLI exit code、Live/Replay 路由和图历史 ID 改变。

**G3 产物**：实际变更清单/迁移映射、各切片 Commit、静态依赖复查、弃用登记更新；对没有发生的“清理”不虚报。

## 6. G4 — Behavior Preservation & Developer UX Acceptance

以最后**实际冻结的 Gen 1.5 版本**为输入基线，分类验证：

| 维度 | 最低验收证据 |
|---|---|
| 文件/工作树 | 原 root + Gen 1.5 worktree 前后 status/index/HEAD 比对；新 worktree 源码 clean、无异常 tracked/untracked |
| 源码身份 | 测试源与私有真值无未经授权修改；真正修改过的每个源码/入口都有调用者/迁移/回滚依据 |
| 全量回归 | 1820 项历史 ID 原则上完整保留；如因合法路径更改影响 `classname`，提供逐项映射；不得以 skip/assertion 放宽换取绿灯 |
| Product | 独立安装、干净 wheel/sdist/source ZIP、MCP 官方 SDK 合同、合法空图、Console Replay/Live 清晰拒绝、三页基础交互 |
| Benchmark | 15 CLI 旧契约、D-v02 Buggy `28/8`、Reference `36/36`、B/C `NOT_IMPLEMENTED`、原始 FAIL/ERROR/TIMEOUT 语义保留 |
| Trust/Package | 公共包不得包含 private truth、Oracle、Reference、维护者源码、凭据或原始 Agent event；Agent 不能行使 Host 权限 |
| 根目录体验 | Product/Maintainer workspace 都能找到真实模块，旧历史仍可访问；用户不能因隐藏配置错过可编辑的活动代码 |
| 历史保护 | 原 Full/Lite/Run 保留路径与哈希；只比较真实检查范围，不据索引声称全量重哈希 |

若 G3 改动活动代码/CLI/路径，必须在可用受控环境中执行**全量 1820+ 当前测试**和受影响的真实 MCP/FalkorDB/Console/Benchmark 验证；如仅改变 workspace/docs 且无运行路径变更，也应完成最小关键回归、公开构建和验证器检查，尽力重跑当前完整回归，无法重跑的如实记录为 `BLOCKED/NOT_RERUN`，**不得把上轮 1820 PASS 冒充这轮结果**。对本轮 `CONDITIONAL PASS` 是否可接受，应按实际变更影响面和证据覆盖判断。

Gateway oversized UDS `BrokenPipeError`、AOF139、D-v02 UDS EPERM、共享 kernel/EOL、RDB RPO、Codex 0.162.1 native compatibility、因果收益/采纳 UNKNOWN 均需原样列入限制，不要求本轮修复；测试偶现失败保留独立收据，不能删除断言或重标历史。

## 7. G5 — Freeze the Real Gen 2 Developer Starting Point

生成真正方便开发者使用的下一代起点，而不是只有一张简洁截图：

- 新的、可追溯到 `47bd9101...` 的本地 Git Commit/Tree，专用 worktree `git status --porcelain` 为空；原维护者 root 与 Gen 1.5 已封存状态保持不变。
- 清晰列出两个 VS Code 工作区入口，链接当前 Architecture、Product Quickstart、Maintainer DEVELOPMENT、Owner/Dependency Map、可信边界和历史索引。第一次参与 Aevora 开发的人应能在几分钟内定位修改某项功能的源文件和测试入口。
- 更新 `GEN1_5_1_GEN2_HANDOFF.md`，准确写出仍被保留的阶段性路径及原因、尚未清理的技术债、仍存在的运行风险，以及哪些目录属于下一代可安全修改的权威实现。
- 保存轻量**维护者级**审阅包：当前相关源码与 Git diff、两种 workspace、根目录分类、必要 JUnit/验收命令和哈希清单。不得向 public release 泄露 Oracle、私有测试真值、原始模型事件或敏感配置；不需要附带几十万历史文件。
- 最终停止在 Gen 1.5.1；不远程 Push、不开始 Gen 2 功能开发、不启动新产品/研究实验。

## 8. 实际 Gate 顺序和失败边界

| Gate | 产物 | 阻断条件 |
|---|---|---|
| G0 只读盘点 | 版本、根目录、依赖、噪声、候选技术债 | 来源 Commit 对不上、目录/依赖不清楚 |
| G1 有界方案 | 精确 Action Plan、Non-Goals | 未证明删除/迁移必要性 |
| G2 工作区 UX | 两种 `.code-workspace`、View/Guide | 隐藏活动代码、错误的 workspace path |
| G3 精修 | 少量真实债务修复或经证明零迁移 | 历史/私有/运行契约受到破坏 |
| G4 验证 | 实际回归、公共构建、信任负控、对比 | 缺失关键集成验证而假报通过 |
| G5 交接 | 新 Commit/Tree、Clean Worktree、Gen 2 handoff | 无法追溯、污染原维护者 root 或远程推送 |

任何历史证据被修改、私有资产进入公共产品、核心行为等价失败、受保护原 worktree 被污染，都必须报告 `FAIL/BLOCKED` 并停止相关步骤。不允许用成功摘要掩盖首次失败；没有重新执行就不能写 `PASS`。

## 9. 最终必须交付的文件

1. `GEN1_5_1_BASELINE.json`、`GEN1_5_1_ROOT_CLASSIFICATION.csv`
2. `GEN1_5_1_DEBT_AUDIT.md`、`GEN1_5_1_SCOPE_FREEZE.md`、`GEN1_5_1_ACTION_PLAN.csv`
3. `Aevora.Product.code-workspace`、`Aevora.Maintainer.code-workspace`（名称可与现有一致）
4. `docs/current/WORKSPACE.md` 或 `WORKSPACE_GUIDE.md`
5. 实际变更/迁移记录及新旧 Git 指纹比较；更新必要的 Owner/Deprecation 注册
6. `GEN1_5_1_VALIDATION_REPORT.md`、当前 JUnit、契约/构建/验证收据及精确失败清单
7. `GEN1_5_1_GEN2_HANDOFF.md`、本地 Commit/Tree 和 clean 状态
8. 小型 `MAINTAINER_AUDIT` 审阅 ZIP + SHA256 与必要的版本对应关系（无 secrets/私有真值/不可变 Full）

## 10. Codex 执行指令

先**只读**核验真实 Git worktree、Gen 1.5 Commit/Tree 与仓库内容。按 G0 盘点三类复杂度，执行 G1 建立 Action Plan；在第三个隔离 worktree 实现 G2 的两种工作区和 G3 的必要小范围工程改动；按 G4 真实验证，最后 G5 建立干净 Gen 2 起始 Commit。

最初输出简洁的 G0/G1 发现：当前真实基线、导致 VS Code 杂乱的根目录分类、经证实的结构性技术债、拟修改文件和不会修改的不可变资产。然后在已授权的范围内直接执行，不要把多次请求重新确认当作工程进度。若尚无证据支持大规模移动，**应主动选择少改动、优先提升工作区体验**。

**最终仅交付 Gen 1.5.1，并停止；未经用户授权不得进入 Gen 2。**
