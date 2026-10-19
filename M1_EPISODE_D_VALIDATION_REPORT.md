# M1 — Episode D Engineering Validation

> 最终报告。三次真实盲测已结束；总体 **CONDITIONAL PASS**，分层工程、运行和任务结果独立列出。

## 1. 范围与证据入口

本轮实现 Task System 规范和 Episode D，复用现有 Registry、Runner、提交保真、bubblewrap、独立 pytest Evaluator、Manual/Codex Adapter。B/C 继续 `PLANNED / NOT_IMPLEMENTED`；Experience 继续 `DISABLED`。没有开发 GraphSwarm、FalkorDB、MCP、经验决策算法或 G0–G3 实验。

独立归档：[M1 evidence](m1_validation/20261010T101602Z-8dfa7d4f-3c6c-4f4c-ac5a-57a06afa3e9e/)。索引由 [CURRENT](m1_validation/CURRENT) 指向。起始真实 HEAD 为 `beba4fba73f2e59e0d5a7fb99aea332ad80ea2cf`，新分支为 `m1-task-system-episode-d`。本轮源码处于工作树，不能将历史 HEAD 当作新源码冻结提交；新的文件哈希见 `LIVE_GATE.json` 和最终 source manifest。

## 2. 先设计、再实现

`BASELINE.json`、`BASELINE_GATE.json`、`design_preimplementation/`、`DESIGN_GATE.json` 保存开发前状态、499 项实际回归与设计自审。设计门禁时间为 **2026-10-10 10:28:47 UTC**，发生在 D 实现之前。顶层规范见 [Task System](docs/TASK_SYSTEM_DESIGN.md)、[Admission Gates](docs/TASK_ADMISSION_GATES.md)、[Task Relations](docs/TASK_RELATIONS.md) 与根目录设计审查。

Engineering Truth 由独立数据库/业务测试判定；Decision Reference 是维护者私有策略适用性审查，两者不混分。`natural` 原始 Codex A 修复、`maintainer_seed` 本地锁/文件锁对照、`synthetic` 错误变体与信息不足条件均有不同来源声明。

## 3. 工程实现与故障因果

### 3.1 真实拓扑

通用 `shared-db-workers` 执行策略启动 2 或 4 个独立 bubblewrap OS Worker。每个进程加载候选 app，访问同一 SQLite 数据目录，宿主不 import 候选 app。`SO_PEERCRED`、进程 start ticks、namespace、启动谱系与 `/proc/<pid>/fd` 的数据库 device/inode 组成可复核证据。PID 的范围明确为 **可信 Supervisor PID namespace**，不是将各隔离 namespace 内重复的 PID 3 当作独立身份。

可信宿主固定轮转并行发起 RPC；记录请求 start/end 与重叠区间；充足库存样本要求每个 Worker 都完成独立订单的持久化写入，重复同 ID 响应不能充当新增写入证据。

### 3.2 真实错误与多解

| 实现 | 机制与业务含义 | 实际结果 |
|---|---|---|
| Buggy / local-lock-only | 进程内 RLock 覆盖写 API，但事务前读取库存、随后按旧绝对值写入；独立进程之间发生 lost update | 单 Worker 路径通过；并发 raw Oracle 发现订单/账本与库存不一致；最终 10/10 FAIL |
| Reference | 原业务事务与条件相对库存更新，使订单、库存、预留账本保持原子一致 | 最终 10/10 PASS |
| Alternate flock | 保留缺陷快照路径，以稳定共享锁 inode、每次新 FD 和本地 RLock 覆盖全部写操作；进程死亡由内核释放锁 | 最终 10/10 PASS；不是 Reference 的语法变化 |
| Split-ledger | 库存和 active order 先提交，预留账本后提交 | 提交后 SIGKILL 暴露 durable active order 缺账本；同候选自定义事务版本三次被识别为 FAIL |
| Compensated phase 正控 | 先原子创建 created/none + provisional marker，再原子预留并清 marker；不足时只补偿新临时订单，重试恢复持久中间态 | 28/28 PASS、36 次 raw Oracle 一致、三个真实恢复窗口 COMPLETE |
| Naive two-phase 错误对照 | 简单先 create(reserve=False)、再 reserve；不足后留下原 API 不应保留的新订单 | 16 PASS / 12 FAIL；原失败未删除，重新分类后的新运行仍真实 FAIL |

