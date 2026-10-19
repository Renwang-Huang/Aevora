# M1.1 Validation Report

**最终结论：PASS，限本阶段声明的运行时、归档、六 Session 先导校准和静态设计范围。**

报告生成于 2026-10-10T18:48:20.209826+00:00。R0–R4逐项留有真实回执与SHA。该结论不表示每次挑战成功、完全敌对安全通过、远端权重得到证明，或Single/Multi具有统计优势。首轮真实Provider故障完整保留；六次原始成绩不改写。已停止在M1.1。

## 1. 执行基线与保护

仓库分支 `m1-1-runtime-calibration-evidence`，既有HEAD `beba4fba73f2e59e0d5a7fb99aea332ad80ea2cf`。工作树包含继承M1改动和本阶段新增文件，没有提交/推送/reset/clean；HEAD不能代表未提交的挑战版本。实际版本由150文件LIVE_GATE、原样snapshot及每Run fingerprints标识。

- R0实际开发者664/664；上线前集成775/775；首次证据修复后836/836；最终 **856/856 PASS**，均无skip/error/failure，最终exit0/126.380秒。
- 实际逐字节重核 **38份旧测试、57份冻结任务真值、82,740份历史文件**，全部不变；原664必要测试身份完整保留。独立哈希校验exit0/33.990秒。
- 最终JUnit SHA256：`9468930a167e2a3b115c1f5508a0ca9308b671f8891dcb1b6e9c767835ead73d`。
- Python3.12.13 / SQLite3.46.1 / pytest9.1.1 / 官方Codex与Code Mode helper0.162.1：来源为本次实际环境与归档metadata；不会推断未来版本相同。
- D-v01 Scenario2.0.0 / Fixture1.0.0 / Suite1.2.0 / Evaluator3.1.0。私有Manifest SHA `a546ef66a541bb96bc6518988297d934d26421982160c0280903e29c8155b486`；Suite SHA `fd3bbaa0f48925ccee30e5b84e591396611259ae05c06df0e16ad117328d6303`；Evaluator SHA `0b8192d042ee53af1be052962103800c9bc2ea5abaf3770ad9255fb8e647606b`。

## 2. R0–R4 Gate 与证据性质

| Gate | 结论 | 真实依据与边界 |
|---|---|---|
| R0 | PASS | 原始M1三次TIMEOUT/PASS/TIMEOUT、664回归、源与历史基线；先定位各层deadline，再改代码 |
| R1 | PASS | 真正None总wall、支持慢首响应/SSE/429/取消、官方CLI本地控制探针、真实1649.902秒自然完成；实时child索引仍PARTIAL |
| R2 | PASS | 旧M1原始五记录Lite、新六Session Lite、独立空cwd/env Python-I verify/inspect、篡改exit2、固定时刻字节确定性、源未变；NOT_INCLUDED只指针 |
| R3 | PASS | 全新S3/M3，S/M/M/S/S/M串行交错，公开业务输入/私有Suite相同；5/6闭环、5/5实际提交正确，1Provider failure留分母 |
| R4 | PASS（仅静态） | 0.3.0规格，两候选，工程与研究独立审查；§2–12/14与已审0.2.0逐字相同，真实校准追加；未实现v02 |

本次新动态执行、历史记录、受控本地fixture、静态设计和UNVERIFIED分开记录。具体Gate为A内 `R0_GATE.json`、`R1_GATE.json`及后置修正Gate、`R2_GATE_FINAL.json`、`R3_GATE.json`、`R4_GATE.json`，和R内新六Session R2 Gate。

## 3. 工程修改与兼容性

1. Adapter/Watchdog/CLI明确bounded与completion-aware。默认bounded900秒/160请求保持；aware必须None，总wall与可选总request预算不会隐式触发。collector不再使用固定总采集时限。
2. Broker把有限连接/TLS与完成响应期限分开；连接建立后首HTTP响应与SSE不继承旧120秒timer。保留有限30秒connect、原生idle600000ms及retry各2，真实429/Retry-After透传并记录。永久错误有限退出；不能称为无任何网络期限。
3. 可信宿主status/snapshot/cancel绑定Run/control身份；不同PID namespace不盲信数值PID。分类CANCELLED_BY_OPERATOR、COLLECTOR_INTERRUPTED、真实Provider/resource/no-patch/invalid-submission，并清理owned进程、cgroup、Broker、socket和state。
4. 新进度/transport原始记录保留请求首响应、body间隔、终态、实际usage和只读源码快照；首树改动的hidden readiness为UNVERIFIED。并发request区间不能相加作墙钟，也不能由差值估纯推理。
5. Full与Lite分层，CAS/DEFLATE、标准库独立verifier；ZIP/JSON/XML/路径/成员预算和完整necessary-set校验拒绝删测试/伪造JUnit。只读源，不装Hidden/Reference源码或业务DB。
6. 六轮结束后的独立审查实际定位final单边strip及父回执substring缺陷。新增严格55+26边界测试；原测试不变，完整typed正文逐字比较。原M6 summary仍2verified；独立同raw重分析为3verified，原成绩/summary/seal不改。新parser不归属于六轮旧cohort。

