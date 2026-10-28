# Aevora

让编码 Agent 在项目开发中积累工程经验，并在后续任务中找到适用的方法和证据。

Aevora 将本地 Host、SQLite、MCP 接口和 Console 集成在一个可执行文件中。
日常使用不需要安装 Python、Node、Go、Docker 或外部数据库。连接 Codex 时，
仍需安装官方 Codex CLI，并使用你自己的模型账户与配置。

## 下载与安装

从 [GitHub Releases](https://github.com/Renwang-Huang/Aevora/releases/latest) 下载
Linux amd64 安装包和 `SHA256SUMS`。当前正式安装支持 Linux amd64；其他平台尚未完成验收。
下载后在同一目录核对所需文件：

```sh
sha256sum --ignore-missing -c SHA256SUMS
tar -xzf aevora_0.6.1_linux_amd64.tar.gz
install -Dm755 aevora "$HOME/.local/bin/aevora"
aevora version --json
```

请把 `$HOME/.local/bin` 加入 PATH。安装包内同时提供使用指南与第三方许可。

## 在你的项目中使用

```sh
aevora project init --name my-project --workspace /absolute/path/to/project
aevora host start --project my-project --background
aevora connect automatic --project my-project --enable-proposals --apply
codex
```

在项目目录内启动新的 Codex 会话，使其加载连接。后台模式使用 Linux 用户级 systemd，
不会默认设置登录自启。新项目没有预置经验，查询空结果是正常状态。

```sh
aevora status --project my-project
aevora memory status --project my-project --json
```

打开 status 输出的 Console 地址查看活动、候选与来源。首次使用时可让 Agent：

> 开始任务前查询相关 Aevora 经验，核对适用条件和来源；任务结束后记录可复用观察及限制。

## 可以帮助你做什么

- 根据任务召回经验，并说明适用条件、支持和反例。
- 保存未核验观察，管理经验的来源、核验、发布与失效。
- 关联工程来源和后台整理作业，查看为什么尚未形成可用经验。
- 用只读 Console 浏览真实记录；数据保存在本机。

模型生成的观察与成功检查不会自动变成可信经验。自然 Codex 采集需要相应适配入口；
只配置 MCP 不代表所有既有会话都被采集。Aevora 也不会因记忆条目增加而保证任务效果改善。

## 使用指南

- [快速开始](docs/QUICKSTART.md)：连接、首次查询和状态排查。
- [本地工作流](docs/LOCAL_WORKFLOW.md)：任务、备份、升级和停止服务。
- [工程记忆](docs/TASK_MEMORY.md)：检查采集、来源整理和自动核验。
- [Console](docs/CONSOLE.md)：如何理解页面中的记录与状态。
- [来源与许可](docs/NOTICES.md)。

本分支包含用户产品及其原生运行源码。开发工具、测试、基准数据、参考实现和评测平台
不随本次用户交付提供。希望从源码编译的用户可使用 go.mod 固定工具链，在仓库外指定输出：

```sh
go -C go-runtime build -trimpath -o /absolute/output/aevora ./cmd/aevora
```

问题与建议可提交到 [GitHub Issues](https://github.com/Renwang-Huang/Aevora/issues)。
