# Participant Execution Environment 的隔离边界

> **Phase 3.5 current profile:** new live runs use the hardened Gateway provider, `gpt-5.6-terra`, explicit `max`, isolated network namespaces and a per-run authenticated Unix model channel. Legacy descriptions below document Phase 3 behavior; they do not describe new live runs. See [PHASE3_5_HARDENING.md](PHASE3_5_HARDENING.md) and [GATEWAY_PROVIDER.md](GATEWAY_PROVIDER.md). New live Legacy entry fails closed.
>
> The Gateway profile enables the official Code Mode helper and native collaboration, uses a fresh private CODEX_HOME without `--ephemeral` so same-run child forks can work, seals exact public stdin before launch, archives redacted official run rollouts after process cleanup, and removes state. Upstream credentials stay exclusively in the trusted broker. The documented CPU/disk sampling and candidate resource limitations require a conditional adversarial security assessment.


## 目标与当前验证状态

Phase 1/2 的 `benchmark/sandbox.py` 保护候选业务评测进程。Phase 3 另用 `benchmark/participant_sandbox.py` 包围整个 Codex CLI、原生子 Agent 及其本地工具。Participant 的工作目录限制与提示词要求之外，还存在独立的实际 mount、PID、user、IPC 和 UTS namespace。

物理文件边界测试在这一外层 bubblewrap 配置中执行读取探针，覆盖维护者隐藏测试、参考补丁、Private Manifest、宿主源码、其他 Run、身份文件及 `/proc/1/root` 路径。测试中的私有 canary 是独立创建的合成内容，真实仓库目录也执行访问探针；测试工具运行不冒充 Codex 模型或原生子任务。

真实 Codex 可执行文件已在相同文件边界中完成版本探针。最初的执行权限禁止 Broker 监听 socket，并且 DNS 解析失败；这轮失败保留为实际开发记录。用户调整执行权限后，listener、DNS 和 HTTPS 已恢复。正式 Run `339f7d73-29df-4242-8920-9e566bce8a9c` 已完成模型调用、三个原生子任务、实际提交和隐藏评测。随后在同一 Participant 树内调用安装 CLI 的 command sandbox，十四个实际私有/身份路径读取全部失败，公开源码可读。详细命令和结论见 [PHASE3_VALIDATION_REPORT.md](history/phase1-3/PHASE3_VALIDATION_REPORT.md)。

## 两个可信层与 Participant

```text
Host / trusted maintainer launcher
  ├── complete Benchmark / hidden suites / reference / run archives
  ├── host identity file → trusted ModelBroker memory only
  ├── official stdout/stderr archive + patch extraction + Evaluator
  └── outer Participant bubblewrap namespace
       ├── /workspace       public app / issue / manifest / tests / roles
       ├── /codex-state     new per-run CODEX_HOME, no host identity
       ├── /opt/codex/codex one official executable, read-only
       ├── /tools           Git and bubblewrap executables, read-only
       └── /usr + minimal runtime / resolver / certificates
```

维护者的 Runner、Fixture Factory、Episode Registry、隐藏评测及模型 Broker 均不在 Participant 的挂载范围内。即使本机 fallback wrapper 已把项目和认证挂入可信维护者 namespace，嵌套 Participant namespace 也不会继承这些父 namespace 文件挂载。

## 允许访问的内容

| 路径/资源 | 权限与用途 |
| --- | --- |
| `/workspace` | 可写，当前 Run 的公开业务源码、公开测试、Public Manifest、Issue 和明确授权的角色说明 |
| `/codex-state` | 可写，新建的单轮 Codex 状态目录，初始无宿主配置或认证；运行结束删除 |
| `/opt/codex/codex` | 只读，官方 CLI 可执行文件 |
| `/tools/git`、`/tools/bwrap` | 只读，必要的成熟工具 |
| `/usr`、必要的 `/lib`、`/lib64`、`/bin` | 只读，工具和运行时依赖；不提供维护者业务源码 |
| `/proc` | 新 PID namespace 的 proc 挂载，不展示宿主进程树 |
| `/dev` | bubblewrap 的基础设备目录 |
| `/tmp` | 独立 tmpfs，Participant 的临时文件和 HOME |
| `/etc/resolv.conf`、`/etc/ssl/certs` | 存在时单独只读提供 DNS 和 TLS 基础设施；不挂载完整 `/etc` |
| 模型 Broker | 仅两个固定模型 HTTP 路由；身份仍在可信进程 |

