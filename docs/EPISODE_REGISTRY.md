# Episode Registry 扩展规范

Phase 2 将 Smoke 专属准备与评测选择移出 Runner 生命周期。现在 `SMOKE-001` 与 Episode A 通过同一个 `BenchmarkRunner` 接口完成 `Load → Prepare → Execute → Evaluate → Report → Reset`，分别使用自己的 fixture、公开测试、私有 suite、参考补丁与运行归档。

## 两个可信注册表

`benchmark/registry.py` 的 `EpisodeRegistration` 负责场景构造：

| 字段 | 意义 |
|---|---|
| `episode_id` | 与 public/private Manifest 一致 |
| `fixture_version` | 故障工作区构造协议版本 |
| `suite_id` | 对应独立 Evaluator suite |
| `default_variant`、`variants` | CLI 默认变体及合法选择 |
| `fixture_factory(destination, variant)` | 在新目录构造候选业务源码，不执行候选业务 |
| `public_tests` | 复制到该 Episode 公开工作区的测试文件 |

`register_episode()` 拒绝重复 ID 和未注册的默认变体；`build()` 拒绝未知变体。Runner 通过 `get_episode()` 查工厂，不在核心准备/提交流程中判断某个 Episode ID。

`evaluator/suites.py` 的 `EvaluationSuite` 负责可信测试：suite ID、suite version、私有 suite 路径和对应 Manifest。`expected_tests` 从宿主 private Manifest 读取并校验为非空、唯一的必要测试身份集合；suite/version 必须与注册匹配。

当前注册对应为：

| Episode | CLI 变体 | Fixture | Suite / version | 必要测试 |
|---|---|---|---|---:|
| `SMOKE-001` | `default` | `benchmark/templates.py` / `1.0.0` | `smoke / 2.0.0` | 8 |
| `A` | `v01` | `benchmark/episodes/episode_a.py` / `1.0.0`，内部 `stale-snapshot` | `episode_a / 1.0.0` | 14 |
| `D` | `v01` | `build_episode_d_fixture` | `episode_d` | IMPLEMENTED |
| `B/C` | 无实现变体 | 无已实现工厂 | 无已实现 suite | NOT_IMPLEMENTED |

这两个简单映射属于宿主可信配置，不是动态插件系统，也不接受候选提交注册自己的判分规则。

## 新增 Episode 的最小路径

新增场景必须经过独立开发授权；以下是扩展接口要求，不表示其他 Episode 已实现。

1. 在 `benchmark/scenarios/<ID>/public.json` 定义版本、任务、运行拓扑、初始 fixture 和公开约束。实现完成前保持 `PLANNED`，不填写虚假的 readiness。
2. 在 `evaluator/private_manifests/<ID>.json` 定义 implemented、suite/version、fixture version、timeout、expected count 与完整 expected tests。参数化测试需包含其实际参数 ID，避免只校验总数。
3. 在 `benchmark/episodes/` 新增工厂，仅在指定目录构造普通业务源码。保留候选 API，独立实现有实际执行路径的故障变体及维护者参考补丁。
4. 新增该场景公开回归测试和宿主私有 suite，使用通用 RPC；若需并发，调用 `BusinessRPC.batch()`，勿用宿主串行转发冒充候选并发。
5. 在 Episode Registry 注册工厂、合法变体和公开测试；在 Evaluator suite 注册可信 suite 路径和版本。保持两侧 ID 与 Manifest 一致。
6. 通过现有 CLI 验证 prepare、patch/workspace submission、独立评测、report、reset 和重复初始化。缺陷必须失败，参考修复必须通过；保留原有场景回归与隔离检查。

这些接入点不要求修改 Runner 核心生命周期。确需扩展新的通用业务能力时，应增加通用 RPC/协议，隐藏断言、测试集合和答案继续留在可信宿主。

## Factory 与 Fixture 责任

Factory 返回包含 `app/` 的新工作区。Runner 负责复制相应公开测试与 public.json/TASK.md，并用可信 `app.service.OrderFlow` 初始化业务数据库。候选源码不会在宿主初始化期间导入执行。补丁应用到对应 Episode/Variant 的新缺陷基线；工作区提交仅复制普通 app Python 文件，不复制候选测试、pytest 配置或报告。

