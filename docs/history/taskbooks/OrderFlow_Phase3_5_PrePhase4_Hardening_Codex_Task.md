# OrderFlow Incident Lab — Phase 3.5 开发指令

**任务名称：Pre-Phase-4 Reliability, Security & Live Runtime Validation**  
**定位：修复与验收，不进入 Phase 4；不实现 Episode D / GraphSwarm / G0–G3。**  
**依据：已有 Phase 1–3 源码与历史验收，以及 `evidence_review/20261010T053144Z-63a0ac7a-cb83-475c-a25e-7eec7417a8fe/` 的最新 Evidence-Only Audit。**

## 0. 为什么必须进行这一轮

Evidence Audit 已提供以下**不同层次**的事实：

- 三期核心功能真实存在：Phase 1 Smoke、Phase 2 Episode A、Phase 3 Codex 原生 Multi-Agent；原 Agent `submission.diff` 在独立离线重放中通过 Episode A 14/14 项测试。
- 本次直接执行完整开发者测试得到 **249 collected / 247 PASS / 2 FAIL**。两项失败是空 Python 文件新增/删除补丁在 Git 父仓库环境下可能被静默跳过，`git apply` 却返回 0。不可简单沿用历史 249/249 PASS。
- 三层文件访问边界各有 21 项探针通过，但 Outer Participant 与 Candidate Business Sandbox 可以连接自建宿主监听端口；只有指定的 Codex Native Command Sandbox 探针被 EPERM 拒绝。
- `ModelBroker` 缺少每 Run 的调用者鉴权和模型访问额度；缺少完整 CPU/内存/PID 限制；现有模型后端及认证路径硬编码程度较高。
- 原生三个 Subagent 的结构化委派与返回可核验，但 child 内部完整工具活动、原始完整 stdin、历史不可变封存和多次新 Session 稳定性仍未证实。

**本轮目标不是制造更多好看的 PASS，而是修复真实缺陷、严格界定安全保证、建立足以支持后续 Episode D 与经验责任研究的证据基础。**

## 1. 执行方式和禁止事项

1. 首先审查当前 `benchmark/participant.py`、`benchmark/runner.py`、`benchmark/participant_sandbox.py`、`benchmark/sandbox.py`、`integrations/codex_agent.py`、`integrations/model_broker.py`、`integrations/codex_trace.py`、`evaluator/`、`tests/`；阅读最新 Evidence Audit 的 `PROJECT_REALITY_REPORT.md`、`FRESH_REPLAY_REPORT.md`、`ISOLATION_AND_TRUST_BOUNDARY.md`、`UNVERIFIED_QUESTIONS.md`。
2. 为本阶段创建单独 Git 提交/分支与验证目录；记录修改前源码指纹。**不要修改历史 Run、历史 JUnit、历史验收结论或原始 66 行 Codex JSONL。**
3. 可以使用 Codex 原生 Subagent 辅助代码审查和分工，但不能用代理自己生成的结论代替独立测试。
4. 本轮允许对当前真实 Codex Multi-Agent 发起新的联网挑战和并行测试；不以 Token 成本为主要限制，但必须设置有限超时、并发上限、进程/内存/请求限额，防止无界运行。
5. 禁止开发 Episode B、C、D，禁止接入 Experience Core、FalkorDB、MCP、正式 G0–G3 对照实验或 Dashboard。
6. 禁止删除、跳过、放宽或替换失败测试以得到 PASS；无法满足门禁时如实报告 PARTIAL/BLOCKED。

## 2. P0-A：彻底修复 Submission Fidelity

### 2.1 现有问题

涉及 `benchmark/participant.py` 的 `_diff()` / `extract_submission()` 与 `benchmark/runner.py` 的 `apply_patch()`。当前临时 `candidate` 可能位于上层维护者 Git 工作树内；在该情况下，Git 可能忽略带空文件新增/删除的合法 patch，输出 `Skipped patch 'app/empty.py'.`，但仍返回 exit 0。

### 2.2 目标实现

- 隔绝父目录 Git 仓库、系统/用户 Git config、hooks、environment 与 attributes 对提交判定的非预期影响；不得只通过设置 `GIT_CEILING_DIRECTORIES` 后让原测试通过而结束。
- Patch 校验、应用和最终文件树校验必须由可信 Runner 完成；只能操作允许的 `app/**/*.py`，明确拒绝路径穿越、链接、特殊文件、非允许 rename/copy/binary 操作。
- 对每次提交保存：**Baseline Tree SHA256、Patch SHA256、Expected Tree SHA256、Applied Candidate Tree SHA256**，并逐文件确认实际新增、删除、修改内容与 `extract_submission()` 输出完全一致。
- `git apply --check` 与 `git apply` 返回 0 **不是唯一成功标准**。如果实际文件与期望树不一致，明确返回 `SUBMISSION_INTEGRITY_ERROR`，禁止启动隐藏评测。
- 补丁部分成功或中途出错不得污染可信基线或已封存的其它 Run；应在临时快照执行、全部验证通过后原子发布。
- 保留现有 Manual Submission 与自动 Codex Submission 路径；不要替换为无法复用的专用一次性工具。

