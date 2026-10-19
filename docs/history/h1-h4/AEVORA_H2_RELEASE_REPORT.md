# Aevora H2 — Release Report

本轮 Full：`aevora_validation/H2-20261011T082213Z-6bd12e96-82e1-4c87-b1df-67bc7fa74ae9/`（以下 A）。历史报告与原成绩不变；新结论来自本轮命令与原始字节。

| epoch | 独立本地Git commit | 实際证据 |
|---|---|---|
| G0 | bfa5db6a71ee2f85324f94b67d25c2dcc4319d9f | 新clone1295、真实Schema/查询/RDB/安全 |
| G1 | 61b5cc67270955b7c9c18031a94a7228f5efc795 | 1414、真实治理/Cypher、15CLI |
| 最终工程 G2 | f09f395318c87a788eef26bfdb04029ab584934e | 独立清洁clone1625；Suite11130Run |
| 正式Native G3 | 6a8e3d7831c27acb27703a7dba0a5d47d90fdbe0 | 326source pin；仅相对f09新增G2报告；两次native成绩 |
| 交付报告封存 | 见A/release-h2-delivery-reviewed-final/COMMIT_RECEIPT.json | 之后新报告/矩阵增量；不虚构已在此Commit重新联网 |

用户根Git HEAD保持beba4fba73f2e59e0d5a7fb99aea332ad80ea2cf，独立release位于 `aevora_validation/h2_worktrees/H2-20261011T082213Z-6bd12e96-82e1-4c87-b1df-67bc7fa74ae9`；未stage根index/force-push/重写旧Commit，所有新release是本轮新snapshot，不重建假H1tag。

本轮联网与最终回归runtime：Python3.12.14、官方SQLite3.51.3编译、pidfd；FalkorDB4.20.4/Redis8.6.3，image digest `sha256:adbddd418916c25618564ff8597a919b08bc76452ebeb74eb985c38d7281df62`；loopback17679独立ownedvolume，H1loopback16379卷不改。Gateway请求gpt-5.6-terra/max；current项目密钥仅trustedhostowner600外部文件，Participant只得到专用socket/capability。

最简清洁复现入口 `aevora_core/scripts/rebuild_h2.py` / `aevora_core/docs/H2_REBUILD.md`；正式挑战 `scripts/aevora_h2_native.py` 在freeze Gate后调用现有CodexAdapter；manual/Hidden CLI `benchmark.h2_cli` 保留旧协议。README/旧GraphSwarm历史、OrderFlow独立Benchmark身份保留。原报告/sourcebyte保护详见FINAL_HISTORY_IDENTITY_GATE。

RootCSV作为交付artifact单独hash；相同docs/AEVORA_H2_TRACEABILITY_MATRIX.csv进入release源码allowlist。完整文件变化、Commit、树摘要、hash由actualreceipt给出，不能用本文自引用替代Git实际结果。

### 剩余限制及不可证明事项

- AOF隔离重放实际SIGSEGV/139，未修复；RDB可靠性仅到完成SAVE的RPO，已测未保存尾部丢失。断电零损失、跨主机storage与上游因果关联UNVERIFIED。
- 共享内核、管理员/侧信道、模型prompt injection敌对级证明PARTIAL。MCP按Run授权，不细分child。当前两项凭据扫描0匹配不能证明任意未知secret或已清理capability原值。
- 独立下载24.08运行时上游EOL，尽管替换为官方SQLite3.51.3，整体发行支撑仍需下一版本迁移；本轮无扩大升级。
- Native公开6项UDS测试EPERM setup ERROR、原失败保留；Host开发者/Hidden通过不能替代Participant中的兼容性。
- D-v02只证明D任务家族新增lease/authority前提。B/C、跨所有故障家族、治理统计收益、策略因果归因均未实现/UNVERIFIED/UNKNOWN。
- 原生身份用官方rollout补充CLI JSON，部分任务明文与最早文件写请求UNAVAILABLE；request gpt-5.6-terra/max已验证，服务端内部路由/权重/计费与真实推理预算UNVERIFIED。
- Hash/CAS/本地独立reader不是第三方不可变存证。Full私有维护者资料不是Participant公开材料；Lite的NOT_INCLUDED只提供hash/purpose，不能证明遗漏字节。


Full/EVIDENCE_MANIFEST与Audit-Lite只在最终writer关闭后创建；封存/独立verify/确定性/篡改拒绝真实结果收据位于 `aevora_validation/audit_exports/H2-20261011T082213Z-6bd12e96-82e1-4c87-b1df-67bc7fa74ae9/`。Hash值以外部FINAL_DELIVERY_RECEIPT为准，Full不被回写。历史H1LiteSHA d38db23087f702b5f5320428b5e622a56de7aa2eacad25ad4ed8373e0bc4708e仍原样保护。
