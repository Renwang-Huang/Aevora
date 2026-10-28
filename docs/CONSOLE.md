# Console 与只读 API

Console 展示 Core 的实际判定和公共证据，不负责审批、发布或生成可信结果。
原生“核验与发布”页增加观察关键词检索，可读取尚未发布或已结束的历史声明。
结果始终标注 UNTRUSTED 和当前状态，只作为排查线索，不生成 APPLY 或可信结果；
搜索范围仅含标题、摘要和方法，不搜索来源引用、私有产物或任意原始 JSON。
使用根 README 的命令体验回放，或按[快速开始](QUICKSTART.md)连接自己的图。

原生开发版本使用`aevora serve`同时启动Go Host与内置Console，输出实际loopback URL；
端口冲突时可显式选择`--port`，不会停止已有服务。`aevora demo`直接打开同一界面的
独立pin回放，无需Python、Node或数据库服务。原生与旧引擎的安装说明见
[运行时](RUNTIME.md)；综合验收前不把开发分支构建标为正式发行。

## 三个页面

| 页面 | 内容 |
|---|---|
| Activity & Decisions | 运行状态、实际工具请求和 Core 推荐；缺失身份保持 unavailable |
| Experience Explorer | 真实节点/关系、WHEN/WHY、属性、来源证明和可访问列表 |
| Governance Timeline | 候选生命周期、查询快照、反馈和结果权限 |

界面默认中文，保留英文技术标识。三个页面分别显示为“活动与建议”“经验库与证据”
和“核验与发布”，每页标题下说明用途。项目概览先解释当前进度和下一步，再列出
任务记录（Run）、经验查询（Query）、待核验候选和可查询经验；每个指标都说明
统计含义。指标覆盖整个项目，下方记录按筛选和分页展示，不能将当前页当作全库。

“第一次使用”可展开查询、核对证据、候选核验的流程与常用术语，并提供可复制给
Agent 的提示。页面内的复制和导航不会发起模型任务或发布经验。任务与查询列表
优先显示可读说明和时间，完整 ID、运行状态、来源及快照标识在展开详情中保留。
经验数量尚未完整核对时显示“待统计”及已加载的核验数量，不推断为零。

候选卡片通过公开白名单展示标题、摘要和声明条件，优先解释当前缺项及下一步。
未确定的范围显示为草稿；声明条件不等于已核验。候选详情保留原始标识、内容摘要、
限制和整理来源。生命周期弹窗以可读计划展示独立来源检查，原始公开 JSON 折叠保留。
计划与准入复用 Core 判断，浏览器不实现另一套适用性规则，也不执行审批或发布。

LIVE 默认每五秒自动刷新，可取消勾选暂停。后台读取不先清空页面，读取完成后
更新；失败时仍立即清除旧项目与建议。展开的说明在刷新后保留，证据弹窗打开时
不执行周期刷新。观察时间是数据读取时间，不是新的工程验证结果。

LIVE 查询实际图；REPLAY 校验固定 pin 下的公共产物，并显示来源与时间。
图不可用时 LIVE 返回错误并清除旧显示，不自动回退。空初始化图显示 EMPTY。
默认页面和 API 使用 LIVE，按当前配置的 graph 展示项目概览、Run、真实查询、
候选和经验库。数据库连接与项目进度分别显示：

| 项目状态 | 含义 |
|---|---|
| EMPTY | 数据库已连接，除 schema 外没有记录；可连接 MCP 开始任务 |
| ACTIVITY_RECORDED | 已有查询或会话活动；是否有可用经验另看门禁计数 |
| CANDIDATES_PENDING | 有候选等待来源核验、审批或完成发布 |
| EXPERIENCE_AVAILABLE | Core 发布门禁允许查询经验；不表示适用于当前任务 |
| RECORDS_PRESENT | 存在其他记录；当前读取未观察到待处理候选或可用经验 |

记录、Run、查询、候选与已存经验的总数由数据库聚合，覆盖当前项目。
可用经验逐条经过 Core 发布门禁；待处理候选来自已校验摘要的 head。未完整读取时，
这两项总数为 `null`，界面显示 UNKNOWN，并单列已加载记录中的数量；
`candidate_states_complete` 披露状态统计是否完整。未读到可用经验不证明全库没有。
Run 筛选在数据库中控制查询、候选、决策声明、时间线、结果与图；
经验库属于项目共享数据。缺失的 Run/经验明确显示 NOT_FOUND，不替选其他对象。
“Demo replay” 是明确的历史演示入口，Case A/B/C 只在 REPLAY 中显示。
LIVE 不查找演示经验 ID，也不采用演示的 threads/workers 上下文。

