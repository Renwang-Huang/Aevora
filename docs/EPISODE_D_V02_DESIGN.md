# Episode D-v02 — 处理租约失效后的迟到写入

**规格版本：0.3.0 · 状态：PLANNED / DESIGN-ONLY · 工程与研究静态设计审查：PASS · 可运行性及难度：UNVERIFIED。**

这是维护者设计材料，含根因、对照和私有参考条件，**不得复制到 Participant 工作区或模型输入**。本轮 M1.1 只设计、审查 D-v02；没有注册新 Variant，也没有实现业务代码、隐藏测试或参考补丁。D-v01 的业务、28 项必要隐藏测试、历史结果及 Oracle 保持其冻结真值。

设计在 [R0 Gate PASS](../m1_1_validation/20261010T154658Z-4e5039eb-6ac2-49c7-8ece-824765e22f5f/R0_GATE.json) 之后编写，遵循 [M1.1 任务](../OrderFlow_M1_1_Runtime_Calibration_and_Evidence_Engineering_Codex_Task.md)、[Task System](TASK_SYSTEM_DESIGN.md)、[Task Relations](TASK_RELATIONS.md) 和 [双准入门禁](TASK_ADMISSION_GATES.md)。设计审查及未闭合事项见 [EPISODE_D_V02_DESIGN_REVIEW.md](EPISODE_D_V02_DESIGN_REVIEW.md)。任何未来实现都需要下一轮明确授权。

## 1. 为什么需要新的因果机制

D-v01 的真实故障是事务外库存快照和绝对值回写，在独立 Worker 间造成 Lost Update。M1 三份实际 Agent 补丁均改回事务内条件相对库存更新；一个正式自动评测及两个另建 Run 的原样残留补丁评测均通过 28 项当前 Oracle。三次原正式结果仍为 **TIMEOUT / PASS / TIMEOUT，自动闭环 1/3**，不能改称三次完成。[M1 Pilot](../M1_PILOT_REPORT.md)

这些样本支持代码问题可解，并提示可能存在任务天花板；它们不能证明稳定成功率、Multi-Agent 收益或经验继承。D-v02 应要求调查新的持久授权与恢复事实。增加 Worker 数、SKU 数、SQL 行数或随机种子，只属于稳健性参数，不能构成新事故。

