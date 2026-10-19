# Episode D-v02 — 设计审查与质量 Gate

**审查版本：0.3.0 · 状态：STATIC ENGINEERING AND RESEARCH DESIGN REVIEW PASS；六轮校准已补全。**

对象：[D-v02 设计 0.3.0](EPISODE_D_V02_DESIGN.md)。本文件由设计子 Agent `/root/m11_v02` 编写；作者自审不计独立审查，也不是新Episode实现验收。0.2.0已得到 `/root` 工程复核PASS和 `/root/m11_runtime` 独立研究审查PASS，具体意见/原始摘要在§7；六个新R3终态现已追加。当前为 **工程/研究静态设计PASS，v02 IMPLEMENTATION NOT_STARTED，工程正确性/难度UNVERIFIED**。主Agent总体M1.1/R4 Gate仍须独立归档，不能用本文件冒充动态业务验收。

## 1. 审查输入与实际动作

- 只读研究根 AGENTS、M1.1 任务、Roadmap、Task System/Relations/Admission、D-v01 public issue/factory、当前 28 项隐藏测试语义和宿主 DB Oracle。
- 直接读取 M1 三个真实 Agent patch 和 Pilot 报告：原正式 TIMEOUT / PASS / TIMEOUT，自动闭环 1/3；两个另建 postmortem 原样代码 PASS 不改变它。
- 浏览 SQLite、etcd 官方文档/官方 GitHub 及现成 Knossos/Porcupine 说明；依据与链接在设计 §16。
- 读取实际 [R0 Gate](../m1_1_validation/20261010T154658Z-4e5039eb-6ac2-49c7-8ece-824765e22f5f/R0_GATE.json)：664 测试、82,740 历史文件与 159 源/文档基线核查 PASS；它是修改前基线，不是 R4 或 Episode PASS。
- 本子任务只新增两份设计文档；没有改 v01、业务、私有真值、历史成绩、Registry、参考 patch 或任何密钥。

这些是静态分析和实际外部资料阅读；没有执行 v02 业务验证、Agent 挑战或反例 Suite。

## 2. 候选审查

| 项目 | 候选 L：失效租约迟到写入 | 候选 S：WAL 快照/DB 代次 |
|---|---|---|
| 与 v01 的实质区别 | 即使数值 SQL 完全事务化，发布授权/终态仍过时；处理权跨阶段和接管 | 正确业务提交可能在错误持久权威/快照中丢失；跨文件/代次恢复 |
| 公开可调查条件 | 请求 API、持久处理记录、统一时间、Worker 拓扑、claim/complete 分阶段 | WAL/恢复点、备份流程、文件身份、运行连接与 Worker 代次 |
| 不强制单一解 | 当前授权条件验证、乐观更新、短范围跨进程协调等 | 一致性备份、排空/切换、恢复点和 ACK 校验协议 |
| 复用与范围 | 可复用订单/库存、Supervisor、fidelity 和 raw DB 思路；不开发支付/事件 | 文件/恢复安全新增边界较大，与现有原生 journal 恢复职责易混淆 |
| 初始结论 | **推荐，需冻结公开新协议后实施** | **保留，不与 L 合并为当前任务** |

独立审查必须尝试反驳推荐 L：若最终实现仍只需要原 v01 SQL 改动，或无法在保留基本事务/约束时形成租约因果错误，则不应接纳为新 variant。候选 S 不能以“数据库旧快照缺少未来写入”为错误，必须先定义恢复点/ACK 目标。

## 3. 设计工程审查（不是动态 Engineering Gate）