LIVE 推荐卡片来自真实 Query 关联且通过摘要与关系校验的不可变 QuerySnapshot，
标注 Run、Query、经验与原查询时间。它是当时的 Core 结果，不是当前重新计算；
撤回后旧快照仍保留，但经验不计为可用。Agent Decision 单独显示为不可信声明。
尚无查询时显示下一步，不生成演示推荐。新任务的适用性通过真实 MCP 查询核验。

LIVE 治理页按候选 ID 打开当前生命周期证明，未发布候选也可读取；弹窗直接
标注 LIVE 和对应候选。候选缺失、链校验失败或数据库断连时显示不可用，不替换
为历史证据。REPLAY 证明标注为历史参考，模式或 case 切换会关闭已有弹窗。
LIVE 候选旁显示 Core 提供的当前状态下一步；来源配置、审批与发布由 Host
按[普通项目来源接入](PROJECT_SOURCES.md)执行。

图布局、排序和邻域筛选属于展示。初始邻域、已加载展开和最大读取范围
分别披露，节点数量和线条位置不能据以推断因果关系。

## HTTP 接口

只允许 GET：

- `/api/overview`
- `/api/{sessions,decisions,experiences,graph,timeline,outcomes,health}`
- `/api/proof/{contract,origin,lifecycle,views,evolution,queries,pilot,readback,graph}`

查询选择器：`mode=LIVE|REPLAY`（默认 LIVE）、`run=<真实 Run ID>`、
`experience=<经验 ID>`，以及有界分页。`limit` 为 1–100（默认 20）；
兼容的 `offset` 为 0–1000，在数据库中执行。
LIVE 返回 `pagination.<资源>.has_more/next_cursor`；将 `next_cursor` 原样作为
`cursor` 继续读取，游标没有 1000 条的历史深度限制。游标绑定 Run/经验选择，
不可与非零 offset 或 REPLAY 混用；错误游标返回 400 / INVALID_CURSOR。
概览的各列表独立推进，前端提供下一页、上一页、返回首页和页大小选择，URL 保留游标。

列表按稳定 ID 升序分页，不声明时间上的连续快照。翻页期间新写入在游标之前的
记录需要回到首页查看；删除和并发写入不会产生全局事务保证。
`decisions` 按 Query header 分页，返回该页 Query 的全部所选经验快照；
`pagination.decisions.unit` 披露分页单位。`outcomes` 的 trusted/external 分别分页。
深链接选中的 Run 即使不在当前选择器页，也会额外返回；经验选择直接读取该经验，
不验证无关库页，避免误报 NOT_FOUND 或消耗无关经验的门禁预算。
`case=case-a|case-b|case-c` 和 `stage=before|after|restored` 用于 REPLAY；
为兼容旧链接，LIVE 接受合法的 case/context/stage 值，但不用于选择或判定。
LIVE 只需运行 `python -m aevora_observatory.server`，无需演示目录；
可选同时配置 `--replay-root` 与独立可信 `--replay-sha256` 启用演示。
未配置时显式 REPLAY 返回 404 / REPLAY_NOT_CONFIGURED。