SQLite 对不同连接的写事务提供隔离和原子提交；应用层先前获得的处理权限是否仍有效，需要业务协议验证。因此“每次 UPDATE 都在正确事务内”可以保持数值守恒，同时仍把已经撤销的请求重新发布为成功。这个区别是推荐方案的因果假设，尚待未来实现与反例验证。[SQLite isolation](https://www.sqlite.org/isolation.html)

## 2. 两个候选与取舍

| 候选 | 新机制与真实症状 | 合法修复方向 | 风险与选择 |
|---|---|---|---|
| **L：请求处理租约失效，旧 Worker 迟到发布** | 旧 Worker 在处理权过期、接管或撤销后，使用先前读取的授权/请求状态提交订单、账本和成功回执；取消请求之后出现新订单，重启后回执与终态不一致 | 持久授权及终态在发布时重新验证；条件状态转换；短作用域跨进程锁加重新验证；等价可证明协议 | **推荐**。共享 SQLite 和现有订单世界可复用，但必须先定义公开两阶段请求契约；不能仅加 lease 注释或人为延迟 |
| **S：WAL 在线快照与数据库代次切换** | 维护代码复制 `.db` 时漏掉已提交 WAL，或切换文件后旧 Worker 继续写上一代 DB；确认订单在恢复后消失，各 Worker 查询不同状态 | SQLite 原生一致性备份；显式恢复/切换协议、Worker 排空与代次确认；保留 ACK 记录并核对恢复点 | 保留候选。成熟恢复方案存在，但涉及文件权限、sidecar、运行连接和持久权威切换，实施/误归因风险更高；当前不推荐合并到 L |

候选 S 的事故来自快照和权威切换，候选 L 来自过期操作授权；它们不是同一竞态换参数。SQLite 官方明确 WAL 是持久状态的一部分；Online Backup 和 `sqlite3_rsync` 是可复用方案。备份一致并不自动等于“包含备份完成以后全部确认请求”，因此未来 S 必须公开恢复点目标，不能把合法旧快照当错误。[WAL](https://www.sqlite.org/wal.html)、[Online Backup](https://www.sqlite.org/backup.html)、[sqlite3_rsync](https://www.sqlite.org/rsync.html)

## 3. 推荐方案 Task Card

| 维度 | 拟冻结内容 |
|---|---|
| Family / Scenario / Variant | D / shared-worker coordination / `v02`（仅拟定，未注册） |
| Fault Mechanism | 已失效处理权仍被缓存并使用；迟到 complete 或 cleanup 未验证当前请求终态/当前处理代次，发生终态复活、丢失回执或清除新所有者 |
| Execution Context | 单机、2/4 独立 OS Worker、同一文件 SQLite、正常 DELETE/WAL、独立连接；共享持久请求记录；进程暂停、SIGKILL、重启、同请求重试 |
| Evidence Condition | 公开源码、API/状态机、处理租约配置、部署拓扑、公开请求与处理记录、统一 Clock 查询接口、普通复现工具；隐藏具体评分时序、种子、断言和参考答案 |
| Experience Relation | A/D-v01 的容量原子性与账本同提交原则可部分复用；完整旧补丁不覆盖新授权条件；本地锁的适用范围不扩展到跨进程；租约能否安全使用取决于实际发布时的协议 |
| Participant Goal | 修复真实迟到处理与恢复问题；保留合法并发、现有订单 API、新请求协议、业务容量和持久审计 |
| Engineering Truth | 独立原始 DB + 宿主调用/ACK/Clock/进程事实；候选自报 audit、Agent 文本或经验标签都不能决定 PASS |
| Decision Reference | 私有策略级 APPLY / VERIFY / ABSTAIN 条件；独立版本、来源和审查；本轮不产生实际决策分数 |
| Reset | 停止所有 Worker/Clock 写入者，保存证据，独立初始化 DB/Clock/请求记录；新 Run ID，不复用旧 Oracle/JUnit |
| Implementation State | PLANNED；Task/Fixture/Suite/Oracle 的运行版本和真实测试结果尚不存在 |

**业务边界：** 不实现支付、完整事件投递、远端分布式数据库、B/C 或治理算法。新增的是订单请求的持久处理协议；处理租约不等于库存预留自动过期，也不增加支付确认/库存消费语义。

## 4. 公开业务契约：先消除不公平和歧义

### 4.1 保留与新增 API

现有 `create_order / reserve_inventory / cancel_order / release_inventory / get_order / get_inventory` 和业务错误保持兼容。未来 v02 单独提供一组公开两阶段请求 API，名称暂定：

| 操作 | 公开语义 |
|---|---|
| `claim_request(request_id, order_id, sku, quantity, ttl)` | 建立/发现同一请求；PENDING 请求没有有效处理者时授予不透明 handle；claim 本身不扣库存、不写业务 reserve 账本 |
| `renew_request(handle, ttl)` | 当前有效 handle 可延长本次处理权；旧、已撤销或过期 handle 不能覆盖新处理者；不能无限阻止取消 |
| `complete_request(handle)` | 在当前授权下完成同一请求的订单预留并形成持久成功回执；重复成功没有额外库存/账本副作用 |
| `cancel_request(request_id)` | 若请求尚未完成，原子成为 CANCELLED，撤销处理权；若完成先发生，返回 ALREADY_COMPLETED，不能谎称取消成功 |
| `get_request(request_id)` | 返回公开状态、payload identity、当前处理记录和已有结果；不得凭内存重建未持久的成功 |

接口名字可在未来实现前评审后冻结；**一旦成为公开任务契约，Participant 不可改签名以规避问题**。新接口是 material variant 的公开行为，不是隐藏测试要求。旧 `cancel_order()` 取消一个已经存在的订单；`cancel_request()` 取消尚未发布的请求，二者不混淆。已完成请求的历史成功回执可以在之后订单取消后继续存在；Oracle 不能拿当前可变订单状态否定合法历史回执。

### 4.2 终态、身份与失败语义

- `request_id` 唯一标识业务意图，固定映射到 `order_id / sku / quantity`；相同 payload 的 retry 发现同一意图，不同 payload 为显式 RequestConflict。不能在 retry 时随机换业务身份。
- 请求状态为 PENDING、COMPLETED 或 CANCELLED。后两者为终态；COMPLETED 回执持久不可被清理覆盖。请求 CANCELLED 成功应先于任何被拒绝的迟到发布；完成先赢时取消请求应明确返回 ALREADY_COMPLETED。
- 有效处理权同时依赖请求未终结、handle 对应当前处理代次，以及**操作合法线性化点**的统一权威时间未达到该代次 deadline。不能只比较 Worker PID；PID/名字可能重用。不要求 handle 是某种整数序列，也不要求物理 COMMIT 必须早于 deadline。
- 过期旧 handle 可以被拒绝，或只读发现已有终态/成功结果；**不能产生新业务写入、撤销新处理者或修改终态**。不得强制所有合法实现返回一种特定错误字符串。
- 相同当前 handle 的续期不会被一个缓存的旧 deadline 错误过期；旧代次在接管后续期不成功。截止边界明确为合法线性化点 `now >= deadline` 已过期；完整时间规则已选定于 §4.3，不能在隐藏测试中临时改为 COMMIT 墙钟规则。
- 容量不足为明确业务结果：本设计选择 **PENDING 意图保留、当前处理权释放、公开可重试拒绝**。不得留下未确认的新订单、库存变更或 reserve 账本；之后新 claim 可在容量可用时完成。不能把一次容量拒绝伪装成成功，也不能悄悄把请求永久 tombstone。
- cancel_request 取消一个尚未完成的请求，不能删除不属于该请求的预先合法 `reserve=False` 订单。若目标订单已存在，相同身份可被发现、冲突身份被拒绝；恢复与补偿必须基于真实所属关系。
- 既有库存守恒、ledger 对应订单、cancel/release 幂等和非法状态错误仍成立。任何未知 ACK 状态要先审计，再通过相同请求重试发现结果。
- 取消请求只终结该意图，不能禁止独立合法调用后来使用同一 `order_id`。两个不同请求指向同一相同 payload 的订单时，发现既有订单不得重复预留；冲突 payload 仍拒绝。Oracle 必须结合宿主调用顺序、前后快照和请求回执归属判断迟到副作用，不能仅凭“某 CANCELLED 请求指向的 order_id 现有一行”就认定复活。
- 既有取消订单被同身份重试发现时沿用旧 API 语义，不能重新预留；新请求 receipt 使用 §4.4 的 `COMPLETE_DISCOVERED_CANCELLED`，不能报告 `COMPLETE_RESERVED`。cancel_request 与 cancel_order 的身份及作用范围在公开说明中分别描述。

这个容量拒绝规则和旧 `create_order()` 的“失败无新订单”可以同时成立：请求记录是新协议的真实意图记录，不是假订单。实施前应确认该已选规则、处理权释放与请求/订单归属已在公开 Issue/API 文档中完整冻结；任何改变需要设计版本更新，不能到隐藏测试时才追加。

### 4.3 已选定的租约线性化规则

公开协议以**存在合法线性化历史**为正确性条件；每个完成调用的线性化点应在该调用的宿主 start/end 区间内，尊重已经完成的调用与后续开始调用的顺序。过期比较在这个逻辑点成立，物理 SQL COMMIT/响应发出可以更晚。

一个明确合法的 Reference 路径是：取得 SQLite 写事务，读取并验证当前请求终态/当前处理代次，在持有写事务期间查询权威 Clock，然后完成原子的条件库存、订单、账本与 receipt 写入。若该时间查询早于 deadline，且 cancel/takeover 尚未先赢，查询点可以作为 complete 的线性化点；即使调度或 I/O 使 COMMIT 越过 deadline，也**不能据此判业务 FAIL**。写事务内的当前行保证别的 writer 不能在其验证与提交之间先提交撤销/接管；未知 COMMIT 失败不能发布成功 ACK，应按持久状态和 retry 处理。

这是合法实例，不是要求修复必须调用某种内部 helper。条件原子更新、短范围稳定共享锁或其他方案，只要能证明当前持久授权/终态与所选时间点一致，也可通过。仅在准备阶段缓存授权或检查时间、之后无条件发布不满足它；也不要求 token 使用递增整数，或要求权威时间与真实 COMMIT 精确同时。

**默认可重复测试只在公开业务操作之间推进 Clock**：例如 claim 已返回，推进到过期，B 接管/取消已 ACK，再启动 A 的迟到 complete。这足以暴露旧授权错误。不得暂停一个已持排他写事务、合法检查时间的正确 complete，再强迫新 owner 先 ACK；该安排会阻塞正确实现并偏袒特定代码路径。必要的 Clock/cancel/complete 重叠测试应接受任一满足公开顺序模型的赢家。

Oracle 以宿主 start/end、ACK、真实权威 Clock 查询/推进日志和 raw 持久快照建立约束；Candidate 自报“我在截止前检查过”不可信。若初期无法取得可信内部点，允许调用区间内存在的合法顺序，不猜测精确 COMMIT 时刻；必要证据缺失应明确 UNVERIFIED/ERROR，不能用 commit wall 跨截止作为唯一 FAIL 理由。

### 4.4 已选定的公开结果类型

请求处理终态与订单预留状态是不同维度。下面是公开协议最小的语义枚举，实施前公开包需使用这些含义并版本化；不得在隐藏测试中重释：

| outcome | 请求状态与业务效果 |
|---|---|
| `COMPLETE_RESERVED` | 请求 COMPLETED；在合法线性化时预留存在或被幂等发现，payload 相符；不意味着这次调用新扣了一次库存 |
| `COMPLETE_DISCOVERED_CANCELLED` | 请求 COMPLETED；同身份订单已取消，处理发现该真实结果；不得重新 reserve，也不能称为 reservation success |
| `REQUEST_CANCELLED` | 请求 CANCELLED；该意图不能由旧 handle 新发布；不对独立其他意图的合法订单作禁止 |
| `INSUFFICIENT_INVENTORY_RETRYABLE` | 请求仍 PENDING；本次处理权释放，没有新业务订单/库存/ledger 副作用；之后可重新 claim |
| `STALE_HANDLE` | 旧/失效 handle 的明确拒绝，无新副作用；若只读发现终态，也可返回该终态原 receipt，不能改写它 |
| `ALREADY_COMPLETED` | cancel_request 发现完成先赢；返回原完成 receipt，不能称取消成功或释放库存 |

成功 receipt 保留 outcome 时的 payload/结果身份；正常后续 cancel_order 不回写或否定以前的 `COMPLETE_RESERVED`。同一请求 retry 返回原持久结果，不把已取消订单重新预留。非法输入、冲突、传输/Clock/SQLite 错误仍按各自公开错误契约分类，不能统一转换为上述业务 outcome。

## 5. 真实事故与可证伪的复现

### 5.1 核心故障窗口

1. Worker A 调用 claim 并收到 handle A；请求 PENDING，库存和业务账本没有变化。
2. A 在**返回的公开两阶段操作之间**被暂停，或其正常准备工作延迟；此处不要求它持有 SQLite 写事务或文件锁。
3. 权威 Clock 达到 deadline；Worker B 实际接管并取得 handle B，或 `cancel_request()` 已确认 CANCELLED。
4. A 恢复后调用 complete / renew / cleanup，真实缺陷代码根据旧授权或旧请求状态提交业务副作用/旧回执/删除 current claim。
5. 宿主原始 DB 和前后持久快照证明终态复活、当前处理者被删除或 ACK 与副作用不一致；不是人为写坏 DB 或编造返回值。

未来 Buggy 应在普通单处理者、不过期路径基本可用。最小缺陷应是发布/清理代码遗漏当前代次及终态验证，保留 SQLite 事务、FK/CHECK、订单身份和账本唯一约束。无需去掉所有约束，也不通过故意抛异常伪装租约竞态。

### 5.2 调度公平

可信 Supervisor 记录独立 PID/启动代次、共享 DB device/inode、实际调用区间和多个 Worker 的持久写入证据。公开 API 的 claim 返回给宿主后，宿主才暂停 A/推进 Clock/安排 B；因此正确修复不必保留私有 checkpoint，也不会被要求在持有排他锁时等全部 Worker 到达屏障。

调度器只安排时间、进程和公开调用，不给 Candidate 发送 expected stock 或 gold label。原生 SIGSTOP/SIGCONT 暂停与 SIGKILL/restart 分开记录。Worker 不能通过关闭并发入口通过；正确的短 SQL 提交串行化仍是允许的并发服务。暂停处理者不能无限阻止无关合法请求或租约接管；相应 liveness 条件须公开，不用任意短墙钟误判慢环境。

## 6. Clock 和状态观测边界

- 所有 Worker 使用同一个公开 Clock abstraction；生产语义为共同权威时间，测试语义为可信控制器可推进的时间。Clock 查询接口、单位、边界和错误语义在 Participant 包中公开。
- Candidate 可读取当前时间，不能修改权威 Clock。未来应使用独立只读挂载或权限受限 UDS 查询接口；不能把时间控制文件放在 Candidate 可写业务目录中，不能把私有调度/断言文件一起挂入。
- 时钟推进必须通过公开 Clock 接口作用于真实代码，不能由 Oracle 直接更新请求 deadline/业务行。默认时间单调，默认复现只在公开操作之间推进；重叠测试遵守 §4.3 的合法历史规则。重启恢复同一时间代次。时钟回退、authority 重建或跨机 skew 是另立变体，当前不声称覆盖。
- 权威时间事件、claim 返回、takeover、cancel ACK、complete 调用和原始 DB 快照各保留可信来源。候选自报 owner/time 仅辅助，不作为宿主真值。
- Clock 通道不获模型身份或宿主凭据；Participant 只看到当前时间信息，Candidate 不获控制 socket 或隐藏文件。隔离新增挂载须单独做实际回归。

## 7. Public Issue 草案

以下为待未来公开包独立审查的草案。它描述部署事实和用户可见契约，不含根因、参考补丁、私有时序或推荐实现。

> ## 订单请求在 Worker 延迟和重启后出现不一致
>
> 服务使用多个独立进程处理订单请求，共享一份持久 SQLite 数据库。请求可以分两阶段领取并完成，以便处理过程中进行准备工作；未完成的处理权具有期限，可以续期或被接管。部署扩容之后，个别请求在取消、重试或 Worker 延迟/退出后出现不一致：请求查询、完成回执与订单/库存记录有时无法对应。普通不间断请求通常正常。
>
> 请使用提供的源码、公开 API 文档、处理记录和复现工具调查原因，修复业务代码，并增加有用的公开回归。必须保留现有订单 API、新请求 API、业务容量及至少 2/4 个 Worker 的并发能力。
>
> 同一请求和相同 payload 的重试必须发现同一业务结果；冲突 payload 应明确拒绝。领取处理权不等于成功预留库存。已确认取消的未完成意图不能被它的迟到操作重新发布；完成先发生时，应明确告知请求已经完成。处理过期、接管、续期、进程重启和响应丢失后，持久请求、订单、库存及账本仍须一致。当前处理期限和统一时间可用公开接口查询。
>
> 遵循公开 API 文档中的租约线性化和结果类型约定。请求处理完成与库存预留成功须区分：发现同身份已经取消的订单时可以形成对应处理结果，但不能重新预留或称它为成功库存预留。
>
> 保持 SQLite 持久化与正常 DELETE/WAL 支持，不得禁用接管或并发、拒绝有效请求、删除审计记录、伪造数据或修改测试要求规避问题。仅提交 app Python 业务源文件；公开测试变更另行保存。运行和诊断方式见公开说明。

“数据库事务也不足够”“应该加入 fencing”之类维护者结论不能加入正式公开 Issue。公开症状日志应来自未来 Buggy 实际运行、可脱敏但不伪造；上述现象目前是设计假设，不是已经采集的 v02 事故日志。

## 8. 合法解与错误策略对照

| 样本/策略 | 未来验证目标 | 不得替代的证据 |
|---|---|---|
| Reference：短写事务内读取当前请求/处理权、验证并原子发布订单/库存/账本/回执 | 租约、终态与容量决定来自当前持久状态；原子 ACK 状态；旧 handle 不产生副作用 | 一个参考补丁存在或一次 PASS 不能证明 |
| Alternate 1：条件状态更新、不可复用 handle、同一事务发布或等价恢复协议 | 乐观竞争/当前所有权判断和幂等 receipt 完整；避免 ABA | 不能只比较 owner 名字或 request_id |
| Alternate 2：稳定共享文件锁覆盖短授权验证及发布，各相关 writer 一致参与 | 协调机制与 Reference 不同；暂停发生在公开两阶段间，不持长锁；锁释放/进程死亡后可接管 | 不能靠无限串行化整个准备阶段获得 PASS |
| Legal staged control | 先持久请求再完成业务；未知 ACK 状态可重试、补偿只作用于自己尚未完成的意图 | 不强制单个事务数量，不误删已有正常订单 |
| Wrong：只移植 D-v01 条件库存 UPDATE | 库存可能守恒，但旧 handle 发布违反 CANCELLED/current owner 真值 | 必须得到实际业务 FAIL，而非接口不兼容 ERROR |
| Wrong：本地 RLock / 仅 BEGIN IMMEDIATE 包旧授权结果 | SQL 提交串行，但在租约接管后仍使用过时授权 | 不能仅凭源码有 RLock 判错 |
| Wrong：仅加长 TTL/不停续期、永不接管 | 无法按公开租约与取消契约恢复；被接管/撤销的实际旧 handle 仍错误 | 不以极短真实 sleep 制造偶然超时 |
| Wrong：以 owner 名字/PID 判断，清理无代次条件 | 同名重启 ABA 或旧 cleanup 清除新处理者 | 需要真实旧/新代次交错及 raw 状态 |
| Wrong：业务提交与成功 receipt 分离且无可恢复意图 | 杀进程或丢响应后出现孤儿副作用/重复或丢失结果 | 实际 SIGKILL/重启/相同请求重试 |
| Wrong：先缓存 ACK、广泛吞异常为库存不足 | 回执无持久副作用、错误拒绝有效请求或抹去基础设施失败 | 宿主 ACK 与 raw DB/错误分类对照 |
| Evasion：关闭多 Worker、全拒绝、硬编码库存、删除请求/账本、换随机 ID | 不能满足拓扑/容量/请求/持久真值；拒绝伪成功 | 准备 ample-stock 写入阶段、不同参数和有效流量 |

以上结果都是 **PLANNED / UNVERIFIED**。Reference 和 Alternate 1 同用 SQLite 原子性，但授权判断路径不同；要满足“机制不同”的工程 Gate，至少加入真正不同协调机制的 Alternate 2 或经独立审查的其他等价方案。不能把仅重排同一段 SQL 称为独立合法修复。

## 9. 独立 Oracle 的设计

### 9.1 数据真值

未来 fixture 公开持久审计契约：订单、库存、库存账本、请求 payload/终态/结果，以及处理代次与租约记录。这是业务记录的最低协议，不指定锁、事务数量或授权 token 算法。Candidate 可以添加表/字段/实现模块；受评测语义必须保留真实公开业务记录。维护者 Oracle 读取普通单链接 DB/sidecar 的真实基表，不运行候选 import、conftest、audit 或候选生成的“审计视图答案”。

停止所有 writer 后，可信侧只让 SQLite 自己做必要 journal/WAL 恢复，记录前后真实摘要与 inode；不补写订单、修账本或删除失败证据。Clock/Supervisor 事实与 DB 事实各自校验。

### 9.2 必要不变量与时序

| 类别 | 独立检查 |
|---|---|
| 库存/账本 | 既有 `initial = available + reserved + committed`；非负；真实 ledger delta 对应库存；每个 active order 与 reserve/release 账本数量一致 |
| 意图身份 | request_id 对应固定 payload；相同重试发现同一意图；冲突 payload 没有覆写；合法已有订单不被请求补偿删除 |
| 当前处理权 | 在 §4.3 合法线性化历史与 takeover/cancel 边界下，旧 handle 不产生新业务效果、改终态或删新处理者；不要求整数 fencing 列，不以 COMMIT 墙钟越 deadline 单独判错 |
| 终态 | 已 ACK CANCELLED 意图的迟到 handle 不产生新订单/预留；其他真实独立意图/旧 API 的合法副作用按宿主顺序归属区分；完成已 ACK 后结果不被清理回退；正常 cancel_order 不否定历史 receipt |
| ACK | 按 §4.4 区分 COMPLETE_RESERVED / COMPLETE_DISCOVERED_CANCELLED 等；payload/持久记录/当时效果相符；未来订单变化不否定历史成功；未知 ACK 通过 raw 状态与 retry 审计 |
| 进程/并发 | 2/4 个可信不同 Worker、共享 DB inode、调用重叠、各 Worker ample-stock 实际写入；不要求每个 Worker 抢到最后一件库存 |
| 恢复 | before claim commit / claim commit-response lost / publish precommit / publish commit-response lost / stale cleanup 各明确实际覆盖、未知 ACK 和 retry 结果 |
| 错误 | 正常业务错误与 RPC/启动/Clock/observer/沙箱/资源故障分开；不可统一转换为 stock exhaustion |

仅检查终态最终库存不足以发现中间取消后复活又被“修好”的行为。可信控制器在关键已完成调用之后保存原始 DB 快照和 ACK，再安排下一阶段；需要历史判定时使用独立顺序模型和宿主实际调用区间。可评估现成 [Knossos](https://github.com/jepsen-io/knossos) / [Porcupine](https://github.com/anishathalye/porcupine) 的历史检查方法；不为了本变体自行构建复杂通用线性化框架。

模型只在没有重叠或已明确 happens-before 时要求确定顺序；并发 complete/cancel 有合法任一胜者。Clock 查询需有可信服务侧原始来源；候选数据库字段或自报 query 时间不能代替。如果只能取得宿主调用区间，Oracle 先判断是否存在合法历史，不能断言内部必须在哪个 wall 时刻 COMMIT。无法证明某个必要恢复窗口时为 `ERROR / RECOVERY_EVIDENCE_UNVERIFIED`，不能把 0 失败升级为 PASS，也不能因为合法内部结构不同直接判业务 FAIL。

## 10. Crash/retry 与调查矩阵

未来必要场景至少覆盖：普通单处理者、2/4 Worker、不同库存/quantity、多个 SKU、相同请求重复和冲突请求；有效续期、精确过期边界、接管后旧 complete/renew/cleanup、同名 Worker 重启 ABA；取消请求与完成竞争、库存不足后公开可重试语义；claim 与 publish 的实际异常退出和响应丢失；WAL/DELETE、正常订单 cancel/release、reset 独立重放和未加协调 hook 的普通流量。

调查信息不能只提供“偶尔错了”的文本。未来公开包需有可运行的请求驱动、公开 Clock 查询/推进的本地诊断方式、原始处理记录查询、示例普通流程以及不包含私有 exact answer 的暂停/恢复示例。隐藏 Suite 可用不同参数和交错，但不能依赖未公开的 API/状态机。

## 11. Private Gold 条件结构与来源

下列是未来私有参考的逻辑契约，**不是本轮新增标签文件或治理服务**：

| 字段 | 内容与来源 |
|---|---|
| relation_id / label_version | 指定策略主张、source/target 版本、独立参考版本 |
| strategy_claim | 精确到“条件库存更新足以完整修复”或“发布必须验证当前处理权”；不能仅写“使用数据库” |
| source_origin | natural / maintainer_seed / synthetic；真实 patch/outcome 的来源不可混淆 |
| assumptions | 共享持久权威、处理权是否过期/可撤销、哪些 writer 参与验证、是否有分阶段准备、ACK/恢复契约 |
| observable_evidence | Participant 在此信息条件下已获得与可合理查询的事实；先区分未知与不可得 |
| decision_reference | APPLY / VERIFY / ABSTAIN 加作用范围；代码成败独立记录 |
| supporting / counterexample | 实际源 Run/patch/tree/Suite/Oracle/Clock/时序引用；未来未执行则 UNVERIFIED |
| reviewer / reviewed_at | 独立工程与研究审查者，分歧及依据 |

拟定条件：

- **APPLY（局部原则）**：把 A/D-v01 的库存条件更新、业务账本同提交和稳定身份幂等用于 v02 的对应子问题；不得称旧 patch 已覆盖新授权协议。
- **VERIFY**：历史描述没有说明 lease 是否可撤销、发布时是否重新验证、准备阶段是否跨事务；Participant 应能通过源码/处理日志/公开 API 查询这些事实。当前只有设计条件，没有运行中的信息不足变体。
- **ABSTAIN（完整性主张）**：有真实接管/取消后旧 handle 路径，而策略只修容量或依赖进程本地锁，不能把它作为完整修复依据。需要未来相同策略的真实正控/反例支持，不能用 Agent 最后 FAIL 反推标签。
- **APPLY（扩展授权原则）**：在目标协议上经独立验证的当前处理权/终态条件验证，可以成为新经验来源；现阶段没有 v02 正向运行证据。

自然历史是 Agent 真正提交的补丁/轨迹，不等于维护者关于其动机的解释。M1 全局/文件锁正控属于维护者样本，不能冒充自然 Agent 策略。标注和 Oracle 都留在可信 Maintainer；Experience Adapter 继续 DISABLED。

## 12. 未来无经验 / Raw Memory / 治理的公平协议

本节仅定义 Benchmark 实验装置，不实现 Exposure Controller、GraphSwarm、FalkorDB、反馈或 G0–G3。

1. 使用同一冻结 v02 Task/Fixture/Suite/Oracle、公开材料、Gateway model/effort、提交协议和安全等级。每个试验新 Run/Session，无授权条件不能继承维护者或旧挑战对话。
2. 无历史组没有跨任务材料；Raw Memory 与治理组获得同源、同版本、同内容上限的历史 corpus。差异是选择/判断方式，不能是治理组额外获得参考补丁、private label 或目标答案。
3. corpus 明确 natural/seed/synthetic，并同时包括原则可迁移、作用范围有限、冲突和证据不足记录。预先冻结私有标签；保存精确曝光内容摘要、时点、ID 和权限。
4. 当前证据先判断，再定义曝光 checkpoint；不能让“VERIFY”强迫 Participant 在完成了正常调查后仍报告不知道。调查途径对所有组相同。
5. Runtime、Task Outcome、Experience Judgment 和 Influence 分别计分。查询过历史不证明采用；采用自报与行为可观察证据分开，无法推断的因果关系为 UNVERIFIED。严格影响评估需配对/随机化曝光及全分母。
6. Single/Multi 设置、并发、请求/Token 配额和 completion-aware 停止政策明确预注册；记录无法完全对齐的差异。429、网络、取消、无提交和无效 patch 不悄悄剔除。

## 13. Ceiling/floor 及难度校准计划

| 风险 | 怎样证伪/调查 | 不允许的修订 |
|---|---|---|
| 只缺一个明显状态判断，所有能力层均很快正确 | 独立盲测、实际 patch、工具/调查阶段与原始错误策略检出；同义中性 Issue 独立审查 | 在公开说明里藏掉必要契约或添加无关代码行 |
| 新协议语义模糊导致全 FAIL | 合法多解、顺序模型、API/状态边界审查；记录失败是业务还是误拒绝 | 把真实合法中间状态改为断言失败制造难度 |
| 长 Gateway/协作等待被当困难 | completion-aware 运行、真实请求/SSE/429/工具/child/结束时间分层；任务结果独立评价 | 使用短总 wall-clock 提高失败率 |
| 观察 hook 偏袒 Reference | 多路径恢复正反控、当前权限/DB/ACK 真值；缺失窗口明确 ERROR | 强制指定 SQL、token 名称或内部 helper |
| 多故障叠加形成无法归因 floor | L 先独立验证；必要时另立恢复/ABA材料变体，保留共同公开语义 | 把 L/S、支付、事件全部塞进一个 v02 |

R3 的六个 D-v01 新 Session 现已实际结束，其全分母结果与设计影响在第 15 节；它们校准旧任务和 Runtime，不能验证未实现 v02 的难度。未来 v02 盲测仍须报告完整分母与难度区间，不由一次 reference PASS、测试数量或主观“更复杂”决定研究准入。

## 14. 未来实现的双质量 Gate

### Engineering Gate（本轮全部未执行）

- 实际 Buggy 单路径基本可用，租约交错产生 raw DB/ACK 业务违反；不能是错误字符串、启动 ERROR 或纯 TIMEOUT。
- 2/4 实际 Worker、共享 DB 身份/写入/重叠成立；受控过期、接管、旧请求恢复不是随机 sleep 唯一依据。
- 至少 10 次独立初始化 Buggy 稳定业务 FAIL；Reference 与机制不同合法替代各 10 次完整必要 Suite PASS；不同参数、Clock 边界和 crash/retry 覆盖。
- 指定已知错误及明显绕过策略被实际业务 Oracle 拒绝；合法多阶段和不同协调机制不被误拒；Observer 缺失单列。
- DB 原始真值、ACK/Clock/调用顺序独立；恢复不修行；JUnit 身份完整无 skip，实际退出及所有指纹可核对。
- 现有 Smoke/A/D-v01 和有效开发者测试无回归；Manual/Codex fidelity、隔离、reset、异常/取消及全部历史哈希保留。
- 新 Clock/诊断通道真实文件/网络/控制权限探针通过；真实密钥只在 Broker；资源、进程停止/清理及完整/Audit-Lite 归档可核验。

### Research Gate（本轮只审查设计）

- L/S 是独立因果候选，推荐取舍和可证伪事实明确；新 API/clock/终态可合理调查，公开 Issue 不含修复答案。
- Gold 独立、策略级有精确来源与条件；natural 与 seed 分开；VERIFY 不由人为隐藏必要信息制造。
- 未来盲测、合法多解、错误对照与难度报告能区分能力、Runtime 和协作开销；不把长运行等同高难度。
- Plain/Memory/治理协议信息公平，来源/曝光/预算可追溯；没有治理实现或收益结论。
- 独立审查意见可追溯；争议、未执行要求与阶段停止清楚。R4 设计 PASS 不能称 v02 Engineering PASS 或任务运行 PASS。

## 15. 六次真实 D-v01 校准与设计影响

**测量来源为 current_dynamic / 设计影响为 static inference，二者分开。** [CALIBRATION_ANALYSIS.json](../m1_1_validation/20261010T154658Z-4e5039eb-6ac2-49c7-8ece-824765e22f5f/calibration_analysis/CALIBRATION_ANALYSIS.json) 于 `2026-10-10T18:17:31.485629Z` 记录全部六个新 Session；实际 SHA256 为 `80d9dfc85344ff7672ca292cead29ad841c941b480fea972d993768a70950e73`。关联的 [原生事件时间线](../m1_1_validation/20261010T154658Z-4e5039eb-6ac2-49c7-8ece-824765e22f5f/calibration_analysis/MULTI_AGENT_TIMELINE.json) SHA 为 `fd65846b46e20152a6206e036bbde42361f83145aa348256d6b695b2cce3d543`；记录中有真实 report/runtime/native/transport 文件和原始引用，而非 Agent 自述。

### 15.1 全分母终态

| 顺序 / 组 | 新 Run ID | Runtime / CLI退出 | Agent秒 / 闭环秒 | 原正式隐藏评测 | 原解析器 native spawned / verified |
|---|---|---|---:|---|---:|
| 1 / S | `a23a8b03-e956-4403-b05f-2cb3941ad827` | ERROR / 2，PROVIDER_FAILURE | 100.36 / 100.60 | NOT_RUN | 0 / 0 |
| 2 / M | `64377ef0-3998-434c-936c-8011886b9cd2` | PASS / 0 | 835.45 / 875.57 | 28/28 PASS | 3 / 3 |
| 3 / M | `2c543377-5be5-4522-a3cf-bc8caf8c1cc3` | PASS / 0 | 1649.90 / 1690.94 | 28/28 PASS | 3 / 3 |
| 4 / S | `f238d8db-dc61-4aa3-9b99-ceb019e307e4` | PASS / 0 | 687.08 / 728.17 | 28/28 PASS | 0 / 0 |
| 5 / S | `47f36a9d-1be2-4405-ab8f-7d322ebc08e5` | PASS / 0 | 1011.25 / 1051.99 | 28/28 PASS | 0 / 0 |
| 6 / M | `eb647097-b595-43cd-b4a6-e5f0057ec5f0` | PASS / 0 | 1142.27 / 1183.70 | 28/28 PASS | 3 / 2 |

S 组正式任务 PASS **2/3**，一轮 Provider ERROR/NOT_RUN；M 组 **3/3**。五个已经评价的实际 Agent 补丁为 **5/5 PASS**，无业务 FAIL，但不能把“已评价”分母代替全部六次或把首轮服务故障删除。表中保留原解析器 M 组 verified **3/3/2**，不重写旧 Run summary 或成绩；M6第三 Child 的实际完成须结合下述独立纠错记录，不能把旧解析计数解释成实际未完成。三个 S 的官方配置/日志无 Child 核验均 PASS，不能用提示词代替零 Child 事实。五个正式成功 Run 的 submission integrity 为 PASS、28 个必要身份完整、0 failure/error/skip、恢复覆盖 COMPLETE；六个 Run 的清理/封存检查均 PASS。

**M6原生证据解析假阴性更正，单独记录。** Investigator `01a126f7-8175-7181-84a8-83f5c6ec329d` 的 [Child原始JSONL](../m1_1_validation/20261010T154658Z-4e5039eb-6ac2-49c7-8ece-824765e22f5f/calibration-continuation/runs/eb647097-b595-43cd-b4a6-e5f0057ec5f0/artifacts/native_rollouts/2026/10/10/rollout-2026-10-10T17-58-37-01a126f7-8175-7181-84a8-83f5c6ec329d.jsonl) 第113行 `AgentMessage(final)`、114行 `response_item final` 与117行 `task_complete` 的完成文本逐字节一致，4071字符、包含末尾两个换行；三者文本SHA为 `8ccf5bc878c59339496c0cf982df08a67d559af4e3953071af7194c93239c7d4`。117行原始字节（含行末换行）SHA为 `eb6fab456fd5d6668c49594f5ec8c2675fc05736de67b010463cb1f612512eff`；[Parent原始JSONL](../m1_1_validation/20261010T154658Z-4e5039eb-6ac2-49c7-8ece-824765e22f5f/calibration-continuation/runs/eb647097-b595-43cd-b4a6-e5f0057ec5f0/artifacts/native_rollouts/2026/10/10/rollout-2026-10-10T17-57-16-01a126f6-3d46-7090-a14f-22418f918930.jsonl) 第154行回传引用SHA为 `66aa86b6f76267a2cb37042046008390723c99d1ab3de8c89e32ec976b8be330`。独立Runtime审查发现 `_text.strip()` 单边删除换行导致假阴性；设计作者亦只读核验了三处文本、长度及原始行SHA，命令退出0。**原解析器verified2，独立raw记录证明第三正常完成；这是单独纠错与复核，不升级旧成绩。** [修复前来源记录](../m1_1_validation/20261010T154658Z-4e5039eb-6ac2-49c7-8ece-824765e22f5f/independent_review/runtime_final/BEFORE_FIX.json) 和 [独立最小Parser修复/82项回归记录](../m1_1_validation/20261010T154658Z-4e5039eb-6ac2-49c7-8ece-824765e22f5f/independent_review/runtime_final/SOURCE_FIX.json) 另存于本次审查，未更写原运行产物。

### 15.2 可比条件、Gate 与历史保护

六轮执行顺序为 S/M/M/S/S/M，各自新 Run 与新 Lead Session。公开业务 Issue/TASK/app/Public Manifest/Public Tests 字节一致核验 PASS；同 Gateway `gpt-5.6-terra / max`，无静默降级。Suite `1.2.0` / Evaluator `3.1.0` / Fixture `1.0.0`，实际 Suite SHA `fd3bbaa0f48925ccee30e5b84e591396611259ae05c06df0e16ad117328d6303`、Private Manifest SHA `a546ef66a541bb96bc6518988297d934d26421982160c0280903e29c8155b486` 全程一致。S/M 的原生协作配置和任务协作提示不同，这个实验处理差异明确记录，不称完全相同输入。

联网前 [R1 动态 Gate PASS](../m1_1_validation/20261010T154658Z-4e5039eb-6ac2-49c7-8ece-824765e22f5f/R1_GATE.json)、[R2 最终 Gate PASS](../m1_1_validation/20261010T154658Z-4e5039eb-6ac2-49c7-8ece-824765e22f5f/R2_GATE_FINAL.json) 与 [R3 Live Admission PASS](../m1_1_validation/20261010T154658Z-4e5039eb-6ac2-49c7-8ece-824765e22f5f/LIVE_GATE.json) 保存实际依据。所有六轮 completion-aware，没有总 Agent wall deadline 和总 request budget，串行试验；CPU600秒、memory2GiB、pids768及每请求/原生并发等控制仍存在，operator cancel 和隔离不移除。不是完全敌对安全或第三方运行证明。

首轮真实 Provider 故障包含 stream interruption、服务端500和连接错误；原 ERROR 留在分母。TLS恢复后 collector 在新目录继续采集预定剩余轮次，每轮仍是**新 Native Session**，不是对失败 Session 的 resume，也不是替换首轮补考。旧 M1 的 TIMEOUT / PASS / TIMEOUT 与自动闭环1/3不变，不能被这组新五次 PASS 回填。

### 15.3 长运行、请求与用量

| 顺序 | 上游请求 | native去重 total Tokens | request duration累计秒 / 区间并集秒 |
|---|---:|---:|---:|
| 1 / S | 12 | 36,838 | 96.71 / 96.71 |
| 2 / M | 81 | 1,705,042 | 1644.85 / 832.75 |
| 3 / M | 96 | 2,028,964 | 2969.61 / 1647.48 |
| 4 / S | 15 | 318,329 | 689.75 / 684.80 |
| 5 / S | 25 | 536,950 | 1015.48 / 1007.88 |
| 6 / M | 80 | 1,559,991 | 2120.13 / 1140.05 |

第三轮 M 自然完成 **1649.90 Agent秒，跨过旧1200秒阈值**；第五轮 S 自然完成 **1011.25秒，跨过旧900秒阈值**。第四轮有一条实际请求持续181.11秒、SSE观察171.86秒但最大body gap约18.41秒，不能把超过120秒的响应当作无进度卡死。这些是新运行的真实完成证据，不证明旧超时 Session 若延长必定成功。

用量来自官方每response ID去重，不相加累计thread counter；cached/reasoning为对应input/output组成部分，不能二次加总。货币账单 UNAVAILABLE。多个模型请求与工具/child工作可以重叠，累计request duration不等于墙钟，也不能以Agent时间减request并集断言纯思考时长。首次源码变化不是原子提交点，是否已经通过隐藏测试为 UNVERIFIED；本设计不称某轮在该时点已“解出”。

### 15.4 对推荐方案的影响和审查结论

实际读取五份新正式 patch，均只修改 `app/inventory.py` 与 `app/service.py`，主要删除或忽略旧 snapshot 写入支路，采用事务内条件相对UPDATE，保留旧API。**完成者5/5通过、包括两个无Child单Agent**，进一步支持“D-v01 在当前模型/公开条件下可能存在代码任务 ceiling”的先导信号；它没有证明所有模型都易解或两组能力相同。

M组本样本请求、reported Tokens和完成墙钟多于两个成功S样本，但n=3/组、Provider故障、TLS恢复跨时段、工具/child重叠和未匹配处理结构使因果归因不足；不能宣称Multi一般更强或更慢。工程能力、服务连接与协作收尾应分别测量。推荐 L 仍聚焦持久授权/终态事实而非加压v01；该推荐是设计推论，**v02是否更难、实际可解及策略判别力均UNVERIFIED**。若L以后仍只需一个显见条件即可普遍通过，保留成绩并另行修订任务分布，不能人为藏契约或缩短运行获得低通过率。

[独立工程审查](../m1_1_validation/20261010T154658Z-4e5039eb-6ac2-49c7-8ece-824765e22f5f/independent_review/root_v02_engineering/REVIEW.json) 与 [独立研究审查](../m1_1_validation/20261010T154658Z-4e5039eb-6ac2-49c7-8ece-824765e22f5f/independent_review/runtime_agent_v02_research/REVIEW.json) 对0.2.0静态设计分别PASS；它们在当时明确six-run pending，原件不更写。0.2.0精确文档及 [输入摘要](../m1_1_validation/20261010T154658Z-4e5039eb-6ac2-49c7-8ece-824765e22f5f/v02_design_0.2.0/INPUTS_SHA256.json) 保留。0.3.0仅追加本章已结束测量/审查出处并更新状态；§2–12和§14的normative设计保持原字节。**设计审查PASS的范围是规格与实验质量，不是Episode v02工程验收。**

未来编码前需冻结公开包/实现版本：新API/错误/receipt具体数据字段、本设计已选的容量不足/租约线性化/结果类型语义、公开审计最小schema、Observation支持、合法恢复模型、实现预算和独立外部评审。语义变更需升版本，不能到隐藏测试才决定。当前没有v02代码、Suite、Reference或Registry；完成M1.1后停止。

## 16. 成熟方案来源与版本风险

调研日期 **2026-10-10 UTC（香港时间 2026-10-11）**，以下为实际浏览的一手资料；用于设计原则，不声称已经集成依赖或复现其代码。etcd 官方 GitHub 示例演示过期持有者暂停、另一持有者取得权限、旧持有者恢复后由资源验证拒绝迟到写入。这支持 L 的现实因果机制；OrderFlow 不需要开发 etcd 或新锁服务。[etcd lock 示例](https://github.com/etcd-io/etcd/blob/main/contrib/lock/README.md)、[官方 concurrency API](https://etcd.io/docs/v3.5/dev-guide/api_concurrency_reference_v3/)

SQLite 文档解释事务、隔离及一致备份；成熟历史检查器提供模型检查思路。引用支持的是这些原则，不证明 OrderFlow v02 已正确。[SQLite transactions](https://www.sqlite.org/lang_transaction.html)、[isolation](https://www.sqlite.org/isolation.html)、[Backup API](https://www.sqlite.org/backup.html)、[Porcupine](https://github.com/anishathalye/porcupine)、[Knossos](https://github.com/jepsen-io/knossos)

本机 M1 冻结 SQLite 为 **3.46.1**。当前官方 WAL 页面 §11 说明一个特殊 checkpoint/reset 竞争的 WAL-reset 缺陷影响 3.7.0–3.51.2，修复在 3.51.3+ 和部分 backport。**OrderFlow 历史发生该缺陷为 UNVERIFIED**；不得据此改写任何旧结果，也不在 M1.1 改 D-v01 依赖争取成绩。未来 v02 应冻结已修复 SQLite 或明确隔离库级竞态，防止把库故障归因给业务修复。进程 SIGKILL 验证不等于真实掉电/硬件 durability 验证。[SQLite 官方 WAL 风险](https://www.sqlite.org/wal.html)

**停止边界：M1.1 只交付设计；D-v02、B/C 与治理实现需后续授权。**