| ID | 审查问题 | 当前设计处理 | 静态状态 / 未来必须证明 |
|---|---|---|---|
| D1 | 故障是否来自实际工程路径 | 旧 handle 在 takeover/cancel 后 complete/renew/cleanup；保留原事务及约束 | 设计可检验；真实 Buggy 未实现，UNVERIFIED |
| D2 | 是否与 v01 不同 | 当前授权/终态和 receipt 约束，而非库存旧值 | 候选有材料差异；未来 mutation 因果验证 |
| D3 | API 是否清楚、公平 | 两阶段公开请求，claim 不扣库存；旧订单 API 兼容；容量不足保留PENDING意图并释放处理权 | 初审条件接受；实际公开包/API/receipt版本待实施前冻结 |
| D4 | 调度是否强迫死锁 | claim 返回之后暂停/推进时间，SQL/短锁内不要求全员 barrier | 静态满足；未来真实锁/无 hook 多解验证 |
| D5 | Clock 是否可被操控/是否误判截止 | 独立只读权威接口；已选操作线性化时间、非COMMIT墙钟；默认只在公开操作之间advance | 已按独立意见修订；新挂载/可信query记录/动态公平性未执行 |
| D6 | Oracle 是否反映业务真值 | raw DB/ACK/Clock/顺序、终态/账本/receipt；不读 audit、不强制整数 token | 静态满足；物理审计 schema 和合法结果模型待冻结 |
| D7 | 是否误拒历史合法状态 | receipt 与之后正常取消并存；已选 COMPLETE_DISCOVERED_CANCELLED 等公开类型；并发存在合法顺序即可 | 已按独立意见修订；模型和 staged 正控待实际验证 |
| D8 | 恢复观察是否偏袒 Reference | 实际 claim/publish/response/cleanup 窗口，缺失单列 ERROR | 静态满足；通用 observer 支持与正反控待实现 |
| D9 | 是否接受真正不同机制 | transaction validation、CAS、短范围稳定 flock | 拟定，不计为已有三份合法 PASS |
| D10 | 错误策略是否实际区别 | stock-only/local-lock/旧 cleanup/receipt split 等对应具体违反 | 拟定，不能把启动 ERROR 算检出 |
| D11 | 旧系统/历史保护 | 独立 v02 package 与指纹；不改 v01 真值/历史 | 本轮边界遵守；未来有效回归全部要求保留 |

### 必须解决的实施前问题

1. **请求容量不足语义。** 设计已选保留 PENDING 意图、释放当前处理权并公开可重试；必须在实现前连同公开包冻结。不能与旧 create_order 的“失败无新订单”混为一条规则。
2. **时间线性化。** 设计 §4.3 已选合法操作历史语义：持写事务验证当前行后，截止前的权威查询可以为逻辑点；之后COMMIT越截止不能单独判错。默认不在排他事务内暂停正确complete并强迫takeover先ACK；动态实现仍需证明可信query/调用区间/ACK与当前行一致。
3. **审计 schema。** 公开最低持久记录与 Oracle 基表读取范围要冻结；允许扩展，不允许候选提供虚构审计答案。
4. **现有订单归属。** claim/补偿不能删除其他意图或合法 reserve=False 订单；取消一个请求不禁止独立合法请求以后使用同一 order_id，Oracle 必须基于宿主调用/快照/回执归属而不能只看最终一行。实施时验证同 payload 发现既有/取消订单、冲突 payload 及不同请求竞争的公开语义。
5. **有界 liveness。** 暂停 Worker 不无限阻塞接管/无关业务；限额依据实际硬件和阶段工作，不能任意短总时限制造难度。
6. **合法恢复中间态。** 未收到 ACK 时允许哪些 pending/completed 行、何时 cleanup 可执行，需独立样本验证，不能由作者 reference 内部实现决定；结果类型已选定，发现取消订单不得记为reservationSUCCESS。

这些不是未来“不完成也可 PASS”的豁免。R4 可以通过设计评审，实际 Episode Engineering Gate 只有在另轮正式实现、这些决策冻结及动态证据齐全时才可通过。

## 4. 研究质量审查

