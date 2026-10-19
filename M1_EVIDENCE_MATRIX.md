# M1 Evidence Matrix

本矩阵引用本轮真实证据；原型/历史结果与最终 suite 1.2.0 的结果分开。归档前缀为 [M1](m1_validation/20261010T101602Z-8dfa7d4f-3c6c-4f4c-ac5a-57a06afa3e9e/)。三次真实Pilot已结束，原闭环1/3，Overall CONDITIONAL PASS；独立postmortem不升级原结果。

| Gate / 可证伪要求 | 已有证据 | 当前判断与边界 |
|---|---|---|
| A：先设计再实现 | DESIGN_GATE 时间、四份 preimplementation 文档哈希、源变更清单 | PASS；设计不代替动态验收 |
| A：统一业务世界、两层真值、任务包、双准入规范 | Task System / Admission / Relations / 根设计自审；B/C 与支付事件明确规划 | PASS；未来服务和治理算法未实现 |
| B：真实 2/4 OS Worker + 同一 DB | SO_PEERCRED / start ticks / PID namespace、DB dev/inode/FD、重叠操作区间、每 Worker 持久新订单 | PASS；本机共享文件，不宣称跨节点 |
| B：真实受控竞态与正常单 Worker | Buggy 十轮同 13 个身份稳定失败；单 Worker 身份通过；实际 raw ledger/order reconciliation | PASS；混合取消/购买子项有时序变化，完整记录 |
| B：崩溃、重启、重试、WAL、多 SKU、规模、reset | 28 项完整隐藏套件、三个 pidfd/SIGKILL窗口、普通 SQLite recovery 证据、全部 Supervisor cleanup | PASS；观察支持范围之外明确 UNVERIFIED |
| C：机制不同合法解 | Reference 10 PASS；稳定 inode flock 10 PASS；compensated multi-stage 28 PASS / 36 raw Oracle | PASS；不限定唯一锁或事务数量 |
| C：已知错策略检出 | exact local-lock A PASS→D FAIL；custom split-ledger 原同树三次 FAIL；naive未补偿16/12 FAIL | PASS；保留旧 falsifier 与错误正控分类的原始失败 |
| C：独立真值与反作弊 | host SQLite raw Oracle/约束探测；spoof-success 与 refuse-workers 都 FAIL；完整 JUnit身份/退出码/无skip | PASS；非完整敌对证明，host不 import候选 |
| C：恢复证据缺失不能冒充通过 | unbound native C commit 候选：业务断言全绿但必要窗口 UNVERIFIED，overall ERROR | PASS；不是因未知窗口断言业务错误 |
| D：499 原测试与完整回归 | baseline499→current664，499身份全部保留；165新增；只有D状态断言显式迁移 | PASS；原源码与历史JUnit保留，零 skip/error |
| D：A / Smoke / B/C / 原自然Agent修复 | offline-final14实际CLI案例；A±/替代，Smoke±，B/C退出4；新Smoke精确patch不改旧diff | PASS；原旧hunk失败和新通过有分别的Run |
| D：提交保真、错误分类、清理 | 完整旧单元/集成测试；实际invalid submission ERROR、实际D timeout2 TIMEOUT；原patch/tree校验 | PASS；没有mock task PASS |
| D：隔离与Broker | isolation-final7实际kernel/native探测；136source freeze；可信宿主credential-content扫描；bounded Gateway4预检 | 强制边界 PASS；整体 CONDITIONAL，namespace/CPU采样/本地来源认证限制 |
| E：三独立新Session盲测 | 原TIMEOUT/PASS/TIMEOUT，各新Thread/输入封存；136源/同stdin/公开ManifestSHA一致 | 三次实测归档，原闭环1/3，先导不作统计结论 |
| E：真实原生子任务执行/完成/回传 | 各三真实child自身执行，verified2/3/1，第二轮三个完整；第三轮429异常回传不计完成 | 原Multi-Agent PARTIAL/PASS/PARTIAL，初始密文task正文UNAVAILABLE |
| E：真实Agent补丁与独立评测 | 第二轮正式28PASS；独立postmortem新Run93c081.../65c82...各28PASS，原样tree保真 | 原NOT_RUN/PASS/NOT_RUN，不升级超时原成绩 |
| F：自然与种子来源、工程分与参考标签独立 | exact-strategy-transfer；private label1.1来源/条件；Experience DISABLED | PASS for已执行策略环境差异；VERIFY是设计级，非治理实验 |
| 历史保护 / 封存 | post-pilot-preseal实际38,640历史/136源未变；最终seal复核/manifest/SUMS | 实际终局见FINAL_SEAL_SUMMARY，无外部不可变认证 |

## 失败与修正索引

- 原 custom transaction split-ledger Run `f9089592-c528-4904-a72d-b6965eba99a4` 错误24PASS：真实 harness盲点；原字节不变，新同树三次各27PASS/1FAIL。
- 原新并发release测试非法调用次序：prefinal失败/producer退出143完整保留；suite1.2先cancel再合法release，断言未放宽。
- 原 naive two-phase 被误当正控，完整matrix退出1：不足后残留新订单是真业务缺陷；新closure已以Known-bad对照重证，合法compensated方案通过。
- 旧Smoke reference hunk偏移严格拒绝：原diff/报告未修改；新增当前精确patch和真实8PASS。
- 原型RPC异常、observer提案断言/路径/peer close预期错误、只读整理脚本字段错误：原证据保留，最终源/控制和已执行回归分别支持修正。
- 首轮联网超时：77上游请求、有限1200秒门禁触发；原Run保持TIMEOUT，两个子Agent完成可验，补丁离线28PASS。模型初始子任务正文部分加密而不可读取，保持UNAVAILABLE。

## 汇总原则

每项工程判断依赖行为不变量、实测拓扑、有效测试集合、错误策略判别与对照。设计完整、case数量或生成patch本身均不能单独完成Gate。Pilot需保留全部分母与实际状态；三次先导不能证明统计成功率或经验治理收益。

最终分层：Design PASS；D Engineering PASS（声明范围内）；Research CONDITIONAL PASS；Pilot原自动1/3；Overall CONDITIONAL PASS。完整命令、状态与未验证条件见其他M1报告。
