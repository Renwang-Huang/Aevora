# OrderFlow Incident Lab — Phase 1–3 证据补全与独立复核指令

> **工作性质：Evidence-Only Audit / Project Reality Check**  
> 本轮不进入 Phase 4，不增加 Episode，不开发 GraphSwarm，不优化成绩。目标是补齐可核验的事实，并明确目前仍无法证明的事项。

## 0. 工作原则（必须遵守）

你是现有项目的证据调查员，而非本轮功能开发者。先检查 `orderflow_incident_lab` 当前源码、Git 状态、三期验收报告、`runs/` 原始产物以及 `scripts/validate_phase1.py`、`validate_phase2.py`、`validate_phase3.py`、`audit_phase3_evidence.py`。**不要先重新实现功能，不要修改业务源码、Runner、Evaluator、隐藏测试、参考补丁、正式 Run 或历史报告。** 新生成的验证结果只能写入新的 `audit_runs/` 或 `evidence_review/` 目录，保留原始失败及异常证据。必要的测试应优先使用现有 CLI 和标准库写的一次性只读校验器，在临时工作区中运行。发现错误先报告，不自行修复；任何修复建议放在报告最后。

区分证据等级：**A 原始机器记录；B 本轮新执行的动态复核；C 文档/源码静态支持；D 推测或暂无法验证。** 不得将 A/C 冒充 B，不得把 Codex 自己的任务总结作为独立验证，不得把单次成功称为成功率证明。对每条关键结论记录证据路径、实际执行命令、退出码、源文件 SHA256、运行条件及局限。

安全：不输出令牌、Cookie、认证文件、个人隐私、完整环境变量或敏感网络请求；可报告存在性、权限、脱敏指纹与隔离结果。不要让 Participant 读取 `evaluator/`、私有 Manifest、参考补丁和既有正式 Run；本轮生成的证据包亦不得挂载到 Participant。**默认不得再次执行完整联网 Codex Agent 挑战**（耗时与 Token 昂贵）。优先离线重放保存的补丁；若某项只能通过新鲜 Codex 挑战核实，标记 `REQUIRES_NEW_LIVE_RUN`，附成本和必要性，不自动执行。

## 1. 三轮开发事实清单与证据矩阵

逐一整理 Phase 1、2、3 实际完成能力，给出 `claim_id | 要证明的事实 | 状态(SUPPORTED / PARTIAL / CONTRADICTED / UNVERIFIED) | 源码位置 | 历史证据 | 本轮实验证据 | 局限`。

至少覆盖：
- **Phase 1**：最小订单/库存事务闭环；SMOKE-001 的正确/缺陷双判分；FAIL/ERROR/TIMEOUT/NOT_IMPLEMENTED；初始化、重置与不串 Run；Manual Adapter、Disabled Experience；可信宿主/候选执行边界。
- **Phase 2**：Episode Registry 真正新增了 Episode A；200 线程在一个 Worker 内实际进入业务方法；TOCTOU/Lost Update 根因；Buggy 10/10 FAIL、Reference 10/10 PASS；两种替代正确修复；宿主 SQLite Oracle/36 项约束探针；版本指纹和回归。
- **Phase 3**：原生 Codex 运行而非 Mock；全新参与者会话；三个 child 的结构化 `spawn_agent`、`wait`、`close_agent` 和父子关系；文件修改及补丁生成；提交 SHA256 与参考补丁区分；Episode A 的 14/14、15 次数据库 Oracle；隔离、TLS、Broker、异常流解析；249 项测试。

明确历史数字差异，例如 Phase 1 初版与 Phase 3 回归时命令/检查数量、Phase 2 的 107 项与 Phase 3 的 249 项分别代表什么。按**测试用例 nodeid/名称**对齐测试身份，而不是只比较测试数量。

## 2. 不依赖既有一键验收脚本的动态复核

在本机**重新执行并保存原始 stdout/stderr、退出码与时间**，至少完成：

1. 清洁临时路径中的 SMOKE-001 默认 Buggy、Reference Patch、语法错误、超时（可缩短超时），并重置后再跑关键正反例；检查不同 Run ID 和数据库初始状态。
2. 清洁临时路径中的 Episode A 默认 Buggy、Reference Patch；检查实际 JUnit 测试集合与宿主 SQLite 原始状态。无需无谓重复十遍——历史 10 轮由原始证据核验，新执行至少一轮用于交叉对照。
3. 不通过项目的 `validate_phase*.py` 聚合脚本，直接调用 `orderflow` CLI、pytest，以及**独立于候选 `audit()` 的只读 SQLite 查询**验证守恒、订单计数、预留账本、重复释放等；若某项因环境无法执行，要列明阻碍。
4. 从保存的 Phase 3 `submission.diff` 在全新 Episode A 缺陷基线重新应用，执行原 Hidden Evaluator，核对补丁 SHA256、变更文件、14 项用例、Oracle 和评测器指纹；不启动新 Codex、不替换为 Reference Patch。
5. 核对意图失败的测试确实失败：缺陷代码、损坏/空 JUnit、非法补丁、语法错误、挂起代码、数据不一致时不能得到 PASS。尽量使用已有回归用例，在隔离复制品测试，不修改正式 Oracle。