| ID | 问题 | 当前处理与限制 |
|---|---|---|
| Q1 | Issue 是否能调查且不泄露修复 | 公开部署、API/状态机、Clock 和普通日志；不写 lease 授权检查遗漏/fencing/位置；实际症状日志未来需采集 |
| Q2 | VERIFY 是否人为制造 | 未知条件必须可从合理工程资料查询；不给已完成调查者强加不知道；没有隐藏必要拓扑 |
| Q3 | Gold 是否独立 | 策略级条件、来源、审查和证据先冻结；不由 Participant 成败回填，不把 SQL 原子性原则全盘标为错误 |
| Q4 | 经验是否有真实来源 | natural 是确切 Agent patch/Run；维护者锁对照是 seed；所有 v02 正向/反例仍 UNVERIFIED |
| Q5 | 能否区分 Runtime 和能力 | 旧 1/3 自动闭环与三个代码 PASS 分开；R3 six-run 新样本仍待终态，不拿墙钟当任务难度 |
| Q6 | Ceiling/floor 是否诚实 | one-condition ceiling、新 API 歧义 floor、多故障混合等显式列出；需实际独立盲测再确定难度 |
| Q7 | 未实现治理是否伪装运行 | 只规定公平历史曝光、同源条件、指标和来源；Experience DISABLED，无 G0–G3/算法/收益 |
| Q8 | 独立审查是否有据 | 当前为作者自审；必须取得不同审查者的工程/研究异议或同意及文件/摘要引用 |

**当前研究判断：独立静态设计审查PASS；v02任务判别力、难度、经验影响和统计效度UNVERIFIED。** 六轮新v01校准补全了设计依据，不能由静态审查宣布“研究级Episode已完成”。

## 5. 旧三份 Patch 的天花板分析

实际源码中三份修复都围绕 `InventoryService.reserve()` 的旧快照支路和 `create_order()` 的 snapshot 传递；保持/恢复同一业务事务与条件库存 UPDATE。第二份保留 snapshot 作为兼容参数但不以它决定写入。代码形状不同不能自动称为三个不同工程原理。

M1 中正常完成者用了 1139.12 秒，两个 wall1200 秒被中断；发生真实 Gateway/SSE/429/协作收尾影响，并且一次 offline postmortem 与另一个 live Trial 重叠。这个证据不支持把 20 分钟描述为纯解题困难，也不支持断言某类网络/协作开销占比。原正式1/3与另建两个28PASS都保留。

推荐 L 的目标是增加**必须验证的新业务事实**，而不是为了让成功率下降隐藏事实、增加代码噪声或缩短时限。如果今后 Single/Multi 都能快速识别并正确修复 L，应如实确认该能力层下仍有 ceiling，保持 v02 成绩，另立更有意义的机制变体。

## 6. 已结束的R3校准与设计影响

当前动态来源为 [六轮CALIBRATION_ANALYSIS](../m1_1_validation/20261010T154658Z-4e5039eb-6ac2-49c7-8ece-824765e22f5f/calibration_analysis/CALIBRATION_ANALYSIS.json)，实际SHA `80d9dfc85344ff7672ca292cead29ad841c941b480fea972d993768a70950e73`；[原生时间线](../m1_1_validation/20261010T154658Z-4e5039eb-6ac2-49c7-8ece-824765e22f5f/calibration_analysis/MULTI_AGENT_TIMELINE.json) 包含实际parent/child/own-turn/结果引用。全量Run ID、request/Token及耗时表见设计§15，不重复复制原始日志。

| 项目 | 当前实际结果与限制 |
|---|---|
| 三个新S | 顺序1/4/5，ERROR/NOT_RUN、PASS28、PASS28；三者官方配置/日志无Child核验PASS，0children |
| 三个新M | 顺序2/3/6，全部正式PASS28；spawn各3，原解析器verified3/3/2；M6第三Child原始记录证明正常完成，保留旧计数并单独纠错，不改旧成绩 |
| 全分母 | S2/3、M3/3；首轮PROVIDER_FAILURE保留，未补考替换；不是六个patch全部PASS，只有五轮实际评价 |
| 真实长完成 | M3 Agent1649.90秒跨旧1200，S5 1011.25秒跨旧900；completion-aware自然结束，无旧成绩回填 |
| 核心条件 | 公共业务输入字节核验PASS；同terra/max、28项suite1.2/evaluator3.1/fixture1.0；源及私有套件冻结、五轮提交保真/恢复COMPLETE、六轮清理/封存PASS |
| 运行差异 | S/M原生协作配置/提示不同；无总wall/request预算、资源/隔离/取消继续保留；TLS恢复后collector续采是新Session，不是native resume |
| 先导信号 | 五份实际新patch均修inventory/service旧snapshot及事务内条件UPDATE；完成者5/5，两个无childS也通过，支持v01可能ceiling的信号 |
| 不支持的结论 | n3/组没有一般S/M优势、纯解题时长、首次改码即隐藏准备完成、模型权重、货币账单或治理收益证明；v02运行/难度仍UNVERIFIED |

