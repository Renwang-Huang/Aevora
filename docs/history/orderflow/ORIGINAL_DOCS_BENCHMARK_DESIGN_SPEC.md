# OrderFlow Incident Lab

> **Benchmark Design Specification · v1.0**  
> **定位：** 面向多 Agent 协作、跨任务经验继承与经验责任治理的可复现软件工程评测环境  
> **状态：** 设计规格（尚未实现和实测）  
> **运行底座：** Codex Native Multi-Agent  
> **历史项目名称：** GraphSwarm（经验治理模块暂用旧名称，待新项目命名冻结）

---

## 0. 执行摘要

**OrderFlow Incident Lab 不应被做成“让多个 Agent 修复四个 Bug”的代码仓库，而应成为一个能够持续制造工程决策困难、观测多 Agent 协作过程，并验证历史经验如何影响后续决策的实验环境。**

核心命题：

> 我们需要的不是一个能够让多个 Agent 一起完成的复杂任务，而是一个能够展示多个 Agent 如何协作、如何遭遇决策困难，以及历史经验如何改变后续决策的任务环境。

Benchmark 的验证目标依次为：

1. **Collaboration：** 多个 Agent 能否通过真实角色协作完成故障诊断、修复和验证？
2. **Persistence：** 一个 Agent 团队留下的经验能否在新会话、新任务中被其他 Agent 继承？
3. **Awareness：** Agent 能否判断历史经验 **WHEN** 适用、**WHY** 值得信任或需要拒绝？
4. **Accountability：** 经验介入决策之后，能否由独立验证产生 **FEEDBACK**，并反馈到经验的评价与演化？

**首个开发闭环：** 基础业务系统 → Episode A → Codex 原生 Multi-Agent → Episode D 的错误迁移识别。  
**完整 Benchmark：** Episode A/B/C/D + 独立评测器 + 经验治理接口 + G0–G3 对照实验。

> **重要边界：** Benchmark 必须在不接入经验治理系统的条件下独立运行、独立判分；经验治理系统只能影响 Agent 的决策，不得更改任务真值、隐藏测试或评测标准。

---

## 1. Benchmark 定位与研究问题

### 1.1 四层验证目标

| 层次 | 核心问题 | 主要验证对象 |
|---|---|---|
| L1 — Collaboration | 多个 Agent 能否有效协作？ | Codex Native Multi-Agent |
| L2 — Persistence | Agent 经验能否跨会话、跨任务传递？ | Experience Persistence |
| L3 — Awareness | 经验何时适用、为什么可信？ | WHEN / WHY |
| L4 — Accountability | 使用经验后，能否根据结果重新评价经验？ | FEEDBACK / Governance |

- **L1 是基础：** 能观测独立 Subagent、任务委派、协作产物以及独立测试结果。
- **L2 是前提：** 历史信息从一个 Episode 的执行过程进入另一个 Episode，但不靠继承聊天上下文作弊。
- **L3/L4 是真正的差异化：** 对经验的适用边界、证据和真实效果负责，而非仅仅检索相似文本。

### 1.2 非目标（第一版不做）

- 不重新开发 Codex 已原生具备的 Agent Orchestrator。
- 不以聊天机器人、小游戏、Todo 应用等过于简单的任务作为主要实验。
- 不把实现一个 MCP Server 作为项目创新点。
- 不在第一阶段引入 Kafka、Kubernetes 或真实第三方支付服务。
- 不在评测引擎尚未可信前，投入大量精力制作演示 Dashboard。
- 不以某一轮修复成功来宣称经验治理已经带来统计显著提升。

### 1.3 与行业评测体系的关系

参考既有评测思想，但不把 OrderFlow 宣称为现成的行业标准 Benchmark：

| 参考 | 可借鉴之处 | OrderFlow 进一步要验证的内容 |
|---|---|---|
| MetaGPT / ChatDev | 软件开发中的角色分工与协作流水线 | 避免角色扮演式流水线；记录真正的协作与决策冲突 |
| MultiAgentBench / MARBLE | 协作策略、沟通和阶段里程碑 | 将协作放入连续工程决策与跨任务经验场景 |
| SWE-bench | 真实代码仓库、Issue、补丁、外部测试 | 对经验适用边界和跨任务反馈建立可控实验 |
| Terminal-Bench | 工程环境操作与可验证交付 | 将环境变体与经验影响对应起来 |

