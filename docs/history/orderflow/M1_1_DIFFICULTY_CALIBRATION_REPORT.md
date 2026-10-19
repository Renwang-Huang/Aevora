# M1.1 Difficulty Calibration Report

本报告只描述六次真实、全新、串行的 D-v01 Session。原 M1 的 TIMEOUT / PASS / TIMEOUT 与两个独立 postmortem 不计入本次样本，也不改变历史成绩。时间均为 UTC；日期跨香港时区午夜不代表额外批次。

## 1. 冻结条件与分母

- 顺序 S/M/M/S/S/M；各组实际启动 3 个新 Session。S 禁用官方两个协作 feature、`agents.max_threads=1`，并核查全部终态原始 Session 文件无 child；M 使用官方原生协作。
- Gateway `gpt-5.6-terra`、`max`；没有静默回退。响应标签可验证，内部模型权重不可验证。
- `completion-aware`，Agent/内外 Watchdog/collector 总 wall deadline 为实际 `None`，总请求预算明确 `None`；并发、cgroup memory/pids、CPU/输出限制、TLS 与文件/网络隔离继续有效。
- Episode D-v01：Scenario 2.0.0、Fixture 1.0.0、隐藏 Suite 1.2.0、Evaluator 3.1.0，28 个必要测试身份，独立宿主 DB Oracle 和三个真实 crash/recovery 窗口。私有 Manifest SHA256：`a546ef66a541bb96bc6518988297d934d26421982160c0280903e29c8155b486`。
- 六轮业务源码、公开 Issue/TASK/Manifest/Tests 的封存输入哈希相同；模式相关 AGENTS 和角色配置不同。这是明确实验条件差异，不是完全相同提示词。原始配置、TLS、宿主负载和 source freeze before/after 记录均保留。运行期间没有额外维护者 heavy pytest/export/联网挑战。
- 首次 S 的真实 Provider 故障保留。随后 collector 在第 2 个 Session 启动前遇到 TLS 连接拒绝；同 endpoint 的独立恢复检查通过后，使用冻结 collector 接口继续剩余五次。它是**采集器续采，不是 Native Session resume，也没有替换失败 Session**。初次 collector exit 1、续采 exit 0 均保留。

## 2. 六次原始成绩

| 轮次 | 模式 | Run ID | Agent 秒 | 端到端秒 | Runtime | Hidden | 原始 verified children | 上游请求 | 已观测 Token |
|---|---|---|---:|---:|---|---|---:|---:|---:|
| 1 | S | `a23a8b03-e956-4403-b05f-2cb3941ad827` | 100.355 | 100.603 | ERROR | NOT_RUN | 0 | 12 | 36,838 |
| 2 | M | `64377ef0-3998-434c-936c-8011886b9cd2` | 835.454 | 875.570 | PASS | 28/28 PASS | 3 | 81 | 1,705,042 |
| 3 | M | `2c543377-5be5-4522-a3cf-bc8caf8c1cc3` | 1649.902 | 1690.938 | PASS | 28/28 PASS | 3 | 96 | 2,028,964 |
| 4 | S | `f238d8db-dc61-4aa3-9b99-ceb019e307e4` | 687.081 | 728.170 | PASS | 28/28 PASS | 0 | 15 | 318,329 |
| 5 | S | `47f36a9d-1be2-4405-ab8f-7d322ebc08e5` | 1011.246 | 1051.985 | PASS | 28/28 PASS | 0 | 25 | 536,950 |
| 6 | M | `eb647097-b595-43cd-b4a6-e5f0057ec5f0` | 1142.270 | 1183.701 | PASS | 28/28 PASS | 2 | 80 | 1,559,991 |

所有五份实际提交的提交保真、完整测试集合、宿主 DB Oracle、三个恢复窗口及 owned-resource cleanup 均通过。首轮无实际补丁、无 JUnit、Hidden NOT_RUN；不是 0/28，也不是工程修复 FAIL。Integration 为 PARTIAL，故障分类 PROVIDER_FAILURE。

M6 原归档为 3 spawned / 2 completed / 2 verified，保持原样。独立原始记录复核发现第三 investigator 有正常 final、task_complete 和父回执，四处原文精确匹配；单边 `.strip()` 导致解析假阴性。后置解析器修复、独立 reanalysis、完整回归另行归档，**不替换原 summary 或成绩**。未经修正地称第三 child 未完成是不成立的；请查看 `independent_review/runtime_final/` 的原始行 SHA 与更正记录。

## 3. 正确性与完成性分别评价

- S：全启动分母自然完成/自动任务 PASS **2/3**；Provider failure **1/3**。已实际评测提交 **2/2 PASS**。三个原始单 Agent 记录均核查 0 child。
- M：自然完成/自动任务 PASS **3/3**，已实际评测提交 **3/3 PASS**；每轮至少两个原始 verified native children，自己的工具活动、完成/回传与父接收均有原始引用。
- 总体自动闭环 **5/6**，实际提交正确性 **5/5**。两分母必须一起给出，不能剔除 Provider 故障展示 6/6。
- M3 Agent **1649.902 秒**后自然完成并 Hidden PASS，S5 **1011.246 秒**后自然完成并 Hidden PASS。这是自然任务实际跨旧阈值的证据，没有人为 sleep 延长任务。旧有界 M1 成绩不能与这组无总时限成绩合并。