工程与服务/协作开销分开：M本样本请求和reported Tokens更多，不能相加重叠request duration当墙钟或用剩余时间当纯推理。首轮provider错误而不是业务FAIL；五个已评价都PASS也不能忽略首轮。推荐L仍应通过新因果/多解/真实错控和未来盲测检验，不因这组结果扩大协议或隐藏事实。

M6的investigator原始Child行113/114/117包含完全相同的4071字符final（含尾部两个换行），Parent行154有回传引用；独立Runtime审查确认 `_text.strip()` 单边归一化导致旧verified2假阴性。作者只读核验三处文本完全一致和两个原始行SHA，退出0；原始链接/逐行SHA见设计§15.1。[独立来源记录](../m1_1_validation/20261010T154658Z-4e5039eb-6ac2-49c7-8ece-824765e22f5f/independent_review/runtime_final/BEFORE_FIX.json) 与 [最小修复及82项回归](../m1_1_validation/20261010T154658Z-4e5039eb-6ac2-49c7-8ece-824765e22f5f/independent_review/runtime_final/SOURCE_FIX.json) 单独归档。**原解析器verified2；独立raw证明第三正常完成；不将第三称作未完成，也不升级旧Run summary/grade。** 它支持原始证据与解析结论分层核验的必要性，不是额外的Participant补考。

[R1](../m1_1_validation/20261010T154658Z-4e5039eb-6ac2-49c7-8ece-824765e22f5f/R1_GATE.json)、[R2最终](../m1_1_validation/20261010T154658Z-4e5039eb-6ac2-49c7-8ece-824765e22f5f/R2_GATE_FINAL.json) 和 [R3 Live Admission](../m1_1_validation/20261010T154658Z-4e5039eb-6ac2-49c7-8ece-824765e22f5f/LIVE_GATE.json) 分别提供真实先决Gate依据；它们都不是v02工程PASS。研究审查原件保留在six-run尚未结束的当时时点，不把其中UNVERIFIED_AT_REVIEW_TIME改为旧时已完成。

## 7. 独立评审记录

| Review | 审查者 / 时间 / 来源 | 结果 | 状态 |
|---|---|---|---|
| 作者静态自审 | `/root/m11_v02`，2026-10-10 UTC / 香港2026-10-11，设计0.1.0初稿 | 推荐 L，列出六项实施前问题；v02未实现 | 已完成自审，不能计独立审查 |
| 独立工程初审 | `/root` → `/root/m11_v02` 原生维护者协作消息，2026-10-10 UTC / 香港2026-10-11 | REVISIONS_REQUIRED：lease Clock线性化歧义、事务中强迫接管风险、取消订单发现receipt含义须冻结 | 意见及修订历史保留；当时未通过 |
| 独立工程复核 | `/root`，2026-10-10T16:36:42.592908Z，[REVIEW.json](../m1_1_validation/20261010T154658Z-4e5039eb-6ac2-49c7-8ece-824765e22f5f/independent_review/root_v02_engineering/REVIEW.json)，SHA `e4764d9075d468247d34cb332a7245430b0e8d9a907c337f091cd0cacc1ac5e9` | 0.2.0 STATIC ENGINEERING DESIGN PASS；当时R3未结束 | 实际独立静态审查，v02动态UNVERIFIED |
| 独立研究审查 | `/root/m11_runtime`，2026-10-10T16:34:57.436317Z，[REVIEW.json](../m1_1_validation/20261010T154658Z-4e5039eb-6ac2-49c7-8ece-824765e22f5f/independent_review/runtime_agent_v02_research/REVIEW.json)，SHA `73347af32b52990325d5e7aba34d9dd44d53a52cb135250a2bde03c11a4e3731` | 0.2.0 STATIC RESEARCH DESIGN PASS；RV01–09与P01–07未来条件、six-run当时UNVERIFIED原件保留 | 与作者独立，0模型调用/0v02动态重放 |
| 六轮测量补全 | 作者只读实际结果，analysis recorded2026-10-10T18:17:31.485629Z | 0.3.0仅补终态、Gate/审查引用与ceiling限制；normative语义不变 | 静态设计所需证据齐备；不替代主Agent总体Gate |