参考入口：
- MARBLE：https://github.com/ulab-uiuc/MARBLE
- SWE-bench：https://github.com/SWE-bench/SWE-bench
- Codex 文档入口：https://developers.openai.com/codex/

---

## 2. 整体系统架构

```text
                    ┌──────────────────────────────────┐
                    │   Codex Native Multi-Agent       │
                    │                                  │
                    │ Lead / Investigator / Test       │
                    │ Engineer / Implementation /      │
                    │ Reviewer                         │
                    └────────────────┬─────────────────┘
                                     │
                  ┌──────────────────┴──────────────────┐
                  │                                     │
                  v                                     v
      ┌────────────────────────┐         ┌──────────────────────────┐
      │ OrderFlow Task World   │         │ Experience Interface     │
      │                        │         │ MCP / SDK (later)        │
      │ Orders / Inventory /   │         │                          │
      │ Payments / Workers /   │         │ resolve / evidence /     │
      │ Persistence            │         │ record / outcome         │
      └────────────┬───────────┘         └─────────────┬────────────┘
                   │                                   │
                   │                                   v
                   │                       ┌─────────────────────────┐
                   │                       │ GraphSwarm Core         │
                   │                       │ (name pending)          │
                   │                       │ WHEN / WHY / FEEDBACK   │
                   │                       │ FalkorDB Experience     │
                   │                       │ Graph                   │
                   │                       └─────────────────────────┘
                   │
                   v
      ┌────────────────────────────────────────────────┐
      │ Independent Evaluation Harness                 │
      │ - workspace reset / isolation                  │
      │ - hidden oracle & regression tests             │
      │ - patch evaluation                              │
      │ - decision traces / metrics / archival          │
      └────────────────────────────────────────────────┘
```

### 2.1 三条不可突破的边界

1. **Codex 是 Agent Runtime，不是我们需要重写的功能。** 首期直接用原生 Subagent 完成委派、并行调查、实施和审查。
2. **业务数据与经验数据隔离。** 业务订单、库存和支付状态保存在 SQLite；经验与决策溯源由独立经验系统和 FalkorDB 管理。
3. **评测器与 Agent 隔离。** Hidden Tests、参考修复、内部适用性标注以及评价真值不得暴露给待测 Agent。

### 2.2 推荐开发技术栈

- Python 3.12
- FastAPI
- SQLite（第一版业务持久化）
- pytest（基础、集成、确定性故障测试）
- Python `threading` / `multiprocessing`（多线程、多进程复现）
- Codex 原生多 Agent / Subagent
- 后期通过 MCP 或 SDK 接入经验治理服务
- FalkorDB（仅用于经验治理，不作为订单业务数据库）

> 所有依赖应在实际实现时固定版本；本规格不预先假定某个尚未验证的 Codex 配置参数或命令已经可用。

---

## 3. 业务任务世界：可运行的 OrderFlow

### 3.1 核心业务模块

| 模块 | 业务责任 | 关键故障维度 |
|---|---|---|
| Order Service | 创建、取消、查询订单与状态转换 | 状态机、重复请求、业务一致性 |
| Inventory Service | 预留、确认扣减、释放库存 | 并发竞态、原子性、账本一致性 |
| Payment Service | 发起、确认、重试支付 | 幂等、外部副作用、崩溃恢复 |
| Event Worker | 事件入队、消费、重试与恢复 | 重复投递、乱序、故障注入 |
| Persistence Layer | 业务持久化与事务管理 | 事务边界、共享状态一致性 |

### 3.2 最小业务路径

```text
Create Order
    ↓
Reserve Inventory
    ↓
Request Payment
    ↓
Record Payment Result
    ↓
Confirm Inventory & Mark Order Paid

Cancellation (where allowed)
    ↓
Release Reserved Inventory (exactly once)
    ↓
Update Order State
```

### 3.3 全局不变量

约定库存状态被划分为 `available`（可售）、`reserved`（预留）和 `committed`（已扣减）。当涉及补货时，满足：

```text
available + reserved + committed
    = initial_stock + replenished
```

要求：

- 库存不可为负；成功接受的订单不能超过可售库存。
- 同一个业务支付意图不得导致重复实际扣款。
- 同一事件重复投递不能导致重复业务副作用。
- 订单状态只能按合法状态机转换。
- 取消、付款确认以及补偿流程必须在业务上有明确定义。
- 所有关键业务状态应可以由持久化数据和账本审计。

