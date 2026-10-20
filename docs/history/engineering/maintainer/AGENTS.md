# G2-FINAL current authority

User-authorized local productization from G23 a4d1450; Sol is the primary Agent.
Reuse Core/MCP/Console and keep G24 independent. Public source is an explicit
allowlist; do not export Benchmark/Oracle/reference/Host pins/raw logs. Synthetic
live demo and sanitized historical G23 summary must remain visibly distinct.
No new paid Agent challenge, remote push, visibility change or contest submission
is needed for this task. Historical phase stop rules below are preserved history.

# Aevora Gen 1.5.1 current handoff

Current task authority: Aevora_Gen1.5.1_Workspace_Hygiene_Repository_Root_Consolidation_Codex_Task_v1.0.md (exact user input copy).
Current authorization stops at Gen1.5.1. Product/Maintainer workspaces use the same
source, not copies; full root/history remain available. Read docs/current/WORKSPACE,
GEN1_5_1_SCOPE_FREEZE and current validation/handoff. Preserve both prior worktrees,
user ROS .vscode, immutable Full/Lite/Run and all inherited1820 test identities.
No directory migration/deletion or business/Gateway/Core/Oracle rewrite was justified.
Workspace filters are UX only; explicit public allowlist and execution fences remain
separate. Use tools/workspace_check.py for additive view contracts. No remote push,
paid model challenge or Gen2 feature. Older phase handoffs below are history.

# Aevora Gen 1.5 current handoff

This linked worktree is the Gen 1.5 consolidation baseline. Read README,
DEVELOPMENT, GEN1_5_GEN2_HANDOFF and GEN1_5_VALIDATION_REPORT before changes.
The old phase stop rules below describe immutable history; current authorization
stops at Gen 1.5. Do not start Gen 2 features or push remotely. Keep the original
root/index, frozen tests, private truth and external archives unchanged.
Canonical public evidence source is tools/public_evidence; run deterministic sync
and --check after edits. Audit Capsule body is private aevora_maintainer with an
optional legacy alias. Public Core/Console must install without OrderFlow.
Use tools/dev.py / Make targets and fresh external outputs for current commands.
No broad add/clean/reset; stage named paths, commit reversible slices.

# OrderFlow Incident Lab — 维护者 Agent 工作指南

## Aevora H4 current handoff

H4 is the authorized product delivery iteration. Use the root
`AEVORA_H4_VALIDATION_REPORT.md`, Gate reports, traceability matrix and limitations,
plus `aevora_validation/H4_CURRENT` and its outside-Full final delivery receipt.
Historical stop rules below describe their old phases; do not start H5 or new
Benchmark/governance work without new user authorization.

- Public runtime: independent `aevora_core`, `console`, `h4` Hero assets and an
  explicit public source allowlist. Root maintainer package/AGENTS/archives,
  private Oracle/tests/repairs/labels and credentials never enter the product.
- `aevora init` is the trusted lifecycle Schema initializer. Do not use the
  historical repository default init for proposal-capable ordinary onboarding.
  Native bridge now accepts legitimately empty initialized graphs; zero
  candidates is valid and cannot be replaced with fake seeded experiences.
- H4 latest full tests1802 preserve all1714 H3 identities; commands/JUnit/source
  pins are actual evidence, not permission to claim a changed checkout passed.
- H4 new ordinary238caf... produced a real untouched repair/7 publicPASS, zero
  VerifiedOutcome. New empty readonly3c307... has nativeexit0/observationPASS,
  originalRuntime ERROR/NO_PATCH. Case A's3 true native children are historical
  H3 evidence, not new H4 single-mode collaboration. Incomplete81d8... and
  startup-failedbc47... remain original, never upgraded.
- User authorized separate Playwright Chromium (CUA unavailable). Public
  Loopback API is read-only, LIVE/REPLAY explicit, old data cleared on failure;
  exact broker/native complete-line provenance, bounded projections only.
- User explicitly chose local source/packages/image validation, no remote
  Git/public deployment yet; ignore competition schedule as a development
  restriction, but do not certify eligibility or forge dates.
- Mature H4 command owner executes one existing command, not an orchestrator.
  Keep native completion-aware mode and existing RuntimeControl cancellation.
  Root worktree is dirty from prior phases: no broad add/reset/clean/push.
  Use the dedicated H4 release checkout and per-run source epochs.
- Full seal is terminal. Final export/verification/delivery receipts belong
  outside Full under `aevora_validation/audit_exports/<H4 archive name>/`.
  Old stopped pending files are explicitly INCOMPLETE_COLLECTION, not live
  writers or completed results. Secrets and individual secret hashes never
  enter archives. Security/shared-kernel/EOL, RDB RPO/AOF139 and D-v02 UDS limits
  stay qualified; adoption/causal value/weights/cost remain unproven.

本文件供维护者仓库中的后续 Agent 复用项目知识。**它不是 Benchmark Participant 的任务输入，不得复制到被测工作区或发送给被测模型。** Participant 的公开 `AGENTS.md`、Issue 和角色配置由 `benchmark/participant.py` 单独生成。

