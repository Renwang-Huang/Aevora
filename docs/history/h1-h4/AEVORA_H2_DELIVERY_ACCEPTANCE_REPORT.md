# Aevora H2 — Post-Seal Delivery Acceptance

## 结论与证据层

**H2 Overall：CONDITIONAL PASS。** 本文件补全最终封存之后的真实导出缺陷、修复、完整回归与外部验证；不修改已封存 Full、原 Gate 或任何历史成绩。

- 原 G0–G3 Full：`aevora_validation/H2-20261011T082213Z-6bd12e96-82e1-4c87-b1df-67bc7fa74ae9/`，下文 A。
- 后续交付修复与导出证据：`aevora_validation/audit_exports/H2-20261011T082213Z-6bd12e96-82e1-4c87-b1df-67bc7fa74ae9/`，下文 E。后续原始测试和失败均在 E，不能借用 A 的此前扫描结论。
- A 的 source commit：`f3568927f4f9f817d200a9af4381433c8f23c737`；实际联网源码 commit：`6a8e3d7831c27acb27703a7dba0a5d47d90fdbe0`。
- 导出器修复的新 source commit 以 `E/release-h2-export-fix-final/COMMIT_RECEIPT.json` 的实际结果为准。该版本没有重新发起模型挑战；业务、MCP、Resolver、Private Oracle 和参考补丁未因此改变。

## 实际导出缺陷和修复

第一次正式导出 `E/export-one/command.json` **退出2**，诊断 `E/export-debug-worker-attempt02/command.json` **退出2**。真实只读 Run 中的 `evaluation_report.json` 是 Runner.prepare 保留的空 PREPARED 生命周期；旧 selector 错把文件存在等同于已评分任务，因此拒绝真实归档。

`scripts/aevora_h2_export.py` 1.0.1 严格检查 Run/Full 封存哈希、同一 Run ID、LOAD→PREPARE、没有测试/提交/评测/结束字段、完整且公开输入未改的 native NO_PATCH 观察。原空准备报告仍为 Full 的 NOT_INCLUDED 指针，不进入 Scored RUN_INDEX；任何 PASS/FAIL/ERROR/TIMEOUT、评分字段、错误 runtime、旧 seal 或显式评分选择均拒绝。没有替换原 NO_PATCH/NOT_EXECUTED，旧 exporter/CAS/独立 verifier 的源码及50项旧测试不变。

新增30项真实执行的结构与伪造拒绝契约，原35项 H2 测试的全部函数/辅助函数 AST 未改。新增测试使用明确的 synthetic archive fixture，只证明分类器，不计自然 Agent 或工程任务结果。

## 最新完整回归

| 本次实际执行 | 退出 / 秒 | 结果 |
|---|---:|---|
| `prepared-observation-export-contracts/command.json` | 0 / 12.400705 | **115 PASS**：原50+35以及新增30，0 FAIL/ERROR/skip |
| `export-fix-full-project-regression/command.json` | 0 / 288.540377 | **1655 PASS**，0 FAIL/ERROR/skip，真实 FalkorDB |
| `post-export-fix-history-integrity/command.json` | 0 / 62.264570 | 原1214身份、58旧测试、57任务真值、101084历史文件逐hash一致 |

实际最新命令主体：

```sh
scripts/aevora-h2-python -m scripts.aevora_h2_governance \
  --pause-auto-save tests "$H2_EXPORT_EVIDENCE/export-fix-full-project" \
  -q tests aevora_core/tests
```

完整 env、argv、UTC、stdout/stderr SHA 在上述原始 command.json；重放使用新输出目录。Python3.12.14 / SQLite3.51.3，旧 H1 endpoint未调用。完整 JUnit SHA256：`784203304902754e0a993b0d9d311f86f1743221281ac6593835a9280f77faeb`。

A 的联网后回归1625仍为其原 epoch 成绩；最新1655明确来自导出修复之后。全部原1625身份仍在1655中，未删除旧有效检查。原15项CLI、30个D-v02独立控制Run和两次36/36原生挑战的实际成绩保持，未为导出重新制造任务成功。