环境先执行 `--clearenv`，再设置公开运行所需的 `HOME=/tmp`、`CODEX_HOME=/codex-state`、工具 PATH、LANG 和 Python hash seed。宿主长期密钥、身份环境变量和个人路径不继承。

沙箱参数包含 `--die-with-parent`、`--unshare-user`、`--unshare-pid`、`--unshare-ipc`、`--unshare-uts` 和 `--cap-drop ALL`。Agent 执行超时时，可信适配器终止整个进程组并等待回收。bubblewrap 或 Git 不可用、目录不安全或 Codex 不可执行时直接失败，没有普通宿主 subprocess 执行业务命令的 fallback。

## 禁止访问的内容

Participant 不挂载以下资源：

- `evaluator/hidden_tests/`、`evaluator/reference_patches/`、`evaluator/private_manifests/`；
- 维护者 `benchmark/`、`integrations/`、原始正确 `app/` 或开发者测试；
- 可信初始基线、统一 Run 归档根目录、其他 Run 的成绩；
- 宿主个人 HOME、完整 `.codex`、认证文件或维护者其他凭据；
- 受控种子经验、其他 Episode 答案及开发者会话内容。

Participant Workspace 使用 allowlist 文件复制构建，拒绝软链接、硬链接、特殊文件、危险文件名、非 UTF-8 及超限输入。允许复制的源码和公开测试必须是单链接普通文件；身份和私有评测不会因为位于同一父目录就被复制进去。

单轮状态目录拒绝 `auth.json`、`credentials.json`、`config.toml`、硬链接及特殊文件。Codex 自己的版本探针可能创建 CLI 别名，只接受指向沙箱固定 `/opt/codex/codex` 的确切软链接，不接受任意宿主指向。

外层边界继续保留 Codex 自身 `workspace-write` 沙箱和 `never` 审批策略。命令构建明确拒绝 `danger-full-access`、`--dangerously-bypass-approvals-and-sandbox`、`--yolo`。不通过运行权限扩大来恢复模型连接。

## 身份认证与模型连接

身份认证分成两条路径：

1. 可信维护者进程读取配置指定的有效 ChatGPT 身份文件，只在内存持有本次固定后端调用所需的 access token 和 account ID。
2. Participant 的官方 Codex CLI 配置一个不要求本地身份文件的自定义 Responses Provider，连接可信 Broker；业务命令环境看不到 token、refresh token、身份文件或完整宿主 `CODEX_HOME`。