| 文件 | 六次挑战cohort SHA | 后置修复最终SHA |
|---|---|---|
| `benchmark/evidence_verify.py` | `61c792cbd8c52b1983ec15e554b9ad632b6e5f62a26754e1b1921fcdf82c9660` | `f4d1b318758a542039a7c1874345811cccda96901d9a8b9c2f14d9bb871d4e42` |
| `integrations/native_rollout_trace.py` | `b83f080726d29069d70dc4d06f23182b075f7492616d0dcfc539744f33baf4f3` | `558b95953f37b92c30db675b8500518a7b03faaeff31b88b50ba468056f7cc1e` |

普通业务、Runner评测流程和独立Oracle真值仍冻结；Manual、Submission Fidelity、Smoke/A/D±/合法替代、B/C NOT_IMPLEMENTED、ERROR/TIMEOUT、归档/reset继续通过真实CLI和开发者回归。具体15项CLI与14项离线策略控制的内层预期退出状态保留，不能把外层exit0当所有任务PASS。

## 4. 实际执行命令与退出状态

`<A>` = `m1_1_validation/20261010T154658Z-4e5039eb-6ac2-49c7-8ece-824765e22f5f`；外部release `<R>` = `m1_1_validation/audit_exports/20261010T154658Z-4e5039eb-6ac2-49c7-8ece-824765e22f5f`。精确argv/cwd/UTC/start/end/stdout/stderr SHA在最终evidence index。表中的耗时是对应collector命令实测，不是纯Agent/模型时间。