## 4. 补丁与就绪观察

| 轮次 | Patch SHA256 | Applied expected tree SHA256 | 首次源码变化 Δ秒 | 当时 Hidden readiness |
|---|---|---|---:|---|
| 1 | `NOT_PRODUCED` | `NOT_SUBMITTED` | UNAVAILABLE | UNVERIFIED |
| 2 | `ff53f168da7274eacd1f6ce66774db4646a576b6bfd20b614398ee14c56d1061` | `84d5df6e1131e9601710f38e210c7afca6b45df0742daae6c2573b24b4ef4594` | 211.481 | UNVERIFIED |
| 3 | `7d97f28bd3c070887caa6258634a3331d1dc4654c41d46bbfaf5e4248d2d3e8d` | `f3ea5ebb005128b78c80820f68ce6d841f7c73ee139459f2107c49ab3d064d96` | 810.531 | UNVERIFIED |
| 4 | `594f899169cbf5b29983c8e9720d733eb177a8547dc29345c71feeead19cc99b` | `dc4c7c2235d9023dba47e9a2cd59e46f41f8aac678fc8f62ffa2f167ca8e04cc` | 323.611 | UNVERIFIED |
| 5 | `33dbb303ad7c01339048df94e20056a533b2aa2cbd5a8813c0bdb7a6efa71f27` | `7aaab9f51f1172ca1f2e569f270137d0bb179e52ca62f25b9a0a270a85cfaea6` | 260.301 | UNVERIFIED |
| 6 | `203b57e67854b42e9bc537c013e373ef5d433a7292b75e1c989ccb6881bb185d` | `ab0f77229304590d31bff8a39738fdff53fad8db9396447b6908fa365e2a5d41` | 545.160 | UNVERIFIED |

Δ秒来自可信观察时间与 Adapter 开始 UTC 的差值，不是精确代码线性化时间；快照明确非原子。第 4、6 轮首次树哈希后来与最终树相同，但当时没有运行 Hidden Evaluator，仍不能把“当时已通过”报告为事实。其他首次树与最终树不同。禁止用上述区间差值硬算纯思考/纯协作开销。

静态阅读五份**实际 Agent diff**：全部移除或忽略事务外库存 snapshot 对库存写入的授权，保留/使用同一事务中的条件相对 UPDATE。M2/M3/S5 删除冗余本地锁；S4/M6 保留本地锁，但跨进程正确性由 SQLite 更新和账本事务保障。可选 snapshot 参数有删除/兼容忽略两类；早期 SKU 验证/公开调度 hook 有保留/移除差异。它们是不同合法补丁形态，**不是五种独立根因修复策略**。无维护者补丁替换、人工修复或削弱隐藏测试。公开测试修改作为独立 diff 归档，不参与隐藏判分。

## 5. Provider 及资源观测

下表使用实际 REQUEST_FINISHED 记录，每请求只计一次。首 HTTP 响应不是整个模型请求完成；SSE gap 是观测到的传输间隔。并行请求总时长可能超过墙钟，union 也与工具/子 Agent 执行重叠。

| 轮次 | 首 HTTP 响应 median/max 秒 | 完整请求 max 秒 | 请求时长 sum/union 秒 | sampled CPU 秒 | sampled RSS peak MiB |
|---|---|---:|---|---:|---:|
| 1 | 6.795/7.876 | 29.990 | 96.713/96.713 | 9.71 | 362.07 |
| 2 | 12.401/31.439 | 89.176 | 1644.849/832.748 | 90.02 | 383.00 |
| 3 | 12.784/25.498 | 127.275 | 2969.608/1647.483 | 174.77 | 384.20 |
| 4 | 9.243/23.079 | 181.106 | 689.750/684.803 | 65.95 | 367.59 |
| 5 | 11.586/48.099 | 172.911 | 1015.480/1007.882 | 95.68 | 373.27 |
| 6 | 10.106/37.091 | 105.947 | 2120.127/1140.048 | 118.19 | 377.17 |

真实错误分布：

- 第 1 轮：`{"UPSTREAM_CONNECTION_ERROR": 4, "UPSTREAM_SERVER_ERROR": 2, "UPSTREAM_STREAM_INTERRUPTED": 1}`。
- 第 2 轮：`{"CLIENT_DISCONNECTED": 7, "UPSTREAM_STREAM_INTERRUPTED": 1}`。
- 第 3 轮：`{"CLIENT_DISCONNECTED": 8, "UPSTREAM_CONNECTION_ERROR": 1, "UPSTREAM_SERVER_ERROR": 2, "UPSTREAM_STREAM_INTERRUPTED": 2, "UPSTREAM_TIMEOUT": 2}`。
- 第 4 轮：`{}`。
- 第 5 轮：`{"UPSTREAM_SERVER_ERROR": 2}`。
- 第 6 轮：`{"CLIENT_DISCONNECTED": 8, "UPSTREAM_SERVER_ERROR": 1}`。