## Full 与 Audit-Lite 的真实结果

Full 实际封存：91,943个普通单链接文件，4,462,145,194B；6硬链接、315符号链接、3特殊文件仅元数据，未读取/跟随。实际独立重读 **退出0 / 10.543220秒**；导出后仍核对同一 seal。Full manifest SHA256：

`243df294b70fd41b595752906a8d68196deeebf782a16c1eeddf59de28df967d`

两次独立正式导出 `E/export-one-fixed/command.json`、`E/export-two/command.json` 均 **退出0**，分别45.212703秒、45.441216秒。相同冻结源与固定 timestamp 的 ZIP 字节 SHA 相同：

`2f2bc3af1ac85ac8a094e31c8d685f007ad9b9b5622e75080a62bca00a1d8f1c`

主包 `E/aevora-h2-audit-lite.zip`：**13,926,046B**，3,877条源记录，88,066条 NOT_INCLUDED。包含 G0–G3报告、原始两轮MCP/官方stdout/8个完整native rollout、36×2隐藏结果、核心源码/Schema/Cypher、JUnit/30轮ATTEMPTS及有限对照；Scored RUN_INDEX仅实际两个工程Run。只读第三Session是SupportingSource，NO_PATCH/NOT_EXECUTED保留。

独立标准库验证 `E/lite-independent-stdlib-verify/command.json` **退出0 / 4.086665秒**；不执行ZIP代码、不联网。`E/lite-scope-determinism-tamper-v3/command.json` **退出0 / 8.015164秒**，其两个实际篡改副本分别因内容改一字节、改评分后重新计算全包checksum而被原独立 verifier **退出2**拒绝。原包与两次导出均不改。

范围 reader 的两个先前 **退出1**保留：第一版期望旧扫描文件名，第二版使用概念性 resolver.py 名称；v3校验的是实际最新扫描报告和 `experience_resolver.py`，没有放宽包/Oracle判据。

## 索引纠错与审计边界

原封存矩阵中的两处 Source 文字路径需要与本纠错一起审查：

| Requirement | 原文字路径 | 实际路径 |
|---|---|---|
| G1-governance | aevora_core/src/aevora/resolver.py | aevora_core/src/aevora/experience_resolver.py |
| Final-private-archive | security/private_archive_audit.py（未说明归档基准） | A/security/private_archive_audit.py |

Root 与 docs 的当前矩阵已纠正，`E/AEVORA_H2_TRACEABILITY_MATRIX_CURRENT.csv` 和 `E/LATE_EXPORT_FIX_SOURCE_REVIEW.json` 包含实际路径与源码哈希。A及Lite中的旧矩阵原样保留，不能把外部纠错描述为包内已有内容。

**主 Lite 是 A 的冻结 G0–G3证据包。** 本轮 post-seal 1.0.1修复、1655回归、当前矩阵和本报告是 E 的配套补充证据，不在主ZIP内；必须与其共同审查。NOT_INCLUDED只是源hash与用途，不能独立证明被遗漏原始字节；本地checksum不是第三方不可变来源认证。

## 停止与残余限制

两次新的工程原生多 Agent挑战各3名真实完成child、36/36隐藏和8窗口通过；可信反馈追加OBSERVED_OUTCOME，归因UNKNOWN；冷恢复后不同Session真实返回两条新Outcome路径。经验增量收益仍UNVERIFIED。

AOF139未修复、RDB RPO仅到完成SAVE、共享内核/任意秘密和模型注入敌对证明PARTIAL/UNVERIFIED、基础运行时EOL、原公开6项Native UDS.bind EPERM setup ERROR仍未修复。本次分类修复没有扩大Participant权限或改public/hidden业务断言。新 Native 试验必须新建归档重新admit，不能复用已封存A覆盖原始Run。

**停止在H2。** 没有H3、B/C、正式统计实验或自动进入下一阶段。
