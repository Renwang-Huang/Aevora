# M1 Episode D — 三次独立 Codex 盲测报告

**最终：三次真实挑战已结束，原自动闭环 1/3。** 两次超时产物另起离线评测通过，不升级原成绩。

## 1. 冻结输入、真实环境与预算

官方 Codex CLI **0.162.1** 与同版本 Code Mode host；Gateway **gpt-5.6-terra / max**，无静默降级。顺序执行三 Trial，每次新 Run/Lead Thread/Participant/CODEX_HOME，不继承维护者对话；Agent wall1200秒、上游160请求、模型并发最多4、collector1380秒。Scenario2.0.0 / Fixture1.0.0 / Suite1.2.0 / Evaluator3.1.0 / Observer1.1.0。136份冻结源每轮前后均无漂移。

Participant只有公开app、中性Issue/Public Manifest/Public Tests/授权角色配置，不含私有答案。三份精确stdin SHA均为 `ae4c47e7f393e4666579358f2d5ca37d3a8bd0ef3bdb42bd8404b20ec691d737`；公开Manifest SHA均为 `9440313fcebc545ea02d1ef357492a39a8708cae09a9ef3d8f3811d875ae1e89`。见 [PILOT_INPUT_COMPARISON.json](m1_validation/20261010T101602Z-8dfa7d4f-3c6c-4f4c-ac5a-57a06afa3e9e/PILOT_INPUT_COMPARISON.json) 与 [LIVE_GATE.json](m1_validation/20261010T101602Z-8dfa7d4f-3c6c-4f4c-ac5a-57a06afa3e9e/LIVE_GATE.json)。

Participant内核memory2GiB/pids768；CPU600为RLIMIT/采样，本机没有委派CPU controller；2TiB AS是官方helper的虚拟地址空间限制。D Worker池另有内核memory/pids。长期密钥仅可信Broker持有，Participant只有限额每Run通道。归档无密钥内容或摘要。

## 2. 原始联网结果（全部三次为分母）

| Trial | Run ID | CLI退出 / Agent实际秒 | Runtime / Multi-Agent / Integration | 原正式隐藏任务 |
|---|---|---|---|---|
| 1 | `fbaae2cb-586f-4573-9cda-035eb7f608a0` | 3 / 1201.01 | TIMEOUT / PARTIAL / PARTIAL | NOT_RUN；原overall TIMEOUT |
| 2 | `48cddbed-6410-44e1-b860-142edef5e3ab` | 0 / 1139.12 | PASS / PASS / PASS | 28/28 PASS，三个恢复点COMPLETE |
| 3 | `463674bc-afba-4959-bb63-cda945c63b5a` | 3 / 1201.10 | TIMEOUT / PARTIAL / PARTIAL | NOT_RUN；原overall TIMEOUT |

原Runtime PASS / Multi-Agent PASS / 自动Integration PASS各 **1/3**。第1/3轮真实wall_seconds1200触发，Runtime exit -9 / CLI exit3，未耗尽160请求；原评测未启动，不是Agent补丁FAIL。三Run的cgroup cleanup_complete为true、remaining_pids为空、模型状态目录已移除。没有第四次补考或Reference替换。

## 3. 原生协作证据

官方结构化session_meta/parent来源、SubAgentActivity、child自己的own-turn工具活动、task_complete/最终结果和Lead实际收到回传共同核验；排除子卷宗继承的父历史。开发子Agent不计作Participant。

