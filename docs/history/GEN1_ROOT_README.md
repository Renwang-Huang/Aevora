# OrderFlow Incident Lab

## Aevora H4 local product delivery

Aevora H4 completes the public Core/MCP/Graph/Console/Replay path. Overall
**CONDITIONAL PASS** retains the existing security and durability limits. See
[H4 validation](AEVORA_H4_VALIDATION_REPORT.md), [release](AEVORA_H4_G5_RELEASE_REPORT.md),
[limitations](AEVORA_H4_LIMITATIONS.md) and [traceability](AEVORA_H4_TRACEABILITY_MATRIX.csv).
Final Full/Lite closure is proved by the linked outside-Full delivery receipt.

Ordinary developers use the separate [public Quickstart](docs/QUICKSTART.md),
[Codex MCP configuration](docs/CODEX_MCP_SETUP.md), [three-case Demo](docs/DEMO_WALKTHROUGH.md)
and [public Docker instructions](h4/deploy/README.md). The delivered public source
ZIP, Core/Console wheels and sdists, prebuilt frontend and image exclude this
maintainer Benchmark. By user choice distribution is local; no remote Git push
or public deployment has occurred. OrderFlow remains an independent Benchmark.

Current H4 developer regression is 1802/1802, preserving all 1714 H3 identities.
Actual new ordinary repair passed seven original public tests and remains
EXTERNAL_UNVERIFIED; the fresh empty-graph native observation passed with original
ERROR/NO_PATCH preserved. No public example minted a VerifiedOutcome. Historical
scores and task truth are unchanged. Stop at H4.

OrderFlow 是独立的工程 Benchmark。Aevora H2 已验收为 **CONDITIONAL PASS**；H3 已完成，结论 **CONDITIONAL PASS**；见 [H3 验收](AEVORA_H3_VALIDATION_REPORT.md)、[生命周期](AEVORA_H3_G1_EXPERIENCE_LIFECYCLE_REPORT.md)及[独立接入](AEVORA_H3_G2_EXTERNAL_CODEX_INTEGRATION_REPORT.md)。SMOKE-001、A、D-v01 与 D-v02 已实现；B/C 保持 PLANNED / NOT_IMPLEMENTED。经验默认 DISABLED，需显式 opt-in。H2 最终1655项回归为历史成绩，不能当作H3结果。见 [H2交付](AEVORA_H2_DELIVERY_ACCEPTANCE_REPORT.md)与 [H3基线](AEVORA_H3_BASELINE.md)。

设计依据：[完整 Benchmark 设计规格](docs/OrderFlow_Incident_Lab_Benchmark_Design_Spec_v1.0.md)、[任务体系](docs/TASK_SYSTEM_DESIGN.md)与[准入门禁](docs/TASK_ADMISSION_GATES.md)。M1 的历史范围仅为 D 和任务设计；本轮 H1 新增的经验图、MCP 和可信反馈由 Aevora 承担。D-v02 已在 H2 实现；完整支付、异步事件、B/C 与正式对照实验未实现。历史报告原封保留。

## 安装

要求 Python **3.12**、Linux/WSL2、`bubblewrap`、`git`。业务使用 SQLite 与服务门面，无 HTTP 服务。

```bash
cd <MAINTAINER_HOME>/data_storage/humble_workspace/orderflow_incident_lab
python3.12 -m venv .venv
ORDERFLOW_BUILD_PROFILE=MAINTAINER_ONLY .venv/bin/python -m pip install -e .
.venv/bin/python -m pip check
```

依赖和构建依赖版本固定在 `pyproject.toml`。根分发包含私有 Evaluator，仅供可信维护者安装，必须显式 MAINTAINER_ONLY；不可交给 Agent。普通用户安装独立 aevora_core，H3 wheel/sdist 扫描与干净安装以 G0 报告为准。

Phase 1 历史安装时本机缺少独立 Python 3.12 且下载域名解析受限，实际使用已安装的 Flatpak Python 3.12 与本机纯 Python 依赖快照离线安装。可复现步骤见 [CLI 环境说明](docs/CLI.md)。当前机器直接使用：

```bash
scripts/orderflow list
scripts/orderflow validate --episode SMOKE-001
scripts/python312 -m pytest -q

```

历史 validate_phase1/2/3 脚本默认写历史验收文件。若要保留历史，不直接运行这些旧入口；Phase 3.5 使用独立归档的 `scripts/phase35_offline.py`、开发者 pytest 和明确的新 `--runs-root`。

## 运行 Episode A

本机入口如下；常规 Python 3.12 环境可使用 `.venv/bin/orderflow`。

