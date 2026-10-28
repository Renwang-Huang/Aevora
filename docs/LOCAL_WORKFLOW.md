# 本地项目与任务

本地项目索引使用 `aevora.local-project/1`；位于所属用户私有 workflow 目录。
日常推荐先配置 `aevora connect automatic --project NAME --enable-proposals --apply`，
再正常启动所选 Codex。每个 MCP 客户端会话自动取得新 Run 和 Host 实际测量的条件，
退出后关闭所属通道；同一会话内的多个回合共用该 Run。`--client-home`明确选择配置根。
默认自动策略只授权所选项目，不根据 Agent 的 workspace 或 facts 声明切换项目或数据库。
如一个 Host 明确负责多个已注册项目，可授权工作目录路由：

```sh
aevora connect automatic --project DEFAULT --route-project PROJECT_A --route-project PROJECT_B --enable-proposals --apply
aevora connect check --project DEFAULT --route-workspace
```

`--route-project`可重复，列出同一 Host 的额外项目；默认项目本身也可按目录匹配。
每个新连接在启动时使用 connector 的真实工作目录匹配最具体的登记工作区；Host 再检查
该项目的名称、工作区和后端均在受保护策略内，并独立观察事实。目录提示不授予其他后端
权限；同目录多个别名、未授权或不同后端的项目均拒绝。未登记的工作目录会建立仅含
Host 运行时事实的任务，所有 `target_*` 保持未知，并在 MCP 初始化说明中提示登记项目；
它不会把默认项目的目录、版本或清单当作当前目标。
同一连接的项目和 Run 固定到退出，工作目录提示不证明客户端实际在该目录执行了任务。
常规配置只显式添加路由，不静默删除已授权路由；重新配置时须列出全部已授权路由。
通过 `aevora connect revoke-route --project DEFAULT --route-project PROJECT_A` 预览
额外项目路由的在用任务，加入 `--apply` 才执行撤销。若存在未关闭的自动任务则拒绝
撤销；关闭后重试。撤销与自动开会话及诊断采集提交互斥，成功后不再通过该路由
新建或恢复任务，也不会接收该项目的新采集记录；已提交来源、任务和历史保留。
未获授权的 outbox 记录保留供检查，默认项目路由不能通过此命令撤销。
使用此模式依赖客户端启动 connector 时继承预期工作目录；应通过真实查询中的
`context.target_project`验证，若客户端使用固定目录则改用显式 `task run --project`。
启用后需重新启动客户端以读取新绑定；不修改旧任务与旧查询。

原生任务同时记录可信项目名称与工作区 Git HEAD/分支；分别使用`target_project`、
`target_revision`、`target_branch`，与 Host 的`runtime_*`不同。Git 缺失或对应状态未知
时不填造值，不运行仓库脚本。恢复时重新观察目标；项目/版本/分支变化要求新任务。
观测还包括 `target_worktree_state`、Git 状态/变化文件元数据摘要、已注册根目录及
有界一级模块清单/锁文件的 `target_dependency_snapshot`，以及清单声明的 go/node/python 版本范围。
不递归追踪所有 workspace 定义，跳过隐藏、vendor、node_modules、构建目录和目录符号链接。
根目录发现最多256项、最多64个模块目录；超过时明确披露 ROOT_ONLY 范围，仍保留根清单。
每个清单最多1MiB、全部最多4MiB；多个模块版本声明不一致时对应单值字段保持未知。
不运行安装器、Git 钩子或项目脚本；超限、不可读或符号链接清单保持未知。
这不是全部未提交文件的内容证明，也不证明实际安装版本、模型覆盖参数或测试成功。
新测量任务在每次经验查询的检索前后检查目标变化；返回 `AEVORA_RUN_CONTEXT_CONFLICT`
时可继续项目工作，但应建立新 Aevora 任务/客户端会话后再查询。旧 Query 证据、决策和
已提交操作回放保留原快照，不被重写。旧版无新指纹的任务保持原快照语义。