原 SQLite schema、CHECK、FK、订单 ID 与账本唯一约束保留。错误库存由实际读取/事务/并发交错产生，没有固定假数值或故意异常。

### 3.3 有界同步、崩溃与恢复

受控 `inventory_read` 首波竞争窗口有 **0.3 秒有限门禁**；Buggy 多进程能同时进入，合法互斥/事务实现允许门禁超时释放，避免强制正确实现死锁。另有不协调调度测试。

`before_commit`、`transaction_committed`、成功的 `before_response` 由宿主等待实际事件、使用 pidfd 对已核验 Worker SIGKILL、观察死亡与启动器退出、启动新进程后在同一 DB 上重试。原始恢复证据、数据库恢复前后哈希、普通 SQLite 热日志回滚及最终完整性检查均归档。独立 Oracle 不编造修复行。

不同实现可以有多个事务。无响应窗口允许 absent、合法 pending created/none 或完整 reservation；成功响应窗口要求订单/库存/账本已完成。试验中带补偿的合法分阶段方案通过，说明测试不强制某个事务数量或锁技巧。

## 4. 独立 Oracle、观测盲点与修复证据

宿主直接检查 inventory、orders、ledger、原始约束、FK/integrity、守恒、订单预留量、返回结果和真实持久化写入。候选 `audit()` 不能决定 PASS。

本轮实际发现了 harness falsifier：Run **`f9089592-c528-4904-a72d-b6965eba99a4`** 的 custom split-ledger 曾错误获得 **24/24 PASS**。仅包装原 `persistence.transaction()` 不能观察合法替换的事务入口。该原报告和候选均保留。当前三次重放的候选代码树 SHA256 均为 `0fd8eaacd0a0148e669401f8f8ba45ebe5847e3b8026ef7a984a2f9320c8aae5`，与原 falsifier 完全相同，均由原始数据库不一致判定 FAIL。

当前通用 SQLite observer **1.1.0** 在候选 import 前安装，支持常用 connect、Connection/Cursor、SQL COMMIT/END、context manager、部分 autocommit/custom factory 等；依据实际 business.sqlite device/inode 与写事务识别，辅助 DB/只读事务不冒充业务提交，提交成功后才通知 committed。依据与实际正反测试见 `proposals/SQLITE_OBSERVER_SUPPORT.md`、`recovery-matrix-final/`、`recovery-closure/` 和 observer 开发者测试。

**观测不是完全敌对环境的可信证明。** 原生未绑定 C API、opaque factories、部分 SAVEPOINT/附加数据库/autocommit batch 等不能完整观测；使用 `UNVERIFIED`。28 项业务断言都通过但必要 committed/成功响应恢复窗口未证明时，结果为 **ERROR / RECOVERY_EVIDENCE_UNVERIFIED**，不是错误业务 FAIL，也不是 PASS。该路径有实际候选回归测试。进程内观测不代替宿主数据库真值。

## 5. 版本与最终重复验证

| 项目 | 当前冻结版本 |
|---|---|
| D Public Scenario | 2.0.0，v01，IMPLEMENTED |
| Fixture | 1.0.0 |
| Private Suite | 1.2.0，28 个完整必要身份 |
| Evaluator | 3.1.0 |
| SQLite observer | 1.1.0 |
| 私有适用性参考 | 1.1.0，REFERENCE-ONLY，动态复测结束后补充证据引用 |
| 实际业务运行环境 | CPython 3.12.13、SQLite 3.46.1、pytest 9.1.1、bubblewrap 0.6.1 |

最终 cohort 命令：

```bash
scripts/python312 scripts/reproduce_episode_d.py \
  --archive m1_validation/20261010T101602Z-8dfa7d4f-3c6c-4f4c-ac5a-57a06afa3e9e/repeatability-accepted \
  --rounds 10
```

