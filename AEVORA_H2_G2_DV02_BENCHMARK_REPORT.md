# Aevora H2-G2 — D-v02 独立 Benchmark 验收

## 结论与版本

**G2：PASS（本报告声明的动态边界内）**。D-v02 是 D 家族内新增的 lease/authority 事故，不是跨所有故障家族的泛化证明。B/C 仍 NOT_IMPLEMENTED。公共场景、Fixture 为 1.0.0；最终 Suite / Oracle 为 **1.1.1**，必要隐藏测试 **36**，必要恢复矩阵 **8**。历史 D-v01、A、Smoke 真值不变。

本轮 Full Archive 为 `aevora_validation/H2-20261011T082213Z-6bd12e96-82e1-4c87-b1df-67bc7fa74ae9/`（下文 A）。`G2_GATE.json` 对实际收据逐文件 SHA256 绑定；不能仅以本段结论代替收据核验。

## 实际工程事故与合法策略

独立 OS Worker 共享 SQLite。claim/renew/complete/cancel/get 五个新公开操作使用永久 request payload、唯一历史 token 和共享权威 Clock。缺陷版本保留库存事务和约束，但错误地把历史曾发放的 token 当作当前发布权；过期、接管、取消或重启后的旧处理者可以实际破坏 request/business 的对应关系。盲目清理另可撤销新处理者的权利。错误来自实际代码执行和真实数据库，不是伪造库存、异常或测试结果。

Reference 在允许的事务边界内校验当前权限并原子发布。另一个合法实现使用合作式稳定 inode flock 和相应状态保护。Oracle 不要求特定锁、固定 SQL、token 数值或事务次数。进程内 RLock 不能保护不同 Worker；inventory_only 明确与已具有库存事务的 Buggy 字节相同，未伪装成独立修复。

公共输入见 `benchmark/scenarios/D-V02/`、`tests/public/test_episode_d_v02.py`；维护者规范 `docs/AEVORA_H2_DV02_TASK_SPEC.md` 与 Usage 分开。Fixture 在 `benchmark/episodes/episode_d_v02.py` 与 `dv02_public/`，不修改旧根目录 app。私有 Oracle、Hidden Suite、Reference、策略标签不进入 Participant。

## 真实调度与独立真值

- 2/4 个实际独立进程、相同数据库 device/inode、kernel peer PID、pidfd 和 Worker generation，不能用候选自报身份替代。
- 在 claim ACK 后，宿主于两次普通调用之间 SIGSTOP 旧处理者，推进只读查询 Clock，确认接管/取消，再 SIGCONT 旧处理者发起迟到调用。
- 新传输复用旧 Worker/control/SQLite observer。八个恢复窗口覆盖真实 write、commit、before_response 和 stale-cleanup；现有未预留订单的已提交恢复状态由可信 before/after 数据库检查。
- 宿主停止/中断候选后直接读取 SQLite 的库存、订单、账本、request、claim-history、typed receipt、约束和历史。候选 audit() 不决定成绩。
- 缺失必要提交观测的 native SQLite 变体得到 infrastructure ERROR，不当作工程 FAIL，也不能得到 PASS。

