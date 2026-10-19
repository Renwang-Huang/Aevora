**Freeze candidate:** `aevora.gen2.contract/2.0.0-rc1`. **Status: PROPOSED / NOT_IMPLEMENTED**, except individually identified AS-IS source and TESTED design probes. This directory is MAINTAINER_DESIGN_REVIEW, not Participant input or an automatically approved public export. G20 does not authorize G2-1.

# G20-D — Experience Evidence Graph v2 Schema

## 版本与迁移

拟版本 `aevora.graph/2.0.0-rc1`，query/policy分别`aevora.witness/2.0.0-rc1`、`aevora.whenwhy/2.0.0-rc1`。v1.0/1.1/1.2真实目录见 source_audit/AS_IS_*。既有 initialize 检查**精确约束集合**，不能往旧图直接加标签再声称向后兼容。Gen2新owned图采用新catalog，按租户显式导入；旧图/历史schema保持只读。

导入是新图中的`legacy_alias`映射，保留原ID、原schema、原payload SHA/sourceManifest；新ID明确tenant namespace。不改原始payload、不自动提升Source authority、不把OBSERVED_OUTCOME变支持，不让未分phase旧facts绕过验证。输出逐文件/节点/边diff、数量与恢复收据。切换仅由Host配置，不由Agent选择graph。

## 节点目录（原名优先复用）

| 标签 | 冻结语义 | 归属 / 新旧 |
|---|---|---|
| Experience | 策略稳定身份，标题不是可执行指令 | Host发布；EXISTING |
| ExperienceRevision / Rule / Premise | 不可变声明、显式scope/validity/supersedes；必要前提与typed phase | EXISTING增量 |
| Evidence / VerifiedOutcome / Context / Task | 完整支持/反证/观察路径、独立结果与phase化事实 | EXISTING增量；仅Host可创可信结果 |
| Candidate / CandidateEvent / LifecycleHead / SourceVerification | 原提案与CAS事件链、来源审批；Head是唯一可变cache | EXISTING复用 |
| GovernanceEvent / AuditEvent / Feedback | 撤回/限制/到期/冲突处理与独立观察；无因果自动归属 | EXISTING增量 |
| Agent | 本次native线程身份，不是人名/人格；source runtime及版本 | EXISTING正式化 |
| Query / QuerySnapshot / Decision / ObservedAction | 查询epoch、不可变裁决、未可信Agent决定、实际Patch | EXISTING正式化；Decision仍名不变 |
| ExternalObservation / Schema | 未认证外部结果/明确schema | EXISTING |
| TenantState | generation/semantic epoch/authz_epoch，Host registry独占 | NEW |
| Authority | verifier/Host principal注册与key/version/source pin，不是Agent自填字符串 | NEW |
| PublicationManifest | 声明待激活revision/edges/hash/authority/expectedepoch | NEW |
| Run / Session | Benchmark/ordinary run与真实独立session分开，source identity/hash | NEW |
| ToolEvent / DeliveryReceipt | 原始请求/响应来源；实际已完成交付的页/bytes/摘要 | NEW |
| SnapshotChunk | ≤64KiB canonical UTF8分块、index/chunkSHA；最多128块，由QuerySnapshot manifest声明 | NEW |
| Recommendation | 指向query/context/policy/epoch/path hashes的Core裁决 | NEW DERIVED |

不新增名为IndependentOutcome的重复结果表；VerifiedOutcome承担该语义。反例沿COUNTEREXAMPLE路径，Conflict是推导assessment，不因一句自然语言建立可信CONTRADICTS事实。

## 共同字段与强制校验

每个不可变节点：`id,tenant_id,record_version,kind,payload_json,payload_sha256,created_at,source_type,authority_ref,visibility`。id=`kind:SHA256(canonical([tenant,source_namespace,stable_key]))`，最长240ASCII；原native UUID作为字段保留。payload采用现有有限JSON规范，拒绝NaN/重复key/非UTF8。typed索引投影必须逐项等于payload；否则 GRAPH_INTEGRITY_ERROR。只有TenantState及原LifecycleHead是明示可变指针，旧值由不可变事件保存。

native投影列按标签固定：tenant_id/id/experience_id/revision_id/run_id/session_id/native_thread_id/epoch/state/kind/verdict/valid_from/valid_until/payload_sha256，不从Agent任意键创建列。空值不能表示已知；fact `{availability:MISSING|UNKNOWN|NOT_OBSERVED|KNOWN,phase,key,value,authority_ref,source_refs}`；非KNOWN时value=null，KNOWN必须有授权独立来源。artifact事实不能填task槽。

每label UNIQUE(id)+MANDATORY共同字段，tenant每图隔离且额外断言tenant一致。合成复合UNIQUE(tenant_id,id)只验证引擎能力；生产以tenant独占物理图+namespace ID为主。每relation id=SHA256(type+typed endpoints+tenant)并声明payloadhash；拒绝跨tenant/缺endpoint/多重语义歧义，关系UNIQUE若未部署验证则应用单queryMERGE+manifest比对，不假装DB约束保证所有端点语义。

## 关系、方向与权限

