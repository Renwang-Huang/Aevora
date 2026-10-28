# 快速开始

先按 [README](../README.md)安装原生文件。使用 `aevora version --json` 确认运行的是原生程序。

## 建立项目与连接

项目名是公开标签，工作区使用项目根目录的绝对路径：

```sh
aevora project init --name my-project --workspace /absolute/path/to/project
aevora host start --project my-project --background
aevora connect automatic --project my-project --enable-proposals --apply
```

已有客户端需重新打开会话，才能读取新的 MCP 配置。在登记的项目目录内运行 Codex。
连接会为会话建立任务范围，保留其他模型设置与安全配置；模型仍负责实际选择工具。
若已有独立 Codex 安装或配置根，使用连接命令的 `--client-bin`、`--client-home` 选项。

## 第一次查询

```sh
aevora query --project my-project --query "描述当前要处理的具体问题" --context '{}'
```

查询空结果表示还没有匹配经验。不要为了填充界面导入无关数据。Agent 可以提交未核验观察，
后续依据实际来源建立条件与核验；观察可作为线索检索，不能直接当成已证实结论。

## 查看连接与页面

```sh
aevora status --project my-project
aevora doctor --project my-project
aevora memory status --project my-project --json
```

status 输出实际 Console 地址；doctor 检查数据库、MCP 和 Console。配置可读取、握手成功、
模型实际调用、采集到工程来源是不同状态。内置示例可用 `aevora demo` 浏览，示例属于历史回放。

## 常见情况

| 情况 | 下一步 |
|---|---|
| Console 为空 | 先从真实任务查询并积累观察；新项目空库正常 |
| MCP 未加载 | 重新打开客户端会话，再检查项目目录和连接配置 |
| 没有工程来源 | 查看 memory status；MCP 连接与工程采集入口分别核查 |
| 上下文冲突 | 保留旧任务，在变化后的工作区建立新任务/会话再查询 |
| 用户服务不可用 | 在正常登录终端使用前台 `aevora host start --project my-project` |
| 结果未知 | 查看操作证据并对账，尤其不要直接重试可能已经执行的写操作 |

Console 默认只监听本机，当前不提供面向公网的用户登录与多租户服务。