SQLite 独立连接只观察已提交状态、写入串行化等语义以[官方 SQLite 隔离文档](https://www.sqlite.org/isolation.html)为依据；本报告的故障和判分来自实际进程及数据库记录。

## 最终 Suite 1.1.1 的实际分母

| 控制 | 独立完整 Run 数 | 实际成绩 | 每轮必要项 |
|---|---:|---|---:|
| Buggy | 10 | 10 FAIL，各 28 PASS / 8 FAIL | 36 |
| Reference，最终重复系列 | 10 | 10 PASS | 36 |
| local_lock | 10 | 10 FAIL，各 28 PASS / 8 FAIL | 36 |
| Reference，独立公平性控制 | 1 | PASS | 36 |
| flock，独立合法替代 | 1 | PASS | 36 |
| blind_cleanup | 1 | FAIL，31 PASS / 5 FAIL | 36 |
| DELETE→COMMIT→reinsert | 1 | FAIL，35 PASS / 1 FAIL | 36 |

最终重复系列为 30 个唯一 Run，共 **1080 case：920 PASS、160 FAIL、0 ERROR、0 skip**，全部八窗口 COMPLETE，执行源 before/after 相同。`g2/suite111-30-runs/ATTEMPTS.jsonl` 保存每轮 UUID、真实退出、失败原因、报告 SHA、补丁 SHA 和 fingerprint。flock 仅在最终 1.1.1 声称一次；1.1.0 的十次不混入。

当前 fingerprint：`51d09e225e43e778f452f69da1be3c5ad7c798aa250bb044933f36e7a66ba7e8`。最终重复 SUMMARY SHA256：`e60712d131da804f7e54fca15c84b1b50f2bb417bb4165a50a6df84d644728d7`。

公平性 Run：Reference `025fbaff-2174-4987-ba7d-e81d94a65686`、flock `6d785236-35f4-4753-bf16-732dbd1f63d5`；删除负控 `44729ac4-58c9-45c3-9353-2b55ef7583b7`、盲目清理 `da312292-501c-4616-a0f1-5dd8196ea4e9`。数量/生命周期修改各 scoped 1 FAIL，audit-only scoped 1 PASS、opaque observer scoped 1 SETUP ERROR，明确不是新增完整 Benchmark 成绩。

## 发现缺口、修复与保留的失败

初次 1.0.0 的 35×40 系列业务正反结果符合预期，但采集器因两个 G3 开发者测试在执行期间变化实际退出 1；原 SUMMARY FAIL 保留，不能升格为最终冻结验收。另有八个早期 Runner ERROR，分别由恢复 wrapper 对矩阵阶段/嵌套 cleanup 记录的错误假设产生；原报告和 JUnit 保留，修复在新增 D-v02 admission 中完成。

独立审查发现仅排除既有订单的发布判据漏掉“既有未预留订单先预留再提交、收据后写”。新 1.1.0 加入必要第 36 项和第八窗口。1.1.0 独立 40 Run 为 Buggy10FAIL、Reference10PASS、flock10PASS、local_lock10FAIL；每轮36、无 ERROR/skip、源码不变。真实引用及 320 个 kernel/FD 窗口独立核验，旧版本保留删除漏洞 OPEN。

审查又以真实 SQLite DELETE+COMMIT 确认既有合法订单消失可能仍被旧 publication predicate 接受。1.1.1 最小修复要求 sole-complete-writer 窗口内 ACK 订单身份、typed payload 和合法生命周期保留；保留全部36身份/8要求及 Hidden Suite 字节，添加4项 Oracle developer cases，不影响无业务效果的审计事务。真实完整候选删除→提交→重建被 FAIL 识别；旧 helper 仅在本次新负控数据库用于诊断，不重新评判历史 Run。

报告/reader 的错误列名、格式假设、opaque observation ERROR，以及 Source Release 收据目录碰撞均保留真实失败。新收据使用独立目录，不覆盖原件；没有删除困难测试或放宽断言。

## 当前回归与干净重建

- 当前完整开发者测试 **1625/1625 PASS**，0 ERROR/skip，原1214身份保留。JUnit SHA：`a5f6c70d6f2e1389a4e933ce94b28a81e0640fd7cbbca18db9454257e12028bf`。
- 15项实际继承 CLI 检查全部达到预期：Smoke8/A14/D-v0128 正反、flock、B/C NOT_IMPLEMENTED、ERROR、TIMEOUT、prepare/report/reset。
- `G2_SUITE111_HISTORY_IDENTITY_GATE.json` 实际核验101084历史文件、58旧测试源、57任务真值以及1214必要身份。
- 源码提交 `f09f395318c87a788eef26bfdb04029ab584934e` 在独立 release Git 中产生；用户原始 Git index 未 staging。新 clone、独立非system-site venv、无个人缓存的公开安装、真实图查询和全部1625测试共8个阶段实际通过。干净 JUnit SHA：`1531c74d86ce3198a8fe10c9d83f3cfe0b5c45c0f413e5e41a5436f47e85a54f`。
- 新隔离 epoch 实际74检查/134契约通过，三层分别拒绝41受保护路径、18非法 Clock 请求无状态变化；总体共享内核安全仍PARTIAL。不得据此宣称模型或子Agent已运行。

## 实际命令与退出

完整 argv、cwd、起止时间、stdout/stderr SHA 均保存对应 `command.json`，环境均为独立 Python3.12.14 / SQLite3.51.3、真实H2 FalkorDB17679。

| 实际命令主体 | 收据 | 退出 / 秒 |
|---|---|---:|
| `aevora-h2-python -m scripts.aevora_h2_dv02_validation ... --repetitions 10 --strategy buggy --strategy reference --strategy local_lock` | `g2-suite111-30-independent-runs/command.json` | 0 / 1128.168034 |
| `aevora-h2-python -m scripts.aevora_h2_governance --pause-auto-save tests ... -q tests aevora_core/tests` | `g2-suite111-full-project-final/command.json` | 0 / 178.902541 |
| `aevora-h2-python -m scripts.aevora_h2_cli_regression ... --cli-module benchmark.h2_cli` | `g2-suite111-inherited-cli/command.json` | 0 / 179.822404 |
| `python3 aevora_core/scripts/rebuild_h2.py ... --source-commit f09f395318c87a788eef26bfdb04029ab584934e --recorded-graph-maintenance` | `g2-suite111-clean-rebuild/command.json` | 0 / 236.021873 |
| `aevora-h2-python -m scripts.aevora_h2_dv02_security all ... --archive ...` | `g3-dv02-security-suite111-final/command.json` | 0 / 37.146874 |

最简复现入口与所有必要公开/私有边界见 `docs/AEVORA_H2_DV02_USAGE.md`。Reference补丁仅供可信维护者验证。Oracle策略覆盖、EOL运行时、共享内核、AOF及统计收益的限制见 `AEVORA_H2_LIMITATIONS.md`。

本报告不赋予G3联网、Trusted Feedback或跨Session回读成绩；它们由G3独立新Run验收。