本机 fallback 的认证只读挂载在维护者 namespace 的 `/maintainer/auth.json`。Participant 不挂载 `/maintainer`，其 HOME 是 tmpfs，其 CODEX_HOME 是新目录。`ORDERFLOW_CODEX_AUTH_PATH` 表示可信文件路径，不把认证内容作为 CLI 参数或 Participant 环境变量传递。官方文档也要求将保存的身份文件视作敏感凭据，并避免把 API Key 放进执行不可信仓库代码的共享环境。[Codex 官方非交互认证说明](https://learn.chatgpt.com/docs/non-interactive-mode)。

### Broker 限制

Broker 是专用 HTTP transport，不调度 Agent，也不是 MCP Server。

| Participant 路由 | 固定可信上游 |
| --- | --- |
| `GET /v1/models` | `https://chatgpt.com/backend-api/codex/models` |
| `POST /v1/responses` | `https://chatgpt.com/backend-api/codex/responses` |

生产上游固定为 HTTPS。不能指定任意主机或路径；只有 models 接受一个受限 `client_version` 查询值；其他方法、路由、查询、Transfer-Encoding、超大请求和无效 JSON 被拒绝。Responses 请求强制 `store=false`。认证由可信 Broker 添加，参与者传入的头部不转发成上游授权。

Broker 不使用环境代理、不追随 HTTP redirect、不向 Participant 返回上游错误正文、redirect Location 或身份头部。日志只记录请求/状态计数与安全错误分类。身份刷新为 `DISABLED`；过期或无效身份产生实际错误，不复制完整身份文件来规避。

这一 ChatGPT 后端与自定义 Provider 的组合已由当前版本的正式执行验证：记录了 56 次真实上游 HTTP 200，原生 turn 完成，实际补丁通过独立评测。合成 HTTP transport 契约测试仍只证明其契约，不替代真实账户或后端兼容性验证。

## 提交回收与独立评测

可信宿主等待 Codex 及其子进程结束，停止模型 Broker，再读取 Participant 文件。基线与证据输出位于 Participant 之外，Agent 无法直接更改最终补丁、Trace 或评测报告。

仅实际 `app/**/*.py` 变化被提取为补丁，接受现有源码和补丁大小上限及 patch 路径校验。公开测试变化单独归档，Participant 的 pytest 配置、私有断言、环境文件或 Git hooks 不进入候选提交。提取阶段不导入或执行候选业务代码。

隐藏测试继续在可信宿主，由原有业务 RPC 沙箱运行提交。Oracle 在业务执行结束后直接检查候选数据库，不依赖候选 `audit()` 或 Agent 声明。pytest 退出状态、必要测试集合、JUnit 数量、skip 和真实版本指纹保持原有规则。模型认证不传给候选业务沙箱。

Agent 原始 stdout/stderr 归档位置在可信宿主。脱敏后保留原始事件结构、行引用和 SHA256；未观测的 thread、子 Agent、Token Usage 和时间字段为 `UNAVAILABLE`。Agent 不可以通过自然语言声明创造结构化子任务证据。

## 当前限制与恢复条件

- **共享 network namespace：** 当前没有 `--unshare-net`。Participant 需要访问 loopback Broker，这一配置没有声明网络隔离或宿主本地服务不可达。
- **模型与业务命令：** 实际双路径 listener 探针表明外层模型运行时可连接 Broker 所在的 loopback；内层原生 `workspace-write` command sandbox 的业务命令创建 socket 被 `EPERM` 拒绝。此结果只证明该命令路径的策略；外层 namespace 本身仍共享网络。
- **Broker 访问与配额：** 固定路由阻止任意认证代理，但没有实现独立的每 Run HTTP 授权、模型请求额度或完整资源配额控制。它不适合宣称完整敌对代码防护。
- **身份刷新：** 只支持可信 ChatGPT access token，不能自动刷新，也没有 API Key Provider。
- **后端兼容性：** Responses/SSE、models 和 CLI 的组合依赖实际版本与服务行为；以正式挑战结果判定，后端或 CLI 升级后重新验证。
- **环境权限：** 初次 listener/DNS 阻塞已保留；当前权限已恢复。未来若连接条件不满足，应报告安全失败，不扩大 Participant 文件访问权限。
- **日志脱敏：** 已知认证键和令牌形态会处理，但模式匹配不覆盖所有任意个人信息；身份文件访问边界是主要保护。
- **系统边界：** namespace 与只读挂载是当前验证的文件边界，没有升级为 VM、完整容器网络策略或内核漏洞防护。

运行需要一个同时允许 bubblewrap、loopback listener、DNS 和固定模型 HTTPS 连接的可信执行环境。Flatpak wrapper 通过明确的可信 CA bundle 路径修复证书位置差异，未禁用 TLS 验证。保持身份在 Participant 外，由全新真实 Codex Session 在同一隔离配置中执行公开访问探针、至少两个独立原生子任务及 Episode A 提交。若这些条件不满足，记录明确 ERROR/NOT_RUN 和未完成验收，停止在本阶段。
