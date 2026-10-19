# Codex Native Multi-Agent Integration

> **Phase 3.5 current profile:** new live runs use the hardened Gateway provider, `gpt-5.6-terra`, explicit `max`, isolated network namespaces and a per-run authenticated Unix model channel. Legacy descriptions below document Phase 3 behavior; they do not describe new live runs. See [PHASE3_5_HARDENING.md](PHASE3_5_HARDENING.md) and [GATEWAY_PROVIDER.md](GATEWAY_PROVIDER.md). New live Legacy entry fails closed.
>
> The Gateway profile enables the official Code Mode helper and native collaboration, uses a fresh private CODEX_HOME without `--ephemeral` so same-run child forks can work, seals exact public stdin before launch, archives redacted official run rollouts after process cleanup, and removes state. Upstream credentials stay exclusively in the trusted broker. The documented CPU/disk sampling and candidate resource limitations require a conditional adversarial security assessment.


## 当前状态与验收边界

Phase 3 增加了真实 `codex exec` 适配器、公开 Participant Workspace、原生事件解析、实际补丁提取及现有 Evaluator 的接入路径。调度、任务委派与子 Agent 生命周期仍由 Codex 原生 Runtime 管理。

本机使用 **Codex CLI 0.162.1**。初次受限环境中的尝试在 Broker 监听阶段遇到 `EPERM / Operation not permitted`，DNS 也失败；该轮归档 `runtime_result=ERROR`、`evaluation_result=NOT_RUN`，没有补丁或子 Agent 成绩。用户调整执行权限后，loopback listener、DNS、HTTPS 已实际恢复。正式 Run `339f7d73-29df-4242-8920-9e566bce8a9c` 启动了三个不同的原生子 Agent，均完成独立任务；实际补丁通过现有 14 项隐藏测试，Runtime、Multi-Agent、Isolation、Evaluation Integration 均为 PASS。

版本探针、模型请求、子任务启动、子任务完成与最终隐藏评测是不同的证据门槛。正式挑战的最终 Runtime 状态、两个子任务完成记录、原始补丁、评测结果、实际命令与 Run ID，以 [PHASE3_VALIDATION_REPORT.md](../PHASE3_VALIDATION_REPORT.md) 为准。测试中的受控进程、合成 JSONL 和测试 HTTP 上游仅验证接口契约，不作为正式 Multi-Agent 运行证据。

## 模块与流程

| 模块 | 职责 |
| --- | --- |
| `benchmark/participant.py` | 从已准备的公开缺陷工作区构建 Participant；提取实际源码补丁与公开测试证据 |
| `benchmark/participant_sandbox.py` | 为完整 Codex 进程及其工具建立外层 bubblewrap 文件边界 |
| `integrations/model_broker.py` | 在可信维护者进程内持有模型认证，仅转发两条固定模型路由 |
| `integrations/codex_agent.py` | 启动一个全新官方 CLI 会话，采集进程退出、事件、耗时和提交 |
| `integrations/codex_trace.py` | 解析官方 exec JSONL 的结构化事实及证据完整性 |
| `BenchmarkRunner.run_agent()` | 衔接 Prepare、Agent 执行、既有提交校验、隐藏评测、报告和重置 |

正常路径为：

```text
Load / Prepare
  → public Participant Workspace + trusted baseline
  → fresh Codex exec session
  → native delegation / investigation / repair / review
  → stop native process group and model broker
  → extract actual app diff on the trusted host
  → existing ManualSubmissionAdapter and patch validation
  → Independent Evaluator / hidden suite / database Oracle
  → report / reset / remove per-run Codex state
```

每次 `run-codex` 都创建新的 UUID Run ID；它不会恢复、fork 或继续维护者开发会话。每轮的 `CODEX_HOME` 来自新建目录。运行结束后删除该目录，下一轮不继承 Session 状态。

`ManualSubmissionAdapter` 及 `evaluate --submission` 路径继续保留。Experience Adapter 始终为 `DISABLED`，没有经验查询、命中、决策或反馈事件。

## Participant 输入与原生角色

Participant 从 Runner 已生成的公开工作区复制实际缺陷基线。复制范围为 `app/**/*.py`、`tests/public/**/*.py`、`public.json` 和 `TASK.md`；不从维护者根目录复制正确业务实现。`ISSUE.md` 的问题、约束、运行参数和初始状态来源于 Public Manifest，没有维护者故障定位或参考修复提示。

