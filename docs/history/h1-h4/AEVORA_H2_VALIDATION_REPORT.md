# Aevora H2 — Final Validation

**最终结论：CONDITIONAL PASS。** 本轮 Full：`aevora_validation/H2-20261011T082213Z-6bd12e96-82e1-4c87-b1df-67bc7fa74ae9/`（以下 A）。历史报告与原成绩不变；新结论来自本轮命令与原始字节。

## 分项结论

| 维度 | 结论 | 本次实际证据 |
|---|---|---|
| G0 Source & Clean-Rebuild Reproducibility | PASS | G0全新1295；最终工程commit新clone/venv/下载后1625，真实图查询；来源Commit不同明确分开 |
| G0 Persistence & Recovery | PARTIAL | 实际RDB正常/异常停止、损坏拒绝、尾部丢失、冷恢复及新原生Session；AOF139未修 |
| G0 Security & Isolation | PARTIAL | 56→74实际检查、134契约、三层41路径、18非法Clock不改状态、凭据0匹配；共享内核边界 |
| G1 Evidence Conflict & Revision Governance | PASS | 1414回归、388核心、5374参数Cypher；冲突/未知/撤回/追加Revision/范围与快照关联 |
| G2 D-v02 Independent Benchmark | PASS | 最终36项/8窗口，30独立正反Run、合法flock、真实删除/盲清理负控、宿主Oracle |
| G3 Codex MCP & New Scenario End-to-End | PASS | 2工程挑战/6真实完成child/72Hidden PASS→Trusted graph→冷恢复新Session实际回读；原公开Native兼容性PARTIAL |
| Historical Non-Regression & Audit Integrity | PASS | 本次1625/1625、1214身份、58旧测试、57任务真值、101084历史文件逐hash相同 |
| H2 Overall | CONDITIONAL PASS | 关键功能闭合；AOF、安全/EOL/公开Native兼容性残余限制如下 |

## 当前实际测试分母

最终完整回归在联网工程挑战结束后执行：**1625 PASS，0 FAIL/ERROR/SKIP**，188.906116秒、退出0。JUnit SHA256 `a5a70c3f5afddf23de83dadc10898974074937dfa3b02617e5b17b10bb0bca2a`。`A/FINAL_HISTORY_IDENTITY_GATE.json` 实际对全历史/旧身份逐项检查，55.966674秒/退出0。不是复用H1的1214历史成绩。

最终原CLI15检查退出0/182.867893秒：Smoke8/A14/D-v0128正反仍PASS/FAIL；flock PASS；B/C NOT_IMPLEMENTED；错误提交ERROR、受控超时TIMEOUT、prepare/report/reset/独立归档达到原预期。检查0退出不意味着错误业务代码PASS。

Suite 1.1.1最终30个独立初始状态Run：Buggy10/10 FAIL、Reference10/10 PASS、local_lock10/10 FAIL；1080 case=920PASS/160FAIL/0ERROR/skip，全部8窗口COMPLETE，1128.168034秒/退出0。Suite fingerprint `51d09e225e43e778f452f69da1be3c5ad7c798aa250bb044933f36e7a66ba7e8`。flock在最终suite仅完整1PASS；blind_cleanup1FAIL、真实DELETE→COMMIT→reinsert1FAIL。各Run UUID/失败原因/退出/patch/reportSHA在 `A/g2/suite111-30-runs/ATTEMPTS.jsonl`；30个实际回归不是2个模型挑战分母。

## 实际修改与功能边界

在现有 Aevora Core/FalkorDB/MCP/TrustedFeedback上追加治理1.1：typed事实三态、作用域支持/反例、追加规则Revision/SUPERSEDES/withdraw/expiry/冲突、冻结QuerySnapshot与Decision关联及回放、VerifiedOutcome规范桥接。公共上下文新增六个语义facts白名单，Episode ID不决定结论。

在原OrderFlow Registry/Runner分层旁新增 D-v02 fixture、五个request APIs、独立Worker、共享Clock、SQL Kernel/FD witness和host Oracle；旧root app/Runner tasktruth58/57文件保持。新的h2_cli注册复用既有生命周期，未整体重构。Reference和flock合法策略由真业务执行验证；不能关闭并发/降低容量绕过。

初始源码252项→联网冻结326，75ADDED/11CHANGED/240UNCHANGED（cache README不作为删除）；逐路径SHA详见 `A/SOURCE_CHANGE_MANIFEST.json`，原Dirty文件不能都归为本轮修改。最终交付仅新增报告和traceability矩阵，原326 live源码不改。模型挑战使用commit6a8；post-delivery报告commit仅加文件不冒充已联网新业务epoch。