本文件记录截至 **2026-10-10、M1 验收结束** 的工程状态；M1 最终结论以根目录新报告为准。开始新任务时重新检查源码、配置和运行环境；历史验收数字是对应冻结版本的证据，不是当前 checkout 自动通过的证明。用户本轮明确授权的范围优先。

## 1. 项目状态与范围

- 目标：评估真实软件工程任务中的原生多 Agent 协作、跨任务经验继承及未来经验治理。
- 已实现：订单/库存 SQLite 业务、Episode Manifest/Registry、Runner/CLI、独立 pytest Evaluator、宿主数据库 Oracle、Manual/Codex Adapter、隔离运行与证据归档。
- `SMOKE-001`：取消订单后恢复库存，重复取消保持幂等；私有 suite 当前为 8 项。
- Episode `A`、CLI variant `v01`：单进程多线程库存竞态；私有 suite 当前为 14 项。
- Episode D、variant `v01`：`IMPLEMENTED` 的独立多 Worker / 共享 SQLite 事故包；当前私有 suite 为 28 项。`IMPLEMENTED` 不是验收 PASS。
- Episode B/C：`PLANNED / NOT_IMPLEMENTED`。Experience Adapter：`DISABLED`。
- Phase 3.5 历史最终结论 **CONDITIONAL PASS**；本轮 M1 正式授权实现 Task System 与 D。完成 M1 后停止；B/C、GraphSwarm、FalkorDB、MCP、Dashboard 或正式 G0–G3 实验需要后续明确授权。
- 完整支付、确认扣减、异步补偿和完整 Event Worker 尚未实现。接口预留不能当作功能已完成。

## 2. 开始工作前

1. 在项目根目录运行 `git status --short --branch`，确认分支和已有改动。本机项目位置是 `<MAINTAINER_HOME>/data_storage/humble_workspace/orderflow_incident_lab`；工具初始 cwd 可能是上一级 workspace。
2. 阅读用户当前任务，明确是开发、修复还是 Evidence-Only Audit。审计任务不得顺手修改实现或历史成绩。
3. 先读 [README.md](README.md)、[当前验收入口](PHASE3_5_VALIDATION_REPORT.md)、[Phase 3.5 Hardening](docs/PHASE3_5_HARDENING.md)、[Gateway 配置](docs/GATEWAY_PROVIDER.md)。
4. 按任务阅读 [总体设计](docs/OrderFlow_Incident_Lab_Benchmark_Design_Spec_v1.0.md)、[架构](docs/ARCHITECTURE.md)、[Episode A](docs/EPISODE_A.md)、[Registry](docs/EPISODE_REGISTRY.md)、[Smoke](docs/SMOKE.md)、[Codex 集成](docs/CODEX_INTEGRATION.md)、[隔离说明](docs/AGENT_ISOLATION.md)及相应阶段报告。
5. 直接检查准备修改的源码与接口。部分早期文档仍保留旧阶段的网络/资源限制和状态描述；涉及当前行为时，以当前源码及 Phase 3.5 动态证据为准。发现冲突应说明，不能把旧描述当作当前事实。

设计或排查问题时，尽可能调研 GitHub、官方文档及已有成熟实现，避免从零重造已有能力。优先复用 Python 标准库、SQLite、pytest、Git、bubblewrap 和官方 Codex Runtime；保持现有模块边界，避免整体重构。

## 3. 模块导航

| 路径 | 职责与修改入口 |
|---|---|
| `app/service.py` | `OrderFlow` 公开业务门面；必须保留 API 兼容性 |
| `app/persistence.py`、`inventory.py`、`orders.py` | SQLite 事务、库存、订单与账本；仓库 `app/` 是正确基线 |
| `app/payments.py`、`events.py` | 支付/事件契约，尚非完整服务 |
| `benchmark/scenarios/<ID>/public.json`、`manifest.py` | 公开场景与协议校验；私有配置在 Evaluator 一侧 |
| `benchmark/registry.py` | Episode 工厂、variant、公开测试、suite ID 注册 |
| `benchmark/templates.py`、`episodes/episode_a.py`、`episodes/episode_d.py` | 缺陷 fixture 与维护者参考修复生成 |
| `benchmark/runner.py`、`cli.py` | 生命周期、独立 Run、提交、评测、报告与 reset |
| `benchmark/submission.py`、`participant.py` | 严格补丁/文件树保真、公开工作区构建和实际 diff 提取 |
| `benchmark/sandbox.py`、`participant_sandbox.py`、`resources.py` | Candidate/Participant 隔离、资源监控与进程清理 |
| `evaluator/runner.py`、`suites.py`、`fingerprints.py` | 可信 pytest/JUnit 判分、必要测试身份集合及版本指纹 |
| `evaluator/rpc.py`、`worker.py` | 候选业务 RPC；`batch` 在同一 Worker 内真正多线程执行 |
| `evaluator/oracle.py`、`episode_d_oracle.py` | 停止 Worker 后，由宿主直接审计 SQLite、约束、真实订单/账本与每 Worker 持久写入；D 原生 journal 恢复单独记录 |
| `evaluator/supervisor.py`、`control.py` | D 通用多进程调度、内核 peer PID/代次、实际数据库 FD 身份、有界同步与 pidfd 崩溃/重启 |
| `evaluator/recovery_coverage.py`、`resource_recovery.py` | 独立恢复窗口覆盖状态、pytest 超时后内核进程池和私有控制 socket 清理 |
| `evaluator/hidden_tests/`、`private_manifests/`、`reference_patches/` | 私有评测与答案；禁止 Participant 访问 |
| `integrations/agents.py`、`codex_agent.py` | Manual/真实官方 CLI Adapter；不承担自制 Agent 调度 |
| `integrations/providers.py`、`gateway_broker.py`、`participant_bridge.py` | 宿主 Gateway、每 Run 鉴权与受限模型通道 |
| `integrations/model_broker.py` | Legacy 后端契约；保留测试，当前新 Live 入口阻断 Legacy |
| `integrations/codex_trace.py`、`native_rollout_trace.py`、`runtime_evidence.py` | 官方事件、child 自身活动、原始引用、输入/最终封存 |
| `integrations/experience.py` | Disabled Adapter 与未来四个经验接口 |
| `tests/`、`tests/public/` | 宿主开发者测试；后者按 Episode 提供公开副本 |