查询时传入具体任务描述，例如：

```sh
aevora --project NAME query --query "原生队列" --limit 5
aevora --project NAME observations "原生队列" --mode ranked
```

任务文本只影响相关性。默认精简结果，完整条件和来源可按真实 Query 身份展开；
无任务描述返回空建议，观察搜索始终为未核验线索。Python 对照和 literal 查询边界见[MCP](MCP.md)。
安装迁移后已有旧客户端需重新连接一次；使用新 connector 的会话在同条件 Host 重启后
保留原 Run 并重新握手。条件改变或已撤销时明确拒绝恢复，不暗中建立替代任务。

自动接入使用单独的受保护 enrollment capability，仅允许申请/恢复和关闭受测量任务；
不包含 Host profile 或管理 token，不允许提供事实、核验来源、审批、发布或任意管理操作。
策略由可信 connect 命令明确配置并跨 Host 重启保存。已有固定连接和旧任务保留为显式入口。
`AEVORA_WORKFLOW_HOME`可显式选择独立的私有索引目录，它不改变 backend 所有权。
别名固定 workspace/profile/backend 身份，已创建任务不会根据另一终端或当前目录改变。
新建任务和 `task run` 省略 `--project` 时，按当前真实工作目录匹配最具体的已注册
workspace；相同目录存在多个别名时要求显式选择，未注册目录拒绝默认落入其他项目。
新项目工作流同时指定不同的 `--project` 与 `--config` 时拒绝执行；旧接口仍尊重显式profile。
旧 `--config` 和机器 JSON 契约继续有效；project/task 的授权只由可信 CLI 完成。

任务定义使用 `aevora.local-task/1`，保存固定 Run、facts、proposal 能力与创建时间。
新任务由原生 Host 采集 `runtime_os`、`runtime_arch`、`runtime_engine`、
`storage_backend`、`console_access`、`runtime_version`、`runtime_revision`，并保存带时间、目录版本、事实摘要和逐项来源的
`context_observation`。OS/架构来自当前程序的 GOOS/GOARCH，描述当前原生运行时，
不证明物理硬件、用户工程的构建目标、测试结果或工程收益。
原有 profile 条件继续标记为受保护配置来源。相冲突的运行环境声明拒绝合并。
恢复带观察记录的任务时重新核对事实，变化要求新任务；旧任务保持原授权条件。
定义不覆盖；辅助状态使用独立 `aevora.local-task-state/1`，不作为可信工程结果。
授权前持久标记 AUTHORIZATION_UNKNOWN，响应不明不自动重试。恢复需显式请求并
保持原事实与能力。关闭撤销所属连接和 grant，保留查询、操作日志与历史；关闭不
等于验证 PASS，客户端退出也不等于工程成功。Host 默认 Run 随 Host 停止而撤销。

同一 Host 同时最多4个 consumer 连接、累计4096输入帧、4096 consumer认证nonce、
1024管理nonce、累计64个不同Run，每个journal最多32MiB；关闭不复位累计预算。
状态在额度达到85%时提示LOW，达到上限时提示EXHAUSTED；连接占用可随断开释放，累计额度只能由显式重启换代。
服务重新启动不恢复历史授权、不重放操作。原始审计不截断或自动删除。

`mcp-config --run-id`保留现有显式授权行为，新连接工作流将导出和授权分别表达。
运行状态、管理、配置应用都属于本地 Host 入口，不授予 consumer 管理工具。

`connect export --project NAME --task TASK --client codex`只导出该任务的固定绑定，
不启动Host、不授权Run。`--client generic`输出标准stdio command/args JSON，
不代表其他客户端已经运行验收。`connect check`用官方Codex的本次配置覆盖解析，
再通过官方Go SDK实际initialize/list/ping；二者均不调用模型，不证明Codex工具调用。

