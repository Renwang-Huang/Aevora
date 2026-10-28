# Core 架构参考

包的应用边界见[项目架构](../../docs/ARCHITECTURE.md)。本页定位具体实现。

| 层面 | 实现 | 职责 |
|---|---|---|
| 记录契约 | `models.py`、`proposal_contract.py` | canonical 载荷、身份、字段/事实 allowlist |
| 适用性与解释 | `experience_resolver.py`、`evidence_bundle.py`、`governance.py` | WHEN/WHY、支持/反例、事实作用域和快照 |
| 候选与反馈 | `candidate.py`、`admission.py`、`feedback.py` | 状态转移、可信来源、有界发布、追加反馈 |
| 图与恢复 | `graph_repository.py`、`checkpoint.py` | 官方 SDK、约束、存取、幂等和恢复边界 |
| 接入 | `cli.py`、`mcp_server.py`、`mcp_broker.py`、`mcp_connect.py` | Host CLI、官方 SDK、run-scoped transport |
| 具体来源 | `orderflow_outcome_bridge.py`、`historical_import.py` | 显式可信 OrderFlow adapter |

文件位于 `src/aevora/`。普通查询与 scoped transport 不需要私有实验包；
OrderFlow source 验证才加载其私有 parser/admission。私有 Audit Capsule
实现位于维护者包，公开 alias 不包含该实现体。

Core 决定业务语义，Console 只读投影，原生 Runtime 承担 Agent 协作。
GraphRepository 的多个职责、部分延迟循环与 Host adapter 的具体格式耦合
仍是可演进边界；当前文档整理不宣称这些运行逻辑已重构。

[Schema](GRAPH_SCHEMA.md)定义记录与图路径；[查询参考](QUERY_COOKBOOK.md)
说明实际访问；[安全与生命周期](SECURITY.md)说明权限、状态和恢复限制。