生命周期为 `Load → Prepare → Execute → Evaluate → Report → Reset`。新增场景需独立授权，按 Registry 文档接入工厂、Manifest 和 suite，复用 Runner 核心流程。

## 4. 业务与评测不变量

- 每次业务操作使用独立 SQLite 连接；正确写入路径以 `BEGIN IMMEDIATE`、条件更新、CHECK/FK 和账本唯一性保护一致性。
- 取消与释放应原子执行；重复取消/释放不得重复增加库存。异常应回滚整个业务操作。
- 库存字段为 `initial_stock / available / reserved / committed`，订单与预留状态必须与账本一致。
- Episode A 缺陷由工厂产生：写事务前读取库存快照，随后按过期快照回写绝对数量。Schema/约束保留，真实竞态仍可造成账本不一致。此维护者分析不得放入 Participant Issue。
- A 的默认 fixture 是 50 件、200 个独立请求、每单 1 件；正确语义为 50 成功、150 不足、available=0、reserved=50。其他参数应从 fixture 计算不变量，不能全局硬编码 50/150。
- 宿主线程并发不等于候选业务并发。使用 `BusinessRPC.batch()`，核查同 Worker PID、不同线程与调用重叠。普通 RPC 单条请求仍顺序处理。D 通过 `WorkerSupervisor` 同时派发到 2/4 个独立 Candidate 进程；本地 namespace PID 可以相同，必须检查可信 Supervisor namespace 的 peer PID、代次、调用区间与实际业务 DB device/inode。
- 不强迫修复使用某一种锁或指定 SQL；事务、原子更新或合适的锁都应按相同业务语义评测。
- 候选代码仅在 Candidate Sandbox 执行；宿主 pytest 不导入候选包，不加载候选 conftest、pytest 配置或插件。
- 候选 `audit()` 和返回值不是唯一真值。停止候选线程后，由可信 Oracle 直接检查真实数据库、订单、账本、守恒和约束。
- PASS 要同时满足 pytest 实际退出状态、有效 JUnit、完整且无重复的必要测试身份集合、正确计数、无 skip/error/failure。不同 suite 使用各自配置，不能把 8 或 14 当作全局常量。

## 5. 提交保真：不能退回旧实现

Phase 3.5 修复过父 Git 工作树下空 `.py` 新增/删除被静默忽略而 `git apply` 返回 0 的真实缺陷。

- 可信 Runner 独立解释 bounded UTF-8 diff，在隔离 Git 仓库中校验并应用，排除父仓库、系统/用户配置、hooks、attributes 和污染环境。
- 只允许普通 `app/**/*.py` 文本源文件；拒绝穿越、符号/硬链接、特殊文件、非允许 rename/copy/binary、冲突和不完整 hunk。
- 必须记录 Baseline Tree、原始 Patch、Expected Tree、Applied Candidate Tree SHA256，并逐文件核对实际字节。
- `git apply --check`/`git apply` 返回 0 不足以证明成功；不匹配为 `SUBMISSION_INTEGRITY_ERROR`，隐藏评测不得启动。
- 临时快照全量验证后原子发布，失败不得污染基线或其他 Run。当前发布使用 Linux `renameat2(RENAME_EXCHANGE)`。
- 自动提交还必须匹配提取时记录和实际 patch 摘要。Manual 提交使用同一可信校验器，支持 diff、含 `app/` 的工作区及任意目录名的安全业务源码目录。
- 公共测试修改单独归档；它们不能替换私有 suite，也不作为业务补丁提交。

