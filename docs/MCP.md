# MCP 接入

原生 `mcp-connect` 使用官方 Go SDK 维持独立的下游会话。Host 断开后 connector
继续存活，后续新调用先验证连接并重新握手；已提交调用丢失响应时返回
AEVORA_RESPONSE_LOST_OUTCOME_UNKNOWN，不自动重放。原固定 Run 不会被当前默认
selector 的另一个 Run 替换。`--auto-session`使用受限 enrollment capability 为普通
客户端建立受测量的独立任务；条件变化或撤销时要求新会话，不能用重连绕过授权。

`search_observations(query, limit=10)`是独立的低信任观察检索入口，最多返回20条
公开声明。它不授予经验身份、APPLY 或 Outcome 权限；`record_decision`仍只接受本 Run
真实查询返回的 Experience。默认规则在经验为空时可查具体关键词线索，再独立检查。
原生使用 SQLite 参数化字面关键词检索，Python 对照最多检查500条候选并明确 PARTIAL。

原生任务检索推荐：

```json
{"task_context":{},"query":"原生队列","limit":5,"detail":"summary"}
```

`query`为不含秘密和私有路径的公开任务描述，最多 1000 字符。它影响相关性，
不改变可信事实。缺失或空描述得到空候选和`TASK_QUERY_REQUIRED`，补充具体任务即可。
`limit`为1..20，默认5；`detail`为`summary`或`full`。默认卡片为有界摘录，整个
业务结果上限32 KiB；`output_truncated`/`more_matches`说明省略。使用实际返回的
`query_id`和`experience_id`调用`build_evidence_bundle`读取完整条件与证据。
完整模式仍受原有传输预算约束，过大请求明确失败，不产生伪完整结果。

摘要裁剪同时检查含 SDK 文本兼容表示与转义的保守128KiB预算，Host再校验实际
完整信封；不能只按原始正文大小判断能否交付。省略的经验不进入 Query 授权集合。

原生`search_observations(query, mode="ranked")`使用同一词法索引和有界摘录；省略
mode 保留旧 literal 子串查询。排名模式支持中文片段、英文词干与披露的工程别名。
已识别的概念共同匹配，避免仅“原生”一词触发与队列无关的经验。排名不是适用性或
成功概率。观察 ranked 目前仍为词法；经验查询可由受保护配置启用本地语义通道与
RRF 融合，服务失败明确降级。配置和真实模型质量边界见[任务检索](RETRIEVAL.md)。

Python/FalkorDB 对照保留无 query 的旧条件诊断和 literal 观察查询；显式任务文本
或 ranked 请求会说明需要原生 SQLite。现行产品方向与后续差距见[产品方向](PRODUCT_DIRECTION.md)。

Aevora 通过官方 MCP SDK 提供经验工具。可信 Host 连接图数据库并授予
可撤销的 scoped 通道；原生 connector 使用同一个Go可执行文件。
部署步骤见[快速开始](QUICKSTART.md)。

| 工具 | 行为 | 结果权限 |
|---|---|---|
| `resolve_experience` | 按任务相关召回，再依据已固定的上下文判断 | 任务文本及 Agent 声明均不能覆盖可信事实 |
| `search_observations` | 按关键词查看历史公开声明 | UNTRUSTED，仅作线索，不授予 APPLY |
| `build_evidence_bundle` | 查看候选经验的规则、来源、支持与反例 | 仅受限公共投影 |
| `record_decision` | 记录 Agent 的选择与理由 | 不可信声明，不证明采纳或因果关系 |
| `record_observation_use` | 把调查线索的用途、处理、理由与可选耗时记为使用反馈 | 原生 SQLite；候选存在性已核对，但是否看到、使用或受益均未核验 |
| `propose_experience` | 提出待核验的经验候选 | 需显式启用；不授予审批或发布权限 |

初始化的 instructions 明确要求：工具启用时，非简单编码、排查和设计任务在选择
方案前主动查询一次，无需用户显式唤醒；空结果继续正常工作，不制造决策或经验 ID。
完成有依据的工作后可提出带限制的候选。用户退出与禁用设置优先，失败不静默冒充
经验支持。工具发现与配置存在仍不证明真实调用，需看实际 MCP 事件与返回结果。

原生 `record_observation_use` 接受 `report`，其中 `candidate_id` 为实际候选 ID，
`report_key` 为本 Run 内稳定幂等键，`purpose` 为 DEBUGGING、PLANNING、IMPLEMENTATION、
VALIDATION 或 OTHER，`disposition` 为 INVESTIGATED、REUSED、REJECTED、NOT_RELEVANT
或 INCONCLUSIVE；`reason` 为简短公开说明，可选 `elapsed_seconds` 为 0–86400 的
声明值。不要填凭据、私有路径或隐藏测试。相同键和相同内容可显式重试，内容不同则冲突；
连接丢失不会自动重放写请求。记录绑定不可变候选及其摘要，在 Console 的外部观察中可见；
查询暴露和采纳没有被证明，`source_sha256`是声明输入摘要，不是独立来源凭据，
不会创建可信 Outcome。Python/FalkorDB 对照明确拒绝此原生功能。
之后的原生 ranked 观察搜索会在每条线索下返回最多两条按记录 ID 排列的反馈摘要；
这不是最近排序、热度排名或完整统计，反馈不改变搜索排序或可信程度。
自动诊断候选的观察搜索还可返回来源记录数、项目提示和有界的会话/回合/工具标识；
它们来自未核验 hook，不代表实际失败次数或已经证实的项目范围。