| Trial | Lead Thread | Child ID / 原生路径 | 自身执行 / 正常完成 / 回传 / verified |
|---|---|---|---|
| 1 | `01a125a6-c480-7ea1-8cf7-3c932b11b06c` | `01a125ab-e120-7612-a13e-55546edd89bb` / `/root/investigator` | True / True / 正常结果 / True |
| 1 | `01a125a6-c480-7ea1-8cf7-3c932b11b06c` | `01a125ac-0539-73b1-8102-1901d669b7d5` / `/root/test_engineer` | True / True / 正常结果 / True |
| 1 | `01a125a6-c480-7ea1-8cf7-3c932b11b06c` | `01a125b5-a50e-7e90-a669-84adcdb21392` / `/root/reviewer` | True / False / UNAVAILABLE / False |
| 2 | `01a125b9-192c-7d32-b348-7136814388f4` | `01a125b9-d5e6-7c82-916e-895549cdbec7` / `/root/concurrency_investigator` | True / True / 正常结果 / True |
| 2 | `01a125b9-192c-7d32-b348-7136814388f4` | `01a125b9-fd70-7321-b4b9-10a7fd7ba62f` / `/root/regression_engineer` | True / True / 正常结果 / True |
| 2 | `01a125b9-192c-7d32-b348-7136814388f4` | `01a125bd-c82e-7061-bcb4-43cae6ebfd70` / `/root/patch_reviewer` | True / True / 正常结果 / True |
| 3 | `01a125cb-1891-7de0-b9ca-da93c83add9a` | `01a125cc-60be-77c2-a041-7bbede9a17f3` / `/root/investigator` | True / True / 正常结果 / True |
| 3 | `01a125cb-1891-7de0-b9ca-da93c83add9a` | `01a125cc-8609-7703-a6b2-d563dac73dbe` / `/root/test_engineer` | True / False / 异常结果 / False |
| 3 | `01a125cb-1891-7de0-b9ca-da93c83add9a` | `01a125d7-dc2f-74b0-b00e-126eb074f641` / `/root/reviewer` | True / False / UNAVAILABLE / False |

已核验正常完成/回传为 **2 / 3 / 1**；三轮每个child均有独立自身活动。第2轮三个child完整；第1/3轮exec流未结束turn/item，formal Multi-Agent为PARTIAL。第3轮Test Engineer虽有task_complete形式记录，其final为null/429 retry-exhausted，主Agent收到的是失败回执，不能算成功完成；第2轮Investigator早期也发生过429，后续own-turn取得正常完成，原异常保留。

原始JSONL、native_rollout_summary、native_agent_trace、artifacts/native_rollouts均保留。[可读时间线](m1_validation/20261010T101602Z-8dfa7d4f-3c6c-4f4c-ac5a-57a06afa3e9e/MULTI_AGENT_TIMELINE.md) 与 [612条结构化native事件](m1_validation/20261010T101602Z-8dfa7d4f-3c6c-4f4c-ac5a-57a06afa3e9e/MULTI_AGENT_TIMELINE.json) 含原文件、行号、行hash与关联。初始任务正文为加密content，task plaintext **UNAVAILABLE**，不猜测或破解；实际自身执行、完成、回传按各自证据判断。

## 4. 实际补丁、提交保真与独立postmortem

| Trial / 评测类型 | Patch SHA256 | expected = applied tree SHA256 | 结果 / Run |
|---|---|---|---|
| 2 / 原正式自动 | `2d5739ae86ffd03414854c6c0764ed2b1e32b475274bf190376cbd5b85b30cfe` | `fb8a5afc7dea1a456578af911ae76684de351ea48b838e4d167bf037c10c4041` | 28PASS / `48cddbed-6410-44e1-b860-142edef5e3ab` |
| 1 / 独立离线postmortem | `782541b3914df52c38e952477b44ed79948ddcf8e41e950bce4579ede5a5bced` | `5de3d24350c46fb3d979a9f7e88f38d3edfba026474502b73201132711404fd6` | 28PASS / `93c081b5-5102-4ac9-b5b4-01126ebf9740` |
| 3 / 独立离线postmortem | `1b7dac99810d6b310a34ca6eac55f2ad691e11bc0b171f377005740d9d07c80a` | `b6e4882275248f69bba688a59f8ef3977ded7edc7f52d8578b9a2f206e662037` | 28PASS / `65c82b38-efd2-4538-9930-38cd20d89012` |