每个私有测试自己初始化独立 SQLite 数据目录；真正的初始状态由宿主 fixture 决定。业务 reset 后再运行应得到相同语义结果，Run ID、时间、线程 ID 和测试耗时不要求相同。公开工作区 reset 重建可信数据库并原子替换，保留代码与归档。

Scenario variant 是可追踪的配置值，不是判分答案。A 的 CLI `v01` 映射为工厂内部 `stale-snapshot`；若将来新增合法变体，必须同时提供真实工厂、独立可复现证据与相应测试标准，不能只改报告标签。

## Evaluator 完整性与 Oracle

每个 suite 有自己的必要测试集合与数量。PASS 同时要求 pytest 退出 0、JUnit 可解析、计数正确、身份集合完整且无重复、无 failure/error/skip。缺失必要测试、跳过或改名导致 ERROR；真实断言失败为 FAIL；整套执行超过场景限额为 TIMEOUT。

宿主 SQLite Oracle 的接口为：

```python
inspect_database(
    db_path,
    expected_stock=trusted_fixture_stock,
    data_dir=trusted_test_data_dir,
)
```

调用前须关闭候选 Worker，使业务线程停止，再读取真实数据库。Oracle 文件不挂载给 Agent；它不依赖 candidate.audit()。新场景需要新业务不变量时，可添加宿主 Oracle 能力或专属 Oracle，不能让候选自己决定 PASS。

现有 Oracle 同时执行 36 项 SQLite 语义约束探针：每项从源数据库 backup 到独立内存副本，建立合法 fixture 后在 SAVEPOINT 中尝试非法写入，以外层 RELEASE 覆盖 deferred 约束并在必要时 ROLLBACK。它不修改原数据库，也不通过 SQL 字符串比较指定唯一修复策略。约束探针结果与真实行对账均进入宿主证据。

失败断言前先保存 batch 与 Oracle 证据；报告保留原始 artifact 路径和结构化结果。A 的 batch 证明同 PID、多线程及重叠调用，可信数据库检查证明实际库存/订单/账本状态。Worker 只有通用执行和调度观测，不包含某个 Episode 的成功数量或隐藏答案。

## 版本与记录

Public/private Manifest、工厂、suite 和真实运行环境组成评测条件。每个 Run 记录唯一 ID、Scenario version/variant、Fixture/Suite version、Evaluator version、源码/私有配置 SHA256、提交摘要、Python/SQLite/工具版本、JUnit、JSON Report 和 Runner trace。Runner 核对准备、评测前、评测后的可信指纹；变化为 ERROR，须用当前条件创建新 Run。源代码改变后，真实 SHA256 必须改变；不能复用旧记录伪装重验。

新增测试或 Oracle 规则应更新对应 suite version，必要时更新 fixture/scenario version，明确结果比较边界。不得把 A 的测试结果赋予其他 Episode。`PLANNED` 始终对应 `NOT_IMPLEMENTED`，经验继续独立于任务真值。

M1 增加带默认值的 `execution_strategy`：既有注册使用 `single-worker`，D 使用 `shared-db-workers`，Public/Private/Registry/Suite 合同互相校验。D 的 Scenario 2.0.0、Fixture 1.0.0、Suite 1.2.0 和 Evaluator 3.1.0 分开记录。独立多 Worker 私有 fixture、Oracle 与 [Task Package 规范](TASK_SYSTEM_DESIGN.md)见 [Episode D](EPISODE_D.md)。新增场景仍复用同一 Runner prepare/evaluate/reset/report/Codex submission 路径。

参考成熟工具为 [pytest](https://docs.pytest.org/en/stable/how-to/usage.html)、[Python ThreadPoolExecutor](https://docs.python.org/3.12/library/concurrent.futures.html#threadpoolexecutor)、[SQLite](https://www.sqlite.org/lang_transaction.html) 与 [bubblewrap](https://github.com/containers/bubblewrap)。没有增加 Agent Orchestrator、MCP、FalkorDB、经验治理系统或 Dashboard。