```bash
scripts/orderflow validate --episode A --variant v01
scripts/orderflow prepare --episode A --variant v01
scripts/orderflow shell --run-id <run_id> -- /usr/bin/python3.12 -m unittest discover -s tests/public
scripts/orderflow evaluate --episode A --run-id <run_id>
# 默认 stale-snapshot 缺陷版本：预期 FAIL，退出 1

scripts/orderflow evaluate --episode A --variant v01 \
  --submission evaluator/reference_patches/A-v01.diff
# 维护者参考补丁：预期 PASS，退出 0；不提供给被测 Agent

scripts/orderflow report --run-id <run_id>
scripts/orderflow reset --episode A
```

基准为 50 件库存、200 个独立订单、每单购买 1 件。正确结果是 50 个成功预留、150 个库存不足、可用库存 0、预留库存 50。缺陷代码在写事务之前读取库存，再将旧快照计算出的绝对值写回；数据库行仍可满足 CHECK，但订单和账本会超过实际库存。候选业务调用在一个受限 Worker 内通过真实线程池执行，判分使用 14 项私有测试和宿主侧数据库检查。场景、复现器及证据说明见 [Episode A](docs/EPISODE_A.md)。

## 运行 Smoke

以下示例使用常规 Python 3.12 环境；当前机器将 `.venv/bin/orderflow` 替换为 `scripts/orderflow`。

```bash
.venv/bin/orderflow prepare --episode SMOKE-001
# 输出唯一 run_id；使用真实隔离环境进行开发和公开测试
.venv/bin/orderflow shell --run-id <run_id> -- /usr/bin/python3.12 -m unittest discover -s tests/public
.venv/bin/orderflow evaluate --episode SMOKE-001 --run-id <run_id>
# 默认缺陷代码：FAIL，CLI 退出 1

.venv/bin/orderflow evaluate --episode SMOKE-001 --submission evaluator/reference_patches/SMOKE-001.diff
# 宿主维护者参考补丁：PASS，CLI 退出 0；此补丁不提供给被测 Agent

.venv/bin/orderflow report --run-id <run_id>
.venv/bin/orderflow reset --episode SMOKE-001
```

提交可为普通 unified patch、含 `app/` 的工作区或安全的业务源码目录（目录名不限）。Runner 在新目录中应用补丁/复制业务源文件，再调用独立 Evaluator；提交中的测试、pytest 配置和运行报告不会作为评测依据。每个已完成 Run 不可重复使用；重复评测会生成新的 UUID。

手动业务命令使用 `orderflow shell`；完整 Codex 挑战使用 `run-codex` 的 Participant 运行时边界。准备目录是公开副本；仅设置 cwd 不能限制宿主文件访问。隐藏测试、参考补丁和维护者归档只保留在可信宿主。

## 原生 Codex 挑战

当前 Gateway 入口由可信宿主读取项目专用 Secret，Participant 不挂载上游密钥或宿主身份。端点为实测的 `/v1`，模型 `gpt-5.6-terra`，推理强度明确为 `max`。每次使用新 Run 与 Session；不静默换模型或降低沙箱。安全配置见 [Gateway 使用说明](docs/GATEWAY_PROVIDER.md)，三层边界及剩余限制见 [Phase 3.5 Hardening](docs/PHASE3_5_HARDENING.md)。

```bash
ORDERFLOW_ENABLE_CODEX=1 scripts/orderflow --runs-root phase3_5_validation/my-new-validation/runs \
  run-codex --episode A --provider gateway --model gpt-5.6-terra \
  --reasoning-effort max --agent-timeout 1200 --request-budget 160
scripts/orderflow --runs-root phase3_5_validation/my-new-validation/runs report --run-id <run_id>
```

物理内存为 2 GiB、任务上限 768、模型请求并发四；缺少必要的 cgroup/namespace 能力会失败关闭。官方 HTTP/stream 有限重试各二，每次仍计入总预算。CPU、磁盘和普通 Candidate 聚合资源有采样限制，因此不能宣称完整对抗安全。Legacy Live 入口暂时阻断，历史低层契约与成绩保留。

Runtime、Evaluation、Integration 分别记录；原生执行成功不等于补丁通过。官方 JSONL 中的结构化 spawn、独立子任务、完成状态和返回结果才用于验证多 Agent。详情见 [Codex 集成](docs/CODEX_INTEGRATION.md) 与 [Agent 隔离](docs/AGENT_ISOLATION.md)。

## 业务入口