### 2.3 必须新增的回归矩阵

- 空 `.py` 文件新增、删除；非空文件新增、删除、修改；多个文件的混合操作。
- 维护者 Git 根目录下、嵌套子目录下、独立非 Git 临时目录、不同 Git parent 的运行条件。
- 可疑路径、符号链接、硬链接、路径冲突、无效 hunk、patch 截断或部分失败。
- 执行后内容 SHA256 必须与提交原始 `app` 文件树一致；拒绝的提交不得生成 PASS、不得污染业务基线。
- **直接运行原先失败的两项测试**，还要完整运行 249 项原开发者测试（可以增加测试总量，但要保留原 249 项身份）。
- 使用原 Phase 3 正式 `submission.diff` 从 Episode A 干净 Buggy 基线离线重放，再得出独立 14/14 评测结果，且记录前后 SHA 指纹。不得改写原历史成绩。

## 3. P0-B：将新中转站实现为可切换的测试 Provider

### 3.1 用户授权与安全要求

用户授权以下测试模型源用于**本项目后续多 Agent 联网测试**：

- Gateway URL：`https://api.renwang-huang.top`
- Requested model ID：`gpt-5.6-terra`
- Requested reasoning effort：`max`（须验证当前 Codex 与 Gateway 真正支持）

**测试 API 密钥不写入本指令、源码、仓库、测试夹具、日志或 artifacts。** 密钥只能由用户在可信宿主上通过新的项目专用 Secret 注入，建议轮换此前曾在聊天中明文发送的测试密钥。不要要求用户将密钥再次输入聊天或 PR。禁止关闭 TLS 证书校验。

### 3.2 架构原则

现有 `ModelBroker` 使用固定 ChatGPT OAuth 后端及认证格式；**不要直接把第三方 API Key 改造成假的 ChatGPT OAuth `auth.json`**。应当引入最小、可替换的模型 Provider / Transport 配置：

- 保留现有受支持的 ChatGPT Backend 作为 Legacy/Optional Provider，既有测试不回归。
- 新增 API Gateway Provider，在可信宿主侧持有密钥并转发给相应 HTTPS 上游；Participant 与 Candidate 永远不接触上游原始 API Key。
- 模型来源配置与 Benchmark Runner/Episode Oracle 解耦；Runner 只认识 `provider_id`、`requested_model`、`effective_model`、`requested_effort`、`effective_effort` 及相关运行元数据。
- 配置应能标记每次 Run 对应的 Provider、Endpoint Hostname（无敏感 query）、模型与推理强度；不能将不同模型的结果混为同一实验基线。
- 若端点的实际 API 根路径是 `/v1`，仅在实测确认后配置，不得随意重复拼接 `/v1/v1`。

### 3.3 从低成本握手到真实多 Agent 的兼容性门禁

先在**可信宿主**执行最小、脱敏的连通性测试，再做实际 Codex 运行。须逐项核查：

1. DNS、TLS 链验证、HTTP 认证、模型发现或等价接口；只记录 HTTP 状态、响应结构和请求 ID，不记录 Authorization 或原始密钥。
2. Codex 需要的 **Responses API** 能力（不是仅验证 Chat Completions）：一次普通文本响应、SSE streaming 完整性、工具调用轮次、错误码和断流恢复。
3. 使用 `gpt-5.6-terra` 的请求是否获得明确成功结果，实际返回的模型标识为何；不得仅因为客户端配置了该名字就宣布上游一定运行了该模型。
4. 优先测试 `max` 推理强度在**实际 Codex CLI 版本**及 Gateway 中能否使用。API 文档支持并不代表本地 Codex TOML 配置一定允许。若 `max` 不能端到端成功，尝试最高可验证的 `xhigh` 并将其如实标为 `effective_effort=xhigh`、`requested_effort=max`，**不得声称已运行 max，也不能静默回退**。
5. 实测原生多 Agent：至少两个真实不同 child IDs，委派/返回完整、工具调用可用，完成后能够提交真实 patch 并交给原 Evaluator。
6. 流式请求中断、上游 401/403/429/5xx、启动失败和异常退出应有明确分类；证书错误不可通过 `verify=False` 绕过。

可参考已安装 Codex 官方 `config` 与 `exec --help`，其中 custom provider 一般使用 `base_url`、`env_key` 或可信 Broker、`wire_api="responses"`，**必须优先验证当前二进制真实支持的字段**。