| 回执目录（A下） | 实际argv（归档路径缩写） | exit | 秒 |
|---|---|---:|---:|
| `r0-developer-command` | `scripts/python312 -m pytest -q --junitxml=m1_1_validation/20261010T154658Z-4e5039eb-6ac2-49c7-8ece-824765e22f5f/r0-developer.junit.xml` | 0 | 125.028 |
| `developer-integrated-command` | `scripts/python312 -m pytest -q --junitxml=m1_1_validation/20261010T154658Z-4e5039eb-6ac2-49c7-8ece-824765e22f5f/developer-integrated.junit.xml` | 0 | 131.681 |
| `developer-postcalibration-command` | `scripts/python312 -m pytest -q --junitxml=m1_1_validation/20261010T154658Z-4e5039eb-6ac2-49c7-8ece-824765e22f5f/developer-postcalibration.junit.xml` | 0 | 124.613 |
| `developer-final-command` | `scripts/python312 -m pytest -q --junitxml=m1_1_validation/20261010T154658Z-4e5039eb-6ac2-49c7-8ece-824765e22f5f/developer-final.junit.xml` | 0 | 126.380 |
| `integrity-final-command` | `python3 scripts/m11_integrity.py m1_1_validation/20261010T154658Z-4e5039eb-6ac2-49c7-8ece-824765e22f5f m1_1_validation/20261010T154658Z-4e5039eb-6ac2-49c7-8ece-824765e22f5f/developer-final.junit.xml m1_1_validation/20261010T154658Z-4e5039eb-6ac2-49c7-8ece-824765e22f5f/INTEGRITY_FINAL.json` | 0 | 33.990 |
| `dependencies-final-command` | `scripts/python312 -m pip check` | 0 | 0.317 |
| `cli-regression-command` | `python3 scripts/m11_cli_regression.py m1_1_validation/20261010T154658Z-4e5039eb-6ac2-49c7-8ece-824765e22f5f/cli-regression` | 0 | 174.108 |
| `offline-regression-command` | `scripts/python312 scripts/m1_offline_regression.py m1_1_validation/20261010T154658Z-4e5039eb-6ac2-49c7-8ece-824765e22f5f/offline-regression` | 0 | 290.887 |
| `isolation-command` | `env ORDERFLOW_ENABLE_CODEX=1 scripts/python312 scripts/m1_isolation.py m1_1_validation/20261010T154658Z-4e5039eb-6ac2-49c7-8ece-824765e22f5f/isolation` | 0 | 1.246 |
| `cross-namespace-control-accepted-command` | `python3 scripts/m11_control_cli_probe.py m1_1_validation/20261010T154658Z-4e5039eb-6ac2-49c7-8ece-824765e22f5f/cross-namespace-control-accepted` | 0 | 1.445 |
| `r1-official-matrix-command` | `python3 m1_1_validation/20261010T154658Z-4e5039eb-6ac2-49c7-8ece-824765e22f5f/r1_transport_matrix.py m1_1_validation/20261010T154658Z-4e5039eb-6ac2-49c7-8ece-824765e22f5f` | 1 | 12.242 |
| `r1-official-permanent-auth-final-command` | `python3 scripts/m11_codex_transport_probe.py m1_1_validation/20261010T154658Z-4e5039eb-6ac2-49c7-8ece-824765e22f5f/r1-official-permanent-auth-final --scenario permanent-auth` | 0 | 2.016 |
| `gateway-connectivity-command` | `env ORDERFLOW_ENABLE_CODEX=1 scripts/python312 scripts/m11_gateway_probe.py m1_1_validation/20261010T154658Z-4e5039eb-6ac2-49c7-8ece-824765e22f5f/gateway-connectivity` | 0 | 8.788 |
| `calibration-command` | `env ORDERFLOW_ENABLE_CODEX=1 scripts/python312 scripts/m11_calibration.py m1_1_validation/20261010T154658Z-4e5039eb-6ac2-49c7-8ece-824765e22f5f/calibration --gate m1_1_validation/20261010T154658Z-4e5039eb-6ac2-49c7-8ece-824765e22f5f/LIVE_GATE.json` | 1 | 101.795 |
| `gateway-recovery-command` | `env ORDERFLOW_ENABLE_CODEX=1 scripts/python312 scripts/m11_gateway_probe.py m1_1_validation/20261010T154658Z-4e5039eb-6ac2-49c7-8ece-824765e22f5f/gateway-recovery` | 0 | 6.743 |
| `calibration-continuation-command` | `env ORDERFLOW_ENABLE_CODEX=1 scripts/python312 m1_1_validation/20261010T154658Z-4e5039eb-6ac2-49c7-8ece-824765e22f5f/continue_calibration.py m1_1_validation/20261010T154658Z-4e5039eb-6ac2-49c7-8ece-824765e22f5f/calibration-continuation --gate m1_1_validation/20261010T154658Z-4e5039eb-6ac2-49c7-8ece-824765e22f5f/LIVE_GATE.json --prior m1_1_validation/20261010T154658Z-4e5039eb-6ac2-49c7-8ece-824765e22f5f/calibration` | 0 | 5535.841 |
| `calibration-analysis-command` | `python3 m1_1_validation/20261010T154658Z-4e5039eb-6ac2-49c7-8ece-824765e22f5f/analyze_calibration.py` | 0 | 1.536 |
| `preseal-gates-command` | `python3 m1_1_validation/20261010T154658Z-4e5039eb-6ac2-49c7-8ece-824765e22f5f/finalize_preseal.py` | 0 | 0.970 |

`r1-official-matrix-command`初始exit1源于401重试次数假设错误：当前真实官方CLI按已配置两次reconnect总共3次401。7个原始单项探针最终动态检查通过（永久401命令的原生exit1是预期，wrapper最终exit0）；不删首次失败。

- CLI15：Smoke/A/D Buggy均实际exit1，Reference与D-flock实际exit0，B/C实际exit4，非法提交exit2，Evaluator TIMEOUT exit3，prepare/report/reset按协议正常。
- Offline14：A-local-lock/atomic/natural正控、D跨进程错误local-lock迁移FAIL、D真实atomic迁移与合法custom事务PASS、fake success/refuse-workers FAIL。其内层命令、RunID和JUnit原件在A/offline-regression。
- 三层隔离7项实际探针exit0；使用自建canary和假凭据，不让不可信程序读取真实项目密钥。可信宿主项目密钥只在内存，Full扫描无命中，且没有留密钥摘要。
- 跨namespace cancel实际关闭工作parent+child/cgroup/socket/state；与真实模型协作证据区分，标明NO_CODEX_MODEL_CALLS。