`task run --project NAME --name NEW --client codex`授权新Run，使用官方Codex CLI
的单次MCP配置覆盖启动。退出后撤销通道，辅助状态为CLIENT_EXITED或INTERRUPTED，
不创建可信Outcome。`--client-bin`选择程序，`--client-home`选择CODEX_HOME，
不复制身份或修改模型、安全设置；已有同名任务用显式resume和export接入。
省略 `--name` 会生成独立任务名和 Run，避免把连续工作累积到同一个日常任务。
固定的 `connect apply` 连接仍绑定所选任务，不会被自动转换或改写。

```sh
# 查看注册词汇与原生 Host 实际观察；命令不调用模型。
aevora context catalog --json
aevora context collect --project NAME --json
# 在已注册工作目录启动独立任务；省略项目与名称时使用明确的目录匹配规则。
aevora task run --client codex
```

词汇和领域支持上下文由发行版本控制，采用 JSON Schema 描述。原生运行时领域
核对实际 runtime/storage，旧并发领域继续要求 concurrency_scope；混合条件同时
满足两个领域的支持要求。Agent 不能上传 Schema 注册可信字段或用 claims 覆盖事实。

`connect apply/remove`默认仅预览，`--apply`明确写入所属配置根的单个托管条目。
原有非托管aevora条目或用户改过的托管条目拒绝覆盖；其他配置字节保持。
TOML使用固定版本的pelletier/go-toml解析，撤销凭据只保存本工具生成的非秘密绑定。
配置中的模型身份、密钥和整份个人配置不进入项目、日志或诊断包。

`connect apply --apply`还为所选 Codex home 的 `AGENTS.md`管理一段工作流说明，
让 Agent 在非简单工程任务开始时主动查询，而非等待用户提及 Aevora。MCP
初始化也返回相同指引，覆盖未使用持久配置的任务入口。明确退出、简单请求和
工具不可用时的处理均在指引中说明。模型仍负责选择工具，不能由配置存在推断
其每次都已调用。新会话需要重新加载指令与工具元数据。

用户原指令保持字节不变；用户编辑过的托管块拒绝覆盖。撤销同一连接同时移除
所属指令块；没有修改其他 CODEX_HOME、模型或安全设置。使用单独的配置根时
仅修改显式选择的 home；已禁用的独立客户端保持禁用。

本地原生升级与回退见[升级说明](UPGRADING.md)。

## 注册身份诊断与备份恢复

`project inspect --name NAME --json` 即使普通命令因后端变化而停止也可使用。
它区分注册匹配、身份变化、数据库不可读和配置不可读；不读取凭据、授权 Run
或修改注册。SQLite 身份包含文件身份与数据库 UUID。备份恢复、文件替换或执行环境
变化都可能影响它；单次不匹配不能确定原因，也不能证明仍是原授权对象。

需要从已确认的数据库恢复时，保留原绑定和数据，用明确 profile 创建一致性备份，
核对备份摘要，然后导入为新别名：

```sh
aevora project inspect --name OLD --json
aevora backup --config /absolute/original/host.json --output /private/new-backup.sqlite
aevora project recover --name OLD --as NEW --backup /private/new-backup.sqlite --sha256 APPROVED_SHA256
aevora host start --project NEW
```

恢复复用现有 SQLite 验证导入与完整图审计，备份、旧绑定和历史记录保持原样。
新实例使用独立数据库与 session root，可信上下文为空，不复制旧 Run 的会话授权、
常设策略、客户端连接或服务配置。之后需显式创建新任务或配置自动会话并重连。
新别名沿用原工作目录；新旧别名并存时按目录选择可能歧义，应显式传 `--project NEW`。
不能恢复为已有别名，也不提供忽略身份检查的开关。失败导入留在独立 recoveries
目录供排查，不进入项目列表、不覆盖原数据。恢复动作本身不证明旧经验对新任务适用。

### 迁移原托管连接