## 真实失败保留

G0隔离Python layout/pidfd缺失53FAIL、GPU下载人工取消、AOF139；G1 GRAPH.COPY/fork失败与按SAVEpause控制的后续验收分开。G2早期8RunnerERROR、35项采集器因执行期源码变化FAIL、1.1.0删除gap OPEN、tuple/schema等reader失败、opaque commitobserver ERROR均保留。Oracle后来1.1.1修复有真实负控，不重判旧35/110epoch，不删除旧有效断言。

G3所有Gateway真实500/502/503/524/断连/timeout/并发限额/MCP5ERROR、Agent命令失败、公开6setupERROR、NO_PATCH读回适配ERROR均保留。成功提交不是人工修复或Reference替换。Final fullPASS与各早期失败的原命令独立归档。

## 原生命令和提交

完整G0/G1/G2命令与Commit分别见相应报告。G3两次原始补丁/Run见G3报告；最终实际命令主体及收据如下：

```sh
env AEVORA_H2_RUNTIME="$H2_RUNTIME" AEVORA_FALKORDB_PORT=17679 \
  AEVORA_FALKORDB_GRAPH=aevora_h2_g0 \
  AEVORA_FALKORDB_PASSWORD_FILE="$H2_EXTERNAL_DB_PASSWORD_FILE" \
  scripts/aevora-h2-python -m scripts.aevora_h2_governance \
  --pause-auto-save tests "$H2_ARCHIVE/final/full-project" -q tests aevora_core/tests
```

上述实际参数在 `A/h2-final-full-project-regression/command.json`；重放必须使用新输出目录。CLI/完整命令索引、复现依赖和私有secret注入契约见 `A/H2_REPLAY_README.md`，不把示例省略argv假称已执行。

## 封存与审查

G0/G1/G2/G3 Gate独立JSON SHA关联source/actualreceipt/rawtests/run。最终Full需要所有writer停止后生成EVIDENCE_MANIFEST；sourceCommit、Full seal与Audit-Lite export/verify/tamper/确定性收据在独立export目录。封存后不写Full；导出后真实验证结果在外部FINAL_DELIVERY_RECEIPT。报告不预先声称尚未执行的ZIP验证PASS。

Audit-Lite包含核心src/GraphSchema/Cypher、报告、全部实际native MCP/rollout、JUnit/Oracle独立结果、回归matrix/ATTEMPTS、hash/NOT_INCLUDED。私有Oracle/Reference/DB/RDB/完整workspace仅Full可信维护者可见。原始大文件用CAS/DEFLATE保持完整行，新只读NO_PATCH仅SupportingSource不进入Scored RUN_INDEX。

### 剩余限制及不可证明事项

- AOF隔离重放实际SIGSEGV/139，未修复；RDB可靠性仅到完成SAVE的RPO，已测未保存尾部丢失。断电零损失、跨主机storage与上游因果关联UNVERIFIED。
- 共享内核、管理员/侧信道、模型prompt injection敌对级证明PARTIAL。MCP按Run授权，不细分child。当前两项凭据扫描0匹配不能证明任意未知secret或已清理capability原值。
- 独立下载24.08运行时上游EOL，尽管替换为官方SQLite3.51.3，整体发行支撑仍需下一版本迁移；本轮无扩大升级。
- Native公开6项UDS测试EPERM setup ERROR、原失败保留；Host开发者/Hidden通过不能替代Participant中的兼容性。
- D-v02只证明D任务家族新增lease/authority前提。B/C、跨所有故障家族、治理统计收益、策略因果归因均未实现/UNVERIFIED/UNKNOWN。
- 原生身份用官方rollout补充CLI JSON，部分任务明文与最早文件写请求UNAVAILABLE；request gpt-5.6-terra/max已验证，服务端内部路由/权重/计费与真实推理预算UNVERIFIED。
- Hash/CAS/本地独立reader不是第三方不可变存证。Full私有维护者资料不是Participant公开材料；Lite的NOT_INCLUDED只提供hash/purpose，不能证明遗漏字节。


## 停止边界

H2实现、部署、真实挑战和后续读回已完成。停止在H2；没有实现H3、B/C或正式统计实验。工程成绩PASS、图谱闭合PASS不转成经验策略因果增益。
