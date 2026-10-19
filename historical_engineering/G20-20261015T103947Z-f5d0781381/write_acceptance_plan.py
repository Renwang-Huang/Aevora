from audit import *
D=P/'docs/gen2/g20'
def doc(n,t):
 with (D/n).open('x') as f:f.write(t.strip()+'\n')
H='**Freeze candidate 2.0.0-rc1 — PROPOSED / NOT_RUN unless explicitly marked.** All real model trials below require the later Gate authorization. No Gen2 challenge runs or production implementation occur in G20.\n\n'
def design(n,t):doc(n,H+t)
design('05_BENCHMARK_AND_CAUSAL_EVIDENCE_PLAN.md','''# G20-F — 可证伪验收与对照实验

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
''')
design('HERO_STORYBOARD_AND_EVIDENCE_SHOTS.md','''# 四幕 Hero 与机器可核查 Evidence Contract

**未执行演示计划**。图中的Agent A/B/C是将来独立真实session，不是本次维护者角色。当前V5C.1两次Single只作历史案例，不算本轮三幕或Multi。

| 幕 | 公开任务与自由决策 | 必须捕获的真实链 | Shot / 可否宣称 |
|---|---|---|---|
| I — Learn responsibly | 全新A可从现有A/D-v02公开任务调查，不指定策略、经验ID或proposal内容；保留原API/并发 | native session→真实graph query→实际diff→原Oracle→自然proposal→source/semantic review→publish；proposal可以在Oracle前、publish必须后 | Activity新Session/patch/outcome；Timeline显示Host审批与R1；无自然提案则PROPOSAL_NOT_ACHIEVED |
| II — Test the boundary | B面临task必要前提变化/未知或相关反证；保留旧经验竞争，Agent可合理VERIFY/ABSTAIN或选另一策略 | Core真实premise/path/authority→changedverdict→真实bundle/claim→行动或明确拒绝→独立Oracle | Explorer前提/反例与path；同时显示Core推荐和Agent声明，不伪造行为遵从 |
| III — Transfer a revision | 新C从独立缺陷初始状态读取R2或R1的合法更新；至少本幕一个真实lead+2child协作 | newSession/newRun→published revisionnewID→完整Bundle→Decision→actualpatch→originalOracle→trustedfeedback；typed父子任务/执行/完成/回传 | Activity可核parent/child、修复和独立结果；新ID列表出现不算采用 |
| IV — Graph makes a difference | Host在隔离copy做cut/反例/版本冲突/restore；原业务fixture与历史Oracle不动 | beforegraph+query+verdict→interventiontypedHostevent→afterquery+reason→restore；工程行动差异需另有freshtrial | Graph witness高亮和Timeline干预；无真实行动差异只称裁决敏感，不称Agent因果收益 |

## 避免指定修复叙事

S1如选择SQLite条件原子更新，尊重真实策略；不要求为了RLock故事制造后续错误。ActII的变化从已声明必要前提、operation scope、unknown或**真实独立反例**建立。A→D多进程可作单进程策略seed的明确合成负控，不能冒充S1自然发现。D-v02 lease-authorization可区分旧inventory经验；需要phase化事实时按新注册/Host验证，不修改旧authority_validation或Oracle。自然提案/修订不成立则如实展示pending/reject与缺口，不把人工代写包装为Agent记忆。

## Evidence Contract（未来生成、G20只冻结）

每act manifest：act_id/run_ids/session_ids/source_commit/tree/query/schema/policy版本；初始publicfixtureSHA；原事件(file,line,originalSHA,sanitizedSHA)；Recommendation/epoch/premises/support/counter/governance ids；实际交付receipt；Decision untrusted；Patch SHA及appliedtree；独立report/JUnit/DBOracle/source pins；Host review/commit/feedback；before/after graphhash；status和missing_fields。

验证器只读原始证据，断言时间偏序而非凭展示顺序：Oracle/source核验 < Host publish < freshC < newID Bundle < decision < first相关action < OracleEnd。第一次临时patch不等最终修复；native日志无official timestamp时用Host observed_at且不伪称官方时刻。所有typedrefs必须可解析到完整rawline并核hash；脱敏映射保留，不能删除失败响应/终止。

## 三页最小叙事（复用Console）

- Activity & Decisions：Session/parent-child/Runtime vs Evaluation、Core verdict vs AgentClaim、Patch+Oracle，来源不够显UNAVAILABLE。
- Experience Explorer：active/scoped revision、必要前提、支持/反例路径、authority与withdrawal；可跳原始安全receipt，不提供文件系统路径/私有Oracle。
- Governance Timeline：proposal/source-review/semantic-approval/publish/feedback/withdraw与graph epoch。LIVE展示当前owned图，REPLAY展示明确历史pin。

G2-5浏览器实际点击/离线/清空状态/Graph选择测试；不用Mock路由。G2-6视频与截图来自已通过Evidence Contract的真实Run，视频不替代原始日志。公共版只使用许可明确synthetic/public例子与审批后的脱敏材料；历史私有图不直接上网。四幕未完整成立不可宣传完整Hero成功。
''')
design('06_IMPLEMENTATION_AND_RELEASE_PLAN.md','''# G20-G — G2-1 至 G2-6 可执行开发顺序

G20冻结**候选合同**，后续每Gate需独立批准。下面目录为明确扩展点，不表示文件已实现。不得重造Runtime、Core、MCPBroker或OrderFlow；新业务Episode B/C不在此计划。

| Gate | 前置/最低垂直切片 | 具体source与验证 | 真实证据/退出/回滚 |
|---|---|---|---|
| G2-1 | G20独立审查批准；新owned tenant graph；真实多跳+必要前提+同域反证→Recommendation | 原models/graph_repository/experience_resolver/evidence_bundle/governance；新graph_queries.py/arbitration.py/contracts.py；新增独立v2 tests，原1897身份保持 | T01–06/10/11/13；真实Qplan/row/epoch/cutrestore、wire分页；Core只用DB，无model演示必要；失败停Gate，切回旧profile/图，保留新图 |
| G2-2 | G2-1完整witness；Host authority注册/phase factreceipt/sourcepin | 原candidate/admission/feedback/outcome bridge + tenant binding；新Host facade；不改私有Oracle | T07/08/14，真实独立buggy/ref报告作为正反source；并发CAS、崩溃staging、撤权cursor；严格来源/范围/外部unverified；回滚授权profile，历史append记录不删 |
| G2-3 | G2-2 + 固定LiveGate + isolation None预算实证 | integrations/codex_agent/trace/native_rollout_trace/aevora、原participant_sandbox；仅精确identity join；不新增orchestrator | 至少新lead+2不同child自身任务/执行/完成/父收回；真实工程diff+原Oracle；S1→B→C自然发布/继承；多Agent/任务/继承分层，不要求一次全PASS；失败保留，必要修复新cohort |
| G2-4 | G2-3链可用；独立expectations和pilot预注册 | 新受控experiment driver调用成熟Runner；aevora_maintainer比较/导出；Raw是只读公开文本，不是伪Graph返回 | 60Run matched Graph/Raw/NoMemory +独立图干预；所有失败分母；原Oracle不变；达不到区分力诚实CONDITIONAL，不调Oracle凑收益 |
| G2-5 | 原生、治理、差异化证据已认证，前三Gate可并行准备shot/公开脱敏 | console/src/projection/server、web现有三页、h4新versioned hero contract；不替换旧Replay | 真LIVE/REPLAY/断库清空/read-only/UI source refs；Evidence Contract完整四幕，实际浏览器和视频素材；失败回旧UI，未支持数据明确不展示成功 |
| G2-6 | 全部前Gate独立结论/未决风险 | tools/public_release allowlist、独立Core/Console包、docs/publicREADME/Cypher/AI披露/视频索引 | 原1897+全部新测试、干净install/真实MCP/DB/Console/Benchmark、安全secret/private-byte扫描/FullLite与负测；来源逐文件；用户另批才push/public；回滚本地release，证据不删 |

## G2-1 第一批直接可做的source-level任务（本轮NOT_IMPLEMENTED）

1. `models.py`增加独立schema2 catalog，原1.x常量/验证保持；`contracts.py`实现本目录typed schemas，同canonical digest，拒phase混淆/tenantCaller/unknown升级。新增test_contract_v2.py，读取example/negative fixtures。
2. `graph_repository.py`增加显式v2 factory/tenant HostBinding，原factory不自动升级；`graph_queries.py`落地Q00–Q05/Q08，包括all-native-projection/payload crosschecks、OPERATIONAL索引、完整manifest和epoch start/end、+1 overflow。query模板先在owned DB跑EXPLAIN/constraints。
3. `arbitration.py`从完整证据生成无全局分数的Recommendation，复用resolver/governance比较器；保持legacy policy不变。新增独立test_graph_v2_arbitration.py：同输入±关键边/同异scope/未知/真实FAIL策略关联；不是固定Episode if。
4. `mcp_server.py`Host选择schema profile，原1.2四工具不破；`mcp_projection.py`增加epoch/authz检查和必要metadata，维持wire/cache上界；新增test_mcp_v2_epoch.py真实SDK/UDS拒绝和完整重组。
5. 新维护者验证脚本由 `tools/dev.py` 的**版本化子入口**启动（待实现，现有--help没有该命令）；单一命令调用既有pytest/ownedDB即可，不重新调度Agent。第一批验收输出必须含sourcecommit/diff、原1897 identity、querycounts/最大wire、正反controls、无Oracle改变。

每个小提交使用明确named paths，真实本地Git时间；不得将新任务带来的文档PASS冒充功能PASS。出问题保留图/命令和原始失败，先在owned分支修复；不合并冻结main，不force reset/GC。

## 非功能要求与前移工作

所有阶段同步维护provenance/AI披露/public allowlist清单与Hero capture，不能G2-6临时编故事。新产品Core保持不依赖Benchmark；trusted generic verifier接口供普通项目独立接入，默认EXTERNAL_UNVERIFIED不假装完整Oracle。公开loopback/read-only保留；多租户/权限边界先于公开部署。资源控制/手动cancel保留，绝不因费用、Token、总请求阈值停止健康挑战。

**Gen2必须完成**：graph-native bounded arbitration、conflict/revision/revoke、Host verified反馈、跨session身份、真实native协作、ordinary接入、三页/四幕、对照和完整交付。**增强但非完整性前提**：向量候选召回（不能覆盖前提）、多DB适配、集群HA、非本地主体签名、广域统计研究。未实现增强披露限制，不把核心故意留给Gen3。

## 比赛来源与发布风险

以实际官方rules+FAQ及本轮HTTP/hash收据为准：[Rules](https://www.wemakedevs.org/hackathons/falkordb/rules)、[FAQ](https://www.wemakedevs.org/hackathons/falkordb)。要求真实FalkorDB核心作用、公开源码/README图模型/Cypher/视频/部署或本地运行说明/track/AI披露；已有通用依赖可复用，但主要作品设计和实现的赛期原创界限需诚实披露。窗口2026-10-15 00:01IST=2026-10-14 18:31UTC，至18日23:59IST=18日18:29UTC。

冻结Gen1大部分为赛前工程；V5C提交时间在窗口前，V5C.1修复commit在窗口中，但**commit时间不证明首次设计/编码时间**，也不把既有主要Core更名成Gen2新作。本轮新架构文档有真实source/commands起源；拟新graph-native索引/authority/phase/epoch/arbitration/交付链将在G2-1等形成独立实际diff和验证。参赛应明确展示这些新增机制及旧底座，而不是重提交旧代码。

`HACKATHON_CONTRIBUTION_MATRIX.csv`逐base文件与本轮新资产记录来源/首次可见commit/内容pin/周期；第三方依赖明确来源与许可核查状态。**ELIGIBILITY_UNCERTAIN**：请主办方确认如此规模的私有旧Core是否属于可复用一般基础设施、哪些新增主要FalkorDB实现足够形成新作品；未得到答复不能自行认证合规。当前不发布GitHub，不改变私有可见性，不伪造日期；用户后续批准发布是单独动作。
''')
design('PUBLIC_PRIVATE_BOUNDARY.md','''# 公共、Participant、可信Host与维护者边界

| 资产 | 产品发布 | Participant | Host / Full | 约束 |
|---|---|---|---|---|
| aevora_core/src、公开Core docs/Receipt例子 | 现有allowlist候选，新增v2需检查 | 只能proxy/tool返回，不mount服务器/admin | 实际server字节pin | Core安装不得导Benchmark |
| console/src/web、批准h4 demo/Replay | 可审核public | 非工程Participant输入 | 保留原镜像/包/浏览器证据 | LIVE/REPLAY明确，不隐藏失联 |
| 新v2 schema/Cypher/公开synthetic例子 | G2-6审核后可公开 | 仅公开任务与工具schema，无期望答案 | 原始design/negative期待保留 | 本G20 docs默认维护者设计，未自动加public allowlist |
| app公开buggyfixture/Public Issue/Public tests | 单独Benchmark公开任务协议 | 当前Run可见 | 基线SHA/实际patch | 不共享前轮patch/rollout |
| benchmark/runner/submission、evaluator/Oracle/Reference/private manifest/labels | 不随产品公开 | 禁止 | 必须保留且独立调用 | 全回归/安全必须保留，不靠命名隔离 |
| Graph admin/password/Gateway key/HostGrant/旧native state | 禁止任何包/日志/单项secretSHA | 禁止，只有run-scope token proxy | 外部0600/0700 | no-follow读取，撤销scope，秘密值仅内存扫描 |
| Full原始Native/HTTP/MCP/Outcome/Graph数据库 | 不公开、不同tenant不可读 | 禁止 | 保存失败/原hash/权限 | 本地hash不等外部存证；sharedkernel限制披露 |
| Audit-Lite/公开Hero摘录 | 独立脱敏/权限/license后单独release | Audit材料不作Participant输入 | 原→导出逐文件/逐行SHA | 无Hidden Oracle/reference/privateDb；不静默删失败 |

现有tools/public_release.py::chosen是可运行权威，docs/gen2/g20不因Git跟踪自动发布。G2-6增加allowlist须逐文件审查、包成员/实际privatebyte/秘密值内存扫描、干净install与真SDK；不把此维护者仓库整体推私有GitHub再假设以后转public安全。

MCP无Host outcome/publication/arbitraryCypher工具；Graph物理tenant映射由可信服务固定。Native Runtime与业务命令两个层级隔离沿用原ParticipantSandbox/bubblewrap/cgroup；Host模型连接key不进入子shell。原生children继承权限，role指令不形成独立安全域。真实攻击探针覆盖Oracle/Reference/privateconfig/maintainersrc/otherruns/credentials，失败则禁Live，不降低沙箱换联网。

历史归档保留只读。新数据生命周期：owned runtime生成→Runner停止候选→独立Oracle→Host验证→graph追加→资源回收→Full seal→Full外Lite/negative/terminal receipts。不用临时历史映射把私有内容暴露给Participant。公开数据限public/synthetic/自有且授权的事实，不直接发布个人/私有graph。第三方license未明确时阻止该文件发布，保留待核，不假设本地拥有就能公开。
''')
print('WROTE_F_G_RELEASE')
