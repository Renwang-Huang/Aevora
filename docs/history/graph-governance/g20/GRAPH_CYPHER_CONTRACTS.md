**Contract candidate:** `aevora.gen2.contract/2.0.0-rc1` — **PROPOSED / NOT_IMPLEMENTED**. Only explicitly named source observations and synthetic probe results are TESTED. Maintainer design, not Participant input.

# Graph v2 — Cypher 与读取成本合同

## 访问约束

只有 GraphRepository 的固定模板可以向真实数据库发送 Cypher。tenant/graph由Host registry映射，工具参数不能提供graph/tenant/Cypher。values走官方SDK params；labels/relations仅编译期allowlist，不拼接模型文本。`GRAPH.RO_QUERY`用于所有查询；`GRAPH.PROFILE`可能执行查询，禁止把不可信写语句当作只读profile。公开MCP不提供任意query工具。保留 GraphError/GraphUnavailable 区分，错误不回显输入或凭据。

原模型的payload_json不是可以随意绕开的可信源：native投影必须对照canonical payload+SHA，所有中间关联及必要完整集必须校验。新schema允许原生id/tenant/state/epoch/scope_key索引；不将原始策略文本向量检索当作证据裁决。

## 模板与结果

| ID | 输入（由Host bound） | 输出/语义 | 上界/超限 |
|---|---|---|---|
| Q00 | tenant,state,generation | TenantState epoch/authz_epoch/policy/schema | 恰一；缺失初始化错误，不静态fallback |
| Q01 | tenant,state | 已提交且公开的候选identity | LIMIT257，超过256即CAPACITY_EXCEEDED，不选前256装作完整 |
| Q02 | tenant,experience,epoch | 已提交revision/rule/premise及声明hash | 最多16有效revision、64premises/revision；读取上界+1检测 |
| Q03 | tenant,experience | SUPERSEDES与治理事件/commit/authority | 最大8hop、256events；循环/歧义VERIFY，不能最新时间胜出 |
| Q04 | tenant,state,experience | Revision→Evidence→Outcome→Context + Authority，原边类型/ID | 固定多跳，LIMIT513；最多512path，超过拒绝完整推荐 |
| Q05 | tenant,state,experience | 当前完整GovernanceEvent及target/authority/manifest | LIMIT257；未知scope保留potential，不过滤掉负例 |
| Q06 | tenant,run,query,request_key | Recommendation + 完整source hash的幂等审计记录 | 固定allowlist写；不提升证据epoch |
| Q07 | tenant,state,expectedepoch,candidate,headsha,manifest | 最终发布fence/COMMITS/不可变event/head/epoch | 单写query；恰一为成功，0为STALE_HEAD，不伪报成功 |
| Q08 | tenant,state,authz_epoch,query,session,experience | 发页前当前授权/epoch/lifecycle检查 | 不同返回STALE_SNAPSHOT/UNAUTHORIZED；权限丢失不返回旧page |

实际模板文件在cypher/。Q04和minimal Q07 query-shape有真实合成探针；**完整生产query、全部typed payload验证与authority/tenant服务均NOT_IMPLEMENTED**。探针返回路径集合，不运行拟议Core裁决，因此不能声称APPLY/VERIFY生产验收。

## 完整 final publication Q07（PROPOSED / NOT_EXECUTED）

前置：prepared candidate/revision/rule/evidence/manifest全部不可变且校验完，manifest列出精确边集、candidate/body/source/outcome摘要，拟下一epoch=expected+1。相同request_key先检查已有完成事件；body不同拒绝ImmutableConflict；相同返回原事件而非当前状态。

```cypher
MATCH (s:TenantState {id:$state,tenant_id:$tenant}),
      (c:Candidate {id:$candidate,tenant_id:$tenant}),
      (h:LifecycleHead {id:$head,tenant_id:$tenant}),
      (previous:CandidateEvent {id:$previous,tenant_id:$tenant}),
      (m:PublicationManifest {id:$manifest,tenant_id:$tenant})
WHERE s.epoch=$expected AND h.payload_sha256=$expected_head
  AND m.epoch=$next AND m.payload_sha256=$manifest_sha
CREATE (event:CandidateEvent {id:$event,tenant_id:$tenant,
        payload_json:$event_json,payload_sha256:$event_sha})
CREATE (c)-[:HAS_CANDIDATE_EVENT {id:$candidate_edge,tenant_id:$tenant}]->(event)
CREATE (event)-[:PREVIOUS_EVENT {id:$previous_edge,tenant_id:$tenant}]->(previous)
CREATE (s)-[:COMMITS {id:$commit_edge,tenant_id:$tenant}]->(m)
SET h.payload_json=$head_json,h.payload_sha256=$head_sha,s.epoch=$next
RETURN event.payload_sha256,s.epoch
```