**支付网关模拟器必须提供持久化的 Idempotency Key 语义。** 否则在崩溃后无法确定外部扣款是否已成功时，要求客户端系统单独实现绝对不重复扣款是不合理的。

### 3.4 业务基线要求

在引入任何 Benchmark Bug 前，先拥有一个逻辑正确且可以完整运行的系统。否则任务会退化为“让 Agent 补写系统”。

业务基线必须满足：

- 正常流程通过单元及集成测试；
- 初始化和重置数据库可重复执行；
- 支持稳定故障注入点和事件投递序列控制；
- 提供跨进程访问共享 SQLite 数据的测试能力；
- 可独立运行，不依赖 GraphSwarm。

---

## 4. 核心 Episode 设计

### 4.1 Episode A — Concurrent Inventory Corruption

**主题：** 高并发库存异常  
**研究作用：** 产生可验证的初始经验（Experience Generation）

**场景：** 单进程多线程下，200 次并发购买请求竞争初始 50 件库存。读取与更新之间存在竞态，造成更新丢失、重复接受订单或账本错误。

**Agent 可见的任务：** 订单系统在并发压力下间歇性库存不一致，需要定位根因、修复并增加回归测试。任务文字不直接告知缺陷位置或参考修复。

**成功判据：**
- 无超卖、无负库存；
- 已接受订单与库存预留/扣减账本一致；
- 公开及隐藏回归测试通过；
- 不允许直接修改库存结果、伪造通过记录或通过关闭并发绕过故障。

**经验维度：** 竞争条件、临界区、锁作用域、数据库事务和原子更新；记录所选策略的环境条件。

**重要说明：** Episode A 允许 Agent 自由选择正确修复策略，不能强迫其使用进程内锁。若 Agent 直接选择数据库级原子方案，应真实记录这一选择，而不是为了后续叙事修改历史。

### 4.2 Episode B — Duplicate Payment on Retry

**主题：** 支付重试与重复扣款  
**研究作用：** 正向经验迁移与适用边界辨别（Experience Transfer）

**场景：** 模拟支付网关已成功接受请求，但 Worker 在本地持久化支付结果之前崩溃；消息重新投递，可能造成重复扣款。

**成功判据：**
- 同一业务支付意图最多一次真实扣款；
- 超时重试、重复消息及崩溃恢复后状态一致；
- 业务和外部模拟支付记录可审计；
- 不通过进程内短时互斥锁或内存标记冒充持久幂等保证。

**经验维度：** 区分“避免同时执行”和“避免重复业务副作用”。并发经验可能提供线索，但不能直接替代幂等键与持久化恢复机制。

### 4.3 Episode C — Out-of-Order Cancellation Events

**主题：** 订单取消、支付确认与异步事件乱序  
**研究作用：** 经验修正与扩展（Experience Evolution）

**场景：** 取消、支付确认和库存释放事件重复、延迟或乱序到达，引发非法状态回退、库存重复释放或补偿流程遗漏。

**成功判据：**
- 状态转换遵循明确规则；
- 重复事件不重复释放库存或重复触发其他副作用；
- 订单、支付及库存账本最终一致；
- 对取消后迟到的已完成支付确认存在明确补偿或退款待处理状态。

**第一版业务定义：** 正常取消仅允许在支付成功前发起；若取消后收到已经完成的支付确认，应进入明确的补偿/退款待处理状态，不直接将取消订单改回已支付。

**经验维度：** 由局部并发保护扩展到版本检查、状态机、事件幂等、补偿和可审计的演化条件。

### 4.4 Episode D — Multi-Worker Lock Failure

**主题：** 从单进程多线程迁移到多 Worker 的一致性故障  
**研究作用：** 拒绝错误迁移（Negative Transfer Prevention）

**场景：** 服务扩容为多个独立 Worker，共享同一库存数据库。过去在单进程多线程条件下有效的 `threading.Lock` 不能约束其他进程。

**成功判据：**
- 至少两个 Worker 对共享库存并发操作仍维持一致性；
- Worker 重启、请求交错和数据库持久化场景通过；
- 不能退回单 Worker、关闭并发或仅使用进程内锁规避缺陷。

