# Aevora H3-G3 — 有限价值对照

结论：**PASS**（机制与证据完整性；探索性对照，不证明因果收益）。

## 真实图与来源

- 17690 独立冷恢复副本执行实际 SDK/Cypher 控制；主实例 17689 不改。真实前提下 APPLY；独立进程前提冲突时 ABSTAIN/VERIFY；不是按 Episode 名称选择。
- 选择实际支持路径中的一条 VERIFIES 边删除：节点数量不变，当前支持路径 1→0、APPLY→VERIFY；恢复相同边正文后 WHY 恢复。旧 QuerySnapshot 原样可回放。5 项实际检查全部 PASS。
- G1 新自然 Candidate 的限定发布、新 Session 阅读、受控撤回和冷恢复与本 Gate 一起证明演化路径。受控维护者图干预不是新 Agent Outcome。

## Raw Memory / Governance 原样对照

公开原始三条经验、事实上下文及业务基线在两种条件运行前冻结于 `g3/PILOT_PUBLIC_CORPUS.json`；相同 Receipt 工程、独立 Git、7 项原有公开测试、gpt-5.6-terra/max、single/new Session、completion-aware。Raw 仅提供原始正文与声明前提；Governance 实际查询 FalkorDB 的 WHEN/WHY。没有在 Prompt 指定正确修复。

| 尝试 | Run | Runtime | 公共测试重放 | 秒 |
|---|---|---|---|---|
| governance | `af26fb0c-865d-472c-97e3-c2a2c73fd597` | ERROR / PROVIDER_FAILURE | NOT_EXECUTED | 166.216 |
| governance | `c8a6a7ae-fb65-4b2d-98ea-0651eb939a7b` | PASS / NONE | 7/7 PASS | 738.180 |
| raw | `f4406efc-d94d-4d21-b30f-d350248f3d4e` | PASS / NONE | 7/7 PASS | 549.552 |

Gov 首次 SSE/上游 TLS 故障完整保留，不能抹去失败分母。成功 Gov 实际 resolve=2、bundle=2、decision=1、propose=1。新 H3 经验出现在查询返回中，但显式 bundle 指向两条既有经验，不能声称采纳了新经验。Raw 实际产生不同 SQL 补丁；两份原样补丁均通过 7 项公开测试。外部观察仍 EXTERNAL_UNVERIFIED，VerifiedOutcome=0。

一次成功配对不足以估计成功率；协议开销、顺序运行和 Gateway 延迟不同，不是随机/统计对照。Token 仅引用 Runtime 官方 usage，费用/实际模型权重 UNVERIFIED。

## 可复核命令与产物

真实 argv、退出码、时间、stdout/stderr SHA 见 `g3/PILOT_COMPARISON_V2.json` 的 commands 引用及对应 command.json。Controller exit 0 表示归档闭合，Gov 首次的 Runtime ERROR 仍是 ERROR。

`g3/PILOT_COMPARISON_V2.json` 保存每次结果/封存哈希、资源、Patch SHA、Run；`g3/graph-checks/necessity_01/` 保存原始 Cypher、前后图、边正文与 5 项检查；G1 生命周期来源见独立报告。最终 Gate 为 `GATE_V2.json`，初版同名排版失败前已写入的汇总仍保留。

报告生成第一版对失败 Run 强取不存在的 `public_test_command_exit` 得到 KeyError，保留于 `g3/REPORT_BUILDER_FAILURE.json`；修复为未执行分支。第二次遭独占写入保护 FileExistsError（旧汇总不覆盖），保存 `g3-build-comparison-report`；最终新文件名生成，没有修改任何成绩。

新 Gate Commit/Tree 存于 `g3/ACCEPTED_SOURCE_COMMIT.json`；不得将 Gate 后续文档 Commit 归给已结束的 native Session epoch04。
