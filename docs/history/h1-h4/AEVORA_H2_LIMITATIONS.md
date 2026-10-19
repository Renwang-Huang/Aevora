# Aevora H2 — 限制与未验证事项

本报告与 H2 独立 Gate 收据配套；历史成绩不升级为当前源码的成绩。最终状态见 `AEVORA_H2_VALIDATION_REPORT.md`。

## 安全与运行环境

- Participant、Candidate 和宿主可信模型连接保留不同的文件/能力边界。实际拒绝检查不等于共享 Linux 内核的敌对级安全证明；安全总体继续 **PARTIAL**。
- MCP 能力按 Run 发放、到期/撤销和重放受限；目前不是每个子 Agent 独立安全主体。维护者数据库管理员和运行宿主属于可信边界。
- 独立下载的 Freedesktop 24.08 运行时已到 EOL。H2 在物理独立副本中实际构建、验证 SQLite 3.51.3，Python 为 3.12.14；这不代表已修复整个旧运行时的安全支持问题。旧运行时和历史结果保持原状。
- Gateway 的 `gpt-5.6-terra/max` 是实际请求配置。底层模型权重、供应商路由、真实计费和模型内部思考强度没有独立证明，标记 **UNVERIFIED**；不会静默替换请求模型或推理参数。
- completion-aware 没有总 wall-clock / request budget 阈值，仍有有限的连接、idle、重试、并发和资源限制及人工取消。SIGKILL/断电之后的自动 Agent resume 未实现。

## 图数据库可靠性

- 官方固定 FalkorDB 4.20.4 镜像的 AOF 回放故障已在独立实例实际复现，退出 139 的原始栈保留。上游问题与本地崩溃之间的因果对应仍 **UNVERIFIED**，没有把 AOF 路径宣传为修复通过。
- 本轮可靠路径为明确 writers-quiesced 的 RDB SAVE/checkpoint/新卷冷恢复。RPO 以最后完成的 SAVE 为界；未保存尾部可以丢失，必须重放可信反馈。不承诺任意断电零损失。
- 显式图谱测试维护窗口暂停自动 SAVE、记录实际 GRAPH.COPY 和 SAVE、恢复原配置；没有通过忽略失败或自动重试改写成绩。原始 fork 竞争的底层原因仍 **UNVERIFIED**。
- 当前图谱治理仍是可信宿主控制的多次查询/写入，不是生产级多租户事务隔离服务。独立 nonce 副本的有限消融不是统计实验。

## Benchmark 与经验边界

- D-v02 是 D 家族内具有新 lease/authority 前提的变体；B/C 未实现，跨全部工程故障家族的泛化 **UNVERIFIED**。
- Controlled Clock 与 kernel pidfd/DB FD 证明覆盖实际调度窗口，不证明任意时钟偏差、任意事务序列、断电或恶意内核。
- 受支持的 SQLite 提交路径必须产生可信恢复观测；不受支持的 native observation 路径判 infrastructure **ERROR**，不能充当业务 PASS 或 FAIL。
- 对既有未预留订单的中间发布审计先后发现并修复了两个缺口。Suite 1.0.0、1.1.0、1.1.1 必须分别报告；旧报告不接受新版本判据的追溯升级。检测第一个目标提交不等于穷尽任意多阶段实现的全部提交时序。
- 原始来源 `natural_agent_run`、`maintainer_seed`、`synthetic_or_test_fixture` 保留。部署到专用 G3 图中的历史自然工程 Outcome 仍是本轮维护者导入的受控历史语料，不能算本轮新 Agent 结果。
- Resolver 的原则适用性与完整操作覆盖分别报告。SQLite 原则的 APPLY 不自动证明请求 authority 已正确处理；未知前提应 VERIFY，实证必要前提冲突应 ABSTAIN。
- 查询、推荐、Agent record_decision、可观察补丁、VerifiedOutcome 及因果采纳不同。工程结果即使 PASS，自动因果归因仍 **UNKNOWN**，治理提高通过率/真实负迁移效果/统计收益均 **UNVERIFIED**。

## 证据与停止边界

- Source Commit、Run Seal、Full/Lite SHA 是本机可追溯一致性证据，不是第三方不可变存储、签名运行证明或模型来源证明。
- Audit-Lite 不包含私有 Oracle、Reference、数据库/RDB、凭据或完整大体积原始图。对应 NOT_INCLUDED/哈希仅定位 Full Archive，不等于外部审查者可见内容。
- 本轮到 H2 停止；H3、B/C、GraphSwarm、FalkorDB替代品、自研 Agent Orchestrator、正式 G0–G3 对照实验均未开发。