第二轮真实修改app/inventory.py与app/service.py，严格diff解释、干净Git、逐文件字节/树比较及原子发布PASS。第1/3轮先确认进程停止与清理，从残留Participant相对于各自缺陷基线提取原样app差异，补丁与新Run只写 **postmortem/**。没有人工改代码、Reference替换或修改冻结suite。各原Run129个普通文件提取前后哈希不变；新离线Run均28PASS、三个真实崩溃窗口COMPLETE。

见 [POSTMORTEM_RESULTS.json](m1_validation/20261010T101602Z-8dfa7d4f-3c6c-4f4c-ac5a-57a06afa3e9e/POSTMORTEM_RESULTS.json)。**原正式成绩仍TIMEOUT/NOT_RUN；原自动成功率不升级到3/3。** 三份实际Agent代码通过Oracle只说明样本代码可解性，不能证明三个Agent都在预算内完成协作和正式提交。

## 5. 真实请求、Tokens、耗时与成本

| Trial | 上游请求/预算 | native去重 total / input / cached / output / reasoning |
|---|---:|---|
| 1 | 77/160 | 1,283,911 / 1,247,262 / 1,063,936 / 36,649 / 24,114 |
| 2 | 89/160 | 1,671,288 / 1,632,727 / 1,471,488 / 38,561 / 22,999 |
| 3 | 82/160 | 1,560,227 / 1,523,246 / 1,377,792 / 36,981 / 24,437 |

Tokens来自官方native按response ID去重reported usage；cached/reasoning是对应input/output组成部分，不能再相加，也不能与同一请求的Broker usage重复累加。货币成本 **UNAVAILABLE**，没有Provider账单。成功响应声明effective model/effort均为gpt-5.6-terra/max、TLS验证开启，无fallback；底层实际模型权重 **UNVERIFIED**。

第1轮有REQUEST_WALL_TIMEOUT、UPSTREAM_TIMEOUT和SERVER_ERROR；第2轮发生瞬态错误后正常闭环；第3轮另有实际429子任务失败。Error counters可能属于同一请求多个阶段，不相加当独立失败请求数。墙钟同时受模型连接、调查/复现/审查与收尾影响，本轮没有充分证据定量分摊原因。第一轮离线复测实际在12:14:30–12:15:07 UTC与第二轮联网挑战重叠。三个联网Session仍是顺序启动，但宿主并非全程空载；不能据此作精确延迟或纯任务难度归因。

## 6. 任务难度与可解性先导判断

- 软件可解性：一个正式原Agent补丁28PASS，两个原样残留补丁各28PASS，合法不同机制正控均能通过恢复/不变量检查。
- 诊断难度：三个代码样本均通过当前Oracle、主要采用DB一致性修复，存在可能的代码任务天花板；接近20分钟不等于高软件难度。
- Runtime可靠性：原闭环只有1/3，两轮wall预算内未结束；Provider/429和协作收尾是实测问题。没有临时延长预算、额外重跑或改suite改变通过率。
- 经验判断：Experience始终DISABLED，无种子历史注入；A→D离线差异不是Pilot负迁移或治理收益实验。
- 三Trial仅先导：保留全分母，不宣称稳定总体成功率、统计显著性、多Agent优越或真实成本。

## 7. 实际命令与原始归档

```bash
env ORDERFLOW_ENABLE_CODEX=1 scripts/python312 scripts/m1_live_pilots.py m1_validation/20261010T101602Z-8dfa7d4f-3c6c-4f4c-ac5a-57a06afa3e9e/pilots --gate m1_validation/20261010T101602Z-8dfa7d4f-3c6c-4f4c-ac5a-57a06afa3e9e/LIVE_GATE.json
scripts/python312 m1_validation/20261010T101602Z-8dfa7d4f-3c6c-4f4c-ac5a-57a06afa3e9e/postmortem_extract.py 1
scripts/orderflow --runs-root m1_validation/20261010T101602Z-8dfa7d4f-3c6c-4f4c-ac5a-57a06afa3e9e/postmortem/runs evaluate --episode D --submission m1_validation/20261010T101602Z-8dfa7d4f-3c6c-4f4c-ac5a-57a06afa3e9e/postmortem/pilot-1/submission.diff
# 第三轮另行执行相同提取/离线命令，编号为3；原Run不改写。
```

实际producer [live-pilots-command/command.json](m1_validation/20261010T101602Z-8dfa7d4f-3c6c-4f4c-ac5a-57a06afa3e9e/live-pilots-command/command.json)：11:50:47–12:50:29UTC、3582.27秒、退出0；三CLI分别退出3/0/3。collector退出0表示三次结果归档完成，不能将内部TIMEOUT视为PASS。两次提取与两次离线评测各退出0，准确argv/UTC/日志SHA见COMMAND_INDEX及各receipt。[PILOT_RESULTS.json](m1_validation/20261010T101602Z-8dfa7d4f-3c6c-4f4c-ac5a-57a06afa3e9e/PILOT_RESULTS.json) 保存关键原始artifact SHA。

**完成M1后停止。** [剩余问题](M1_REMAINING_ISSUES.md) 保留安全、CPU采样、SQLite观察范围、来源与难度不确定性。