**经验维度：** 判断经验适用条件是否发生改变，识别锁的同步作用域，必要时 `VERIFY` 或 `ABSTAIN`，并选择共享持久化状态下有效的机制。

**避免任务答案泄露：** 面向 Agent 的 Issue 只能描述“扩容后出现库存异常”，不能直接以“进程内锁失效”命名任务或提示修复。

**实验严谨性：** 不假设 Episode A 的 Agent 一定产生某条错误可迁移经验。可以额外使用一条有真实测试依据、明确仅对单进程环境有效的**受控种子经验**来稳定测量拒绝错误经验的能力；必须标记为受控输入，不得伪装成未知 Agent 的历史产物。

### 4.5 两种 Episode 顺序

- **工程开发顺序：A → D → B → C。** 尽快用 A/D 打通“历史经验有效 → 环境改变 → 拒绝错误迁移”的最小闭环。
- **最终叙事顺序：A → B → C → D。** 用“经验产生 → 迁移 → 修正 → 拒绝错误应用”讲清整个故事。

---

## 5. 标准 Episode 格式与可重现性

### 5.1 每个任务实例的组成

| 组成 | 说明 | Agent 是否可见 |
|---|---|---|
| Base Repository | 含目标缺陷的可运行代码 | 是 |
| Incident Report | 症状、业务要求、禁止绕过的约束 | 是 |
| Runtime Context | 运行拓扑、数据库、环境信息 | 是 |
| Public Tests | 公开测试和允许的故障复现工具 | 是 |
| Hidden Tests | 独立判定正确性的测试 | 否 |
| Fault Specification | 真实缺陷位置与机制 | 否 |
| Reference Fix | 经过验证的参考修复 | 否 |
| Experience Labels | 经验适用与迁移的人工标注 | 否 |
| Evaluation Output | 执行后的结果、补丁与记录 | 运行后按实验权限提供 |

### 5.2 Manifest 示例（拟定接口，不代表已经实现）

```yaml
id: orderflow-episode-a-v01
family: inventory_concurrency
version: 1

environment:
  python: "3.12"
  database: sqlite
  topology: single_process_multi_thread

incident:
  title: "Inventory inconsistencies under load"
  initial_stock: 50
  concurrent_requests: 200

constraints:
  - No overselling
  - No negative inventory
  - No disabling concurrency
  - Preserve existing API behavior

evaluation:
  public_suite: tests/public/
  hidden_suite: evaluator/hidden/episode_a/
  timeout_seconds: 120

artifacts:
  - patch.diff
  - agent_trace.jsonl
  - evaluation_report.json
```

**隔离实施要求：** 实际应用中将 Manifest 拆为 `public.yaml` 与 `private.yaml`；私有配置中的 `hidden_suite` 路径、参考答案及评测标准不可出现在 Agent 可读取的工作区。上面的完整配置仅供 Benchmark 开发者理解。

### 5.3 Buggy / Reference 双重验证

每个 Episode 的发布门槛：

1. **Buggy Implementation：** 正常业务路径大体可用，但针对目标故障的可控测试稳定失败。
2. **Reference Implementation：** 目标故障、边界条件和主要回归测试稳定通过。
3. **独立复现：** 可在干净数据库和工作区中重跑；不依赖前一次测试残留。
4. **外部验证：** Agent 提交的是补丁，由独立评测器在隔离环境应用和检测。

### 5.4 确定性故障注入

并发 Benchmark 不能把随机压力测试作为唯一判分依据，应使用：

- 同步屏障 / Hook 强制触发读-改-写竞态；
- 指定在“支付成功、持久化记录前”崩溃；
- 固定事件投递顺序或重放脚本；
- 多进程启动屏障及共享数据库；
- 固定随机种子、初始化数据库快照、记录环境版本。

随机压力测试可作为补充鲁棒性测试，而不是唯一真值。

### 5.5 Episode 验收矩阵

| Episode | 必须测试 | 应排除的错误方案 |
|---|---|---|
| A | 200 并发、库存守恒、账本一致、回归 | 修改库存结果、关掉并发 |
| B | 重复事件、超时重试、支付后崩溃、恢复 | 内存已支付标记、仅用局部锁 |
| C | 事件重复、乱序、迟到支付、只释放一次 | 无条件改状态、重复释放、遗漏补偿 |
| D | 多 Worker、进程重启、共享库存一致性 | 局部线程锁、改回单 Worker、依赖偶然时序 |