CLI 加载[Host profile](MCP.md#host-配置与会话恢复)，也可显式 `--config PATH`。
普通 LIVE 默认端口为 17805，Demo replay 为 17804；profile 的 Console 端口和
显式 `--port` 可调整。实际绑定后打印 `LISTENING` 与 URL。占用端口返回
`CONSOLE_PORT_IN_USE` 和处理提示，不停止已有进程或静默改用其他端口。
没有 Host 配置时，LIVE 启动返回 `HOST_CONFIG_REQUIRED` 并提示 `configure`。

Proof 接口接受 `mode=LIVE|REPLAY`，省略时兼容既有 REPLAY 读取。
`/api/proof/lifecycle?mode=LIVE&candidate=<候选 ID>` 必须指定候选；服务使用
Core `CandidateLifecycle.inspect` 校验该候选的 head、事件链和实际关系，只返回
公共字段。候选不存在返回 404，链校验失败返回 422，DB 不可用返回 503。
其他 proof 名称暂不支持 LIVE，返回 404，不读取回放；前端仅在 REPLAY 展示
这些历史产物入口。REPLAY lifecycle 也可携带 `candidate`，不匹配时返回 404。

API 使用 Core 发布门禁及已保存的查询快照，不从 HTTP 执行新 resolver 查询或创建 QuerySnapshot、
Decision、Outcome 或 review。公开字段按 label allowlist 投影，浏览器
不获得原始模型/MCP载荷、私有评测、Host 凭据、任意文件读取或 Cypher。

## 有限读取与错误

服务绑定 loopback，检查 Host/Origin，限制请求大小和并发，返回 no-store、
CSP、no-sniff 和 referrer policy。LIVE 不先检查或装载整张图，各资源接口只读取
所需页面，概览组合有限页面；项目累计节点、边和经验数量不再作为拒绝读取的条件。
每次请求仍最多读取 500 个不同节点、1200 条关系、8 MiB payload，并限制
查询次数与总读取时间。Core 发布门禁、快照和生命周期证明的读取共享该预算；
payload 在数据库返回前有大小保护，公开投影继续校验摘要和身份。
请求内缓存复用不可变节点；可变的 `LifecycleHead` 每次读取均实际查询数据库，
使 Core 的末尾 head 复查能发现读取期间的撤回。重复 head 读取累计查询次数、
payload 字节并检查剩余时间，同一身份只计一个不同节点。观察到变化时，
LIVE proof 和 overview 返回 422 / ImmutableConflict，无旧成功数据且不回退 Replay；
用全新请求重读。这项复查不提供原子多查询快照。
LIVE JSON 响应也限制为 8 MiB，避免多个 Query 复用一个快照时放大响应。

未选择经验时，图读取当前 Run 或项目的一页节点；Run 页额外读取这些记录的
一跳实际邻居（例如无独立 Run ID 的 QuerySnapshot、Experience 与 head），
合计最多 64 节点，不扩散到其他 Run 的记录。分页按 Run 种子节点推进；
`pagination.graph.total_seed_nodes` 披露种子总数，邻域总数保持未知。
选择经验时，以该经验为中心逐层读取最多 3 跳、64 个节点的结构邻域，
不沿其他 Run 的查询关联扩散。局部图的全量邻域计数未知时为 `null`，
不冒充项目总数。初始前端展示最多 24 个邻近节点，图布局不增加实际关系。
页或邻域被截断时图返回 PARTIAL，节点页面可继续游标读取；经验邻域保留固定深度与上限。
实际请求超预算返回 413 / GRAPH_READ_BUDGET_EXCEEDED，可缩小页面或选择更具体的对象；
界面在预算错误时提供缩小页面入口。单个记录或完整证明仍可能超预算而拒绝读取。
`read_budget` 返回本次实际读取量和上限。DB 不可用返回 503，回放不一致返回 422。
具体实现以 `console/src/aevora_observatory/` 为准。

`--mcp-events` 只显示 Host 配置通道中的实际工具请求头；请求不单独证明
原生 Session、child 作者或进程存活。没有采集到的信息不补造。
profile 的会话根或显式 `--session-root` 会在每次读取时选择当前会话日志，
Host 重启后无需重启 Console。它与固定 `--mcp-events` 互斥。历史 Run 的图记录
继续可见；当前日志不包含的历史工具请求不补造。正常停止后可查看最后实际事件，
不将残留 selector 解释为进程仍存活。

## 前端开发

构建版本以 console/package.json 和 lockfile 为准：

```sh
npm --prefix console ci --ignore-scripts
npm --prefix console run build
```

静态文件写入 Python 包资源。构建将模板字符串转为转义字符串，保留内嵌
shader 内容并避免生成代码的行尾空白；生成资源与 BUILD_MANIFEST 一并更新。
Cytoscape 展示图，esbuild 打包；来源与许可见
[NOTICES](NOTICES.md)。维护者的 Node、浏览器、隔离检查见根开发指南，
公开回放操作见[演示](DEMO.md)。

生命周期绑定的专项浏览器回归位于 `console/browser/proof-binding.mjs`。
它要求独立测试图中至少两个显式合成候选、`AEVORA_BROWSER_URL` 指向该图的
Console，以及 `AEVORA_BROWSER_OUTPUT` 指定全新仓库外目录；运行
`node console/browser/proof-binding.mjs`。结果区分实际 HTTP 检查和模拟响应
错配的拒绝检查，不构成 Agent 或可信 Outcome 证据。

项目入口浏览器回归位于 `console/browser/live-project.mjs`，通过显式配置的
独立空图、待核验图和已发布图检查实际状态、筛选、记录来源、演示入口与断连清除。

中文引导回归位于 `console/browser/guidance.mjs`。指定实际运行候选构建的
`AEVORA_BROWSER_URL` 与全新的仓库外 `AEVORA_BROWSER_OUTPUT` 后执行
`node console/browser/guidance.mjs`，检查指标与真实 API 一致、查询空结果解释、
引导展开状态在刷新后保留、筛选深链接、手机宽度及断连清除。它只读所选 Host，
不会创建经验或调用模型；必须以实际浏览器结果区分源码检查与视觉验收。

容量与分页回归位于 `console/browser/pagination.mjs`。`AEVORA_BROWSER_URL` 必须
指向显式创建、超过 500 节点和 16 条经验且有多页 Run/Query/Candidate 的独立
合成测试图，`AEVORA_BROWSER_OUTPUT` 指向全新仓库外目录。它检查真实翻页、
深链接、局部图和候选证明；预算与断连的界面检查显式模拟 HTTP 错误，
与真实 API 容量检查分开记录，不构成 Agent、模型或可信 Outcome 证据。