## 5. 六次真实新Session与难度

| trial | mode | Run ID | Runtime | Hidden | Agent秒 | 端到端秒 | 原始verified child |
|---|---|---|---|---|---:|---:|---:|
| 1 | S | `a23a8b03-e956-4403-b05f-2cb3941ad827` | ERROR | NOT_RUN | 100.355 | 100.603 | 0 |
| 2 | M | `64377ef0-3998-434c-936c-8011886b9cd2` | PASS | PASS 28/28 | 835.454 | 875.570 | 3 |
| 3 | M | `2c543377-5be5-4522-a3cf-bc8caf8c1cc3` | PASS | PASS 28/28 | 1649.902 | 1690.938 | 3 |
| 4 | S | `f238d8db-dc61-4aa3-9b99-ceb019e307e4` | PASS | PASS 28/28 | 687.081 | 728.170 | 0 |
| 5 | S | `47f36a9d-1be2-4405-ab8f-7d322ebc08e5` | PASS | PASS 28/28 | 1011.246 | 1051.985 | 0 |
| 6 | M | `eb647097-b595-43cd-b4a6-e5f0057ec5f0` | PASS | PASS 28/28 | 1142.270 | 1183.701 | 2 |

三个S均官方配置禁用原生child，原始自身Session记录0child；三个M使用官方真实Subagent，不把维护者开发agent计入。原verified 3/3/2满足每M至少2的证据要求；末轮第三child是原解析假阴性，独立修复证明完整正文回传，另存不改原summary。

第一轮`PROVIDER_FAILURE`，无补丁/JUnit、NOT_RUN，不是0/28或软件修复FAIL。初始collector随后在第二Session前遇同endpoint TLS拒绝，exit1；实际TLS/SSE恢复检查通过才续采剩余五Session，exit0。续采是operator collector continuation，不是native resume，也没有替换失败Session或降级model/effort/TLS。

M3自然运行1649.902秒，1361.641秒运行中快照仍为ACTIVE/SSE、wall=None，最后28/28PASS；证明旧1200阈值不再武断中断。六次全部owned清理/每Run seal通过。旧M1有界1/3不得与新5/6合并。

任务正确性分母5/5；S全启动2/3、可评测2/2，M3/3。已观测实际per-response去重总Token6,186,114，上游309请求；缺失失败usage不估造，cached/reasoning为子项不重复加总。费用与远端权重UNAVAILABLE/UNVERIFIED。五实际补丁均采用库存条件相对更新与事务账本原子性，合法代码形态不同而因果策略收敛；本模型/公开条件可能ceiling，但六样本不足以宣称一般难度低、Single/Multi显著优劣或治理收益。详细请求区间、CPU/RSS、五patch/tree SHA和首改动时刻见校准报告。

## 6. Full Archive、Audit-Lite与独立验收

Full实际封存 **8,116普通文件 / 1,076,365,987 bytes**，另4个停止隔离fixture helper符号链接仅封存link-text元数据，target bytes NOT_READ。原始scan拒绝符号链接exit1完整保留；无跟随的新扫描exit0，普通来源/导出仍拒绝symlink、hardlink或非普通文件。没有移除或改写原测试证据。

Full manifest SHA `65171f3cff02fcc87b47ca4e75a5d7bf0e5103bd621ad0bf21efeabe07c597c0`；SUMS SHA `049f9cfdc581258bd335620603583164012f4df7b8f0af8d1b95e84626bc9da9`。封存后禁止任何写入A；所有新导出/验证/最终report副本和release seal仅在R。源码及历史保护哈希与Full hash是本地一致性，不是第三方执行存证。

| Audit-Lite | bytes | ZIP SHA256 |
|---|---:|---|
| 原M1三个TIMEOUT/PASS/TIMEOUT + 两个独立postmortem | 12,743,304 | `0906688bcf4a9a1c6ef0a6f5ed91b9498b5a3b6c668e664283ef1d8727dc2dc3` |
| 本次六Session，包含首轮ERROR/NOT_RUN | 16,812,105 | `678e6a0741a63effd492ff7b4a0d29498a4fb6ea7b83263eeb1f3962f4452f0f` |

