# Episode A — Concurrent Inventory Corruption

Episode A 在 Phase 2 接入既有 Runner，用真实的单进程、多线程 SQLite 业务竞争验证第一次正式场景扩展。Smoke 与 A 分别构造工作区、选择测试套件和归档结果；B/C/D 继续 `PLANNED / NOT_IMPLEMENTED`。

| 配置 | 当前值 |
|---|---|
| Episode / Scenario version | `A / 1.0.0` |
| CLI scenario variant | `v01` |
| 内部 fault variant | `stale-snapshot` |
| Fixture version | `1.0.0` |
| Evaluator suite / version | `episode_a / 1.0.0` |
| 必要私有测试数 | 14 |
| 初始库存 / 请求 / 每单数量 | 50 / 200 / 1 |
| 拓扑 | 一个 sandbox Worker、200 个线程池槽位、每单独立 ID |
| SQLite busy 等待 | 30 秒 |
| 整套评测上限 | 120 秒；CLI 可降低 |

## 真实缺陷

正确业务源代码位于 `app/`。`benchmark/episodes/episode_a.py` 复制该基线，仅修改 `service.py` 与 `inventory.py`，形成以下错误路径：

1. `create_order()` 在写事务之前通过另一条连接读取库存快照。
2. 可选同步观测点位于读取之后、写事务之前。
3. 在原有 `BEGIN IMMEDIATE` 事务中创建订单，依据之前的快照判断容量。
4. 把 `snapshot.available - quantity`、`snapshot.reserved + quantity` 作为绝对值写回，再写订单与预留账本。

这是现实中“把读取移出事务以缩短写锁持有时间”可能引入的 TOCTOU/Lost Update。单线程读取仍新鲜，基础预留和取消路径可用；多线程会把相同的旧库存用于不同订单。写事务虽然依次提交，却未重新验证库存，也无法修正事务外已计算的值。

该变体完整保留原有 CHECK、外键、唯一账本约束、连接策略及事务实现。假设两个线程都读到 `(available=50, reserved=0)`，各自依次写入 `(49,1)` 并写一条独立订单/账本。库存行仍满足非负和 `49 + 1 = 50`；两条预留账本合计 2，实际库存只记录 1。数据库行 CHECK 和 `UNIQUE(order_id,action)` 无法表达跨多个订单的整体账本关系，宿主 Oracle 会发现差异。

当受控首波 200 个请求均在写入前读取相同初始快照时，可观察到 200 个成功订单/预留账本、可用库存 49、预留库存 1。缺陷复现不要求固定输出这些错误数字；判据始终是实际业务不变量和可信数据库状态。普通未受控竞争也单独测试。

## 并发执行与确定性窗口

宿主发一个 `batch` RPC，Worker 内的 `ThreadPoolExecutor` 将普通业务方法提交给线程池。所有操作共享一个 `OrderFlow` 实例，但每次数据库操作创建自己的连接。普通单条 RPC 仍顺序处理；在宿主创建多个客户端线程不能替代这条 Worker 内并发路径。

`synchronize_start=True` 时，首波 `min(max_workers, requests)` 个任务通过 `threading.Barrier` 同步起步。后续排队任务不加入首波屏障。可选 `_schedule_checkpoint("inventory_read")` 在真实库存读取之后等待 Event：首波参与者全部到达时放行，或首次等待超过两秒后永久放行。没有使用随机 sleep 作为唯一复现手段，也没有修改库存结果或人为制造业务异常。

checkpoint 是通用调度观测装置，不包含隐藏断言或修复答案。参考修复可以移除该调用；使用锁且串行到达 checkpoint 的实现也会在有限等待后继续，不会要求所有线程进入锁内才能释放。隐藏测试不要求修复保留某条错误路径或采用 `threading.Lock`。