---

## 6. Codex 原生 Multi-Agent 协作协议

### 6.1 Agent 角色

| 角色 | 职责 | 默认修改权限建议 |
|---|---|---|
| Lead Agent（主 Agent） | 解读 Issue、拆分任务、整合证据、协调执行与交付 | 协调所有操作 |
| Investigator | 调查代码路径、日志、依赖关系与可能根因 | 默认只读分析 |
| Test Engineer | 构造复现、边界案例、回归测试 | 测试目录写入，避免与实施者冲突 |
| Implementation | 依据诊断设计并实现修复 | 业务代码写入 |
| Reviewer | 独立审查补丁、约束与风险 | 默认只读验证 |

这些是推荐角色，不是自行开发 Python Agent 类或独立调度器。运行机制优先使用 Codex 自带的 Subagent / 任务委派能力。

### 6.2 标准协作序列

```text
Incident Intake (Lead)
    ↓
Parallel Investigation
    ├── Investigator → hypotheses / evidence
    └── Test Engineer → reproducible failing test
    ↓
Experience Decision Point (if enabled)
    ├── query relevant experiences
    ├── review evidence & applicability
    └── APPLY / VERIFY / ABSTAIN
    ↓
Implementation → patch
    ↓
Independent Review → findings
    ↓
Independent Evaluation Harness → verified outcome
    ↓
Experience Feedback (if enabled)
```

约束：

- 独立的分析任务允许并行；共享文件修改必须协调，避免写入冲突。
- 实际运行可迭代调查、重新规划和再次委派，不能为了流程好看掩盖真实决策分叉。
- Reviewer 的结论不等于最终评测真值；真值来自隔离测试环境。
- 必须保存真实子 Agent 任务委派/执行证据，不允许把一个 Agent 的角色扮演当作多 Agent 实验。

---

## 7. Experience Accountability 接入规范

### 7.1 决策链路

```text
Task & Current Context
         ↓
resolve_experience()
         ↓
Candidate Experiences
         ↓
build_evidence_bundle()
         ↓
APPLY / VERIFY / ABSTAIN
         ↓
record_decision()
         ↓
Agent Executes & Produces Patch
         ↓
Independent Hidden Test Oracle
         ↓
Verified Outcome
         ↓
submit_outcome() / Feedback Evolution
```

**WHEN：** 当前任务是否以及何时该参考某条经验。  
**WHY：** 该经验有哪些实际支持证据、失败案例、局限和适用边界。  
**FEEDBACK：** 被经验影响的决策完成后，实际测试结果是什么；该结果怎样更新经验可信度或适用边界。

### 7.2 最小 Experience Schema（示例）

```json
{
  "experience_id": "EXP-001",
  "strategy": "Use process-local mutex",
  "context": {
    "topology": "single_process",
    "concurrency": "multi_thread",
    "shared_state": "in_process_or_serialized_local_access"
  },
  "evidence": {
    "source_run_id": "RUN-A-001",
    "verified": true,
    "test_report_id": "REPORT-A-001"
  },
  "limitations": [
    "Not sufficient for cross-process coordination"
  ]
}
```

**注意：** `RUN-A-001` 等为示例 ID，不能视为已取得的测试证据。真正写入 `verified: true` 必须基于实际独立评测报告。

每条经验至少要存储：

- 来源任务、运行 ID、Agent 与时间；
- 当时采用的策略与决策理由；
- 环境拓扑与相关前提；
- 成功及失败的独立测试证据；
- 已知局限、风险与适用边界；
- 后续被查询、应用、验证、拒绝的记录；
- 经独立结果确认的演化历史。

### 7.3 Episode D 的负迁移示例

**历史经验：** 在单进程多线程环境，进程局部互斥锁能够保护进程内共享临界区（前提由测试支持）。

**当前任务：** 四个独立 Worker 访问同一个共享数据库。

**合理的经验层判断：**

```text
Decision: ABSTAIN (do not directly inherit old locking strategy)
Reason:
  A process-local mutex does not coordinate different processes.
Next step:
  Investigate database-level atomic updates / transactions
  and verify the selected scheme under multi-worker contention.
```

