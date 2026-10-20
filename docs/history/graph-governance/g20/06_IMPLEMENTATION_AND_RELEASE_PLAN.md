**Freeze candidate 2.0.0-rc1 — PROPOSED / NOT_RUN unless explicitly marked.** All real model trials below require the later Gate authorization. No Gen2 challenge runs or production implementation occur in G20.

# G20-G — G2-1 至 G2-6 可执行开发顺序

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

1. `models.py`增加独立schema2 catalog及有界SnapshotChunk/manifest loader，原1.x常量/验证保持；`contracts.py`实现本目录typed schemas，同canonical digest，拒phase混淆/tenantCaller/unknown升级。新增test_contract_v2.py，读取example/negative fixtures。
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