恢复完成后，可把同一个 Codex home 的 Aevora 托管块迁移到新实例。默认只读预览；
只有原回执、实际配置块和原 profile 的 session root 同时匹配时才能写入。原后端
不必在线，但目标项目必须通过身份检查，应用时目标 Host 必须能够确认新的自动接入策略。

```sh
aevora connect migrate --from-project OLD --project NEW --route-workspace --enable-proposals
aevora connect migrate --from-project OLD --project NEW --route-workspace --enable-proposals --apply
```

`--client-home`明确选择配置根；其他 home 不参与。迁移先保存只含公共托管块的回执，
再原子替换 MCP 配置块，最后归档原所有权回执。用户其他配置和 AGENTS 内容不变；
不保存整份配置或其摘要，不迁移凭据，不恢复旧 Run。若原 home 存在与回执及内置定义
完全一致的 Aevora 采集回调，也会一起改为目标 session root 并迁移其回执，避免只迁移
查询而漏掉采集。用户修改过的已托管回调会阻止迁移；非 Aevora 回调保持原样。
回调内容变化后的官方运行时独立信任仍需满足，迁移不会复制或授予该信任。
官方客户端可能在末尾注释之前追加其他 TOML 表。若这些设置落入 Aevora 的结束
标记之前，编辑器只接受回执中完全一致的配置前缀，并验证整份配置的解析语义不变后
移动自己的结束注释。其他设置保持原字节，不进入迁移 journal；修改过的 Aevora
字段、无法确认的前缀或语义变化继续拒绝。
目标的新策略独立授权，额外路由
须逐项通过 `--route-project` 指定。重新打开客户端后才加载新目录和新会话。

自动连接与有策略的采集回调仅在所属 Host 的显式项目/路由中按目录选择；其他后端的
旧注册或未列出的别名不参与歧义判断。Host 仍核对能力、当前后端、注册与允许列表。
同一授权范围内的相同目录别名继续报歧义，不靠名称顺序选择。未配置策略的旧离线
回调保留原低信任分类行为；损坏策略不会静默回退。

中断后重复完全相同的命令可核对并继续；用户改过的块或回执会被拒绝，不能强制覆盖。
错误输出会给出恢复 journal。添加 `--undo`预览，`--undo --apply`恢复原公共配置块
及其所有权；其他选项保持一致。撤销不启动旧 Host、不恢复任务、不撤销已确认的新
Host 自动策略。原回执归档和迁移历史保留，旧项目不能误删已迁移的目标配置块。

`host start --project NAME --background`显式注册并启动Linux用户级systemd服务。
默认不设置登录自启；需要时显式`--autostart`。`host stop/restart/status/remove`
只控制已核对所属源文件的服务，不根据裸PID杀进程。缺少用户服务管理器时使用
`serve`或前台`host start`；不隐式产生无管理的后台进程。删除服务保留数据和证据。
重复start保持单writer。启动等待同backend的实际MCP握手，服务进程运行不等于就绪。
后台Console使用OS分配的loopback端口，实际端点由Host发布，doctor跟随它核对身份。

Host的`aevora.runtime-status/1`是有限大小的私有观察快照，包含epoch/PID、端点、
观察时间、连接/Run/协议和认证预算，不含token或其摘要，不是数据库提交凭据。
定期快照不调用管理通道；陈旧或身份不符保持不可用。每个Host运行周期内预算
不因重连或任务关闭而复位；用户显式restart才创建新周期，历史任务不自动授权。
服务对异常信号退出采用有限重启；配置/权限错误的正常错误退出不自动重启，
原始审计仍有32MiB上限且不自动删除。普通诊断日志交给用户服务管理器处理。

`status --storage`提供有界的只读空间统计与保留清单，不读取日志内容、不删除文件。
实时文件长度不是一致性备份；活动journal统计仅覆盖当前授权代，历史代仍保留在session目录。
盘点达到10000个目录项或访问失败时明确显示PARTIAL_OR_UNAVAILABLE。