要区分：
- **经验判断正确：** 拒绝不适用的历史策略；
- **任务修复正确：** 最终补丁通过全部相关测试。

这两个结果需要分开评分。`VERIFY` 也必须对应真实验证步骤，不能只是更换一个状态标签。

### 7.4 可信反馈原则

- Agent 自己声称“修复成功”只能视为提交声明。
- `Verified Outcome` 必须由外部 Evaluation Harness 产生。
- GraphSwarm 可以记录主观反思，但不得将其当作独立测试替代品。
- 防止经验系统或 Agent 读取 Hidden Tests、Reference Patch 及私人标注。

---

## 8. 对照实验方案

### 8.1 实验分组

| 组别 | Runtime | 经验能力 | 核心目的 |
|---|---|---|---|
| G0 | 单 Codex Agent | 无共享经验 | 单 Agent 基线 |
| G1 | Codex Multi-Agent | 无共享经验 | 测量多 Agent 协作增益与成本 |
| G2 | Codex Multi-Agent | 普通历史经验检索 | 测量共享 Memory 的作用 |
| G3 | Codex Multi-Agent | Experience Accountability / Governance | 测量 WHEN、WHY、FEEDBACK 的额外价值 |

**核心比较：G2 vs G3。** G1 → G3 的变化混合了“拥有历史信息”和“具备经验治理机制”两种因素，不足以独立证明后者。

### 8.2 公平比较协议

1. 各组从相同代码 Commit、数据库状态和故障注入条件开始。
2. 固定模型版本、Agent 角色配置、工具权限、执行预算和测试截止条件。
3. 不同 Episode 启动全新 Agent Session，不继承未经授权的对话信息。
4. 跨任务经验只能通过 G2/G3 被允许的经验入口传输；G0/G1 不得读取历史。
5. G2/G3 尽可能使用相同历史任务数据与信息预算；区别是证据组织、边界判断、决策追溯与反馈机制。
6. 每次运行保存补丁、测试报告、运行日志、经验调用和决策事件。
7. 正式结论应覆盖多个故障变体与重复运行，单次 Demo 不能替代统计评估。
8. Episode D 的受控种子经验应明确作为实验条件，不能和自然生成经验混淆。

### 8.3 评价指标

| 指标 | 定义 | 数据来源 |
|---|---|---|
| Task Success Rate | 成功修复且通过必要独立测试的比例 | Hidden Oracle |
| Regression Rate | 引入其他业务故障的比例 | Regression Suite |
| Experience Decision Accuracy | APPLY / VERIFY / ABSTAIN 是否符合已知环境与证据 | 预先制定的适用性标注 + 审核 |
| Negative Transfer Rate | 不适用经验被错误采纳并造成负面影响的比例 | 决策日志 + 测试证据 |
| Verified Feedback Coverage | 被记录的经验使用中，具备独立结果关联的比例 | Decision / Outcome Traces |
| Token Cost / Latency | 执行所需资源消耗和耗时 | Runtime Logs |

注意事项：

- 不将“任务修好”直接等同于经验判断正确。
- 不将“查询了经验”直接等同于“经验影响了决策”。
- 经验适用性应依据运行前定义的环境前提与策略证据标注，允许存在多种正确修复策略。
- 正式报告同时呈现成功率、失败案例、负迁移、成本和局限，不能只展示有利指标。

---

## 9. 工程目录结构

```text
OrderFlow-Incident-Lab/
│
├── README.md
├── pyproject.toml
├── docker-compose.yml
│
├── app/                         # 基础业务系统
│   ├── api/
│   ├── orders/
│   ├── inventory/
│   ├── payments/
│   ├── workers/
│   └── persistence/
│
├── benchmark/
│   ├── scenarios/
│   │   ├── episode_a/
│   │   │   ├── public.yaml
│   │   │   └── incident.md
│   │   ├── episode_b/
│   │   ├── episode_c/
│   │   └── episode_d/
│   ├── fixtures/
│   └── fault_injection/
│
├── tests/
│   ├── unit/
│   ├── integration/
│   └── public/
│
├── evaluator/                   # Agent 运行时不可见
│   ├── private_manifests/
│   ├── hidden_tests/
│   ├── reference_patches/
│   ├── oracles/
│   ├── metrics/
│   └── runner.py
│
├── agent_profiles/
│   ├── investigator.md
│   ├── implementation.md
│   ├── test_engineer.md
│   └── reviewer.md
│
├── integrations/
│   ├── codex/
│   └── experience_client/
│
├── experiments/
│   ├── configs/
│   ├── run_experiment.py
│   └── results/
│
└── docs/
    ├── BENCHMARK_SPEC.md
    ├── EPISODE_DESIGN.md
    └── EVALUATION_PROTOCOL.md
```