独立审查可以由不同原生维护者子 Agent 或主 Agent 进行，必须保存具体问题、修订/保留理由和明确来源；不能把作者自己的再次阅读更名为“独立”。维护者评审 Agent 不算 Participant 协作证据。

### 0.2.0 修订处理与已完成复核

- **接受 Clock意见。** 0.1.0 将 deadline 与“发布”混写，可能误拒持事务内合法检查、提交稍晚的方案。0.2.0 §4.3 固定合法线性化规则、默认操作之间推进时间、重叠接受合法任一历史；Oracle不读候选自报时间、不凭COMMIT墙钟跨截止判FAIL。存在可信query时用原始来源，缺失内部点不猜测。
- **接受 receipt意见。** 0.2.0 §4.4 固定最小语义枚举；COMPLETE_DISCOVERED_CANCELLED 表示处理发现已取消订单，无重新预留，不能算COMPLETE_RESERVED。请求终态与业务预留结果分开，容量不足仍PENDING可重试。
- **接受冻结意见。** 容量拒绝、lease线性化、结果类型是当前设计已选规则，未来只冻结公开包/实现版本和数据字段；不延后到隐藏测试决定。
- 没有实现任何v02代码、测试、reference，也没有修改v01或历史。上述修订是静态规格修正，不能称动态公平性验证已经通过。

### 0.3.0 测量追加与未来要求

0.2.0精确文档及摘要保存在 [v02_design_0.2.0](../m1_1_validation/20261010T154658Z-4e5039eb-6ac2-49c7-8ece-824765e22f5f/v02_design_0.2.0/INPUTS_SHA256.json)；0.3.0仅更新测量/审查状态及出处，设计§2–12/14字节保持0.2.0原样。独立研究审查P01–07继续作为未来实施/比较要求：公开顺序模型及未知ACK、真实授权因果错控、多合法机制/恢复正控、同源曝光和计算预算、预注册全分母及区间去重、six-run实测补全、Clock权限及已固定库风险。P06的本轮测量补全已落实；其余不冒充已运行。

## 8. 版本/威胁模型与最后边界

官方 WAL 页面指出一个特殊 reset/checkpoint 竞争缺陷的影响版本范围包括本机 SQLite3.46.1。**是否在 OrderFlow 中发生，UNVERIFIED**。本设计不修改旧依赖/成绩；未来实施前固定已修复库或限定并核实库级干扰。SIGKILL/进程重启不能证明真实掉电 durability。引用来源为 [SQLite 官方 WAL](https://www.sqlite.org/wal.html)。

Clock 新权限边界尚未实测；本机 namespace/CPU采样/SQLite Observer unsupported路径与本地 SHA 非第三方不可变证明等已知安全限制也没有通过设计消除。原始证据与 Audit-Lite 的省略范围应明确，不能把仅有摘要的原件称为外部独立验证。

**当前结论：工程/研究静态设计审查PASS，六轮D-v01校准终态及设计影响已补全；v02 IMPLEMENTATION NOT_STARTED，工程结果/难度/策略判别力UNVERIFIED。** 主AgentR4/M1.1最终Gate另归档；静态设计PASS不能替代它或v02动态验收。

完成 M1.1 后停止；不实现 D-v02、B/C、GraphSwarm 或正式对照实验。