每条 batch 结果记录 `pid`、`thread_id`、`start_ns/end_ns` 与独立业务结果；batch 执行元数据记录线程集合、最大同时处于业务调用中的数量、线程池参数和 checkpoint 到达/放行信息。必要并发测试检查同一 PID、多线程与重叠调用。SQLite 将写事务串行化是正常持久化行为，线程业务入口仍保持并发。[SQLite 单写者及隔离说明](https://www.sqlite.org/isolation.html)

## 参考修复与独立判据

维护者补丁 `evaluator/reference_patches/A-v01.diff` 从缺陷工作区恢复正确基线：创建订单和预留共用写事务；库存使用带容量条件的增量 UPDATE；容量不足抛出明确业务错误并回滚创建订单。它没有关闭并发入口、降低请求数或更改测试条件。

对一个 SKU、同一合法数量、互不相同的订单 ID，测试按参数计算：

```text
accepted = min(request_count, initial_stock // quantity)
insufficient = request_count - accepted
available = initial_stock - accepted * quantity
reserved = accepted * quantity
```

基准相应为 50 成功、150 库存不足、可用 0、预留 50。所有请求须有明确结果；SQLite OperationalError、IntegrityError 或其他非预期异常不能被当成库存不足。宿主同时核对返回成功的订单 ID、数据库成功订单集合和预留账本集合。

判据允许事务内读取、条件原子更新或适当范围的锁等不同正确策略。SQLite 自身只允许一个同时写入的事务；`BEGIN IMMEDIATE` 与条件更新是本仓库参考修复选择，不是隐藏测试要求的唯一写法。[SQLite 事务与 BEGIN IMMEDIATE](https://www.sqlite.org/lang_transaction.html)

## 私有测试与数据库 Oracle

14 项私有测试覆盖：

| 测试组 | 项数 | 核心检查 |
|---|---:|---|
| 单线程 | 1 | 购买、耗尽与明确库存不足 |
| 基准并发 | 1 | 50 库存、200 请求、真实同进程多线程 |
| 高竞争 | 1 | 1 件库存、40 请求、20 workers |
| 参数化 | 4 | 库存 7/23/0；17 库存、每单 3 件；不同 workers/request 数 |
| 非法请求混合 | 1 | 合法成功、非法业务错误、无持久状态污染 |
| 取消回归 | 1 | 重复取消只释放一次 |
| 初始化/重复执行 | 1 | 两次重新初始化后的独立并发运行 |
| 普通竞争 | 1 | 不启用读取 checkpoint 的 batch |
| 多 SKU | 1 | 独立库存与订单/账本账户 |
| 创建/预留幂等 | 1 | 重复请求不重复记账 |
| 容量不足回滚 | 1 | 不遗留订单或账本 |

每项使用自己的 SQLite 数据目录。batch 原始结果先写入 `concurrency-*.json`；Worker 完成并关闭后，可信宿主调用 `evaluator/oracle.py` 并写 `oracle-*.json`，再执行断言，故障证据不会因断言失败丢失。

Oracle 拒绝数据库及 sidecar 的符号链接、硬链接、非常规文件或目录外路径。它以只读 URI 和 `query_only` 查询 SQLite，执行 `integrity_check`、`foreign_key_check`，记录真实 Schema/索引/FK/CHECK 信息，并独立验证：

- SKU 集合及初始库存与宿主 fixture 一致；候选存储的 initial_stock 不单独定义真值。
- 库存非负、守恒，与账本 delta 聚合相符。
- 订单状态、预留状态、数量合法，实际 active 订单预留量与库存相符。
- 账本的订单、SKU、动作、数量、delta、唯一动作及状态关系正确。
- 业务成功结果与真实持久订单、账本数量和身份集合一致。

为验证约束确实生效，Oracle 为每项语义探针创建独立 SQLite 内存 backup，构造合法的库存/订单/账本 fixture，再在 SAVEPOINT 中尝试非法写入。36 项探针覆盖 CHECK 对应语义、NOT NULL、唯一性及 FK；外层 RELEASE 也检查 deferred FK，失败则 ROLLBACK。源数据库始终只读，错误尝试仅发生在可丢弃副本。报告保存每项探针的实际拒绝/错误结果；CHECK 字样或一个无效 CHECK(1) 不能替代语义约束验证。

Episode A 判分不调用候选 `audit()`。Smoke 保留原有 audit() API 回归断言，并增加相同宿主检查。宿主 Oracle 加强真实性，但本阶段未实现完整敌对代码反作弊机制。

## 维护者运行方式

```bash
scripts/orderflow validate --episode A --variant v01
scripts/orderflow prepare --episode A --variant v01
scripts/orderflow shell --run-id <run_id> -- /usr/bin/python3.12 -m unittest discover -s tests/public

# 正式 suite；默认 Buggy 预期 FAIL / 退出 1
scripts/orderflow evaluate --episode A --variant v01

# 维护者参考补丁预期 PASS / 退出 0
scripts/orderflow evaluate --episode A --variant v01 \
  --submission evaluator/reference_patches/A-v01.diff

# 单独观察基准 batch 与真实数据库
scripts/python312 scripts/reproduce_episode_a.py
scripts/python312 scripts/reproduce_episode_a.py \
  --submission evaluator/reference_patches/A-v01.diff

scripts/orderflow report --run-id <run_id>
scripts/orderflow reset --episode A

# 包括 Phase 1 回归和 10 轮独立 Buggy/Reference 完整 suite
scripts/python312 scripts/validate_phase2.py
```

手动统一补丁或含 `app/` 的工作区也可提交；Runner 在独立候选快照中处理。Run 结束后清理评测数据库并恢复公开初始数据库，归档提交与测试证据。重跑必须使用新的 Run ID。

最终真实命令、退出状态、失败记录、10 轮 Buggy/Reference 独立初始化、Phase 1 回归与隔离验证见 [PHASE2_VALIDATION_REPORT.md](history/phase1-3/PHASE2_VALIDATION_REPORT.md)。本说明描述实现与判据，不替代实际验收结果。

## 可追踪证据与边界

每个 Run 保存 Scenario Version/Variant、Fixture/Suite Version、Evaluator 和 Private Manifest SHA256、提交/补丁及已评测代码摘要、运行环境版本、逐项测试结果、并发和 Oracle 证据。准备至评测前、评测前至结束的可信指纹变化将判 ERROR，防止旧工作区对应新的测试条件。没有实际采集 Agent 分工、策略决策、经验检索或反馈；报告相应字段保持 UNAVAILABLE/null 或 DISABLED。后续经验只能基于真实环境和提交证据产生，不预设 Agent 一定选择进程内锁。

当前仅声明单进程、多线程、SQLite 的验证范围；多 Worker、进程间锁、支付重试和乱序事件不属于 Phase 2。网络隔离、完整资源配额、完整恶意代码防护、Codex 自动调度、GraphSwarm/MCP/FalkorDB 和 G0–G3 实验尚未实现。

## 成熟实现依据

- [Python 3.12 ThreadPoolExecutor](https://docs.python.org/3.12/library/concurrent.futures.html#threadpoolexecutor) 与 [threading.Barrier/Event](https://docs.python.org/3.12/library/threading.html)：直接复用标准并发工具。
- [Python sqlite3 连接/timeout/URI](https://docs.python.org/3.12/library/sqlite3.html)：每次操作独立连接，busy 等待和宿主只读查询。
- [SQLite isolation](https://www.sqlite.org/isolation.html) 与 [transaction](https://www.sqlite.org/lang_transaction.html)：解释写串行化、事务边界以及为何事务外旧快照仍会损坏业务关系。
- [CPython 3.12.13 SQLite connection 实现](https://github.com/python/cpython/blob/v3.12.13/Modules/_sqlite/connection.c)：SQLite 调用周围存在 `Py_BEGIN_ALLOW_THREADS`，GIL 不构成跨连接业务原子性保证。