### 9.1 工程分层责任

- `app/`：正常业务代码，可在独立工作区植入故障变体。
- `benchmark/`：公开任务描述、场景初始化与受控故障装置。
- `tests/public/`：Agent 可以访问的公开测试。
- `evaluator/`：任务真值、隐藏测试、参考补丁、独立判定，仅评测宿主可访问。
- `agent_profiles/`：推荐的 Codex 角色定义，不额外实现 Orchestrator。
- `integrations/`：对 Codex 和经验接口做薄适配；经验核心逻辑不写在 Benchmark 内。
- `experiments/`：执行实验组、归档结果和统计指标。

**运行安全：** 即使 `evaluator/` 存在于开发者源码仓库，创建 Agent 工作区时也必须物理隔离，不能只靠“请勿查看”这样的提示词保证安全。

### 9.2 推荐 CLI（待实现的接口，不代表现有可运行命令）

```bash
# 检查场景与故障注入是否有效
orderflow validate --episode A

# 初始化干净任务环境
orderflow prepare --episode A --variant v01

# 使用 Codex 原生多 Agent 执行任务
orderflow run --episode A --agent codex-multi

# 在隔离环境独立评测提交补丁
orderflow evaluate --run-id <run_id>

# 执行对照实验
orderflow experiment --group G3 --suite core
```

每次运行至少归档：

```text
runs/<run_id>/
├── patch.diff
├── agent_trace.jsonl
├── evaluation_report.json
├── runtime_metadata.json
└── artifacts/
```

`agent_trace.jsonl` 应记录真实可观察的任务委派、工具调用和经验接口事件；无法从 Codex 原生日志确定的信息不能由 Agent 自述伪装为底层事件。

---

## 10. 开发里程碑与验收标准

| Milestone | 交付内容 | 通过门槛 |
|---|---|---|
| M1 — OrderFlow Core | 正常业务、Schema、初始化、测试 | 正常业务流程通过、可重置、无故障注入 |
| M2 — Episode A | 库存竞态、可控复现、参考修复、隐藏测试 | Buggy 稳定失败；Reference 稳定通过 |
| M3 — Codex Multi-Agent | 原生子 Agent、任务委派、补丁与评测 | 可观察真实子 Agent，补丁被独立评测 |
| M4 — Episode D | 多 Worker 和不适用经验的受控实验 | 旧经验在原条件下有效、新环境下不足，可独立评价拒绝决策 |
| M5 — Episode B/C | 支付重试、事件乱序及对应评测 | 四个 Episode 均可初始化、复现、修复、评分 |
| M6 — Experience & Ablation | 经验接口、FalkorDB、G0–G3 实验 | 经验查询→决策→结果→反馈证据链可追踪 |

**优先级逻辑：** 先保证 Benchmark 的公正性和可重复性，之后才有资格讨论经验治理的效果。

### 10.1 第一版 MVP 冻结范围

- 第一阶段只开发 M1，不越界实现四个 Episode。
- M2/M3 验证真实软件工程协作，而非角色扮演。
- M4 尽早验证最具辨识度的经验适用边界问题。
- M5/M6 再完整展开正向迁移、演化和对照实验。
- 演示 UI 最后开发，不妨碍 CLI 先提供完整证明材料。

---

## 11. 交付给 Codex 的首轮开发指令（M1）

以下内容可直接复制给 Codex 执行。