### 3.4 密钥管理与数据边界

- 密钥文件在维护者专属目录，权限至少 0600；或仅可信宿主环境变量。不得放入 Agent 共享工作区、容器内的可读文件、Participant 环境、Git 及 JUnit。
- 运行日志只能存放脱敏请求元数据。若捕获原始请求正文或提示词，视为受限证据，只能放可信宿主，并排除凭据、私有答案和意外个人信息。
- 只上传**公开 Episode 任务材料**到中转模型源。隐藏 Oracle、私有 Manifest、参考补丁、密钥和维护者本地资料不得传给中转服务。
- 测试前明确第三方中转网关的代码/提示词隐私边界，不要将其与 OpenAI 官方直连混为一谈。

## 4. P0-C：Agent、Candidate 与 Broker 信任边界

按**三个独立运行层**设计、测试和报告：

A. Outer Codex Participant：允许的公开工作区 + 有限模型通道。  
B. Native Command Sandbox：Codex 实际执行命令的进一步限制。  
C. Candidate Business Sandbox：被测业务代码 + 临时 SQLite，不应获得模型 Broker 或其它宿主服务访问权限。

### 必须修复或提供技术上诚实的门禁

- **Broker per-Run 访问控制**：为每个 Run 建立独立短期身份/令牌或等价强绑定凭据；限制来源、允许路由、期望模型、请求并发数和总请求预算；在可信宿主验证未授权请求被拒绝、跨 Run Token 不可复用。不能只靠监听 127.0.0.1 视为安全。
- **网络权限**：优先让 Candidate 处于隔离网络 namespace，不应连接宿主自建监听端口或模型 Broker。Outer 至少只能访问明确授权的模型通道，不能无限制连接宿主任意监听服务。若当前 Linux user namespace 限制使网络隔离不可用，评估 rootless Podman / slirp4netns / VM / socket-based dedicated broker 等可实际运行的替代方案。不得为满足验收而禁用所有现有文件隔离。
- **资源界限**：为 Codex 总 Run、子进程组、Candidate Worker 分别设置有限的 wall-time、CPU/内存/PID/文件输出或等价限制，并有模型请求数/并发数限制。支持优雅超时与强制清理，不遗留进程。
- **安全测试范围**：只用自己创建的本地监听端口和专门的测试虚拟环境做探针，不扫描未知宿主服务、不尝试真实密钥读取、不在无授权资产上做渗透实验。
- **失败关闭**：必要的安全设施不可用时不得降级为无限制宿主执行，明确标记 `BLOCKED_SECURITY_GATE`。如果部分模型联网只能在受控协作测试下运行，可标记 CONDITIONAL 并解释边界，不能宣布完整对抗安全 PASS。

验证至少包括：上轮三层 21 项文件边界复测、本地自建端口访问矩阵、Broker 无令牌/错误令牌/跨 Run 令牌拒绝、Candidate 网络拒绝、资源超限杀进程、无泄漏和回收干净。

## 5. P1：证据溯源、保真和报告升级

- 在 Codex 开始前由可信宿主封存 Public Manifest、公开 Issue、Agent Role 配置、`AGENTS.md`、初始文件树快照与 SHA256，以及将实际传给 `codex exec` 的 **exact stdin**。不得在 Runtime 结束之后靠重建 prompt 冒充原始输入。
- 分离 Agent 原生事件与 Runner 产生的合成/映射事件，保留 event line hash、source、parent/child ID、run ID、补丁 SHA 和关联的 Evaluation Report ID。没有 child 内部日志就标注 `UNAVAILABLE`。
- 为每次 Run 生成可审计的 manifest（环境版本、Provider/model/effort、资源限制、初始树、最终树、补丁、Oracle 指纹、真实时间戳、结果及哈希）。追加写/防覆盖；如无法实现真正防篡改存储，诚实标注“本地哈希链/宿主保护，不是第三方不可变证明”。
- 更新报告结构，将 `runtime_status`、`multi_agent_status`、`submission_integrity_status`、`evaluation_status`、`isolation_status`、`integration_status` 分开判定。
- 不修改历史 Run 的内容和成绩。新增运行使用新的 UUID 和单独 `runs/` 子目录。
- 如能使用官方受支持接口取得 child 工具事件或 token 用量则保存；无法取得时不要通过解析 child 的自然语言自述构造机器事件。模型使用量应包含实际官方 usage 字段，不能以“无限额度”为理由不记录。
- 将上轮 5 次 STREAM_INTERRUPTED 的“方向无法定位”问题作为 Transport 观测性改进：记录异常阶段（upstream read/downstream write/timeout/client disconnect）和受控分类，不记录请求正文或秘密。

