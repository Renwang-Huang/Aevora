# Aevora Core

此包保留Python/FalkorDB历史对照和维护者API。原生用户安装与Go/SQLite入口见
[项目快速开始](../docs/QUICKSTART.md)；不需要安装本包才能运行原生产品。

独立的经验治理 Python 包。FalkorDB 保存实际图记录；Core 提供适用性解析、
证据解释、候选生命周期、受限 MCP 和可信 Host CLI。

```sh
python3.12 -m pip install ./aevora_core
```

部署和普通项目接入见[快速开始](../docs/QUICKSTART.md)。公开安装不依赖
OrderFlow Runner、Evaluator、私有审计或原始模型记录。

## 接口

- `GraphRepository`：真实 SDK、约束、稳定记录与有界 Cypher。
- `ExperienceResolver` / evidence bundle：图中的前提、支持、反例与 UNKNOWN。
- `CandidateLifecycle`：不可信提议、来源核验、有界 review、发布与撤回。
- CLI：可信 Host 初始化、健康、查询、检查和管理。
- Host 启动：configure 保存设置，serve 每次创建新会话，mcp-config 生成稳定连接配置。
- `source-project`：独立项目来源契约与 Host 核验，见[完整接入路径](../docs/PROJECT_SOURCES.md)。
- MCP：查询、证据包、记录不可信决策与可选提议，不提供 admin/Cypher/Outcome 工具。

图为空和零候选合法。Agent 的声明或项目自测不会自动成为 VerifiedOutcome；
实际结果也不单独证明经验采纳或因果收益。多语句写入不保证全局事务。

参考：[架构](docs/ARCHITECTURE.md) · [Schema](docs/GRAPH_SCHEMA.md) ·
[查询](docs/QUERY_COOKBOOK.md) · [安全与生命周期](docs/SECURITY.md)。