为简洁展示仅列关键属性；G2-1/G2-2实现时必须给所有节点/边补齐共同字段和canonical payload/hash，不得直接复制缩写绕过MANDATORY。最终完整可执行模板、schema与异常rollback须一起冻结，不能宣称此文档是已运行事务。

## 一致读取协议

1. Q00获取E0/authz0/generation/policy；确认capability可读该tenant及profile。
2. Q01/Q02/Q03/Q04/Q05在同graph、受限模板里获取witness。只读取有实际TenantState→COMMITS→Manifest路径的语义事实。
3. 校验声明的完整节点/边集合、payload投影、Source/Authority、时效与scope；任何+1 overflow拒绝完整裁决。未关联Authority的结果不支持推荐。
4. Q00复读，E1≠E0重试一次；持续变动GRAPH_CHANGED。所有激活/撤回/可信事实变动必须在原子epoch fence内；telemetry不变更证据epoch。不是跨query的数据库快照事务。
5. 生成Recommendation与manifest、返回有界summary，记录**成功写出的真实页**。每次Bundle/cursor用Q08重新授权。历史snapshot只在read_history grant+显式REPLAY下可读。

## 预算与性能可证伪合同

每图默认100000nodes/300000edges为运行资源准入上界，不声称已压测。每query DB timeout5000ms（现有配置上限30000不变），读合计20MiB中间结果、每experience最多512paths、活跃16revisions/64premises/256governance events；最坏查询数≤2+7*256（包括每manifest一次有界批量chunk读取），不隐瞒N+1。完整resolve wall目标p95≤5s（64candidate/每项8path）、≤30s上界；**PERFORMANCE_NOT_RUN**，G2-1测量索引plan/真实时延/内存。超限明确CAPACITY_EXCEEDED；不能用超时当ABSTAIN或偷偷丢反证。若目标未达，优化批量查询/索引，不改变裁决和Oracle，变更预算需版本化重审。

wire继续真实SDK text+structured序列化≤196608bytes，broker MAX_MESSAGE_BYTES262144、depth16/node20000；page24576、document8MiB、cache32/16MiB、TTL900s。图中保留完整不可变历史，不全量内嵌重复paths到每个响应。所有category含count/hash/disclosed omissions、lossless continuation；无新数据库缓存真值。

## 探针范围与重放

独立network=none、无发布端口、合成数据、实际镜像digest和server/module版本见外部probes/。P1验证复合index/UNIQUE/MANDATORY readiness和真实拒绝；P2验证完整多跳、支持边cut/restore、tenant filter以及epoch CAS stale返回空。首次容器readiness失败保留，配置/资源修正使用新owned目录；日志与退出码决定实际状态。没有写任何旧图、没有创造真实OracleOutcome。

`Q07_epoch_fence_probe.cypher`明确为minimal语法探针，不替代生产权限、候选审查、完整manifest或恢复测试。无大图压测、生产图迁移或Gen2正式Agent运行。

Snapshot和Publication record-set的chunk读取使用固定`MATCH (m)-[h:HAS_CHUNK]->(c:SnapshotChunk) WHERE m.tenant_id=$tenant AND c.tenant_id=$tenant RETURN h.id,c.id,c.chunk_index,c.payload_json,c.payload_sha256 ORDER BY c.chunk_index LIMIT 129`，Host绑定manifest id并验证实际typed关联、顺序与全SHA；模板在此为PROPOSED/NOT_EXECUTED。不得对每chunk额外无界循环单查询，计入20MiB/总query/wall预算。Q03读取受限直接SUPERSEDES边后以有界DAG校验深度，避免枚举指数数量的所有变长path。

## 可直接实施的完整模板边界

`cypher/Q07_publication_commit.cypher`补齐共同节点/边payload、candidate-head关联、event_id与state native投影、epoch+1以及TenantState新payload SHA；上文缩写仅说明形态，以该完整模板为实现合同。所有state_json/head_json/edge JSON必须由Host canonical生成并逐项对照native字段，不接受Agent直接提供。`Q06_record_recommendation`为不提升证据epoch的派生记录；`Q09_document_chunks`核对实际HAS_CHUNK和chunk metadata。两者均PROPOSED/NOT_EXECUTED。生产权限/完整性/并发失败仍须G2-1/2动态验证，合成minimalfence不替代完整Q07。