```python
from app.service import OrderFlow

flow = OrderFlow("orders.sqlite")
flow.initialize({"SKU-1": 10}, reset=True)
flow.create_order("order-1", "SKU-1", 3)
assert flow.get_inventory("SKU-1")["available"] == 7
flow.cancel_order("order-1")
flow.cancel_order("order-1")
assert flow.get_inventory("SKU-1")["available"] == 10
assert flow.audit()["consistent"]
```

公开门面另支持 `create_order(..., reserve=False)`、`reserve_inventory()`、`release_inventory()`、`get_order()`。数据库为文件型 SQLite；每个操作独立连接，修改操作使用事务。`committed` 字段保留，支付确认与库存扣减尚未实现。

## 交付导航

- [架构与模块边界](docs/ARCHITECTURE.md)
- [CLI 与安装方式](docs/CLI.md)
- [Episode A 场景、竞态与复现](docs/EPISODE_A.md)
- [Episode Registry 扩展规范](docs/EPISODE_REGISTRY.md)
- [Smoke 与独立评测协议](docs/SMOKE.md)
- [Phase 1 范围与当前扩展边界](docs/PHASE1_SCOPE.md)
- [Phase 1 实际验收报告](PHASE1_VALIDATION_REPORT.md)
- [Phase 2 实际验收报告](PHASE2_VALIDATION_REPORT.md)
- [Codex 原生运行与事件协议](docs/CODEX_INTEGRATION.md)
- [Participant 与模型认证隔离](docs/AGENT_ISOLATION.md)
- [Phase 3 实际验收报告](PHASE3_VALIDATION_REPORT.md)
- [Phase 3.5 实际验收报告](PHASE3_5_VALIDATION_REPORT.md)
- [Phase 3.5 安全与提交修复](docs/PHASE3_5_HARDENING.md)
- [Gateway Secret 与有限运行配置](docs/GATEWAY_PROVIDER.md)

唯一运行 ID、提交 SHA256、场景及变体、Fixture/Suite 版本、Evaluator/私有 Manifest 摘要、运行环境版本、JUnit、JSON Report、UTC 时间与真实 Runner 事件保存在 `runs/<run_id>/`。Episode A 还保存并发响应及宿主数据库 Oracle；原生运行保存 `submission.diff`、`codex_events.jsonl`、`agent_trace.jsonl` 和 `runtime_metadata.json`。仅官方实际事件提供的子任务、工具、修改和 usage 会被记录；缺失字段明确为 `UNAVAILABLE`。原始日志留在可信宿主并脱敏。默认经验为 `DISABLED`；授权的 H1 Run 使用 `--experience aevora`，并另存真实 MCP 原始日志。

历史 M1.1 停止边界仍适用于其原始成绩。本轮正式任务止于 **Aevora H1**；真实 FalkorDB、原生 Codex MCP、Trusted Feedback 和跨 Session 证据属于新 H1 归档。没有 Episode B/C、D-v02 业务、Dashboard 或 G0–G3 正式实验结果。GraphSwarm 仅为历史名称。

## Phase 3.5 current runtime

Submission fidelity and the secure Gateway profile are described in [docs/PHASE3_5_HARDENING.md](docs/PHASE3_5_HARDENING.md). Safe secret injection and the current CLI are in [docs/GATEWAY_PROVIDER.md](docs/GATEWAY_PROVIDER.md). Historical Phase 3.5 evidence lives in `phase3_5_validation/`; M1 evidence lives in `m1_validation/`. Native collaboration remains Codex-owned. Episode B/C and experience governance remain unimplemented.

## Episode D — independent workers sharing persistent state

Trusted Supervisor starts 2 or 4 independent sandbox processes sharing one SQLite directory. Host kernel peer identities, database inode, dispatch intervals, persistent rows and crash/restart observations are archived. The private suite accepts multiple valid synchronization mechanisms and checks durable order/ledger agreement independently of candidate `audit()`.

```sh
# New archive; expected Buggy FAIL / reference PASS.
scripts/orderflow --runs-root m1_validation/local-runs evaluate --episode D
scripts/orderflow --runs-root m1_validation/local-runs evaluate --episode D \
  --submission evaluator/reference_patches/D-v01.diff
scripts/orderflow --runs-root m1_validation/local-runs evaluate --episode D \
  --submission evaluator/reference_patches/D-v01-flock.diff
scripts/python312 scripts/reproduce_episode_d.py --archive m1_validation/new-repeat --rounds 10
# Only after security gates and explicit live authorization:
ORDERFLOW_ENABLE_CODEX=1 scripts/orderflow --runs-root m1_validation/new-pilots/runs \
  run-codex --episode D --provider gateway --model gpt-5.6-terra \
  --reasoning-effort max --agent-timeout 1200 --request-budget 160
```

