# 快速开始

已经有原生项目时，推荐将普通 Codex 改为按会话自动建立任务：

```sh
aevora connect automatic --project inventory --enable-proposals --apply
codex
```

首次应用后重新连接已有客户端。后续新客户端自动获取独立 Run、Host 条件与主动查询
说明，不必每次执行 task new。仍可用 task run 或固定 task binding 显式选择项目。
连接、观察留痕和查询成功不等于采纳或工程收益，后者需实际任务及独立结果。

原生交付是单个可执行文件，内置 SQLite、MCP Host 和 Console。用户无需 Python、
Node、Go、Docker 或外部数据库。解压后把 `aevora` 放入 PATH；Windows 使用
`aevora.exe`。已有 Python 同名入口时使用原生文件的绝对路径。
平台构建、原生运行和正式发行的通过状态以对应交付报告为准。

## 推荐的本地日常入口

以下示例面向Linux与已安装的官方Codex CLI，不安装模型或修改个人身份配置。

```sh
aevora project init --name inventory --workspace /absolute/path/to/repo
aevora host start --project inventory --background
aevora task new --project inventory --name connection-check
aevora connect check --project inventory --task connection-check --client codex
aevora status --project inventory
aevora task close --project inventory --name connection-check
```

check不调用模型，依次验证Codex本次MCP配置解析和官方SDK实际握手。status只读取
本地观察快照/服务状态，不进行握手、不消耗认证nonce，也不产生Query。

准备开始真实Agent任务时，由用户执行：

```sh
aevora task run --project inventory --name fix-stock --client codex --enable-proposals
```

这会启动官方Codex CLI，使用原有账户与安全策略，仅覆盖本次的Aevora连接；
不修改全局MCP配置。客户端退出后撤销该Run的通道，保留历史；成功退出不表示
工程PASS。已有任务通过`task resume --name TASK`重新授权，再`connect export
--task TASK --client codex`给既有客户端显式重连。同名任务不会被新定义覆盖。
如果使用自定义Codex安装或独立配置根，加`--client-bin /absolute/codex`与
`--client-home /absolute/private/codex-home`；不复制原账户文件。

后台Host的Console端口由OS分配，通过start/status获取实际URL；多个项目可并行。
`host stop/restart/remove --project inventory`管理所属服务，remove不删数据库。
登录自启仅在显式`--autostart`时设置。没有用户级systemd则用前台host start或serve。
其他客户端可用`connect export --client generic`取得stdio配置，格式导出不等于
该客户端已运行验收。完整约束见[本地工作流](LOCAL_WORKFLOW.md)。

已有项目用`project register --name inventory --workspace /absolute/repo --config
/absolute/private/host.json`登记，不重复创建数据库。以下保留底层前台与维护入口。

## 1. 创建自己的空项目

```sh
aevora version --json
aevora init
```

`init`创建私有 v2 profile 和 SQLite，不覆盖已有配置或数据。Linux 默认 profile 为
`${XDG_CONFIG_HOME:-$HOME/.config}/aevora/host.json`，数据为
`${XDG_DATA_HOME:-$HOME/.local/share}/aevora/data/experience.db`；macOS 与 Windows
使用系统应用目录。命令输出实际路径；权限由平台实现保护，拒绝不安全文件或链接。

另一个项目使用新的 profile 与 data 路径：

```sh
aevora --config /absolute/private/project/host.json init --data-dir /absolute/private/project/data
```

已有数据库应使用原 profile，不能重复 init。Host facts 默认为 `{}`，缺失事实保持
未知；已有独立确认的公开事实时，在创建配置时用 `--facts` 提供 JSON。
Agent 的输入不能建立或覆盖 Host 已知事实。

## 2. 启动 Host 与 Console

```sh
aevora serve --enable-proposals
```

Host 就绪后打印 Run、事件位置和实际 Console URL，默认 **http://127.0.0.1:17805**。
需要时显式使用 `--port` 选择空闲端口；不会停止已有服务。Console 为 GET-only
公共视图，不执行 resolver、审批或发布。新项目合法地显示 EMPTY，没有隐藏 seed。

保持 Host 运行，在另一个终端生成连接配置：

```sh
aevora mcp-config
```

把输出 stanza 放入所选 Agent 的 MCP 配置，重连即可。connector 不读取 Host
profile，也不获得数据库或模型凭据。这份固定连接配置绑定已授权的原 Run；Host
重启后需要由可信入口重新授权，connector 在下一次请求前读取新 grant 并握手。
推荐的 `connect automatic` 入口会在条件不变时恢复所属 Run；条件或版本变化则应
重新连接建立新任务。已经退出的旧 connector 不能被新版复活。工具及权限见 [MCP](MCP.md)。

按任务隔离 Run 时，由 Host 明确授权：

```sh
aevora open-run --run-id my-task --facts '{}'
aevora mcp-connect --session-root /absolute/owned/session-root --run-id my-task
```

第二条是 connector 的 stdio 入口，通常由 Agent MCP 配置启动。也可用
`mcp-config --run-id my-task`按 profile facts 授权并生成 stanza。同 Run 的事实和
能力一经绑定不能变化；新任务或不同事实使用新 Run。消费者不能自行创建授权。

## 3. 查看结果与核验来源

`aevora doctor`分别报告数据库、真实 MCP initialize/list-tools/ping 和配置端口的
Console health；不执行 Query 或模型。离线时可确认数据库，Host 未运行的通道仍
显示不可用；若 serve 覆盖了端口，以其打印的 URL 为准。

```sh
aevora query --context '{}'
aevora inspect CANDIDATE_ID
```

query 会记录新 Query/Snapshot，Console 读取已有历史，不制造查询。候选自述或
自测不建立可信来源。按 [PROJECT_SOURCES](PROJECT_SOURCES.md) 的 Host policy 和
独立 receipt 契约执行 source-project、review 与下一次复用。
CLI JSON 的结果位于 `result`，操作身份位于 `operation_id`；UNKNOWN 不自动重试。

## 4. 停止、备份与恢复

Ctrl-C 正常停止 Host，会撤销当前授权/socket，保留 manifest、原始事件和数据库。
再次运行同一条 serve 会新建会话。崩溃残留不复用、不清理；活动连接必须重建。
数据文件的 OS 锁保证同一数据库只有一个正式 writer，换 session root 不能绕过。
Console 随 Host 退出，演示可由 `aevora demo`在独立端口运行。

```sh
aevora backup --output /absolute/private/backup.db
aevora --config /absolute/restored/host.json restore --input /absolute/private/backup.db --sha256 BACKUP_PIN --data-dir /absolute/restored/data
```

backup 使用 SQLite 一致性快照，输出独立 SHA256。恢复要求新目录与新配置，核对
schema、完整性、外键和领域历史后才启用。保留原库；恢复后使用新 Run。旧 FalkorDB
项目先停写并做可信逻辑导出，流程见 [RUNTIME](RUNTIME.md)。

升级只替换二进制，保留配置、数据库与证据；新版本 schema 不兼容时拒绝打开，
不会自动降级或重建。卸载只移除二进制，不删除项目数据。
Python/FalkorDB 仅作为显式对照和旧库导出环境，见 [Core 文档](../aevora_core/README.md)。
