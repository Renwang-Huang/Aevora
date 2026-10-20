from audit import *
D=P/'docs/gen2/g20'
text='''# G20 架构决策记录（冻结候选，不是生产实现）

全部 **ACCEPTED_FOR_REVIEW / PROPOSED**。本地合成探针只对标出的语法/集合性质 TESTED；未执行生产或新Agent。每项都给实际源依据、替代方案、代价、兼容和可证伪回退。

## ADR-01 — 保留显式ExperienceRevision，不覆写旧策略

依据 graph_repository.append_rule_revision / governance.project，已存在不可变revision+SUPERSEDES。选择增量typed projection/manifest activation，复用既有节点；不建立同义第二套Revision。替代原节点可变version属性会使旧Query/Outcome失去原语义，拒绝。代价是更多path与显式选择。1.x保持原图；新v2图导入记录原ID/SHA，不改旧字节。验收并发revision、scope并存、循环/缺边、旧snapshot原值；失败切回旧profile/图。

## ADR-02 — 反证是受信观察事实，CONTRADICTS是作用域内推导

依据已有COUNTEREXAMPLE→Evidence→VerifiedOutcome/Context和resolver.evidence_conflicts。保留真实独立FAIL与strategy/artifact关联，当前context下推导同域冲突；可持久化DERIVED ConflictAssessment，不是Agent可造的事实边。替代让LLM自然语言直接连CONTRADICTS会混淆异域策略与authority，拒绝；静态全球冲突表同样拒绝。成本是每次scope/phase核验。1.x行为不改；v2权威匹配支持+反证VERIFY，只有匹配反证ABSTAIN，不自动最新胜出。T04/05差一前提/异域控制和恢复证伪。

## ADR-03 — 无全局信心分数

依据resolver严格bool/type/必要前提/真实scope判定与feedback的UNKNOWN归属。选择硬性否决/unknown/完整性优先，列全多候选，不以PASS次数累计可靠度。替代相似度+成功率权重可能覆盖必要前提违反，拒绝。相似检索最多未来召回优化，不能参与可信裁决；不需要为了增强而另建Vector DB。成本是保守VERIFY较多。T03增加100异域成功仍ABSTAIN；1.x不改，v2回滚策略版本，不重打历史分数。

## ADR-04 — 官方客户端、受限多跳模板，不采用新Agent/Graph框架替代Core

依据实际GraphRepository官方falkordb-py、官方MCP SDK、CodexAgentAdapter。调研[FalkorDB Python SDK](https://github.com/FalkorDB/falkordb-py)、[Graphiti](https://github.com/getzep/graphiti)的现成图/时间建模能力；复用官方参数化、索引/约束、原有governance，不引入从模型抽取事实即可信的第二套生命周期。Graphiti是成熟时态图研究参考，不替代独立Oracle/Host，未装入产品。替代整体GraphRAG重构不可证明兼容且增加信任面，拒绝。新增只在query witness/typed projections/tenant epoch/arbitration扩展。真实owned Q04/cutrestore探针；生产预算/性能在G2-1实测，回退旧profile。

## ADR-05 — 有限查询、原wire预算与snapshot分块

依据mcp_projection实际SDK双序列化、连接cursor/cache；models.validate_record256KiB。选择196608wire/24576page/8MiB document/16MiB cache/32docs/900s游标保持，Graph各候选/路径上限+1检测。替代扩大262144、先limit丢反证、无限缓存都拒绝。**传输分页不能解决单个Graph QuerySnapshot超过256KiB**：v2 QuerySnapshot为不可变manifest，完整canonical document可分成至多128个≤64KiB UTF8文本SnapshotChunk，以HAS_CHUNK实际边、index、chunkSHA、fullSHA重组；单节点payload仍≤256KiB，文档仍≤8MiB。小snapshot可inline，新profileloader显式识别，旧snapshot原语义不改。成本额外节点与IO；未知/缺块/越权/超限error而非残缺推荐。T10、边界Unicode/丢块/重排/hash/撤权测试；回退旧图profile，不改历史快照。

## ADR-06 — Staging + 单query提交fence + 双读epoch，不虚构全局事务

依据CandidateLifecycle.transition已是单queryCAS，publish/feedback多query明确非原子。选择不可变prepared manifest/关系，只有TenantState→COMMITS激活；candidate event/head与epoch同最终写query。读取epoch前后相同、所有语义激活遵守fence才声称coherent epoch。替代“多个Python操作包起来就事务”拒绝；直接覆盖旧图节点也拒绝。代价是staging垃圾/恢复路径和Host写者纪律。Minimal CAS probe已TESTED，完整生产CAS/崩溃恢复NOT_RUN。G2-2并发恰一提交、stale拒绝、PUBLISHING不可见；失配停Gate，不提高隔离宣称。

## ADR-07 — 每tenant独占图，Host registry固定映射

依据现GraphRepository graph_name来自Host环境，但尚无完整tenant API。选择服务能力绑定一个tenant及graph、id namespace、逐endpoint tenant校验和authz epoch。替代单图只依靠工具传tenant WHERE容易串租户/漏过滤，拒绝；也不新造数据库系统。成本是每图schema/运维开销。合成复合约束/WHERE只验证引擎，不证明服务隔离。1.x仍是单配置图，v2显式工厂；cross-tenant cursor/broker/导入混边T11必须实测。回滚registry指向旧profile，不销毁任何图。

## ADR-08 — 四工具版本profile，Host authority不上放

依据mcp_server的8-field Claims/typed proposal、admission真实来源与Outcome verifier。选择每SDK实例由Host固定1.2/2.0 profile；工具名称继续4个，review/outcome/publish不公开。替代不断新增Host工具或让Agent传verified bool/任意Cypher被拒。代价schema适配/兼容测试，freeze legacy list_tools真实快照；版本不匹配显式拒绝，不静默降级。默认普通项目仍EXTERNAL_UNVERIFIED，注册独立verifier后才可进入Host权威。T07/08/K01–12证伪，回退旧profile。

## ADR-09 — 原生身份与工具归属分别证明

依据native_rollout_trace pinned0.162.1及mcp_service agent_thread_id=UNAVAILABLE。选择真实父typed spawn+子自身session_meta/newturn/action/final+父回执为协作证据；MCP actor另做精确join，不用PID/时间邻近硬连。替代三个Single当多Agent、主Agent正文声明或解析角色名字造spawn拒绝。成本可能有工具thread归属UNAVAILABLE；不影响真实已证父子事实，但不能宣传更细粒度归属。官方[非交互模式](https://developers.openai.com/codex/noninteractive/)和[Subagents](https://developers.openai.com/codex/subagents/)是参考，当前安装help/schema优先，不把新版API字段拷成旧CLI字段。G2-3新两child必测；回退single只报告single，不冒称multi通过。

## ADR-10 — task前提与artifact/evaluation后置事实分phase

依据平面normalize_context、V5C.1 CoreVERIFY/AgentAPPLY、feedback._environment初始能力。选择新Host phase facts+rule前提catalog，结果验证不伪装目标已具备条件。替代把authority_validation从unknown写true或删除material键以得到APPLY拒绝。成本是新context规范/独立来源；旧flat事实只在legacy原语义，不能自动重标。v2必要条件只task.*或明示artifact_before.*；artifact_after/evaluation仅证据与后置结果，不为自身前提背书。T02/T13/真实S1→C新来源验证；回滚新profile，历史成绩不更新。

## ADR-11 — 可追踪关联不等于因果

依据feedback真实CONSIDERED/Decision/Snapshot/ObservedAction，V5C.1二次完整Bundle与patch时间证据。选择DeliveryReceipt/Recommendation/Action分离，claim untrusted，原Oracle只判工程。替代“PASS+新ID=采用有效”“更多曝光=更强支持”拒绝。W3C [PROV-O](https://www.w3.org/TR/prov-o/)的Entity/Activity/Agent分离作为概念参考，不引入RDF转换或声称标准一致。成本是多层unknown；Graph/Raw/NoMemory与干预预注册，失败分母完整。T09/对照可证伪；因果仍UNKNOWN不阻塞诚实交付，但不能营销因果收益。

## ADR-12 — 参赛来源保守声明

依据官方Rules/FAQ和真实Git source/history。选择逐文件区分继承、第三方、本轮设计与将来生产新增；V5C.1赛期commit仍不自动是主要新作。替代今天重新提交旧仓库并暗示原创，拒绝。成本是需主办方确认旧Core复用边界，ELIGIBILITY_UNCERTAIN，不自行认证。后续新graph-native关键实现必须有真实diff/现场sourceepoch/验证，AI辅助披露与人类理解。公共allowlist扫描前不push，发布另批。

## ADR-13 — completion-aware无累计计费预算，故障保护仍有效

依据CodexAgentConfig与GatewayBroker None配置和V5C.1实际77完成请求。选择Live明确None总时间/请求/费用/Token，保留并发/idle/provider429有限退避/重复错误风暴/cgroup/磁盘/cancel；Tool/DB单次资源预算不是Agent计费上限。替代旧900s/160、soft20USD/hard40或大整数伪无限拒绝。保留legacy bounded回放只为兼容，不用于新正式Live。G2-3挑战超过旧阈值不截断/真实cancel清理；故障保留谱系，不洗原ERROR。
'''
with (D/'ARCHITECTURE_DECISIONS.md').open('x') as f:f.write(text)
print('ADR13_WRITTEN')