实际 producer 退出 **0**，2026-10-10 11:27:15–11:47:12 UTC，1196.95 秒。30 个独立 Run，Buggy 每次退出 1/FAIL，Reference/flock 每次退出 0/PASS；无测试 ERROR/SKIP。每轮完整执行 28 个身份、提交保真 PASS、环境 reset；三恢复点 COMPLETE，各 Supervisor 最终 cleanup 完成。Evaluator/Suite/Private Manifest 指纹一致。逐轮 Run ID、P/F/E/S、失败原因和原命令见归档 `REPEATABILITY_REPORT.md`、`repeatability-accepted/summary.json`。

这 30 轮以 **业务不变量、机制不同的多解、原始数据库、崩溃、拓扑和判别对照** 支持工程结论；测试数量或单次 PASS 不能单独证明质量。

Buggy 的逐项失败数为 13 或 14。唯一变化项为混合取消/购买：6 FAIL、4 PASS；该交错受取消与首次读取的先后影响，不能将偶然通过当作错误策略正确。另有 13 个身份在全部 10 轮均 FAIL，包括受控 2/4 Worker 竞争、容量、多 SKU、WAL、重置与非协调流量。整轮 Buggy FAIL 稳定；所有 Reference/flock 正控无非确定性失败。详见 `BUGGY_TIMING_VARIATION.json`。

## 6. 既有功能回归与实际 CLI

最终 `final2-developer-command` 退出 **0**，**664 PASS / 0 FAIL / 0 ERROR / 0 SKIP**。原 499 项身份全部保留，新增 165 项。`TEST_IDENTITY_MIGRATION_FINAL.json` 保存逐身份迁移及原 27 份测试源码比较；只有原 framework 中 D 从 PLANNED 转为 IMPLEMENTED 的当前态断言作了显式语义迁移。

`offline-final` 14 个实际 CLI case 全部达到预期：SMOKE Buggy FAIL / 当前精确 Reference 8 PASS；A Buggy FAIL / Reference、maintainer RLock、atomic alternate、原 natural Agent patch 均 14 PASS；同代码 A→D 正负迁移；custom transaction 正控；伪造响应和拒绝其他 Worker 均 FAIL；B/C NOT_IMPLEMENTED（退出 4）。

旧 Smoke reference diff 原文件不变；提交保真严格校验发现旧 hunk offset 不再匹配当前基线，新增 `SMOKE-001-current.diff` 与当前 fixture 精确匹配，有独立测试。原失败与新通过都有新 Run，历史报告没有回填。

CLI `list / validate D / prepare D / report / reset` 均实际退出 0。无效提交 Run `0c702f9a-8593-4ae3-a854-9a3a4a7efeb5` 退出 2/ERROR；D `--timeout 2` Run `08fc4b42-0698-4867-8f36-61990c279fe0` 退出 3/TIMEOUT，有 owned resource 回收。原 Broker、网络、资源、Submission Fidelity、Native Trace 及失败分类测试完整保留。

## 7. A→D 私有策略适用性证据

| 来源 | 同代码 A | 同代码 D | 提交代码树 SHA256 |
|---|---|---|---|
| maintainer_seed RLock | `6a312f02-3e28-406a-81f7-86b2636e836f`，14 PASS | `c39773d4-33fe-408b-81af-2b3dcd19fa84`，FAIL | `85127c72226424724269e005543f81c61fb80ab8cebdf1dc15e84d62f15917a5` |
| natural 历史 Agent 的数据库原子策略 | `4943e873-6e9d-4905-a281-dfb621b56748`，14 PASS | `cf083714-0a91-4392-81ed-1070f2cdef71`，28 PASS | `5011b878e81cb73aa604867e866cfc52d5db25f37a21c4b22e3721277eeba2b5` |

相同代码分别进入不同执行上下文，有真实正向适用和负迁移证据。RLock 属于维护者替代策略，不能冒充此前 Codex 自主选择。`VERIFY` 是信息不足的设计级私有参考，未实现第三个正式 Variant，也未记录任何实际 Agent 经验决策。标签与以上离线检查均不是 Experience Retrieval 或治理提升实验。

## 8. 安全门禁与历史保护