请分别报告历史重放、新鲜动态复核和无法执行的项目，勿把它们混为“独立实验全部 PASS”。

## 3. 真正的 Participant 知识边界审计

列出 Phase 3 正式 Run `339f7d73-29df-4242-8920-9e566bce8a9c` **实际传给 Codex** 的完整非敏感输入清单及 SHA256：公开 Issue、Manifest、TASK/AGENTS、角色 TOML、初始代码、公开测试、工作区 Git 状态。重点核实：

- 新会话是否可能继承维护者已有对话、Git 历史、Agent 配置、已修复源码、隐藏评测线索或持久缓存；区分“请求新会话”与“实际证实隔离”。
- 真正的 Codex 主 Agent **及其子 Agent**执行命令时的工作目录、可读挂载、HOME/凭据边界、可写位置和允许工具；不要只复述沙箱配置。
- 在真实 Participant 命令执行上下文做**非破坏性**路径探针：隐藏测试、私有 Manifest、参考补丁、原始项目源码、其他 Run、宿主用户目录；记录每项是否可读、退出状态、实际隔离类型。无需输出私有文件内容。
- 可信宿主的隐藏 pytest 和候选业务 Worker 是否真的分进程，候选是否可能篡改 Oracle/JUnit/提交快照；哪些恶意行为仍未防护。
- 模型 Broker：认证材料是否隔离，TLS 是否验证，端口的网络可达范围、请求认证/配额是否存在；只做合法且有界的本地访问检查，不进行未经授权的网络扫描。

区分 **Agent 文件隔离**、**候选业务执行隔离**、**网络隔离**、**资源限制**，用 `VERIFIED / PARTIAL / NOT_IMPLEMENTED` 分别标注，不能将 14 个路径探针说成全面安全保证。

## 4. 原生 Multi-Agent 证据链与真实性

从正式 Run 的 `codex_events.jsonl` **按原始行号和 SHA256** 重新构建时序：主线程 → 三次 spawn → child 对应任务 → wait 返回 → close → 主线程代码变更 → 最终提交 → 独立评测。

要求提供独立 JSON/CSV 时序表，含：事件源、父/子 Thread ID、可观察任务提示、完成状态、原始行号、可核对的文件变化或测试活动、证据缺失项。特别区分“官方流确证的事件”和“依据 child 返回文字推断的内部动作”；如无 child 完整内部工具调用日志，明确记为 `UNAVAILABLE`，不能虚构。

核对：正式提交相对公开 Buggy 基线确实发生改变、SHA256 与报告一致、与 Reference Patch 不同；运行归档的补丁、候选最终源码和评测快照属于**同一 Run**，最终评测前后无人工替换；人工手动动作和自动动作分别列示。

## 5. 可复现性、失败史与成本边界

整理系统实际约束：OS/内核、Python/SQLite/pytest/bubblewrap/Codex 版本、CLI 子命令、模型、依赖及构建来源、权限、网络/TLS、DNS、沙箱特性。不要输出敏感环境变量。

审计 Phase 3 之前失败 Run 的**失败类型、是否保留、如何修复和修复后是否新建独立 Run**；说明 metadata fallback 与流中断的实际数量、分类、影响及目前仍不可靠的观测字段。

保留官方 Token Usage 原样及准确统计范围，明确是否能获得每个 child 的单独用量和真实账单成本；不能推断则标注 UNAVAILABLE。现在只有**一次正式 Codex 多 Agent 成功挑战**：请明确其足以证明集成可运行，但不足以证明跨会话稳定成功率或 G0–G3 的统计收益。

## 6. 最终交付与停止条件

只生成新的 `evidence_review/` 目录，至少交付：

- `PROJECT_REALITY_REPORT.md`：Phase 1–3 状态、源证据与新动态复核、目前真实能力 vs 尚未实现能力；结论按每个命题给出。
- `CLAIM_EVIDENCE_MATRIX.csv`：逐条 claim 和证据路径、命令、退出码、SHA256、等级、限制。
- `FRESH_REPLAY_REPORT.md`：新执行命令及 stdout/stderr/JUnit/JSON 的相对路径、原样失败；特别包括 Phase 3 原补丁离线重放。
- `AGENT_PROVENANCE_TIMELINE.json`：真实父子事件和提交映射，不能臆造缺失字段。
- `ISOLATION_AND_TRUST_BOUNDARY.md`：真实探针结果、访问矩阵、Broker 边界、未防护风险。
- `UNVERIFIED_QUESTIONS.md`：尚不能证实的事项、为什么、下一次需要何种最低成本实验。
- `SHA256SUMS.txt` 和简短 `README.md`：可复查证据清单，另可打成脱敏轻量 ZIP。

不要归档完整 home、认证材料、所有旧 runs 或巨型缓存；需要引用大文件时提供相对路径+SHA256。保留历史文件不被覆盖。最后只汇报：（a）这轮**新执行**了什么；（b）支持/矛盾/未知的关键事实；（c）文件位置与证据包；（d）阻碍后续可信实验的 P0 问题。**不进入 Phase 4、不改业务逻辑、不修改已有测试和正式验收标准、不偷偷再次发起联网 Codex 正式挑战。**
