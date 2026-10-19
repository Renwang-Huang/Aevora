# 长时间 Codex 运行策略（M1.1）

运行模式与任务得分分别记录。去除研究模式的 Agent 总时限，不改变隐藏测试、提交保真、隔离或者历史 TIMEOUT 成绩。

## 两种显式模式

| 策略 | Agent 总 wall-clock | 请求总量 | 官方 SSE idle | 原行为 |
|---|---|---|---|---|
| `bounded`（默认） | 默认 900 秒，可设至 7200 秒 | 默认 160，可有限配置 | 默认 120000 ms | 保留 |
| `completion-aware` | 必须显式 `none` / Python `None` | 可明确 `none`，并发仍最多 4 | 默认 600000 ms，可明确配置有限值至 3600000 ms | 等待真实自然终态或可信取消/故障 |

```sh
scripts/orderflow --runs-root <new-runs-root> run-codex --episode D --variant v01 \
  --provider gateway --model gpt-5.6-terra --reasoning-effort max \
  --completion-policy completion-aware --agent-timeout none --request-budget none \
  --agent-mode multi
```

无 wall 限制使用真实 `None`。Adapter 以及内外 `ResourceWatchdog` 都不会按累计 wall-clock 自动停止它；0、NaN、Infinity 及大数替代 None 不合法。CPU 600 秒、2 GiB memory、768 tasks、有限输出/文件/地址空间等已有资源限制继续有效；它们是明确资源政策，不是时间限制。内核 CPU controller 尚未委派，CPU/部分输出依赖采样，不能宣称无限对抗安全。

自然完成仍要求官方 `turn.completed`、正常进程退出、完整 Trace、实际合法补丁和独立 Evaluator。No Patch、无效提交、真实任务 FAIL、Provider 故障、资源违规和取消分别报告。

## 慢响应与真实网络边界

Gateway Broker 在 completion-aware 中：

- 连接/TLS 建立采用独立有限 30 秒限制；**连接建立后的 HTTP 首响应等待不继承这个值**。
- 认证及客户端请求 framing/body 有有限 ingress 时限和大小约束。
- 认证和 body 校验完成后取消完整 response Timer，不给 HTTP 首响应、SSE 间隔或完整响应添加 Broker 总 deadline。
- 实际 socket 注册到可信宿主，等待首响应或闲置流仍可在退出/取消时 shutdown。
- 原生 CLI 自身仍有明确的有限 SSE idle 参数及有限 HTTP/stream retries；这是可恢复网络层边界，**不等于无任何网络期限**。若当前 CLI 对某类慢首响应另有不可调限制，必须按动态结果报告，不能猜测它不存在。
- 真实 429 的有效 `Retry-After`（秒或 HTTP date）被验证、归一化并转发。记录的 backoff 是上游指示；`actual_client_wait` 不可直接观测时为 `UNAVAILABLE`。
- 永久 400/401/403/422 等保持真实 HTTP status。Broker 不自行无限重试；官方 CLI HTTP 和 stream retry 默认各 2，不启用 unbounded retries。
- TLS 验证、禁止重定向/环境代理、模型/effort/route/peer UID/run 身份校验保持。

身份在 completion-aware 中属于 Broker owner lifetime：只授权该 Run 的受限 socket/短期 Run bearer，Broker 结束后立即清除并撤销。上游密钥仅在可信宿主内存使用，既不传 Participant，也不写归档或摘要。删除历史 1800 秒硬 TTL 的同时保持 owner 生命周期；不存在可跨 Run 复用的通道。

## 可信可观察性

`runtime_status.json` 是可信控制器的原子快照；运行中明确 `PARTIAL_SNAPSHOT`。它包括 Run/控制身份、模式、最近真实进度、子 Agent 状态、请求数/错误、可获取 usage、资源观测和有限只读源码哈希快照。

源码快照非原子事务视图，`readiness=UNVERIFIED`；不能根据首次看到改动宣称补丁当时已通过隐藏测试。正式补丁仍在运行停止后使用统一保真协议提取。

`runtime_activity.jsonl` 只描述实际观察到的官方 exec 事件、控制信号和退出，不合成官方事件。`gateway_transport_events.jsonl` 持续 append 请求开始/结束和错误，保存各请求的首 HTTP 响应、首 body、实测 body gap、真实响应身份/usage；metadata 的 request/error ring 仅用于近期摘要，不能替代完整日志。