旧M1 Lite相对6,444,877,841逻辑字节缩减99.8023%；新Lite相对本次Full缩减 **98.4381%**。相同固定created-at第二完整导出字节一致。可信仓库独立复制verifier、空cwd/env、Python-I实际verify/inspect exit0；README单字节篡改真实exit2。实际选中2,353源文件、1,570内容对象、1,576 ZIP成员，5,763项NOT_INCLUDED只为指针。关键sources前后SHA检查通过，主Agent随后独立重哈希Full全部8,116普通文件和4链接元数据，实际exit0/0.973秒，封存后无新增/缺失/修改；见R/FULL_POST_EXPORT_VERIFICATION.json。完整执行见R/R2_NEW_SIX_SESSION_GATE.json，included/sanitized与omitted pointers明确区分。

| 外部release真实回执 | exit | 秒 |
|---|---:|---:|
| `determinism-command` | 0 | 37.401 |
| `export-command` | 0 | 36.685 |
| `export-help-command` | 0 | 0.117 |
| `export-help-failed-command` | 2 | 0.120 |
| `final-offline-dynamic-command` | 0 | 11.449 |
| `full-postexport-verification-command` | 0 | 0.973 |
| `full-seal-command` | 0 | 1.202 |
| `full-secret-scan-command` | 1 | 3.038 |
| `full-secret-scan-nofollow-command` | 0 | 0.876 |
| `lite-secret-scan-command` | 0 | 0.508 |
| `pre-export-command` | 0 | 0.575 |

Full项目密钥精确及base64/hex/URL encoding扫描无命中，4链接只扫描link text不读target。新Lite实际解压成员扫描无命中；不证明任意加密/分片、未知秘密或全部恶意通道。Audit-Lite为MAINTAINER_AUDIT，禁止给Participant。

## 7. 失败记录与未验证事项

所有开发失败和负控保留，包括首次fixture/collector/CLI问题、selector/`.git`binary选择拒绝、collection语法错误、401次数假设、Provider outage、final文本边界修前失败、最后归档symlink拒绝及metadata helper错误路径假设。实际命令/exit/stdout/stderr纳入evidence index；修复定位后重跑，没有删旧测试、降低断言或把失败Run换成参考补丁。预期负控非零与未预期开发失败分别解释。

- live Code Mode child indexing PARTIAL；opaque初始任务正文UNAVAILABLE；最终自身工作/typed完成/父回传可核验。
- First patch hidden readiness UNVERIFIED；纯推理/协作开销精确分离UNAVAILABLE；request overlap不算串行成本。
- Namespaces/cgroups非VM或全部对抗攻击证明；CPU/output采样/普通Candidate限额保持旧声明。SIGKILL/断电恢复或native resume未实现。有限connect/idle/retry/resource仍可真实终止异常。
- Unsupported SQLite commit/recovery observer通道（例如不透明C扩展）维持RECOVERY_EVIDENCE_UNVERIFIED/ERROR边界；不能升级为业务PASS或按证据缺失推测修复失败。
- Gateway/model/effort标签可观察，真实权重/账单不可证明；六试验无统计显著性，正式样本量与变体设计仅未来计划。
- Lite只验证included evidence；NOT_INCLUDED/source pointer、删敏前原文、本地hash起点及历史真实性不能仅凭该包独立证明。
- D-v02只完成设计及工程/研究双审查，业务实现、实际难度、策略判别和经验迁移效果UNVERIFIED。SQLite未来backup场景需新环境冻结，不能据推测改旧结果。

## 8. 交付与停止

- [基线与失效假设](M1_1_BASELINE_AND_FAILURE_HYPOTHESES.md)、[长运行策略](docs/LONG_RUNNING_CODEX_POLICY.md)、[证据导出规范](docs/EVIDENCE_EXPORT_POLICY.md)。
- [六Session校准报告](M1_1_DIFFICULTY_CALIBRATION_REPORT.md)、[剩余事项](M1_1_REMAINING_ISSUES.md)、`M1_1_EVIDENCE_INDEX.json`。
- [D-v02设计](docs/EPISODE_D_V02_DESIGN.md)、[双审查及版本记录](docs/EPISODE_D_V02_DESIGN_REVIEW.md)，推荐lease/authority、备选WALbackup/generation；仅设计。
- 新Full源、两个轻量示例、确定性/篡改/离线receipt、精确patch SHA、原生timeline及current/cohort源码指纹分层保存；AGENTS.md补充当前维护规则。

**到M1.1停止。没有开发B/C、D-v02实现、GraphSwarm/FalkorDB/MCP或G0–G3正式实验；没有追加联网挑战，也没有改变旧M1三次正式成绩。**