## 6. 动态验收：可以使用新的模型源开展真实联网测试

在修复和契约测试通过、明确安全门禁之后启动联网测试。**本轮授权真实请求，无需再次确认额度**；但不得无限循环或无界并发。

### 6.1 离线/本地门禁（必须先过）

1. 项目完整开发者 pytest：原 249 测试身份全部保持，本次新加测试也必须通过，不允许 skip 取巧。
2. 已有 Phase 1/2/3 核心回归（SMOKE 正反、Episode A Buggy/Reference/替代补丁、ERROR/TIMEOUT、隔离、重置和 JSON/JUnit）。
3. Git 提交保真矩阵：包括上轮两项真实失败，在原仓库布局直接通过，不借助只在测试启动器内设置的环境 workaround。
4. 原 Phase 3 `submission.diff` 离线重放 14/14，保存 exact SHA 与指纹一致性。
5. Trusted Broker 与安全隔离的正反探针；机密内容扫描，确保新的配置/日志/ZIP 中不存在密钥或完整 auth 文件。

### 6.2 在线模型握手与并发回归

- 首先执行一次极小的 API/Responses/SSE/tool-call 冒烟请求，确认 Gateway、认证、TLS、目标模型与推理强度。
- 然后执行 **3 次新建 Session、独立 Run ID 的 Episode A Codex Native Multi-Agent 联网挑战**；三次都使用同一个明确的 `gpt-5.6-terra` Provider 配置、实际获支持的 reasoning effort 和相同任务预算，独立初始化缺陷仓库和业务数据库。
- 每次记录真实子 Agent count、subagent ID、补丁生成、Submission Integrity、14 项 Hidden Tests、可信 SQLite Oracle、模型事件、Token usage（如有）和耗时。
- 集成是否 PASS 与任务本身是否 14/14 PASS 要分开判断。Agent 可以失败，但不允许把失败补丁替换成 Reference Fix，也不允许把一次成功写成稳定成功率结论。
- 在完整链路内测试至少一个可控的异常场景（如上游 429、断流、强制超时、无 patch 或 Invalid patch），要求被如实分类和归档；不需要额外发起真实昂贵的破坏性任务。
- 不同模型的 Phase 3 历史成绩不能直接作为新模型的同组统计对照，必须保留版本与 Provider 标签。

### 6.3 验收分类

**Phase 3.5 Overall PASS** 需要：Submission Fidelity 缺陷修复、回归全绿、Gateway 真实 Responses/Codex/原生多 Agent 兼容、可信提交+评测联通，且已承诺的安全门禁按定义通过。  
如果功能可用但有明确未补齐的强隔离边界，只能 **CONDITIONAL PASS**；如果提交内容仍可能被静默漏用、密钥泄露或危险沙箱降级，必须 **FAIL/BLOCKED**。  
新 Agent 任务的成功数量单独报告；不是 Phase 3.5 工程 PASS 的必要条件。

## 7. 交付目录和报告

新建独立 `phase3_5_validation/<UTC-id>/`，保留：

- `PHASE3_5_VALIDATION_REPORT.md`：分项 PASS/PARTIAL/FAIL、结论和实际动态运行清单。
- `SUBMISSION_FIDELITY_REPORT.md`：原失败复现、修复原理、前后测试和文件树哈希。
- `GATEWAY_COMPATIBILITY_REPORT.md`：请求/API/流式/工具调用/推理强度兼容性；**仅脱敏，不含密钥**。
- `TRUST_BOUNDARY_REPORT.md`：三层文件与网络矩阵、Broker 访问控制、资源和阻断条件。
- `LIVE_MULTIAGENT_RUNS.md`：3 次新 Session 的独立 Run ID、Agent evidence、补丁哈希、14 项评测结果与失败/成功分析。
- `EVIDENCE_MANIFEST.json` 与 `SHA256SUMS.txt`：全部新增材料的哈希及来源关联。
- 变更清单、实际 `pytest`/CLI 退出码、运行日志引用及新写的单元/集成测试。

文档说明怎样在用户可信宿主上**安全提供新的 Gateway Secret**，但不能打印它、存储它或将明文拼入命令行参数。最终只提供本地 Secret 配置说明和执行命令模板。

## 8. 停止条件

完成后只汇报 Phase 3.5：什么问题修复了、哪些证据是新现场执行的、哪些能力仍受限、哪些历史数据未变，以及是否具备进入 Phase 4 的真实准入条件。

**禁止自动实现 Episode D、经验治理服务、FalkorDB/MCP、G0–G3 或 Dashboard。**

如果 Gateway 无法真正支持 Codex 原生工具调用或 `max` 推理强度，必须原样报告，不得伪造模型兼容、隐式更换模型、关闭 TLS 或撤销沙箱换取假 PASS。
