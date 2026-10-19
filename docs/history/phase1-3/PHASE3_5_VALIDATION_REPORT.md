# Phase 3.5 验收入口

**最终结论：CONDITIONAL PASS。已停止在 Phase 3.5。**

完整的实际命令、退出状态、JUnit、原生子 Agent 证据、补丁与文件树 SHA256、可信数据库审计和剩余限制见本轮独立归档：

[完整验收报告](phase3_5_validation/20261010T064039Z-261add09-cb16-4726-b3c5-da8d14b09480/PHASE3_5_VALIDATION_REPORT.md)。

## 主要结果

- Submission Fidelity 已修复：隔离 Git 环境、严格补丁解析、四项 SHA256 与逐文件实际内容比较；不一致时阻止隐藏评测。
- 最终开发者测试 **499/499 PASS**，退出 0，无失败、错误或跳过；原有 249 项测试身份和 18 份原测试源码及断言保留。
- 真实 Gateway Responses / SSE / 工具调用及 Codex 原生 Multi-Agent 使用 `gpt-5.6-terra`、`max`。完成响应的实际 API 标签匹配，没有静默降级；上游内部模型权重和路由仍不可证明。
- 三轮修复后挑战使用同一核心提交 `cee9bbaf1c7df55049a91e890bb4cf2e0d313310`、相同公开输入及预算，分别创建新 Run 和 Session。每轮均有三个可核验的原生子 Agent。

| 挑战 Run ID | Runtime / CLI exit | 自动隐藏评测 | 自动闭环 |
|---|---|---|---|
| `272384f8-eb91-4eb1-9c37-52f46157dfbe` | PASS / 0 | 14/14 PASS | PASS |
| `7cec1187-72a0-4ee5-b12c-addc4758f5b1` | TIMEOUT / 3 | NOT_RUN | PARTIAL |
| `1fa7ec49-e9f3-480a-b5f3-4e67ff4e7d38` | PASS / 0 | 14/14 PASS | PASS |

第二轮超时后，停止时实际生成且未经维护者修复的补丁另建 Run `2ba58809-fc3e-4f95-9b8f-2b70c93fdaa9`，独立重放 **14/14 PASS**。该结果不能改写原 TIMEOUT，也不计为自动闭环成功。因此本轮自动闭环为 **2/3**；三轮样本不能证明总体成功率。

初始 900 秒系列的三次失败原样保留，与修复后的 1200 秒系列分开记录。原始 Phase 1–3 报告、运行结果、原 66 行 JSONL 以及 9,089 份受保护历史文件均保持原字节。

## 证据索引

- [提交保真修复报告](phase3_5_validation/20261010T064039Z-261add09-cb16-4726-b3c5-da8d14b09480/SUBMISSION_FIDELITY_REPORT.md)
- [Gateway 兼容性报告](phase3_5_validation/20261010T064039Z-261add09-cb16-4726-b3c5-da8d14b09480/GATEWAY_COMPATIBILITY_REPORT.md)
- [三层隔离与资源边界](phase3_5_validation/20261010T064039Z-261add09-cb16-4726-b3c5-da8d14b09480/TRUST_BOUNDARY_REPORT.md)
- [真实挑战、子 Agent 与补丁哈希](phase3_5_validation/20261010T064039Z-261add09-cb16-4726-b3c5-da8d14b09480/LIVE_MULTIAGENT_RUNS.md)
- [最终完整性检查](phase3_5_validation/20261010T064039Z-261add09-cb16-4726-b3c5-da8d14b09480/FINAL_INTEGRITY_CHECKS.json)
- [证据与源码清单](phase3_5_validation/20261010T064039Z-261add09-cb16-4726-b3c5-da8d14b09480/EVIDENCE_MANIFEST.json)
- [SHA256 校验和](phase3_5_validation/20261010T064039Z-261add09-cb16-4726-b3c5-da8d14b09480/SHA256SUMS.txt)

## 条件与停止边界

已验证的文件、网络和 Broker 鉴权边界通过。宿主未委派 cgroup CPU controller，CPU 与输出总量部分依赖采样；普通 Candidate 没有独立内核聚合 memory/pids cgroup。因此完整对抗安全只能给出 **PARTIAL / CONDITIONAL**。本地哈希和独占创建不是第三方不可变存储，也不是原生运行的密码学证明。

Secret 只由可信宿主持有；扫描范围为源码、Git 与全部新 Phase 3.5 证据，未记录 Secret 内容或其哈希。限制详情及无法验证的事实以完整报告为准。

B/C/D 仍未实现，Experience 为 DISABLED。没有推进 Phase 4、Episode D、GraphSwarm、FalkorDB、MCP 或 G0–G3。
