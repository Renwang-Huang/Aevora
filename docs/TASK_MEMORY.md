# 工程任务记忆

原生运行时可关联同一项目、任务标签、官方会话中的多个回合。来源保留为
`ENGINEERING_TASK_EVENT`，固定身份的重复投递可核对；不同内容不能覆盖旧来源。
接收时间不等于事件时间；未知版本和发生时间保持未知。任务关联不证明根因、修复或收益。

## 接入与观察

用 `aevora memory codex --project PROJECT --task TASK --client codex2` 替代客户端
启动的 `codex app-server`，客户端仍使用官方 stdio JSON-RPC。参数通过 `--` 传给
app-server。仅观察这个适配器实际连接的会话；不接管已启动的任意 Codex 进程。
必须从官方线程元数据确认工作目录在登记工作区中，未知线程与其他目录不继承项目。
原始流转发不变，超出观察上限的帧仍转发并记录跳过；不保存 reasoning、原始命令、
完整输出或 transcript。生成摘要只包含动作类别、状态和受限测试名称。

检查分类支持 `go -C DIR test`、`python -m pytest`、`npm --prefix DIR test`
及受支持的 workspace 形式。官方命令文本用固定版本的
[mvdan shell parser](https://github.com/mvdan/sh) 只解析单个字面命令；不执行 shell，
不展开变量。链式命令、管道、否定、重定向和替换保持普通 COMMAND，避免把整个
shell 的成功退出误认为其中测试成功。不支持的选项、包装器或语法保持未知。
分类只说明调用形式，不证明可执行文件身份、实际运行了测试或独立检查通过。

`aevora memory status --project PROJECT` 分别显示三个入口标签的观察样本、drainer
和整理作业。标签不是客户端 home 的身份认证；最近样本不是进程存活或全面覆盖证明。
`memory record --event JSON` 可补充明确的公开工程观察；它是调用者声明，不能取得信任。
事件字段与上限见 `internal/domain/task_memory.go`，不接受原始日志或任意扩展字段。

## 开发中实际使用

不经过 app-server 的终端检查可以显式接入同一工程记忆队列：

```sh
aevora memory run-check --project my-project --task check-capture -- go -C go-runtime test ./internal/taskcapture
aevora memory run-check --project my-project --task check-capture -- python -m pytest tests
aevora memory run-check --project my-project --task check-capture -- npm --prefix console test
```

命令在所选项目登记根目录执行，直接传递 argv，不经 shell。支持的检查族与上文分类一致；
未知命令、shell 包装和无效公开标签在执行前拒绝。子进程继承当前环境与权限，输入输出直接
转发；该入口是用户显式指定的本地检查，不是独立核验器或任意 Agent 调度器。

子进程的正常退出码原样返回；启动失败/无法判定结果返回2，中断返回130，来源状态均为UNKNOWN。
终端 stderr 追加一条采集回执，`QUEUED_UNTRUSTED`表示已持久排队，不能据此认定已摄入、
提炼或发布；`CAPTURE_FAILED`要求检查队列。采集失败不改变检查本身的退出码。
只保存动作类别、状态、退出码、完成观察时间和公开标签；不保留 argv、环境、stdin 或原始输出。
版本保持未知，不把一个进程的执行结果绑定到未经完整观察的代码版本。

同项目、task和session标签关联为一个episode，默认session为`local-checks`，可用
`--session`区分不同工作批次。每次执行有独立来源身份，重复运行不会覆盖先前结果。
`memory status`的`local_check`单独显示最近本地检查回执，三个`clients`标签只描述
app-server适配器。最近回执不是进程存活、已经摄入或自然会话覆盖的证明。
已运行的Host可按授权路由自动摄入；离线时保留outbox，之后用`memory work`处理。
它不代表任意已有Codex进程被自动采集，也不代表三个客户端全部覆盖。

开发时先查询已有经验；确实调查过观察线索后记录使用反馈。检查结束后核对实际来源、
整理状态和阻塞原因；用具体任务词查询，不用条目数代替有效经验。缺少改动或失败证据时，
整理器可以合法停在`MORE_ENGINEERING_EVIDENCE_REQUIRED`，不能补造事件以生成候选。

来源先进入私有持久 outbox。Host 在已授权路由内后台接收和整理；也可以执行
`aevora memory work --project PROJECT` 有界地接收和处理，Host 未运行时仍能工作。
损坏项消耗扫描预算，轮转不会让晚到或较小 ID 永久漏掉；坏游标保留供恢复，
不静默覆盖。`memory reset-scan` 会保留旧游标文件再重置扫描。队列只接受通过校验的公开事件，失败不改变 Codex 原始工具结果。

## 整理与读取

当前内置提炼器 `task-summary/1` 压缩来源中的工程摘要。在同一任务已有失败、完成
改动和成功检查时，形成带来源的候选；不足时自动保留观察，下一条来源会触发新作业。
它不从词汇命中或退出状态推断根因，也不声称具备任意领域的模型提炼能力。

整理作业采用 SQLite 内的追加审计账本，保留占用期限、单调 fence 和重试次数。
同一输入集的候选确定性去重；来源变化重新整理，迟到 worker 不能提交旧结果。
结果、来源关系和已处理记录同事务；默认每次只处理有界作业，不在写事务中等待
网络、模型或测试进程。每任务最多接收有界来源快照，超限进入明确隔离状态，
不会让坏任务阻塞其他任务。历史不会被删除或就地改写。

MCP `read_observation_sources(candidate_id, after, limit)` 提供 1..20 条来源分页，
`memory sources --candidate ID --project PROJECT` 和 Console 使用同一领域逻辑。单页同时受字节预算约束，长摘要可能使实际条数少于 limit，沿 next_cursor 继续即可。
MCP 根据固定的 target_project 授权，未知或其他项目拒绝。
来源 ID 分页供界面浏览，后台整理使用处理账本，不将字典序游标当作摄入进度。

## 独立 JSON 工件核验

首个原生核验器检查固定 JSON 工件契约（提交最多 1 MiB、suite 最多 256 KiB），不执行提交中的代码。
用 `aevora memory evaluator --json` 获取内置 verifier 的内容与摘要；由 Host 在工作区外
保管 suite、source policy 和 automation policy，普通用户二进制无需 Python 或外部 DB。
提交必须位于已登记工作区，不能把检查器用于复制任意个人秘密文件。

suite 格式为 `aevora.json-contract-suite/1`，checks 包含 name、RFC6901 pointer，
以及二选一的 equals 或 contains。contains 检查数组中存在匹配指定字段的对象。
缺少字段、类型错误和不匹配会失败；测试名称固定，生成的 JUnit 必须符合 source policy
的 required_tests。来源事实和晋升范围必须同时限定
`operation_semantics=json_artifact_contract_only`；查询缺少该可信操作事实时保持 VERIFY，
不能仅因项目相同而把工件核验当作任意任务的可用建议。它只证明该 JSON 工件符合固定断言，不证明运行时执行或因果收益。

原始任务叙述保持未核验。核验器自动派生新的有界候选，只发布固定检查方法和实际检查身份，
不因 JSON 检查通过而认证任意修复叙述。派生候选保留原观察和全部来源关系。

检查计划保存在工作区外的 0600 文件：

```json
{
  "schema_version": "aevora.json-check-plan/1",
  "project": "PROJECT",
  "task_ref": "TASK_CATEGORY",
  "submission": "/absolute/project/artifact.json",
  "suite": "/absolute/protected/suite.json",
  "source_policy": "/absolute/protected/source-policy.json",
  "automation_policy": "/absolute/protected/automation-policy.json",
  "output_root": "/absolute/protected/evidence"
}
```

source policy 继续使用 `aevora.project-source-policy/1`，固定 suite / evaluator 摘要、
必要测试身份、`origin=independent_project` 和实际核验事实；target_project 必须匹配项目。
使用既有 `candidate automation-policy` 创建绑定后端与来源策略的常设授权。
不应根据候选内容生成其自己的正确答案或独立测试。

`memory check --project PROJECT --plan PLAN --candidate ID` 执行一次。
`memory enable-check --project PROJECT --plan PLAN` 将计划委托给已运行的 Host 后台 actor，
无需保持终端打开；`memory disable-check --project PROJECT` 可停止该计划，历史与证据保留。后台轮询不消耗外部管理鉴权预算，不为无变化的只读巡视追加操作回执。
计划、来源与策略由 Host 在既有权限范围内处理；最多登记 16 个项目计划，每轮最多轮转两个，
不会让单一计划占满采集循环。输入变化与不可用采用轮询发现，不承诺瞬时全局一致。

`memory watch --project PROJECT --plan PLAN` 用于前台短期检查，自动接收来源、整理、
分页核验并在常设策略范围内晋升；`--once` 处理一页后退出。它只维护记忆，不调度 Agent。
普通观察不需要人逐条审核；人负责设置策略、处理冲突和抽查质量。

核验产物、回执和初始 head 固定保留，中断后可复用原回执对账。重复巡视不会重复产生
可信结果。已核验提交或固定策略发生变化、核验输入不可用时撤回当前候选，禁止把旧经验自动复活。
`memory revoke-source --project PROJECT --source ID` 撤销确定的来源并传播到依赖候选；
历史查询和原来源保留。新的任务/来源形成新候选，重新核验。

## 仍需验证的范围

模型提炼与多领域技能生成未包含在内置压缩器中；完整磁盘故障、长期保留/压缩和
真实模型收益对照仍需单独验证。检索质量基线见 [RETRIEVAL_QUALITY](RETRIEVAL_QUALITY.md)。
固定合成用例、真实运行时连接和真实模型供应商任务必须分别报告，不相互替代。

新二进制声明 `task_memory_reader=1`。升级和自动回退在已有工程来源/作业时阻止不兼容
读取器；首次启用此保护应由新版 upgrade 操作已安装 target，避免使用尚无保护的旧升级器。
