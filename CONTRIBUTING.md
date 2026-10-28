# Contributing

Aevora 的公开产品由 Core、Console、演示和部署文件组成。按功能修改对应
模块，并在现有指南中更新使用方式。架构与信任边界见 [架构](docs/ARCHITECTURE.md)。

## 本地开发

原生产品在`go-runtime/`，使用go.mod固定的Go工具链；Python 3.12用于参考实现与
开发评测，前端版本固定在`console/.nvmrc`、package.json和lockfile。

```sh
cd go-runtime
go test ./...
CGO_ENABLED=0 go build -o /absolute/external/output/aevora ./cmd/aevora
```

本地工作流契约见[LOCAL_WORKFLOW](docs/LOCAL_WORKFLOW.md)。开发只运行相关检查，
服务/真实客户端/故障与领域回归在功能收口后集中验收；模型调用单独授权。

```sh
python3.12 -m venv .venv
.venv/bin/python -m pip install -e ./aevora_core -e ./console pytest==9.1.1
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/python -m pytest -q aevora_core/tests/unit
python3 tools/sync_public_evidence.py --check
npm --prefix console ci --ignore-scripts
npm --prefix console test
npm --prefix console run build
```

单元检查不需要数据库或模型。前端构建会更新 Python 包中的 static 文件；
提交前检查生成内容与源码的一致性。公开证据工具的唯一作者来源是
`tools/public_evidence/`，使用现有同步命令生成分发副本。

## 提交改动

- 一次改动围绕一个明确职责，说明行为变化、运行前提、实际检查和限制。
- 增加或修复契约时保留有效断言；错误、空数据和撤销路径同样需要覆盖。
- 不提交凭据、grant、数据库、原始模型日志或私有评测材料。
- 公共 API、持久化记录或证据格式改变时，明确版本与兼容策略；旧证据保持原义。

工作流在独立安装后运行公开单元检查、前端检查和包构建。私有 Benchmark、
真实数据库与物理隔离的维护者检查使用源码仓库中的 `DEVELOPMENT.md`。
公开包运行不需要这些私有组件。