运行状态包括 `ACTIVE_MODEL_REQUEST`、`SSE_STREAMING`、有真实 Retry-After 的 `RATE_LIMIT_BACKOFF`、`LOCAL_TOOL_RUNNING`、`CHILD_AGENT_RUNNING`、`WAITING_FOR_CHILD`。缺乏充分信号仅提示 `POSSIBLE_STALL`，不因此按时长判死锁。子 Agent 最终是否自己的工作完成并被主 Agent 接收，仍由停止后的原生 rollout parser 核验；live 快照不是替代证据。

## 可信宿主 status / snapshot / cancel

```sh
scripts/orderflow --runs-root <new-runs-root> status --run-id <uuid>
scripts/orderflow --runs-root <new-runs-root> snapshot --run-id <uuid>
scripts/orderflow --runs-root <new-runs-root> cancel --run-id <uuid> --reason '研究人员明确停止'
```

控制文件位于未挂载到 Participant 的可信 Run archive。通过 owner、普通单链接文件、Run ID 和独立 control identity 绑定，取消只提交给该控制器，不对调用方看到的数字 PID 发信号。每个 `scripts/orderflow` 自身有独立 PID namespace，不能把另一次 wrapper 的 PID 误认为同一进程。状态/取消功能不添加宿主 `/proc` 挂载。

正常 operator 请求或控制器 SIGINT → `CANCELLED_BY_OPERATOR`；collector 向控制器发送 SIGTERM → `COLLECTOR_INTERRUPTED`。二者都保留分母与原始状态，停止进程组后清理 Watchdog/cgroup、Broker socket/upstream socket、原生 state；不能报告为模型能力 FAIL、TIMEOUT 或成功。

SIGKILL、宿主断电或内核崩溃无法执行 Python `finally`；已有 bubblewrap `--die-with-parent` 与内核边界继续阻断活跃不可信进程，原始归档可能不完整。恢复必须保留不完整证据并重建独立 Run，不声称已实现同 Session resume。正式 Session 默认全新。

## Single / Multi 条件

Single 同时使用实际 `--disable multi_agent` 和 `agents.enabled=false`，公开工作区不装角色配置。Multi 使用官方原生协作能力，要求至少两个真实独立 child 的工作与回传证据。Single 的完整原始记录必须没有 child；观察到任何 child 为完整性错误。两组都使用相同业务源码、Issue、Public Tests 和冻结私有 Suite，只有协作开关、角色配置和必要指令不同。

## 兼容性与验证来源

默认配置继续满足 M1 的 bounded 测试身份与断言。新增测试通过真实 OS socket/HTTP/SSE 与实际 Participant/Adapter 进程边界，使用专用假凭据；它们是控制/传输测试，不是模型能力或原生协作运行证据。正式校准必须另外使用实际 Gateway 与官方 Runtime。

安装版本及实际原生 Probe 结果以本轮命令回执为准。官方配置字段来源：[Configuration Reference](https://learn.chatgpt.com/docs/config-file/config-reference)；JSONL 终态：[Non-interactive mode](https://learn.chatgpt.com/docs/non-interactive-mode)。没有添加未经确认的 `request_timeout_ms` 或修改上游 Codex 二进制。

## M1.1 真实校准与观测限制

本阶段交错六 Session 全部使用真正的 `None` 总时限；第三轮 Multi Agent 自然运行 1649.90 秒并完成提交及 28/28 隐藏评测，越过旧1200秒阈值的运行中快照独立保存。第一轮 Provider 故障保留为 ERROR/NOT_RUN；另五轮自然闭合，不能把新的5/6和旧有界1/3直接合并。

Code Mode 并不保证实时 JSONL 暴露全部 child 关联。实时空 child索引为PARTIAL；最终需核对每个child自身rollout、typed完成及父接收。官方首任务正文不透明时为UNAVAILABLE。运行期间看到源码改变仅能证明首次改动，不能证明当时通过隐藏测试。请求区间相互重叠，扣掉区间并集也不能反推纯推理时间。

六次运行结束后，独立审核发现final文本的单边strip和父回执substring判据，新增严格测试并修复。原Run不改写，当前parser和cohort parser版本分开记录。对应实际来源见最终报告及evidence index。