相关回归入口：`tests/test_submission_fidelity.py`、`test_manual_directory_compatibility.py`、`test_native_archive_failclosed.py`。

## 6. 本机运行方式

要求 Python **3.12**、SQLite、pytest、Git 和 bubblewrap；依赖版本见 `pyproject.toml`。本机已验证 `scripts/python312` 与 `scripts/orderflow`，前者复用已安装 Flatpak Python 运行时；宿主裸 `python3` 不一定是 3.12。常规环境可使用 Python 3.12 venv + editable 安装，安装细节见 [CLI 文档](docs/CLI.md)。

只读入口：

```sh
scripts/orderflow list
scripts/orderflow validate --episode SMOKE-001
scripts/orderflow validate --episode A --variant v01
```

需要执行验证时，按本轮用户授权选择检查，并使用新的归档目录。仅编辑文档时不自行运行业务测试或联网挑战。以下均为命令模板，不表示已执行：

```sh
# 每轮使用新的 UTC + UUID；不要复用历史目录。
orderflow_validation_dir="phase3_5_validation/$(date -u +%Y%m%dT%H%M%SZ)-$(python3 -c 'import uuid; print(uuid.uuid4())')"
mkdir -p "$orderflow_validation_dir"

# 记录精确 argv、UTC 时间、退出状态及 stdout.log/stderr.log。
python3 scripts/phase35_record.py "$orderflow_validation_dir/developer-command" \
  scripts/python312 -m pytest -q --junitxml="$orderflow_validation_dir/developer.junit.xml"

# 本机维护者离线回归；包含原 Phase 3 归档 patch 重放，依赖该历史文件存在。
python3 scripts/phase35_record.py "$orderflow_validation_dir/offline-command" \
  scripts/python312 scripts/phase35_offline.py "$orderflow_validation_dir"

# 统一 CLI：--runs-root 必须放在子命令前。
scripts/orderflow --runs-root "$orderflow_validation_dir/runs" prepare --episode A --variant v01
scripts/orderflow --runs-root "$orderflow_validation_dir/runs" evaluate --episode A --variant v01
# 上一命令评测默认缺陷，预期 FAIL / exit 1。
scripts/orderflow --runs-root "$orderflow_validation_dir/runs" evaluate --episode A \
  --submission evaluator/reference_patches/A-v01.diff
# 参考补丁仅在可信维护者侧使用。
scripts/orderflow --runs-root "$orderflow_validation_dir/runs" report --run-id <run_id>
scripts/orderflow --runs-root "$orderflow_validation_dir/runs" reset --episode A
```

CLI：PASS/PREPARED/RESET→0，FAIL→1，ERROR→2，TIMEOUT→3，NOT_IMPLEMENTED→4。`report` 是读取操作，成功显示 FAIL 报告仍返回 0；prepare/reset 或批量记录脚本的 exit 0 也不等于任务 PASS。必须读实际 JSON 状态和内层命令结果。

`scripts/validate_phase1.py`、`validate_phase2.py`、`validate_phase3.py` 等旧验收入口可能写历史报告/归档。运行前读源码确认所有写入路径；保留历史时优先使用新的 `--runs-root` 和 `phase35_offline.py`，不要直接重跑旧验收脚本。

## 7. 真实 Codex 与安全门禁

只有本轮授权联网挑战时才启动真实模型请求；不能为文档更新、静态审查或既有证据核对顺手发起昂贵挑战。

```sh
ORDERFLOW_ENABLE_CODEX=1 scripts/orderflow --runs-root "$orderflow_validation_dir/runs" \
  run-codex --episode A --provider gateway --model gpt-5.6-terra \
  --reasoning-effort max --agent-timeout 1200 --request-budget 160
```

- 使用官方 `codex exec --json`、原生 subagent 和同版本官方 Code Mode helper；不开发另一套 Planner/Coder/Reviewer Orchestrator。
- 0.162.1 是 Phase 3.5 实测 CLI 版本，不是对未来安装的假设。重验版本、features、help 和实际事件字段；优先查官方文档/源码，不猜配置或协议。
- 每次挑战新 Run、新 Lead Session、新 CODEX_HOME；不继承维护者会话。当前 same-run 持久 state 用于原生 child fork，不能随意加 `--ephemeral`；归档并停止 writer 后删除 state。
- Gateway 为第三方 `https://api.renwang-huang.top/v1`。只上传公开任务材料；实际完成响应的 model/effort 字段可证明观察到的 API 标签，不能证明内部模型权重。
- 不静默改变 provider/model/effort，不关闭 TLS、放宽挂载或切换全宿主执行来获取 PASS。Legacy 新 Live 入口当前阻断。
- 项目 Secret 在可信宿主仓库外的专用目录，位置/注入方式见 Gateway 文档。权限为目录 0700、文件 0600。不得输出内容或其哈希，不放入源码、命令参数、Participant 环境、日志或归档；不复制完整宿主 Codex 身份文件。
- Participant 只获短期每 Run 通道身份；可信宿主 Broker 持上游密钥。限制 token/TTL/peer UID、路由、模型、请求数、并发、消息大小和超时；Candidate 不获模型 socket/token。
- 三层分别验证：Outer Participant、官方 Native Command Sandbox、Candidate Business Sandbox。仅 cwd 或路径命名不构成隔离。
- 当前外层物理内存 2 GiB、任务 768，native/model 并发各四，请求预算 160。2 TiB 是官方 helper 所需的**虚拟地址空间**上限，不是物理内存额度。Gateway 官方 HTTP/stream 重试各二，重试计入同一请求预算。
- 缺少必要 namespace/cgroup 时失败关闭为 `BLOCKED_SECURITY_GATE`，不进行无限制执行。
- CPU controller 未委派；聚合 CPU/输出部分依赖采样，普通 Candidate 无独立内核 memory/pids cgroup；M1 D Worker 池新增独立内核 memory/pids cgroup，此提升不能回填普通 Candidate 历史安全结论。因此当前完整对抗安全仍为 CONDITIONAL，不能提升为无条件 PASS。
- 安全探针仅针对自建端口和专用假凭据/测试目标，不扫描未知服务，不让不可信程序尝试读取真实密钥。