`isolation-final` 的 7 个实际探测全部退出 0：外层 Participant、官方 native command sandbox、Candidate 均拒绝 hidden tests、reference、private manifest/labels、原宿主源码、其他 Run、宿主目录、proc root 绕过、路径遍历、控制通道父目录及受控宿主 TCP；公开 app 可访问。公开输入清单无私有根因/迁移标签泄漏。该探测使用 surrogate auth，不尝试读取真实长期密钥。

随后 `live-admission-command` 在可信宿主侧扫描 **42,423 个普通文件**，未发现项目密钥内容；密钥本身不进入参数、归档或任何 SHA256。模型连接由可信 Broker 注入，Participant 只获得单 Run 的受限模型通道。

联网前新预检 `live-gateway-preflight-command` 退出 0，四次真实 text/SSE/tool-call/tool-return 均 200/completed、响应声明 `gpt-5.6-terra / max`，TLS 验证通过，无静默降级。Provider 返回标签不能证明其内部实际模型权重；本轮不作该断言。

`HISTORY_INTEGRITY_PREFLIGHT.json` 比较 **38,640 份**受保护 Phase 1–3.5 历史普通文件，0 改变/0 缺失。三轮运行停止后，post-pilot-preseal-command实际再次核对38,640历史/136冻结源无变化，退出0；credential内容扫描44,154普通文件未发现密钥，不记录密钥值/摘要。最终seal再次核对，真实终局见HISTORY_INTEGRITY_FINAL、CREDENTIAL_SCAN_FINAL与FINAL_SEAL_SUMMARY。已有 `.vscode/`、roadmap 与用户任务文档保留；未执行 broad reset/clean。

## 9. 三次正式Pilot与最终结论

| Trial | Run ID | CLI退出 / Runtime | Multi-Agent / Integration | 原任务成绩 |
|---|---|---|---|---|
| 1 | `fbaae2cb-586f-4573-9cda-035eb7f608a0` | 3 / TIMEOUT，1201.01秒 | PARTIAL / PARTIAL，2个verified child | NOT_RUN |
| 2 | `48cddbed-6410-44e1-b860-142edef5e3ab` | 0 / PASS，1139.12秒 | PASS / PASS，3个verified child | 28/28 PASS，recovery COMPLETE |
| 3 | `463674bc-afba-4959-bb63-cda945c63b5a` | 3 / TIMEOUT，1201.10秒 | PARTIAL / PARTIAL，1个verified child | NOT_RUN |

三次新的独立Session，同一公开stdin/Manifest、冻结136文件、gpt-5.6-terra/max、1200秒/160请求/最多4模型并发，串行运行。原自动闭环 **1/3**。两次超时停止后原样补丁在新Run `93c081b5-5102-4ac9-b5b4-01126ebf9740`、`65c82b38-efd2-4538-9930-38cd20d89012` 各28PASS，三个恢复窗口COMPLETE，expected/applied tree一致，原Run提取前后129文件哈希不变。**不回填原Run，不把离线通过升级为自动成功。** 未人工修复或替换参考补丁。

| 分层结论 | 最终判断 | 支持与限制 |
|---|---|---|
| Task System Design | **PASS** | 开发前规范、自审和门禁，统一世界/分类/任务包/双真值/双准入 |
| Episode D Engineering Gate | **PASS（声明测试范围内）** | 真实2/4进程/共享DB/竞态/崩溃、多解与错策略、独立Oracle、10/10/10及回归 |
| Episode D Research Gate | **CONDITIONAL PASS** | 策略环境差异实测和三次先导；难度未稳定校准，无治理/统计证明 |
| Agent Pilot | **原自动闭环1/3** | 原TIMEOUT/PASS/TIMEOUT；另有2个独立原样补丁postmortem PASS |
| Phase M1 Overall | **CONDITIONAL PASS** | M1交付完成；既有安全、CPU/observer、来源证明限制与Runtime超时仍保留 |