| 来源→关系→目标 | 性质 | 基数/权限 |
|---|---|---|
| Experience→HAS_REVISION→Revision→USES_RULE→Rule→REQUIRES→Premise | 事实声明 | 已激活revision的rule恰一；premise列表与immutable声明完全相同 |
| Revision→SUPPORTED_BY/COUNTEREXAMPLE/OBSERVED_OUTCOME→Evidence→VERIFIES→Outcome→IN_CONTEXT→Context→FOR_TASK→Task | 事实观察 | 完整path；支持PASS/反例业务FAIL、同域且有策略工件关联；仅Observation不自动支持 |
| Outcome→ATTESTED_BY→Authority | NEW授权来源 | 注册独立verifier且精确Outcome digest；未认证External不得连 |
| Revision→PUBLISHED_BY→PublicationManifest←COMMITS←TenantState | NEW激活事实 | staging无COMMITS不可见；finalfence和epoch同query |
| Revision→SUPERSEDES→旧Revision | 有scope的显式取代 | 同Experience、无环、最大8hop；未知scope不任意选最新 |
| GovernanceEvent→GOVERNS→Evidence/Revision；GovernanceEvent→PUBLISHED_BY→Manifest | Host治理事实 | 同tenant、已提交、有效时间、scope；撤回只影响当前选择不删历史 |
| Session→HAS_AGENT→Agent；Agent→SPAWNED→Agent | NEW/正式化观测 | official自身metadata与父typed事件匹配，不能靠sharedRun推定 |
| Run→HAS_SESSION→Session；ToolEvent→IN_SESSION→Session；ToolEvent→BY_AGENT→Agent | 观测 | BY_AGENT仅精确可验证映射；未知保留UNAVAILABLE，不乱连 |
| QuerySnapshot→HAS_CHUNK→SnapshotChunk | NEW immutable storage事实 | manifest/index/hash完整匹配，同tenant，非授权内容不可分页 |
| Query→CONSIDERED→Experience；Query→AT_SNAPSHOT→Snapshot | 原候选/快照 | 不等于送达；Query→PRODUCED→Recommendation为派生 |
| ToolEvent→DELIVERED→DeliveryReceipt→OF_RECOMMENDATION→Recommendation | NEW交付事实 | broker完整frame写出/成功响应；用户阅读/采纳仍未知 |
| Decision→RESPONDS_TO→Query；Decision→CITES→Recommendation；Decision→DECIDED→Experience | 原claim+新准确引用 | 同run/session/授权scope；claimedAPPLY不改变Core |
| Outcome→OBSERVED_ACTION→Action；Decision→CORRELATED_ACTION→Action | 原事实/新派生 | Patch/tree/source hash；correlation不是mental causation |
| Feedback→FROM_OUTCOME→Outcome；Feedback→RESPONDS_TO→Decision；Experience→HAS_FEEDBACK→Feedback | 可信结果观察 | source/epoch准确；相关Query全候选可观察、不得反推全部已采用 |

Computed conflicts/Recommendation/CORRELATED_ACTION边以`authority=DERIVED`和policy/sourcehash标注；可重算，不能反向作为独立证据。Source和Authority不是Owner自填trust标签，创建面在Host权限内。

## 快照存储与预算

原record256KiB保持。v2 QuerySnapshot采用inline或manifest明确discriminator；超过单record容量时完整canonical document按UTF8边界分≤64KiB的SnapshotChunk，最多128块/8MiB，以HAS_CHUNK的实际有序index、chunkSHA、documentSHA核对。manifest声明所有chunks，缺块/重复/重排/跨tenant都拒绝；每块仍通过payload_json+SHA和MANDATORY。Recommendation保存witness refs/manifest而非重复嵌入全部paths。旧inline QuerySnapshot不变；新loader仅schema2显式启用。

## 完整性、有效性和撤销传播

PublicationManifest不可变列出revision/rule/premise/support/counter/governance必要typed边ID及hash（分块Merkle式manifest可选增强，首版有界完整列表）。读者校验实际reached集合，不把漏掉counter当作无counter。原始删边→INCOMPLETE/VERIFY，不能从丢失负证据获得APPLY。合法撤回以已提交GovernanceEvent解释inactive，重新裁决；历史auditor可按旧epoch只读查看，当前普通cursor失效。

authority撤销触发authz_epoch/semanticepoch，依赖该Authority的当前支持不可用；重新verify之前不推荐。SourceVerification在发布前、读结果在发页前检查当前权限。visibility字段不能被工具输入直接设为PUBLIC，Host public projection/tenant grant共同决定可见性。

多条Cypher不声称全局事务：staging幂等写，单query finalCAS；并发失败记录conflict，不新增可见publication。异常恢复从PUBLISHING检查完整manifest并使用相同request id重试，不篡改旧记录。图谱断库明确Unavailable，空图EMPTY，超限CAPACITY_EXCEEDED；保留原262144wire。语义完整性验证不可被展示分页替代。

PublicationManifest的大型record-set清单也使用同一bounded文档manifest和SnapshotChunk/HAS_CHUNK存储（不新建blob数据库）。root只存expectedepoch、candidate/source/outcome摘要和完整listing的documentSHA/orderedchunkrefs；实际读取并重组listing后核对全关系。不是只信一个complete=true。QuerySnapshot和PublicationManifest最多128chunks、每块64KiB UTF8、整体8MiB；任何缺块/跨tenant/哈希错都明确失败。typed schemas包含document/lifecycle/independent outcome，但结构符合不赋予Host权威。