## 8. 原生协作证据与结果判定

- 配置文件、主 Agent 自述、生成 patch 都不能单独证明多 Agent 或任务成功。
- child 必须匹配本 Run 的自身 Session/parent 来源、真实委派、自己的工具活动、完成/最终答复与主 Agent 实际接收；排除 child rollout 中继承的 parent 历史。
- 保留官方原始 JSONL、line hash（包含原换行）、原始引用、child/session/run ID。Runner 映射事件与原生事件分开。
- 原生日志缺失或归档异常应标记 INCOMPLETE/PARTIAL/UNAVAILABLE；不得凭自然语言构造 spawn 或用旧证据维持 PASS。
- Token usage 使用实际官方字段，按 response ID 去重；不能把累计计数重复加总，不能估造缺失 usage。
- 分开报告 `runtime_status`、`multi_agent_status`、`submission_integrity_status`、`evaluation_status`、`isolation_status`、`integration_status`。Runtime 成功不等于任务 PASS；有效任务 FAIL 也不自动等于集成设施失败。
- 停止/超时 Run 的原补丁可以另建 Run 独立重放，但必须标为 postmortem；不能改写原成绩，不能算成原自动闭环成功，不能人工修复或换参考补丁冒充 Agent 产出。

## 9. 历史证据与已知基线

以下是 Phase 3.5 封存时的事实，后续修改后需重新执行才能宣称当前有效：

- 最终开发者测试 **499/499**，原 249 项身份保留；18 份原测试源码/断言、27 份业务/Evaluator 文件和 9,089 份受保护历史文件未变。
- 核心冻结提交 `cee9bbaf1c7df55049a91e890bb4cf2e0d313310`；最终文档提交 `beba4fb`。后续提交不要被误写为当时挑战使用的代码。
- 恢复系列：`272384f8-eb91-4eb1-9c37-52f46157dfbe` 和 `1fa7ec49-e9f3-480a-b5f3-4e67ff4e7d38` 自动闭环，各 14/14 PASS；`7cec1187-72a0-4ee5-b12c-addc4758f5b1` TIMEOUT，原自动评测 NOT_RUN。三轮各有三个 verified native children，自动成功 **2/3**。
- 超时 Run 的原始补丁独立重放 `2ba58809-fc3e-4f95-9b8f-2b70c93fdaa9` 得到 14/14 PASS，不能计为第三次自动成功。
- 初始 900 秒系列自动 0/3，原失败保留；不能与修改后的 1200 秒系列混成同配置统计样本。
- 原 Phase 3 patch 新建离线重放 `119461d5-b551-4fa1-80f3-3158816ff931` 为 14/14 PASS，原 Run `339f7d73-29df-4242-8920-9e566bce8a9c` 未修改。

证据目录：

- `runs/`：原阶段运行归档。
- `evidence_review/20261010T053144Z-63a0ac7a-cb83-475c-a25e-7eec7417a8fe/`：Phase 1–3 Evidence-Only Audit，含早于 Phase 3.5 的源码快照。
- `phase3_5_validation/CURRENT`：本轮封存目录指针；当前指向 `20261010T064039Z-261add09-cb16-4726-b3c5-da8d14b09480`。其中有完整验收、提交保真/Gateway/隔离报告、原生时间线、修正记录、SOURCE_CHANGE_MANIFEST、COMMAND_INDEX、EVIDENCE_MANIFEST 和 SHA256SUMS。

这些归档被 Git 忽略，不等于可以删除。**不得修改历史 Run、JUnit、报告结论、原 66 行事件或已封存校验和，也不得给旧 manifest 追加新文件。** 新审计写入新的 `evidence_review/<UTC-UUID>/`；新 Phase 3.5 验证写入新的 `phase3_5_validation/<UTC-UUID>/`；本轮 M1 验证写入独立 `m1_validation/<UTC-UUID>/`（入口 `m1_validation/CURRENT`）。后续阶段另行授权并分目录。