详见 [Pilot](M1_PILOT_REPORT.md)、[设计审查](M1_TASK_SYSTEM_DESIGN_REVIEW.md)、[矩阵](M1_EVIDENCE_MATRIX.md) 和 [剩余问题](M1_REMAINING_ISSUES.md)。三份Agent代码都通过当前Oracle，可能有软件难度天花板；墙钟不能单独证明难度。初始子任务正文加密为UNAVAILABLE，原生事件和子自身活动/完成/回传另有可核验证据。

## 10. 保留的限制与停止边界

- namespace 隔离不等价于 VM；未证明完全恶意 Participant/原生 SQLite observer 绕过的安全。
- memory/pids 有实际 cgroup 限制；本机没有委派 CPU controller，RLIMIT/聚合采样存在窗口和短命子进程低估风险。输出/文件数也有采样窗口。
- 本地原始日志、哈希和证据可供追溯，没有第三方不可变存证/来源签名。
- SQLite 为单机共享文件；没有模拟独立节点数据库、跨网络事务或真正云集群。
- 三次 Pilot 仅为先导校准，不能推断统计显著性、多 Agent 优越或经验治理效果；成本缺乏账单证据时为 UNAVAILABLE。
- 新证据体量较大，保留了失败 cohort 和重复拓扑快照；未为了减少体积删除失败记录。
- B/C、经验治理以及正式对照实验继续未实现。M1 完成后停止。

## 11. 实际命令、退出、指纹与封存

`M1_ARCHIVE` 以下仅为本报告第1节实际路径缩写；精确argv/cwd/start/end/退出、stdout/stderrSHA均在各receipt和 [COMMAND_INDEX](m1_validation/20261010T101602Z-8dfa7d4f-3c6c-4f4c-ac5a-57a06afa3e9e/COMMAND_INDEX.json)。包装器退出0不改变内部Buggy FAIL或Pilot TIMEOUT。

| 实际命令 | 退出 / 内容 | receipt目录 |
|---|---|---|
| `scripts/python312 -m pytest -q --junitxml=M1_m1_validation/20261010T101602Z-8dfa7d4f-3c6c-4f4c-ac5a-57a06afa3e9e/final2-developer.junit.xml` | 0；664/664 PASS | final2-developer-command |
| `scripts/python312 scripts/reproduce_episode_d.py --archive M1_m1_validation/20261010T101602Z-8dfa7d4f-3c6c-4f4c-ac5a-57a06afa3e9e/repeatability-accepted --rounds 10` | 0；30完整Run，10FAIL/20PASS | final2-repeat-command |
| `scripts/python312 scripts/m1_offline_regression.py M1_m1_validation/20261010T101602Z-8dfa7d4f-3c6c-4f4c-ac5a-57a06afa3e9e/offline-final` | 0；14项预期正反/NOT_IMPLEMENTED | final2-offline-command |
| `scripts/python312 scripts/m1_recovery_probe.py --archive M1_m1_validation/20261010T101602Z-8dfa7d4f-3c6c-4f4c-ac5a-57a06afa3e9e/recovery-matrix-final --preserved-counterexample M1_m1_validation/20261010T101602Z-8dfa7d4f-3c6c-4f4c-ac5a-57a06afa3e9e/custom-split-observer-probe/candidate` | 1；原错误正控分类失败保留 | final2-recovery-command |
| `scripts/python312 scripts/m1_recovery_probe.py --archive M1_m1_validation/20261010T101602Z-8dfa7d4f-3c6c-4f4c-ac5a-57a06afa3e9e/recovery-closure --preserved-counterexample M1_m1_validation/20261010T101602Z-8dfa7d4f-3c6c-4f4c-ac5a-57a06afa3e9e/custom-split-observer-probe/candidate --styles two-phase compensated-phase` | 0；内部真实FAIL/PASS达到预期 | recovery-closure-command |
| `env ORDERFLOW_ENABLE_CODEX=1 scripts/python312 scripts/m1_live_pilots.py M1_m1_validation/20261010T101602Z-8dfa7d4f-3c6c-4f4c-ac5a-57a06afa3e9e/pilots --gate M1_m1_validation/20261010T101602Z-8dfa7d4f-3c6c-4f4c-ac5a-57a06afa3e9e/LIVE_GATE.json` | 0；3582.27秒，内部CLI3/0/3 | live-pilots-command |
| `scripts/orderflow --runs-root M1_m1_validation/20261010T101602Z-8dfa7d4f-3c6c-4f4c-ac5a-57a06afa3e9e/postmortem/runs evaluate --episode D --submission M1_m1_validation/20261010T101602Z-8dfa7d4f-3c6c-4f4c-ac5a-57a06afa3e9e/postmortem/pilot-1/submission.diff` | 0；独立28PASS | pilot-1-postmortem-evaluate-command |
| 同上，submission为pilot-3/submission.diff | 0；独立28PASS | pilot-3-postmortem-evaluate-command |
| `env ORDERFLOW_ENABLE_CODEX=1 scripts/python312 M1_m1_validation/20261010T101602Z-8dfa7d4f-3c6c-4f4c-ac5a-57a06afa3e9e/final_seal.py --preflight-only` | 0；实际历史/冻结源/密钥内容复核 | post-pilot-preseal-command |