提议的 necessary_conditions 和 scope 可用空对象表达尚未界定的草稿，不要求
编造事实通过参数校验；草稿保持未核验。准入和发布继续要求非空条件、有界范围
和独立可信来源，空范围草稿需要在条件明确后以新 key 提交有界候选。

原生配置生成器 `aevora mcp-config` 读取 Host profile 的稳定会话根，输出
connector stanza。将其放到所选 Codex home/config.toml，Host 重启后重新连接即可。
Python对照兼容入口 `python -m aevora.mcp_config --python 绝对路径 --capability-file 绝对路径`
仍可绑定一个显式 grant；也支持 `--session-root 绝对路径`。模型服务身份由
使用者单独管理，不写入 Aevora 配置或公开源码。

`codex mcp list` 只确认配置；实际工具结果与完整 MCP 事件才证明调用。
数据库不可用、grant 撤销和外来 Query 身份应得到明确错误，不静默提供回放。
原生Host持有通道到退出；Python对照可显式指定capability TTL，它不等于Agent总运行期限。

## Host 配置与会话恢复

`aevora init`创建原生`aevora.host-config/2`，固定字段为：

```json
{"schema_version":"aevora.host-config/2","database":{"kind":"sqlite","path":"/absolute/private/experience.db"},"session":{"root":"/absolute/owned/sessions","public_context":{}},"console":{"port":17805}}
```

原生profile不含数据库密码。`--config`或`AEVORA_CONFIG`选择项目；省略时使用平台
默认配置目录，命令输出实际路径。同库OS所有权绑定固定root，换root不能创建第二writer。
新Run由Host管理授权，consumer的claims不改变固定facts。`open-run`与
`mcp-config --run-id`属于可信入口，授权后connector使用相应Run selector；
命名空间客户端可只挂载一个`aevora.connector-grant/1`与socket，调用`mcp-connect
--grant`。管理通道/token不进入MCP工具或消费者grant。

以下v1配置与环境优先级仅用于Python/FalkorDB对照：

`aevora configure` 创建 `aevora.host-config/1` JSON，默认位于
`${XDG_CONFIG_HOME:-$HOME/.config}/aevora/host.json`。文件只允许以下字段：

```json
{
  "schema_version": "aevora.host-config/1",
  "database": {
    "host": "127.0.0.1",
    "port": 17790,
    "graph": "aevora_local",
    "password_file": "/absolute/private/falkordb.password"
  },
  "session": {
    "root": "/absolute/private/sessions",
    "public_context": {}
  },
  "console": {"port": 17805}
}
```

这是可信 Host 文件，目录须为所属用户 0700、文件 0600；拒绝链接、重复键、
未知字段和内嵌密码。`configure` 独占创建；修改已有配置需明确编辑，或使用
`--output PATH` 新建另一项目配置。先用 `health` 确认目标数据库。
创建默认配置时会将所属用户的 Aevora 应用目录保护为 0700，上层 XDG 目录和
显式 `--output` 的已有目录不自动改权限。

加载顺序：显式 `python -m aevora --config PATH 子命令` 或 `AEVORA_CONFIG`
优先；没有显式 profile 且存在任一 `AEVORA_FALKORDB_*` 连接设置时，沿用 DB
环境，不混入默认 profile；否则加载默认文件。环境部署需提供完整连接设置。
Console 同样支持 `--config PATH`。Python `GraphRepository.from_environment()`
只读取显式环境；只有可信 Host 入口负责加载 profile，consumer connector 不读取它。

`aevora serve` 使用 profile 的会话根，每次独占创建 `s-<随机值>/`、新 Run、
`session.json` 与 `mcp_events.jsonl`。可显式 `--run-id` 固定 Run authority，
但不会将旧会话事件接着写入新文件。`.owner.lock` 的内核锁保证一个根只有一个
活动 Host；`current.json` 是可原子替换的当前会话选择器，没有 token，也不是证据。
grant 就绪后才更新选择器。connector 每次连接重新读取它，不自动重连活动调用。

正常停止撤销当前 grant/socket，保留 manifest 和事件。崩溃后锁自动释放，
下一启动使用新目录，旧残留保留但不再被新连接选择。会话根属于私有运行状态，
可能含 grant，不能整体归档。Host 只复用既有官方 MCP Runtime/broker。
显式路径模式仍要求全新 socket/grant/events；`SESSION_PATH_EXISTS` 提示使用
自动会话或全新路径，不能通过覆盖事件恢复。Unix socket 路径过长时使用较短的
`--session-root`。此处的重启恢复不保证图数据库未保存尾部或中断调用恢复。

## 权限

Agent 不获得图密码、上游密钥、任意 Cypher、source-orderflow、review、
source-project、publish、withdraw 或 Outcome 写入工具。普通项目的自测 PASS 是外部观察，
必须经过独立可信来源验证才能成为 VerifiedOutcome。
Host 接入独立项目验证器、审批、发布和下一次查询的完整步骤见
[普通项目来源接入](PROJECT_SOURCES.md)。

本地同 UID 通道是可信开发者连接；Host 自身不为不可信程序提供文件系统
隔离。对不可信 Participant 使用既有物理隔离及每 Run proxy，不将 Host
代码或秘密目录挂入其中。程序、事件字段和 SDK 能力以实际安装及源码为准。

接口实现位于 `aevora_core/src/aevora/mcp_server.py`、`mcp_broker.py`、
`mcp_connect.py`。底层依赖按包元数据固定，不在文档中静默替换 SDK 主版本。