```text
# OrderFlow Incident Lab — Milestone 1

你需要构建一个名为 OrderFlow Incident Lab 的多 Agent 软件工程
Benchmark 的基础业务系统。

## 项目目标

这是一个用于验证 AI Agent 协作、跨任务经验继承和决策反馈治理
的可复现测试环境。

当前只执行 Milestone 1：构建可运行、可测试、可重置的订单处理系统。

不要在本阶段实现 GraphSwarm、MCP、经验治理引擎、四个故障
Episode 或前端 Dashboard。

## 技术要求

- Python 3.12
- FastAPI
- SQLite
- pytest
- 模块化设计，明确业务服务边界
- 兼容 Windows + WSL2 开发环境
- 关键依赖固定版本

## 核心业务模块

1. Order Service：订单创建、查询、取消与状态管理。
2. Inventory Service：库存预留、扣减、释放与库存账本。
3. Payment Service：模拟支付网关、交易记录及幂等请求。
4. Event Worker：事件入队、消费与基础重试。
5. Persistence Layer：订单、库存、支付及事件状态持久化。

## 业务约束

- 库存数量不能为负。
- 订单与库存账本必须一致。
- 同一支付意图不能重复扣款。
- 同一个事件重复消费不能产生额外业务副作用。
- 状态转换必须符合明确的订单状态机。
- 测试数据必须能够恢复到初始状态。

## 架构要求

- 保持业务代码、公开测试和未来独立评测器的边界清晰。
- 为后续故障注入预留可控的测试接入点。
- 支持未来从单进程扩展到多 Worker 环境。
- 不要通过编写大量 Mock 替代可运行的业务逻辑。
- 正常业务实现优先保证正确性，不要提前注入 Benchmark 故障。

## 工作方式

使用 Codex 原生 Subagent 机制开展独立设计审查、代码实现与
测试工作。协调并行写入，避免多个 Agent 修改同一文件产生冲突。

## 必须交付

1. 项目目录结构及架构说明。
2. 可直接运行的基础业务服务。
3. 数据库 Schema 与初始化工具。
4. 正常业务流程的单元和集成测试。
5. 一键重置测试环境的方法。
6. README，说明安装、运行和测试步骤。
7. Milestone 1 验收报告，包括实际执行过的测试与结果。

完成后停止，不要擅自推进后续 Milestone。
```

---

## 12. 关键设计决策冻结

| 决策项 | 当前建议 |
|---|---|
| Benchmark 名称 | **OrderFlow Incident Lab**（工作名称） |
| 核心任务 | 真实工程语境下的复杂故障诊断与修复 |
| Runtime | Codex 原生 Multi-Agent |
| 业务底座 | Python 3.12 + FastAPI + SQLite + pytest |
| 核心 Episode | A、B、C、D 四个连续经验主题 |
| 工程优先顺序 | M1 → A → Codex Multi-Agent → D → B/C → 治理实验 |
| 对照组 | G0 单 Agent、G1 多 Agent、G2 多 Agent + Memory、G3 多 Agent + Governance |
| 评测真值 | 与 Agent 隔离的 Hidden Oracle |
| 经验系统边界 | 与 Benchmark 独立，通过标准接口接入 |
| Dashboard | 在可运行、可追踪、可测量之后开发 |

## 13. 需要在实现中坚持的审查清单

- [ ] 正常业务系统先通过测试，再注入缺陷。
- [ ] Agent 看不到私有测试、参考修复、适用性标注。
- [ ] Buggy 版本稳定失败，Reference 版本稳定通过。
- [ ] 每个任务可重置、可独立复现，不依赖前一轮污染状态。
- [ ] 真正使用 Codex 原生子 Agent，而不是单 Agent 角色模拟。
- [ ] 不因演示效果强行固定某一种修复策略。
- [ ] 经验记录必须带出处、证据和适用边界。
- [ ] Agent 自述与独立验证结果严格区分。
- [ ] Episode D 的受控经验有真实来源且标注清晰。
- [ ] G2/G3 信息来源、模型和预算尽可能可比。
- [ ] 保留失败案例与负迁移情况，不只展示成功结果。

---

## 14. 最终叙事

Benchmark 所要展示的不是“多个 Agent 在终端同时编写代码”，而是：

1. **Episode A：** 第一个 Agent 团队留下经过验证的工程经验。
2. **Episode B：** 后来的团队在新故障中判断哪些经验可以迁移。
3. **Episode C：** 新结果促使经验边界和策略持续修正。
4. **Episode D：** 环境条件发生改变，团队主动拒绝不适用的历史策略。

> **Agents should not merely remember what worked. They should understand when it still works — and be accountable when it doesn't.**

**最终原则：先把 OrderFlow Incident Lab 建成没有 GraphSwarm 也能独立运行、客观判分的高质量 Benchmark，再让经验责任治理层在同一组任务环境上证明自身价值。**