新证据应区分历史、当次动态执行、静态分析、合成故障及 UNVERIFIED。记录实际命令、时间、退出状态、文件 SHA 和产物；发生 collector/文案错误时保留原件并新增修正说明。目录中晚于修改的观察快照不能称为 pristine baseline。

封存前停止所有 writer，再生成 manifest/checksums；不要把仍在写入的 recorder stdout 纳入封存。既有 `EVIDENCE_MANIFEST.json` 与 SUMS 的生成输出/receipt 排除规则见相应工具。独占创建与本地哈希不是第三方不可变存储或密码学运行证明。

## 10. 修改纪律与交付

- 优先 `rg`/`rg --files`，定向读取。避免对包含海量运行归档的根目录做无范围递归扫描。
- 保留已有本地改动和无关 `benchmark_roadmap/`；不使用 broad reset/clean，不擅自删除归档或推送。
- 使用子 Agent 时由主 Agent 分配文件所有权，避免同文件并发写入；维护者协作 Agent 不能计入 Participant 的 benchmark child 证据。
- 用户授权验证时，保留失败记录、定位实际问题；不删除有效测试、不放宽断言、不跳过必要测试。影响已有协议时维护 Manual、Smoke、A、NOT_IMPLEMENTED、隔离、reset、JUnit/JSON 和错误分类回归。
- suite/Oracle/fixture 改变需更新相应版本并生成真实新指纹；不要将新评测成绩回填历史 Run。
- 最终说明改了什么、实际执行什么、退出状态、产物位置、风险及未验证事项。文档修改与静态检查不宣称业务重验，三轮样本不宣称总体成功率。
- 到用户指定阶段停止，等待下一轮审查或明确授权。

## 11. M1 Task System 与 D 维护规则

- 先读 `docs/TASK_SYSTEM_DESIGN.md`、`TASK_ADMISSION_GATES.md`、`TASK_RELATIONS.md` 和 `EPISODE_D.md`。前四份规范/自审在实现前已冻结于 M1 `design_preimplementation/`；检查 `DESIGN_GATE.json`，不要把实现后快照冒充开发前方案。
- D 的公开 Issue/Manifest 必须中性，只给症状、拓扑和业务语义；根因、策略适用性、设计文档及 `evaluator/private_labels/` 禁止进入 Participant。
- D 缺陷源于真实 stale read / absolute write 与独立进程内锁，不移除全套数据库约束。Reference 为一致事务，合法替代为合作式稳定 inode flock。不得要求 Agent 选择某个指定方案。
- 多 Worker 在 ample capacity 阶段分别完成唯一订单的真实写入；不能用重复同 ID 响应、同路径字符串或宿主派发线程数代替实际进程/数据库证据。
- 2026-10-10 发现并保留了真实 falsifier：`f9089592-c528-4904-a72d-b6965eba99a4` 的分离账本提交换自定义事务后错误获得 24/24 PASS；旧内部 Persistence observer 不足。M1 必须以同候选代码树的正反控制、common SQLite API 提交观测及独立 Oracle 修复敏感性，不能仅引用初次 10 轮成功。
- 事务 observer 是通用调度观测，不是候选自证真值。未支持的真实提交路径为恢复覆盖 UNVERIFIED；trace 出现 COMMIT、只读事务、辅助 DB commit 或尚未结束的 RETURNING 都不能被当作业务提交已完成。
- 私有 Applicability Reference 与 Engineering Outcome 独立。A 中进程内 RLock 来源为 `maintainer_seed`，历史 Codex 的数据库修复为 `natural`；不伪造经验继承、决策或治理提升。未知拓扑 VERIFY 标签仅为 REFERENCE-ONLY 设计条件。
- 有效 M1 当前回归必须保留原 499 项测试身份；只允许显式迁移旧 D=PLANNED 断言，保留原源码快照。B/C 仍 NOT_IMPLEMENTED。旧 Smoke patch 若不满足现有严格 hunk 校验，不改历史文件；使用版本化 `SMOKE-001-current.diff`，记录迁移和真实新验证。
- 三次 D 盲测必须使用同一冻结 cohort、新 Run/Session、Gateway `gpt-5.6-terra/max`、1200 秒、160 请求、顺序 Trial。真实 child 自身执行证据与实际修复/隐藏评测分开统计；开发子 Agent 不计入 Pilot。
- 可复现入口：`scripts/reproduce_episode_d.py`、`m1_offline_regression.py`、`m1_recovery_probe.py`、`m1_isolation.py`。`m1_live_pilots.py` 要求先有可信冻结 `--gate`，不得跳过安全/保真/模型兼容性门禁。

## 12. M1 最终实测状态（后续改动需重验）

