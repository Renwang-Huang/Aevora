# Aevora H3 — Remaining Limits

1. **PARTIAL**：共享 Linux 内核、采样资源限额，不能证明 hostile-kernel/VM 级隔离。22 项新物理/权限/SDK 负控通过，未因此升级安全结论。
2. **PARTIAL**：原 Native UDS bind EPERM 保留（6 个 setup ERROR）。安全的 in-process 公开入口保留原 6 项业务断言且 host/outer/native 通过，不能证明跨进程 Clock transport。
3. **UNVERIFIED**：AOF reload exit139 未修复；当前仅最后完成 RDB SAVE/checkpoint 的恢复边界，未保存尾部/断电零损失不成立。旧故障未删除。
4. **PARTIAL**：Flatpak24.08 基础运行时 EOL 保留；未虚报升级。下一步应在独立基础镜像重跑 kernel/UDS/业务/SDK/模型门禁后再切换，不能原地重写历史。
5. **UNKNOWN**：Query/decision/proposal/Outcome PASS 不能证明策略采纳或因果增益；一个有限 paired pilot 不支持成功率或显著性。协议、时间、Provider 负载不同。
6. **EXTERNAL_UNVERIFIED**：Receipt 示例 7 项公开测试不是独立 hidden Oracle。Source Candidate 可停 PENDING，ExternalObservation 无 VerifiedOutcome；没有自动为任意项目构建可信评测机制。
7. **UNAVAILABLE**：per-run MCP 身份不能识别具体哪个 Subagent 作者。只归属真实 Run/连接/native typed event；没有从自然语言生成关系或缺失时间。
8. **UNVERIFIED**：Gateway 公开请求模型名/推理强度兼容且完成，实际后端权重、计费和价格没有独立证明。
9. **LIMITED**：单次 head 转移有实际 GRAPH.QUERY fence；多语句 staging/source inspection/snapshot collection 不构成全局串行化事务。Host 检查并重试/撤回 staged publication；管理员妥协不在当前敌对证明范围。
10. **LOCAL_AUTHORITY**：SHA、Git 与本机证据验证是本地一致性，非第三方存证。独立 verifier 应从另一个可信渠道取得并外部 pin。
11. **LIMITED**：输入边界和 text-as-data 防护不证明通用 prompt-injection 免疫。普通安装本身不产生隔离，需保持 Host/Consumer 物理挂载与最小 capability 边界。
12. H3 完成后停止。没有 H4 Dashboard、完整 B/C、新 Agent orchestrator、多租户 SaaS、其它 Runtime SDK 或正式随机 G0–G3 实验。

13. 首轮 A 集成的原 own-native summary 未验证身份（agent_path=None），Runtime 使用官方 exec 结构化三子 Agent fallback。原始分数不修改，Lite 完整纳入为 qualified supporting evidence；第二轮拥有完整 own-native 身份链。强校验器未降低要求。G4 原时间线首轮 children 来自 Runtime fallback，不能据其统一 source 文本推断完整 own-native 验证。
14. Audit-Lite 导出先后保留 Python3.10 StrEnum 拒绝、首轮 native-summary 严格拒绝及第一版支持报告选择遗漏。最后 v2 与 sidecar 验证通过。后续 Source/Docs supplement 独立封存，不补写 Full，不归给早期 native epoch。
