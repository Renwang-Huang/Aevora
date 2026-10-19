# Phase 1 完成范围与扩展接口

下表保留 Phase 1 的交付边界。Phase 2 已在同一工程中增加 Episode A、Episode Registry、并发 RPC、宿主数据库 Oracle 和评测指纹；这些增量见 [Episode A](EPISODE_A.md)、[扩展规范](EPISODE_REGISTRY.md) 与 [Phase 2 验收报告](../PHASE2_VALIDATION_REPORT.md)。

| 模块 | 已实现并需实测验收的能力 | 尚未实现 |
|---|---|---|
| Business | 创建/预留、取消/释放、查询、幂等、SQLite 事务/初始化/重置、账本审计 | 支付执行、扣减确认、补偿、异步 Worker |
| Episode Framework | 公共协议和校验；SMOKE-001；A–D 的 PLANNED 配置 | A–D 故障、复现器、参考答案和真实 oracle |
| Runner | 加载、准备、手动提交、隔离评测、报告、重置、CLI | 自动实验调度、同 Run 并发协调 |
| Evaluator | 真实独立 pytest/JUnit；PASS/FAIL/ERROR/TIMEOUT；未实现分支 | 完整敌对代码安全与反作弊 oracle |
| Agent Adapter | 数据协议、真实手动提交与 SHA256 | Codex 自动启动/调度、多 Agent 执行事件采集 |
| Experience | 四接口数据协议、Disabled Adapter 与契约测试 | 检索、证据治理、决策持久化、反馈演化、MCP、FalkorDB |
| Reports | UUID、版本、提交引用、测试、时间、异常、Artifacts、Runner 事件 | Agent 分工、工具调用、token、经验事件和正式指标统计 |

Protocol、dataclass 和 `NotImplementedError` 属于已交付的扩展接口，不能视为相应业务能力已运行。报告将经验显示为 DISABLED、Agent 执行数据为 UNAVAILABLE/null。

Phase 2 首次复用相同 Episode/Submission/Report 协议增加了第二个真实场景：A/v01 的 fixture、14 项私有测试和独立 Oracle。Smoke 保持独立注册和 8 项必要测试。原有单阶段范围说明不表示 A 在当前版本仍为 PLANNED。

当前尚未实现 B/C/D、Codex 自动启动/调度、多 Agent 执行事件采集、GraphSwarm Core、经验检索/治理、MCP、FalkorDB、G0–G3 实验、Dashboard、完整支付与异步 Worker。Payment/Event 与 Agent/Experience 的 Protocol 属于扩展接口；不能算作相应功能已经运行。经验继续 DISABLED，未采集的 Agent 信息继续 UNAVAILABLE/null。

后续可按已验证的 Registry 增加其他场景，并在另行授权后接入 Codex 原生运行时和 ExperienceAdapter。经验层不得修改私有配置和测试标准。本轮停止在 Phase 2。

当前限制：要求 Linux user/mount/pid namespaces；本机网络 namespace 不可用，网络未隔离；未配置资源配额/seccomp；RPC 输出未限流；宿主 Oracle 检查实际数据库，但未提供完整敌对代码防护；同一 Run 并发协调、原生 Windows、wheel 发布和大规模实验运行未验证。Episode A 当前只声明单进程、多线程、SQLite 下的证据，不推断多进程或分布式环境结论。