- 总体CONDITIONAL PASS，Design PASS，D Engineering PASS（声明范围内），Research CONDITIONAL PASS。根目录M1设计/工程/Pilot/矩阵/限制报告为入口。
- 当前664/664开发者PASS，原499身份保留；D Scenario2.0.0 / Suite1.2.0 / Evaluator3.1.0 / Observer1.1.0，28必要身份。最终30Run：Buggy10FAIL、Reference10PASS、flock10PASS，合法compensated分阶段正控通过；同树错误split-ledger识别FAIL。
- 正式新盲测Run fbaae2cb-586f-4573-9cda-035eb7f608a0 TIMEOUT、48cddbed-6410-44e1-b860-142edef5e3ab PASS28、463674bc-afba-4959-bb63-cda945c63b5a TIMEOUT。原自动闭环1/3；verified children2/3/1。两次超时原样补丁离线新Run各28PASS，不升级原成绩。
- m1_validation/CURRENT及FINAL_SEAL_SUMMARY/SOURCE_CHANGE_MANIFEST/COMMAND_INDEX/EVIDENCE_MANIFEST/SHA256SUMS/SEAL_OUTPUTS_SHA256记录本轮。历史38,640普通文件、136冻结源实际核对未变；新实现仍是dirty分支，SHA识别运行版本，不能冒称历史HEAD含新源码。
- 完全敌对安全/CPU内核聚合/unsupported observer/加密初始task/底层模型权重/实际费用/第三方存证/统计难度仍有限或UNVERIFIED。到M1停止，不自动再发起挑战或实现B/C/治理。

## 13. M1.1 维护规则（2026-10-11，历史规则按其阶段解释）

- 本阶段已授权 completion-aware、Full/Lite、D-v01 六 Session 校准和 D-v02 **仅设计**。完成后停止，不启动 B/C、D-v02 业务/隐藏测试/参考补丁或 GraphSwarm。原 M1 TIMEOUT/PASS/TIMEOUT 及所有历史 postmortem 不能升级或重写。
- 新证据入口 `m1_1_validation/CURRENT`；根目录 `M1_1_VALIDATION_REPORT.md`、`M1_1_DIFFICULTY_CALIBRATION_REPORT.md`、`M1_1_REMAINING_ISSUES.md`、`M1_1_EVIDENCE_INDEX.json` 为最终索引。Full seal 后只读；最后 ZIP、独立验证和 release receipt 位于 Full 外 `m1_1_validation/audit_exports/`。
- bounded 仍默认900秒/160请求；研究模式必须显式 `--completion-policy completion-aware --agent-timeout none --request-budget none --agent-mode single|multi`。None 是真实无总量阈值，仍有有限连接/原生idle/retry、并发4、2 GiB/768 pids/采样CPU600等限制。不可用大数代替None。
- 新CLI `status`/`snapshot`/`cancel --run-id <id>` 由可信控制身份处理。不同 wrapper 的 PID namespace不同，不能盲目向同数字PID发信号；cancel后检查全部owned process/cgroup/socket/state已清理。SIGKILL/断电没有实现自动resume。
- native live `child_states={}` 可能是观测不完整，不是证明没有child；最终自身rollout+typed完成回执才是证据。初始分工正文不透明时标UNAVAILABLE。Final answer和parent receipt比较必须保留完整whitespace，不用substring认定精确回传。
- 六次新Run是探索校准，首轮PROVIDER_FAILURE/ERROR/NOT_RUN不得排除或替换；其余五轮28/28 PASS。禁止合并旧1200秒cohort分母、推断Single/Multi显著优劣或经验治理收益。
- LIVE_GATE冻结150份源码用于全部六次挑战；其后修复native/evidence final文本解析，记录独立before/after指纹与原样日志重分析，不能把新parser归给当时挑战。原第六轮3spawn/2verified保持原样，另外标注真实第三child的纠正证据。
- Audit-Lite是MAINTAINER_AUDIT，不能给Participant。导出/verify/inspect只读、不联网、不执行包内业务；用另渠道获取的可信stdlib verifier和外部ZIP SHA验证。NOT_INCLUDED仅指针。固定created-at可在同压缩库下验证确定性，绝不原地改Full。
- 当前完整开发者回归保留M1原664身份/38测试源、57任务真值、82,740历史文件；新增测试不可放宽旧断言。确切最新数量以最终JUnit/命令receipt为准。默认不要为文档维护重新发起模型挑战。
## Aevora H1 current development boundary

The authoritative H1 task is `Aevora_H1_Experience_Accountability_EndToEnd_Codex_Task_v1.1.md`.
Its explicit authorization supersedes historical stop rules for this H1 work only.
New experience-governance assets use **Aevora**, Python package `aevora` in
`aevora_core`; OrderFlow remains the independent Benchmark, FalkorDB the actual
database, and Codex the native collaboration Runtime. Keep old GraphSwarm
references as historical provenance. Do not rename old Runs, hashes or reports.

- Read `aevora_core/README.md` and its architecture, schema, WHEN/WHY, MCP and trust docs.
- Default experience remains Disabled. Live opt-in uses `scripts/aevora-python`
  with `ORDERFLOW_ENABLE_CODEX=1` and `run-codex --experience aevora`.
