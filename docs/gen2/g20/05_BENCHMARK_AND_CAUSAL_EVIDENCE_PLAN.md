**Freeze candidate 2.0.0-rc1 — PROPOSED / NOT_RUN unless explicitly marked.** All real model trials below require the later Gate authorization. No Gen2 challenge runs or production implementation occur in G20.

# G20-F — 可证伪验收与对照实验

## 两个独立评价面

**Engineering outcome**：继续原 OrderFlow suite/DBOracle：Smoke8、A14、D-v01 28、D-v02 36（B/C仍未实现）；Fixture/Oracle/Reference/suite版本hash冻结，实际候选完整diff经Submission verifier，独立评测只收代码，不接受Agent自评分。Runtime/Provider故障与任务FAIL分开，原NOT_RUN绝不补写。普通项目未配置独立verifier仅EXTERNAL_UNVERIFIED，不能进入可信Outcome主张。

**Governance correctness**：独立维护者 expectation manifest/直接数据库读校验，用预注册可公开事实和scope、完整typed路径、已注册source、epoch与撤回事件判断预期三态/理由/不可访问性；与Core实现分文件、不同权限，不能只读取Core返回decision当Oracle。Synthetic图必须明确source_type=synthetic_or_test_fixture，永不声称来自真实Agent或新OracleOutcome。模型试验的可信反证必须来自真实独立FAIL工件与正确关联，不把任意FAIL挂到经验上。

## 强制场景与独立判据（全部 PLANNED）

| ID | 公开合成fixture/输入 | 独立验收定义与负控 |
|---|---|---|
| T01 | 完整同scope支持链、所有task必要前提KNOWN | APPLY含全部必要path/ref；删Authority或manifest后不再APPLY |
| T02 | 同T01，只把一个必要task事实UNKNOWN/MISSING/NOT_OBSERVED | VERIFY+正确缺项；bool字符串/1不可代true；Claim填值不升级 |
| T03 | 一个必要拓扑前提已知违反，如单进程RLock经验转独立进程 | ABSTAIN+具体冲突premise；增加100个异域成功也不得APPLY |
| T04 | 两条真实成功经验分属库存/lease-authority或不同datastore | 两scope独立，不能因success次数/相似文本自动合并；删Episode字段不改变结果 |
| T05 | 同域策略关联的真实独立支持+业务FAIL反证 | VERIFY/conflict并列路径；仅反证ABSTAIN；ERROR/TIMEOUT不当业务反证 |
| T06 | 隔离图copy支持/反证关键边cut，再逐字节恢复 | 删除→完整性降级而非利好；恢复→同context/policy裁决恢复；原图不动 |
| T07 | Agent注入verified/outcome/Hostprincipal/私有path/prompt payload | Schema+broker+Host拒绝，DB无可信结果/COMMIT；原始拒绝不被掩盖 |
| T08 | 已发布R1被Host撤回/过期/authorities revoked | 新推荐不含当前可用支持，旧cursor失败；history单独grant才可REPLAY |
| T09 | 新Session只获得正式图，初始缺陷代码与source epochs一致 | raw resolve确含newID→完整bundle→decision→实际patch/明确拒绝→原Oracle→Hostfeedback；任一步缺失不得称采用 |
| T10 | 空图、DB断连、规模257候选/513path/8MiB+等 | EMPTY合法；断库/overflow显式error、无fallback或虚构PASS；重连重新查询 |
| T11 | 两tenant相同localID/同run字段，外tenantcursor/资源猜测 | physical graph selector不受Caller控制；无数据返回/无写入；恢复授权不复用旧epoch |
| T12 | 真实原生lead+至少两个不同child，继承历史/伪child重复记录负例 | typed父spawn+child自身新turn/action/final+父completion；无法观察身份UNAVAILABLE，三个Single不通过 |
| T13 | 错把artifact_after验证事实填入task或artifact_before | 拒绝/UNKNOWN，不绕过必要前提；历史legacy flat context不自动重标 |
| T14 | 两Host并发对同expected_head/epoch审批，准备阶段崩溃 | 恰一个提交、另一个STALE_HEAD；无半发布可见；相同body幂等、不同body冲突 |