依赖安装实际命令 `scripts/python312 -m pip install --no-index --find-links .wheelhouse --no-build-isolation -e .` 和 `scripts/python312 -m pip check` 均退出0，原始receipt为 `install-command/command.json`、`pip-check-command/command.json`。原命令示例不替代这些实际receipt。

### 核心文件实际SHA256

| 文件 | SHA256 |
|---|---|
| `DESIGN_GATE.json` | `38b19e360fdc2f537e65e767e17906f000fd9055b415a0bd48ab476db1e796f8` |
| `repeatability-accepted/summary.json` | `7c54c184bf2b460caa508d57ca5d633079ce9e1c2f4c1e64a2c9be02d6abde6e` |
| `final2-developer.junit.xml` | `3fe561aba28cc2d402d408223b50378c140ed6947bdac0668f8d9f972ca7ff73` |
| `LIVE_GATE.json` | `7108a60da27e876fee936a1e132f66281a0f8a1c425cb0a6e6cbfdf1620c8eb8` |
| `evaluator/episode_d_oracle.py` | `a1269feb0b76b78b81a2f2d885f014c3c4b3217efce5f4e31b829a196eb2c60a` |
| `evaluator/private_manifests/D.json` | `a546ef66a541bb96bc6518988297d934d26421982160c0280903e29c8155b486` |
| `D-v01.diff` | `096e7b4687eb9ab44f5e12ad1154a3a98851c2b8a5d1facb8ce8edcd18c2f38b` |
| `D-v01-flock.diff` | `389a8f90947f805d9b0656ec1404ed9b24bf3e4665521be9e450ec21b362ea69` |

最终入口：[FINAL_SEAL_SUMMARY](m1_validation/20261010T101602Z-8dfa7d4f-3c6c-4f4c-ac5a-57a06afa3e9e/FINAL_SEAL_SUMMARY.json)、[SOURCE_CHANGE_MANIFEST](m1_validation/20261010T101602Z-8dfa7d4f-3c6c-4f4c-ac5a-57a06afa3e9e/SOURCE_CHANGE_MANIFEST.json)、[EVIDENCE_MANIFEST](m1_validation/20261010T101602Z-8dfa7d4f-3c6c-4f4c-ac5a-57a06afa3e9e/EVIDENCE_MANIFEST.json)、[SHA256SUMS](m1_validation/20261010T101602Z-8dfa7d4f-3c6c-4f4c-ac5a-57a06afa3e9e/SHA256SUMS)、[SEAL_OUTPUTS_SHA256](m1_validation/20261010T101602Z-8dfa7d4f-3c6c-4f4c-ac5a-57a06afa3e9e/SEAL_OUTPUTS_SHA256.json)。仅普通文件，不跟随symlink。manifest/SUMS/自身summary与正在写入的final-seal-command为显式循环排除；命令结束后另做输出摘要闭合。本地seal不是第三方不可变来源证明。新代码仍在记录过的dirty branch，以文件SHA识别实际执行版本，不能冒称历史HEAD已含新实现。

**到M1停止。** 不进入B/C、GraphSwarm、FalkorDB/MCP、治理算法或正式对照实验。