- Graph admin credentials stay in the host-only project secret directory; the
  Participant gets only this Run's Unix socket and stdlib proxy. Its native
  business commands retain their original network restrictions.
- Query is not adoption; Participant Decision is an untrusted claim; Outcome
  comes only from strict, pinned OrderFlow evidence verification. New observed
  feedback preserves UNKNOWN attribution and does not upgrade support from PASS.
- New evidence belongs in `aevora_validation/<UTC-UUID>/`; freeze sources before
  live execution, stop all writers before sealing, and export Audit-Lite outside Full.
- Preserve all original developer assertions and task truth. After H1 stop;
  no B/C, D-v02 business, orchestrator, dashboard or formal G0–G3 study without new authorization.


## Aevora H1 accepted evidence snapshot

- H1 Overall CONDITIONAL PASS; dimensions and exact latest JUnit count are in `AEVORA_H1_VALIDATION_REPORT.md`. All original 856 test identities/44 test source bytes, 57 task truth files and 90,800 historical files are preserved.
- Actual D Run 5089297e-39e7-4bd5-8b87-cbc7e21de022: 3 verified native children, untouched patch, 28/28 Hidden PASS, Oracle36/36. New read-only Session 4a141343-0714-4992-a0cf-119b61cff121 sees OBSERVED_OUTCOME; its original Runtime ERROR/NO_PATCH/session_idUNAVAILABLE and NOT_EXECUTED are preserved.
- Live source epoch is release_admission_v2; later path/session/persistence audit fixes and bounded MCP owner-close hardening are separately versioned post-live. Never attribute these newer bytes to the original model Run.
- FalkorDB4.20.4 retained AOF replay actually exits139. Current deployment is authenticated loopback RDB; explicit SAVE/graceful restart passes, unsaved crash tail/power loss UNVERIFIED. No AOF deletion or untested engine upgrade.
- Review the complete chain without model/DB/candidate execution via `scripts/aevora_demo.py verify-existing` with the separately approved CLOSURE_INDEX_V2 SHA. For fresh live work, generate new same-namespace Gates and source freeze; the old gate must refuse changed current source.
- Full at `aevora_validation/CURRENT`; export/verification and ZIP receipt outside Full in `aevora_validation/audit_exports/`. Source hash consistency is local authority, not external attestation. Query/decision/PASS are not causal adoption; feedback stays UNKNOWN.
- Stop at H1. No B/C, D-v02 business, formal randomized G0-G3, dashboard or new governance stage without explicit authorization.

## Aevora H3 current handoff boundary

The authoritative H3 task is `Aevora_H3_Experience_Lifecycle_Competition_Readiness_Codex_Task_v1.0.md`. H3 source is incremental: Core Schema1.2 candidate lifecycle/host-only source and admission, opt-in fourth typed MCP tool, ordinary Core CLI/serve, controlled Receipt example, read-only demo/independent verifier and a thin Audit-Lite selection adapter. Do not rebuild the Runner/Oracle/Broker.

- D-v02 was implemented in H2, with 36 necessary cases. Smoke8/A14/D-v01 28/BCplanned remain independent. Default experience is still DISABLED.
- H3 actual final developer JUnit: 1714 passed, 1 upstream SDK warning. Keep original1655 identities/74 old test sources/39 truth files/195885 protected historical evidence bytes. Current results and final delivery stage are in `AEVORA_H3_VALIDATION_REPORT.md`.
- New natural Candidate source Run405c481e-ae7a-420d-8502-fb1d9ede02e6: real proposal, three verified native children, independent14/14 PASS, bounded Host publication. Different read-only c4cd6c0e-fb38-465f-bee1-63d3d50374a6 sees it; ERROR/NO_PATCH is preserved, not a task grade.
- Ordinary project c8a6a7ae-fb65-4b2d-98ea-0651eb939a7b and Raw f4406efc-d94d-4d21-b30f-d350248f3d4e pass original7 public tests. They remain EXTERNAL_UNVERIFIED/zeroVerifiedOutcome; first Provider-failed ordinary attempt remains archived. One paired pilot is exploratory, no causal benefit claim.
- `aevora_validation/H3_CURRENT` is an absolute Full path. Source epochs/live/gate/document commits differ. Full sealing is terminal; post-seal export, verify, final gate/report and Git receipts live under separate `aevora_validation/audit_exports/<H3 archive name>/`. Do not backfill a sealed Run or Full.
- H3 own DB17689; cold control17690 and demo17691 have separate Volumes. H1/H2 remain untouched. Host secrets are external0600/0700, never Participant or archive data. Only per-run scoped proxy is public; host review/source/graph admin never MCP tools.
- Current actual fence is one GRAPH.QUERY head transition; staged materialization and arbitrary read paths are not global transactions. RDB lastSAVE RPO, AOF139, EOL, NativeUDS EPERM and shared-kernel PARTIAL remain.
- After H3 stop. No H4/B/C/dashboard/formal randomized experiments or extra Runtime SDK unless newly authorized.