T01–T14分别预注册expectation JSON、graph before/after、实际read/write query、public MCP envelope、来源hash；不在Participant输入中提供期望裁决。复杂样例不能仅靠固定字典返回PASS。

## 实验预注册与公平性

三arm：**Graph Governance**使用正式四工具和实时图裁决；**Raw Memory**得到同一授权语义corpus的原始公开records/relations/validity/withdraw信息的确定性文本文件（普通文件读取，非伪Aevora工具，不调用Core裁决）；**No Memory**没有经验corpus。Graph与Raw同源snapshot、public事实/信息范围一致，Graph的关系查询和裁决是处理因素。没有办法让NoMemory拥有相同memory信息；该差异正是处理。记录不同tool surface和可见字节，不假装完全相同token开销。

同一matched block：相同任务/初始buggy tree/公开测试/模型实际标签与max/运行模式/原Oracle/环境资源/Gateway重试与completion-aware政策。每arm全新Session/workspace/owned graph，不分享其他trial对话/patch。Graph/Raw起点从相同已审批public corpus生成；trial反馈写入各自owned分支，**不更新后续比较试验的冻结起点**。组内顺序由预注册seed随机化，保留原请求与分配表；失败首轮不删除、不挑成功。

计划主cohort：4任务cell × 5 matched blocks × 3arm = **60 fresh Runs**，属于G2-4 NOT_RUN。cells：A单进程线程、D-v01多进程、D-v02 lease任务、D-v02同域策略反证/必要事实未知上下文；工程Oracle分别14/28/36/36，对比在cell内，不直接混合测试数量。pilot每arm一个独立Run仅验证配置，单独标pilot不混入分母，失败亦保留。预注册后样本数或设计改变需新protocol/version，不用结果驱动扩样伪显著性。

**Graph Intervention**：同一graph的owned copy，固定输入/policy/source，分别cut支持、引入有可信来源的同域反证、产生并行revision冲突、恢复；语义层metamorphic检查先离线完成。工程行动对照用全新matched Agent session读取intervened/restored图，至少2 matched pairs；不resume旧session使它记住答案。不把query差异自动宣称Agent行为差异。

## 指标、失败分母与结论

- 任务成功率：所有分配Run为分母；同时给native启动/完成、Oracle执行、任务PASS三个分母，不排除provider失败。
- 负迁移率：预注册与当前公开前提已知不符的策略仍被实际claim/patch采用的Run；仅候选返回不算采用。claim-only与action-correlated分别报告；无法判别UNVERIFIED进入独立分类，不能当无负迁移。
- 溯源完备率：RETRIEVED/BUNDLED/DECIDED/ACTION_CORRELATED/INDEPENDENT_OUTCOME/FEEDBACK_PUBLISHED逐层布尔与unknown，不合成一个“智能度分数”。
- 耗时：native/协作等待/Gateway首字节与SSE/评测/Host各分段；实际requests、去重usage、429与重试。获取不到真实billing标UNAVAILABLE；不设置费用/Token/总请求上限。
- 决策正确性：独立T矩阵期待、Graph敏感性、scope错误率；工程PASS不能替代WHEN/WHY正确，OracleFAIL也不自动说明治理系统失效。
- 置信/效应：报告原始paired outcomes、cell分层率与区间；不因一次或两次成功宣传普遍收益。未经随机分配、同源信息和前置冻结，保持CAUSAL_UNKNOWN；即使配对结果较好也披露小样本/任务族局限。

正式采集前冻结LiveGate(source/contract/query/schema/fixtures/expectations/model/资源)、安全隔离和支持None总预算；任何改源产生新epoch/cohort，不能旧Run补打新代码分数。Provider重试是故障谱系，不是静默替换失败Run。