`AGENTS.md` 要求 Lead 委派至少两个不同的独立原生子任务，等待真实结果，再协调修复和审查。三个公开角色分别是 `investigator`、`test_engineer` 和 `reviewer`；每个 TOML 只使用官方支持的 `name`、`description`、`developer_instructions`，继承主 Agent 的模型及沙箱设置。Lead 协调共享文件的唯一写入者，独立调查可并行开展。这些配置定义工作要求，真实委派是否发生由执行证据判定。角色格式依据 [Codex 官方 Subagents 文档](https://learn.chatgpt.com/docs/agent-configuration/subagents)。

Participant 带有一个公开 Git 初始提交。初始化不读取宿主 global/system Git 配置，不执行 hooks，也不签名。公开测试可由 Agent 增补：

```bash
python3 -m unittest discover -s tests/public -v
```

## 官方 CLI 运行方式

适配器使用 `codex exec --json --ephemeral`，启用 `multi_agent`，保留 `workspace-write` 与 `approval_policy=never`，通过 stdin 提交公开任务。不会使用 `danger-full-access`、`--yolo` 或审批/沙箱绕过开关。宿主配置、rules、Memories、Apps、Plugins 等非本任务输入能力被禁用或忽略，实际开关列表保存在成功启动后的 `runtime_metadata.json`。

`--json` 将 stdout 变为事件 JSONL；`--ephemeral` 不持久化会话 rollout 文件。具体选项以实际安装版本的 `codex exec --help` 和 `codex features list` 核查结果为准，升级 CLI 后需要重新验证。[官方非交互模式说明](https://learn.chatgpt.com/docs/non-interactive-mode)、[官方 CLI 参数说明](https://learn.chatgpt.com/docs/developer-commands?surface=cli)。

本机 Python 3.12 fallback launcher 的使用方式：

```bash
scripts/orderflow run-codex --episode A --agent-timeout 900
```

支持 `--variant v01`、`--model <model_id>`、`--evaluation-timeout <seconds>`，以及在子命令前指定 `--runs-root <trusted_archive_root>`。Agent 时限必须在 `(0, 7200]` 秒；Evaluator 时限只能在现有 Episode 上限以内缩短。默认模型为 `gpt-6.1-sol`，模型可用性与账户权限需要真实服务验证。

使用普通 Python 3.12 虚拟环境时，由可信启动器配置路径，再运行已安装的 CLI：

```bash
export ORDERFLOW_CODEX_BINARY=/absolute/path/to/codex
export ORDERFLOW_CODEX_AUTH_PATH=/absolute/path/to/trusted/auth.json
orderflow run-codex --episode A --agent-timeout 900
```

这些变量只指定维护者可访问的文件路径，不向 Participant 环境传递认证内容。当前认证读取器只支持有效的 ChatGPT `auth.json`，不实现 API Key Provider 或认证刷新。不要把该文件放进仓库或 Participant Workspace。

本机 `scripts/orderflow` 对 `run-codex` 自动开启 wrapper 的 `ORDERFLOW_ENABLE_CODEX=1` 路径。该路径仅把可信身份文件只读挂在维护者 namespace 的 `/maintainer/auth.json`，把 Codex 可执行文件挂在 `/tools/codex`。Participant 再建立独立 namespace，仅挂载该可执行文件到 `/opt/codex/codex`，没有 `/maintainer`、宿主个人目录或完整身份文件。Flatpak fallback 的可信维护者 Python 使用挂载的 `/etc/ssl/certs/ca-certificates.crt` 作为 `SSL_CERT_FILE`，保留 TLS 证书验证。详情见 [AGENT_ISOLATION.md](AGENT_ISOLATION.md)。

## 原始事件与 Trace 契约

Trace 使用安装版本对应的官方 [rust-v0.162.1 `exec_events.rs`](https://github.com/openai/codex/blob/rust-v0.162.1/codex-rs/exec/src/exec_events.rs) 定义，不套用 app-server 的 camelCase 事件，也不从自然语言内容推断委派。

| 观测值 | 实际来源与处理 |
| --- | --- |
| 主线程 ID | `thread.started.thread_id`；缺失则 `UNAVAILABLE` |
| 原生协作 | `item.*.item.type=collab_tool_call`，读取 `tool`、`sender_thread_id`、`receiver_thread_ids`、`prompt`、`agents_states`、`status` |
| 已启动子 Agent | 完成状态的 `spawn_agent`，并具有不同于 sender 的 receiver thread ID |
| 子任务完成 | 后续结构化 Agent state 为 `completed`，同时保留对应原始事件引用 |
| `verified_count` | 具有实际 spawn、非空任务、completed 状态及非空完成 message 的不同 child thread 数量 |
| 工具与文件事件 | 官方 `command_execution`、`file_change` 等原始 item；不会创造缺失的工具调用 |
| Token Usage | 仅累加实际 `turn.completed.usage`；字段及统计范围保存在元数据 |
| 独立 Session ID | exec 协议未提供单独 Session ID，标记 `UNAVAILABLE`；不把 Run ID 冒充 Session ID |
| 官方事件时间 | 协议未提供则 `UNAVAILABLE`；统一 Trace 时间明确来自宿主归档采集或解析时间 |

每条统一 Trace 记录具有 Run ID、source、事件类型、归档路径、真实行号及该行字节 SHA256。原始归档整体也有 SHA256。未知事件保留并计数；缺少 thread/turn、未完成 item、重复/错配协作 ID、无效 JSON 和无效 Usage 等会得到 `INCOMPLETE`。未完成 Trace 不满足 Runtime 成功条件。

`verified_count >= 2` 是结构化证据门槛。验收还需要检查实际任务内容确实独立，不能仅凭角色配置、Lead 的口头描述或测试构造的事件满足要求。当前 exec 事件提供父线程观察到的子任务状态和结果；本集成没有宣称采集所有子 Agent 内部工具日志。

stdout/stderr 先由可信宿主采集，再针对认证键、令牌形态及实际 Broker secret 值脱敏。无需脱敏的行保留原字节，需要脱敏的行记录修改计数；证据引用指向最终脱敏归档。临时未脱敏捕获文件在结束路径移除。模式脱敏不能识别所有任意格式的个人信息，文件边界首先阻止 Participant 获得维护者身份。

## 实际提交与客观评测

Runtime 已终止后，宿主比较可信基线与 Participant 实际 `app/**/*.py`。只生成这些源码的 unified diff，不执行候选代码。新增、删除、空 Python 文件及没有末尾换行的变化均支持；链接、特殊文件、非 UTF-8、非法路径以及超过现有文件/大小上限的提交被拒绝。

公开测试变化保存在 `public_test_changes.diff`，不作为隐藏测试或评测配置提交。没有业务源码变化时明确返回 `NO_PATCH`，仍保存公开测试证据及元数据。

Runner 把真实补丁交回原有提交校验与 Evaluator。Episode A 继续使用现有 **14 项隐藏测试**、独立数据库 Oracle、pytest/JUnit 完整性检查及真实版本指纹。Agent 未修好时归档其真实 FAIL；不替换参考补丁、不人工补写修复、不修改评测条件。

## 三类结果

| 字段 | 含义 |
| --- | --- |
| `runtime_result` | 官方 CLI 是否执行了完整 turn 并产生可接受源码提交；可能为 PASS、ERROR 或 TIMEOUT |
| `evaluation_result` | 独立 Evaluator 的真实 PASS/FAIL/ERROR/TIMEOUT；没有提交时为 NOT_RUN |
| `integration_result` | 提交是否通过既有评测及重置闭环；正常评测出 FAIL 仍可表示集成闭环 PASS |
| `multi_agent_result` | 根据原生 Trace 证据完整性及至少两个已验证子 Agent 判定，不能由任务测试成绩代替 |

CLI 的退出状态仍以报告的 `overall_status` 为准：PASS=0、FAIL=1、ERROR=2、TIMEOUT=3、NOT_IMPLEMENTED=4。启动失败、Broker 失败、执行失败、超时、Trace 不完整、无补丁、无效提交与进程清理失败分别在 `runtime_metadata.failure_kind` 中归档。Runtime 失败时不调用隐藏测试。

## 归档布局与后续验证

```text
runs/<run_id>/
├── public_manifest.json
├── workspace/                 # trusted public baseline; database reinitialized by reset
├── participant/               # actual public Agent workspace
├── submission.diff            # exists only after actual source changes
├── public_test_changes.diff   # generated at submission extraction
├── submission_metadata.json
├── codex_events.jsonl          # redacted official stdout; may be empty on startup failure
├── codex_stderr.log
├── agent_trace.jsonl
├── runtime_metadata.json
├── execution_trace.jsonl
├── evaluation_report.json
└── artifacts/                 # pytest/JUnit/concurrency/database evidence, if evaluated
```

启动前失败时缺少补丁、Usage 或官方 thread 是真实缺失，不创建占位修复。空 JSONL 和 `UNAVAILABLE` 字段用于明确这种情况。

运行环境必须同时支持 loopback listener、DNS、固定 HTTPS 模型连接及 bubblewrap。每次正式验收需核实真实模型流、两个不同的已完成原生子任务、实际提交及隐藏评测闭环；后端、CLI 或网络策略变化后应重新验证。若环境再次阻塞，保留实际 ERROR/NOT_RUN，不通过关闭沙箱、挂载完整宿主或暴露长期凭据绕过。

完整验收与现有归档的补充证据检查：

```bash
ORDERFLOW_ENABLE_CODEX=1 scripts/python312 scripts/validate_phase3.py --agent-timeout 900
ORDERFLOW_ENABLE_CODEX=1 scripts/python312 scripts/audit_phase3_evidence.py --validation-id <validation_uuid>
```

第一条会重跑 Phase 1/2 和十轮正反对照，再启动新的真实挑战。第二条重解析已有原始事件，检查补丁、版本指纹、原有 107 项测试身份和十四个隔离路径，并执行当前完整开发者测试；不调用模型、不更改原 Run 的任务成绩。补充审计使用新的 UUID 子目录归档，保留原验收结果。

当前正式流保留一个模型 metadata fallback startup warning，以及 Broker 的非致命流中断分类。它们不被删除或冒充无异常，具体次数、证据范围与限制见验收报告。CLI/模型升级后需重新核实 catalog 和事件协议。

Phase 3 范围到此为止；Episode B/C/D、经验检索与治理、MCP、FalkorDB、Dashboard 和 G0–G3 实验继续未实现。