没有在六轮中观察到真实 429；429/Retry-After 恢复由真实官方 CLI + 受控本地 HTTP/SSE 的动态 probe 验证，不冒充联网 cohort 中出现过。CLIENT_DISCONNECTED 不能仅凭字段归因为 Gateway 或协作错误，精确原因 UNAVAILABLE。真实 127–181 秒完整请求没有被旧 Broker 120 秒总 deadline 武断终止。正常跨 1200 秒的 Agent 也没有总 wall TIMEOUT。

全 cohort 上游请求 **309**（按实际 Broker 计数，包含支持路由/失败尝试），官方可获取、按 response ID 全局去重的 usage：input **6,011,247**、output **174,867**、cached input **5,451,264**、reasoning output **121,859**、total **6,186,114**。cached/reasoning 是各自总量中的细分，不再相加到 total。中断而未暴露的 usage 不估造，因此不是完整账单。S 已观测 total 892,117；M 5,293,997。实际货币成本 **UNAVAILABLE**。

所有资源 violation 为 None；2 GiB physical memory、768 pids、600 秒 sampled CPU、128 MiB output 等限制保留。采样 RSS 不是内核实际物理峰值；内核限制与原始读数另见 metadata。代码/业务吞吐能力和资源成本须分开。

## 6. 难度信号与后续校准条件

五份可评测提交全部通过、修复机制收敛、Single 无经验也能解题，支持**本模型/本公开输入下可能存在 ceiling effect**的先导信号。真实 Buggy/错误控制被既有独立 Oracle 稳定识别、crash/ledger/multi-worker 不变量覆盖仍有工程价值；不能由“28 项”或单个 reference PASS 单独判任务质量。只有 6 个 Session、单模型、S 的 Provider 故障及不同时间负载/提示词条件，不足以证明一般难度低、M 优于 S、S 更省成本的普遍因果结论或经验治理收益。

完成 Session 的端到端中位数：S **890.077 秒**（n=2），M **1183.701 秒**（n=3）。仅为描述性数据，不能把差值叫纯协作开销；不同请求失败和重叠模型流、工具、审查均混在里面。网络首响应/流区间本身也包括服务侧计算，不能推断纯网络、纯思考分解。

未来正式方案：先冻结 v02 合法修复/错误因果 controls，完成独立 model-based Oracle、crash/retry 与可观测性 Gate，预注册输入/模型/资源/失败分母和随机交错顺序。可从每条件每变体 **至少 30 个独立 Session**的预算设计起步，再按先导方差、期望最小业务差异和预设置信精度做样本量计算；30 本身不保证统计显著性。要有 provider-failure 敏感性分析、全启动与可评测两分母、多次 host/时间段重复及不同合法策略实证。当前不实施该实验。

v02 推荐 lease/authority stale publish，备选 WAL backup/generation replacement；它们不能仅增加 Worker/参数。库存条件 UPDATE 的经验应可正迁移一部分事务能力，但单独做库存 UPDATE 不应修复过期授权和 receipt 一致性。v02 的工程/研究双审查是静态设计结论，实现、难度、迁移收益均 **UNVERIFIED**。

## 7. 原始证据和命令

Full Archive：`m1_1_validation/20261010T154658Z-4e5039eb-6ac2-49c7-8ece-824765e22f5f`。分析源 `m1_1_validation/20261010T154658Z-4e5039eb-6ac2-49c7-8ece-824765e22f5f/calibration_analysis/CALIBRATION_ANALYSIS.json`；原始 outcome `m1_1_validation/20261010T154658Z-4e5039eb-6ac2-49c7-8ece-824765e22f5f/R3_ORIGINAL_OUTCOMES.json`；逐行来源时间线 `m1_1_validation/20261010T154658Z-4e5039eb-6ac2-49c7-8ece-824765e22f5f/MULTI_AGENT_TIMELINE.json`。

- `calibration-command`：exit **1**，101.795 秒；完整实际 argv/stdout/stderr 见同目录。
- `gateway-recovery-command`：exit **0**，6.743 秒；完整实际 argv/stdout/stderr 见同目录。
- `calibration-continuation-command`：exit **0**，5535.841 秒；完整实际 argv/stdout/stderr 见同目录。
- `calibration-analysis-command`：exit **0**，1.536 秒；完整实际 argv/stdout/stderr 见同目录。

本次分析使用完整原始字段和 source-line hashes；最终轻量包与独立离线核验回执见 `M1_1_EVIDENCE_INDEX.json` 和 `M1_1_VALIDATION_REPORT.md`。含维护者审计数据，不得用作 Participant 输入。停止在 M1.1。
