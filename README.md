# Aevora

让编码 Agent 在复用工程经验时，能够说明适用条件、证据来源和结果边界。

原生 Aevora 将 Go Host、经验治理、SQLite 和只读 Console 放在一个可执行文件中。
用户运行不需要 Python、Node、Go 工具链、Docker 或外部数据库服务。Python 保留为
开发、历史对照和独立 benchmark/Oracle 环境。

- **判断适用性**：根据实际上下文、支持与反例，给出 APPLY / VERIFY / ABSTAIN。
- **解释依据**：保留规则、前提、来源、版本与不可变查询快照。
- **相关召回**：公开任务描述参与原生词法检索；默认精简卡片，完整证据按需读取，目标项目事实与 Host 事实分开。
- **控制权限**：Agent 可以查询和提出候选；来源核验、审批、发布由可信 Host 执行。
- **自动学习**：观察可自动保存；预先授权的独立验证作业可在限定范围内完成核验与治理，人工处理例外和策略调整。
- **观察变化**：Console 区分实时状态与独立 pin 的历史回放，LIVE 失败不回退。

## 开始使用

从 [GitHub Releases](https://github.com/Renwang-Huang/Aevora/releases) 获取原生交付包与校验和，
将 `aevora`（Windows 为 `aevora.exe`）放入 PATH。平台支持与验证状态以对应发行说明为准；
下载或解压不会自动安装系统服务。
已有同名 Python CLI 时，使用原生文件的绝对路径，并用 `version --json` 确认。

```sh
aevora version --json
aevora demo
```

打开 **http://127.0.0.1:17804/?mode=REPLAY**，浏览已有公共证据。回放不运行模型。

本地日常工作流优先接入 Codex CLI。先在自己的项目目录外安装二进制，再执行：

```sh
aevora project init --name my-project --workspace /absolute/path/to/repo
aevora host start --project my-project --background
aevora connect automatic --project my-project --enable-proposals --apply
codex
aevora status --project my-project
```

后台模式使用 Linux 用户级 systemd，不默认登录自启；Host 打印实际分配的 Console URL。
默认接入为每个客户端会话建立受测量的独立 Run；退出后关闭所属通道。也可用
`task run`显式选择项目，以本次 MCP 配置覆盖启动官方 Codex，结束后撤销所属通道。
它会启动用户的 Agent；模型账户、安全设置由所选 Codex 配置管理。新项目没有预置
经验，空候选是有效结果。`--client-bin`与`--client-home`可选择独立安装与CODEX_HOME。
`connect check`进行无模型配置解析与MCP握手，不能替代真实Agent调用证明。

其他系统或无用户服务管理器时保留 `aevora init` / `aevora serve` / `aevora mcp-config`
前台接入。当前服务管理优先 Linux；平台原生通过状态以交付报告为准。

[快速开始](docs/QUICKSTART.md)说明多项目配置、Run 授权、停止和恢复。
[本地工作流](docs/LOCAL_WORKFLOW.md)说明任务结束/恢复、客户端配置与预算边界。
已有候选后，按[普通项目来源接入](docs/PROJECT_SOURCES.md)核验独立产物、
有界审批并发布，再在新任务中查询；公开产品不依赖私有 OrderFlow。
原生入口 `aevora candidate plan CANDIDATE_ID`说明候选还缺什么；
`candidate derive`将草稿整理为新有界候选并保留原历史。新任务自动保存本机可信
运行环境观察；`context collect`可检查实际条件，`context catalog`解释可用词汇。
详见[本地工作流](docs/LOCAL_WORKFLOW.md)；声明条件和自测仍不授予发布权限。

原生项目可用 `candidate automation-policy`预先授权固定验证器与范围，再由独立作业
调用 `candidate automate`完成来源核验、准入和发布，不要求逐条人工点击。
原始观察仍可自动保存；验证未通过或范围未建立时不晋升。配置与命令见
[普通项目自动化流程](docs/PROJECT_SOURCES.md#由可信作业自动核验和晋升)。

MCP 提供 `resolve_experience`、`build_evidence_bundle`、`record_decision`，以及可选
`propose_experience`。Query 不证明采纳，Decision 是不可信声明，自测 PASS 不自动
成为可信 Outcome；反馈归因和因果收益保持 UNKNOWN。

`connect apply --project NAME --task TASK --client codex --apply`同时安装所属 Codex
配置根中的 MCP 条目和受管理的 `AGENTS.md` 使用指引，保留用户其他配置与指令。
新会话在非简单开发、调试和设计任务开始时主动查询，无需用户再次提及 Aevora；
MCP 初始化也提供相同的工作流说明。模型仍负责选择工具，配置检查不证明真实调用。
无法确定适用条件的观察可提交为空条件、空 scope 的未核验草稿；它不会进入可复用
经验，条件明确后以新 candidate_key 提交有界候选，原草稿历史保留。

Linux 用户服务安装可用一条命令升级本地原生文件：

```sh
aevora upgrade --project my-project --binary /absolute/new/aevora --sha256 RELEASE_SHA256
```

升级核对校验值、平台与存储格式，保留旧程序和一致性数据库备份，再替换程序、
恢复原 Console 地址并检查 Host/MCP 就绪。自动接入的新会话使用新版实测条件；
固定任务可显式加 `--resume-task my-task`，条件变化要求新任务。业务操作不重放；
失败尝试恢复旧程序与服务，记录实际恢复状态。详见[升级说明](docs/UPGRADING.md)。

## 继续了解

[架构](docs/ARCHITECTURE.md) · [原生运行时 / 迁移](docs/RUNTIME.md) · [MCP](docs/MCP.md) ·
[Console](docs/CONSOLE.md) · [限制与排查](docs/LIMITATIONS.md) · [来源与许可](docs/NOTICES.md)

当前能力与后续差距见[产品方向](docs/PRODUCT_DIRECTION.md)。相关召回、自动采集、
整理、技能和收益分别验收，不以记忆条数或自测 PASS 代表 Agent 已经获得真实收益。
开发检查可用`aevora memory run-check --project my-project --task checks -- go test ./...`
显式采集有界结果；[工程任务记忆](docs/TASK_MEMORY.md)说明采集、整理与自动核验的范围。

Python/FalkorDB 对照入口保留在 [Core 包](aevora_core/README.md)，不作为原生用户安装
前提。开发与贡献见 [CONTRIBUTING](CONTRIBUTING.md)；私有评测、隐藏 Oracle 与维护者
材料不随公开产品分发。