Maintainer design: [Episode D](docs/EPISODE_D.md), [Task relations](docs/TASK_RELATIONS.md). These documents and private strategy labels must never enter Participant inputs. CLI prepare/reset/report lifecycle and submission integrity are shared with A/Smoke.

## M1 final evidence

Task System and EpisodeD implemented; final **CONDITIONAL PASS**. Developer664/664; D final10BuggyFAIL/10ReferencePASS/10flockPASS. Three fresh native Multi-Agent pilots: original closure1/3; two separate timeout-patch postmortemsPASS do not alter original outcomes. See [engineering](M1_EPISODE_D_VALIDATION_REPORT.md), [design](M1_TASK_SYSTEM_DESIGN_REVIEW.md), [Pilot](M1_PILOT_REPORT.md), [matrix](M1_EVIDENCE_MATRIX.md), [remaining issues](M1_REMAINING_ISSUES.md). Maintainer private analysis never belongs inParticipant. Stop atM1.

## M1.1 runtime and evidence

The historical M1 results above remain frozen. M1.1 adds explicit completion-aware execution, trusted live control, independent Audit-Lite export and six-session Single/Multi exploratory calibration. Current acceptance evidence belongs in `m1_1_validation/`; its results are reported separately from M1.

```sh
# A fresh session with no total wall-clock or request-count deadline.
ORDERFLOW_ENABLE_CODEX=1 scripts/orderflow --runs-root m1_1_validation/new-live/runs \
  run-codex --episode D --provider gateway --model gpt-5.6-terra \
  --reasoning-effort max --completion-policy completion-aware \
  --agent-timeout none --request-budget none --agent-mode single
# Use --agent-mode multi to allow official native delegation.
scripts/orderflow --runs-root m1_1_validation/new-live/runs status --run-id <uuid>
scripts/orderflow --runs-root m1_1_validation/new-live/runs snapshot --run-id <uuid>
scripts/orderflow --runs-root m1_1_validation/new-live/runs cancel --run-id <uuid> \
  --reason 'operator decision'
```

Memory, process, CPU, output, TLS, identity and concurrency limits still apply. The official configurable SSE idle deadline is a network limit, separately reported; completion-aware does not promise infinite network retries or automatic resume. See [runtime policy](docs/LONG_RUNNING_CODEX_POLICY.md) and [Full/Audit-Lite policy](docs/EVIDENCE_EXPORT_POLICY.md). [D-v02 design](docs/EPISODE_D_V02_DESIGN.md) is maintainer-only and **not implemented**.

## M1.1 运行与证据入口

当前新增 completion-aware 研究模式、可信 status/snapshot/cancel、Full Archive 与独立 Audit-Lite 导出。旧 bounded 与 Manual 路径保留。六次新 D-v01 Session 的真实分母、Gateway 故障及原样补丁成绩见 [M1.1 验收报告](M1_1_VALIDATION_REPORT.md) 和 [难度校准报告](M1_1_DIFFICULTY_CALIBRATION_REPORT.md)；完整来源和ZIP SHA见 `M1_1_EVIDENCE_INDEX.json`。

策略和权限见 [长运行规范](docs/LONG_RUNNING_CODEX_POLICY.md)、[证据导出规范](docs/EVIDENCE_EXPORT_POLICY.md)；后续 [D-v02 设计](docs/EPISODE_D_V02_DESIGN.md) 仅通过静态审查，未实现。原M1三个正式 TIMEOUT/PASS/TIMEOUT 及全部历史证据继续保留。
## Aevora H1 integration

The independent **Aevora Experience Accountability Core** lives in
[aevora_core](aevora_core/README.md). It uses real **FalkorDB** for WHEN/WHY and
append-only trusted feedback, and connects to native Codex through a scoped MCP
interface. **OrderFlow Incident Lab** retains its independent Benchmark identity,
original task IDs, hidden Oracle and historical results. Experience remains
Disabled by default; the new runtime integration requires explicit
`run-codex --experience aevora` through the trusted Aevora launcher.

The name GraphSwarm is retained only in historical materials and provenance.
See the current [H1 validation report](AEVORA_H1_VALIDATION_REPORT.md),
[decision trace report](AEVORA_H1_DECISION_TRACE_REPORT.md), and
[limitations](AEVORA_H1_LIMITATIONS.md) for actual gate results. Prior reports below
remain the original records of their stages.

