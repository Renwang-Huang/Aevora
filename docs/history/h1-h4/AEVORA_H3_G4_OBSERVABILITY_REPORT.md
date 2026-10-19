# Aevora H3-G4 — Observation, Demo & Independent Audit

结论：**PASS**。

新 SAVE/checkpoint → 独立 Volume / 17691 → 真实 SDK 验证恢复 → H3-demo → 独立 stdlib H3-verify 已实际完成。源/目标容器、镜像 digest、RDB 与图哈希见 `g4/demo-deployment`。未替换 17689 主实例或 17690 撤回控制库。

## 观察与验证

- 实际候选、5 个审查/发布事件、自然来源核验节点及独立 PASS Outcome；关系边和显示的正向 WHY 路径逐条校验。
- 同一外部工程 Run 的 EXTERNAL_UNVERIFIED / NOT_CREATED；VerifiedOutcome=0。独立进程前提冲突负迁移仍 ABSTAIN/VERIFY。
- 两次只读重放，4 份数据文件字节一致；WHEN/WHY 仅实际 as_of 时刻不同，其余语义完全一致。保留所有实际时刻，没有改写数据获取字节 PASS。
- 原始时间线覆盖 6 个真实 Session、1042 条完整原始事件行，逐行 SHA 与 Full 一致。17 条关键实际 SDK Cypher 保存原语句与行引用。
- 独立校验不导入 Aevora 或 Benchmark；对真实目录校验通过，对单字节改动 exit1。14 项负控覆盖额外/缺失文件、链接/硬链接/FIFO、大文件、重复/非有限 JSON、错误外部 manifest pin。

## 可执行入口与命令证据

`aevora_core/scripts/h3_demo.py` 与 `h3_verify.py`，部署、配置、权限和独立校验说明见 `aevora_core/docs/H3_OBSERVABILITY.md`。

Full 内 `g4-fresh-demo-deployment`、`g4-actual-demo`、`g4-final-independent-demo-verify`、`g4-observation-dynamic-controls`、`g4-complete-event-and-cypher-references` 的 command.json 记录真实 argv、退出与流 SHA；原型比较 AssertionError 和后续限定比较原样保留。

Audit-Lite 使用原有 CAS/脱敏/完整行引用及标准库 verifier。工程 A Run 进入 scored index；只读和外部 Session 仅 supporting，Prepared 报告不伪装评测。私有 Oracle、Reference、原始拓扑和凭据不公开；NOT_INCLUDED 仅是原始 SHA 指针。

最终分发/确定性/独立 verify/篡改/脱敏结果以 Full 外 `aevora_validation/audit_exports/H3-20261012T082407Z-d0e93931-8fdf-4999-b05b-160b9ca20959/DELIVERY_CHECKS.json` 为准。Full 内冻结的 G4 报告如处于 export-pending，是封存前阶段；最终 G4_FINAL_GATE 与当前报告在交付侧独立保存，绝不补写封存 Full。

没有 Dashboard、外部密码学存证、全局原子图快照或因果收益声明。

## Final delivery closure (post-seal)

Final Lite: `aevora-h3-audit-lite-v2.zip`, 6678503 bytes; SHA256 `c7d36870084a90b14e4fb11b8651a80d3bf5aef2e2a2b07690990826772aeeec`. Independent stdlib verify exit0; same-time re-export identical; one changed content byte rejected with exit2. All six original event streams and first original executed report remain included.

Full manifest SHA `60868e1a3b12c034712cda60f4b29903ad0889ada5c0e4f5c6c14014683e6dae`; Full SHA256SUMS `44117bffd2979405f14888583a8e5d25cc6f37f261d85cb280d3e33694b5bad7`. Full never changed after seal. Current document/source closure is separately versioned in the delivery directory.

Post-seal current-source regression: **1714/1714 PASS**, same 1655 required identities, one SDK warning, JUnit SHA `0dc764956dc7ca8eaffa70d3c8f59a55d866219e15c2fd08269da877cf677974` (`post-seal-current-source-regression`, exit0). The thin selector was corrected to retain first executed report as qualified support; no Evaluator/Oracle/business/legacy verifier assertion changed.

首轮 source Run `ac3e66ff-38c4-4a4c-90b8-ae635e836dcb` 的 exec 事件子 Agent=3，而原 own-native summary=0/UNAVAILABLE（缺少 agent_path）。原分数完整保留；它作为 supporting attempt，不能被 Lite 升级成 fully own-native verified 的 scored entry。只有 `405c481e-ae7a-420d-8502-fb1d9ede02e6` 进入严格 scored index（14/14、3 个完整身份链）。所有尝试仍在原分母与日志中。详细指纹见 `NATIVE_TRACE_QUALIFICATIONS.json`。

Post-seal exporter fixes and current report bytes are delivered as a separate public source/document supplement; the original Full/Lite frozen source snapshot is not falsely identified as containing these later bytes.
