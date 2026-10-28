# 工程记忆与核验

## 连接与采集

MCP 用于查询和提出观察；工程来源还需要采集入口。不能从 MCP 已连接推断所有 Codex 进程都被采集。
需要转接官方 app-server 时，可用以下入口替代客户端原本的 app-server 启动命令：

```sh
aevora memory codex --project my-project --task fix-build --client codex
```

如需额外app-server选项，放在`--`后。适配器只观察实际经过它且
工作目录匹配项目的会话，不接管已经运行的任意进程；客户端标签不证明配置根身份。

不经过该入口的终端检查，可以显式记录：

```sh
aevora memory run-check --project my-project --task fix-build -- go -C go-runtime test ./...
aevora memory run-check --project my-project --task fix-build -- python -m pytest tests
aevora memory run-check --project my-project --task fix-build -- npm --prefix console test
```

命令在登记的项目根目录执行，继承你的环境与权限。支持直接测试调用，不接受shell包装。
正常退出码保持不变；启动失败或结果无法判定返回2，中断返回130。原始输入、参数、环境和输出
不会写入记忆，只保留有界类别和结果。分类不证明实际测试覆盖或独立正确性。

## 判断记录到了哪一步

```sh
aevora memory status --project my-project --json
aevora memory work --project my-project
```

| 状态 | 含义 |
|---|---|
| QUEUED_UNTRUSTED | 已保存到队列，尚不代表已经摄入或形成候选 |
| CAPTURE_FAILED | 检查已结束，但采集失败；查看队列和目录状态 |
| local_check | 最近一次显式本地检查，与Codex适配器样本分开 |
| MORE_ENGINEERING_EVIDENCE_REQUIRED | 当前来源不足以形成候选，观察仍保留 |
| PROPOSED | 待核验观察，可以作为线索；还不是可直接信任的经验 |

已授权项目可由后台Host处理队列；Host离线时保留，之后用memory work处理。
当前内置整理器压缩同一任务的失败、完成改动和成功检查；仅有成功检查时可能继续等待。
不要补造事件来强行得到候选。用 `memory sources --project my-project --candidate ID` 查看候选来源。

## 产品中的自动核验

来源核验、适用条件和失效处理属于Aevora产品能力。原生核验器当前支持固定JSON工件断言，
它只能证明工件符合这些断言，不能顺带认证全部修复叙述或因果收益。

```sh
aevora memory evaluator --json
aevora memory check --project my-project --plan /absolute/private/plan.json --candidate CANDIDATE_ID
aevora memory enable-check --project my-project --plan /absolute/private/plan.json
```

检查计划由Host所有者放在工作区外，包含project、task_ref、submission、suite、source_policy、
automation_policy和output_root，schema_version为`aevora.json-check-plan/1`。
固定suite为`aevora.json-contract-suite/1`，使用name、RFC6901 pointer及equals或contains断言。
来源策略通过`aevora.project-source-policy/1`固定检查器、suite和必要测试身份；
事实及自动化范围必须明确限定`operation_semantics=json_artifact_contract_only`。
可用`aevora candidate automation-policy --help`查看常设授权参数。候选不能提供自己的独立真值或授权策略。

普通观察无需人工逐条审批；可信固定计划可在常设策略内自动处理。人工负责策略、冲突和抽查。
如要停止计划，使用 `memory disable-check --project my-project`；历史保留。
