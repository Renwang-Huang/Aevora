// Presentation only: counts and recommendations still come from the Core API.
export const pageGuides = {
  activity: {title:'活动与建议', purpose:'查看 Agent 查过什么经验、Aevora 给过什么建议，以及哪些信息还需要核实。'},
  explorer: {title:'经验库与证据', purpose:'了解一条经验适用于什么条件，并查看支持它的证据、反例和关联记录。'},
  governance: {title:'核验与发布', purpose:'跟踪候选经验如何经过核验、准入和发布，以及后续的撤回记录。'},
};

export const metrics = [
  {key:'runs', label:'任务记录', term:'Run', description:'按授权 Run 汇总的活动；不等同于独立 Agent 或已完成任务。'},
  {key:'queries', label:'经验查询', term:'Query', description:'Agent 发起的检索次数；没有返回经验的查询也会记录。'},
  {key:'pending_candidates', label:'待核验候选', term:'Candidate', description:'已提出、尚待核验或完成发布的经验，暂不能作为已发布经验复用。'},
  {key:'available_experiences', label:'可查询经验', term:'Experience', description:'通过发布门禁的经验；是否适用于当前任务，还需查询判断。'},
];

export function projectGuide(project) {
  const counts=project.counts||{};
  switch(project.state) {
    case 'EMPTY': return {title:'项目已连接，从第一次查询开始', text:'当前项目还没有活动记录。在已接入 Aevora 的 Agent 中开始任务并查询经验，记录就会出现在这里。', action:'query'};
    case 'CANDIDATES_PENDING': return {title:'有候选经验等待核验', text:'Agent 已提出经验候选。接下来由可信 Host 核验来源、审核适用范围并完成发布；候选不会自动成为可复用经验。', action:'governance'};
    case 'EXPERIENCE_AVAILABLE': return {title:'经验库已有可查询的经验', text:'可以查看经验及其证据。开始新任务时仍需查询适用性；已发布并不代表适用于每个任务。', action:'explorer'};
    case 'ACTIVITY_RECORDED':
      if(counts.available_experiences===0&&counts.pending_candidates===0) return {title:'活动已记录，尚无可复用经验', text:'连接已经产生了活动记录。当前没有已发布经验，也没有待核验候选；查询返回 0 条是正常结果，可以继续完成实际任务，再提出有依据的经验候选。', action:'query'};
      return {title:'项目已记录任务活动', text:'已有任务或查询记录。经验与候选的完整数量尚需核对，请结合下方统计和当前页记录查看。', action:'query'};
    default: return {title:'项目已连接，查看已记录的信息', text:'这是当前项目的观察结果。未完成统计的数量保持未知，请结合已加载的记录检查项目进度。', action:'query'};
  }
}

export function queryResult(query) {
  if(!query.query_snapshot_ids||typeof query.query_snapshot_ids!=='object'||Array.isArray(query.query_snapshot_ids)) return {title:'结果快照尚未提供', text:'本次读取未提供结果快照，不能据此判断返回了多少条经验。', count:null};
  const count=Object.keys(query.query_snapshot_ids).length;
  return count===0
    ? {title:'本次查询未返回经验', text:'查询已记录，没有可展示的经验建议。可继续完成实际任务；有可复用结论时再提出候选。', count}
    : {title:`本次查询保存了 ${count} 条经验结果`, text:'下方建议来自查询当时的快照；需要最新适用性时，请在任务中重新查询。', count};
}

export const terms = [
  ['Run · 任务记录','一次固定授权下的活动分组。多个客户端可能共用一个 Run，它不证明 Agent 身份或任务成功。'],
  ['Query · 经验查询','向经验库检索适用经验的一次请求。查询成功与有经验可用是两件事。'],
  ['Candidate · 候选经验','Agent 提出的待核验结论；需要来源核验和审核才能发布。'],
  ['Experience · 已发布经验','通过发布门禁、可供任务查询的经验；每次复用仍要核对条件。'],
  ['APPLY / VERIFY / ABSTAIN','分别表示可以考虑采用、先核实关键条件、当前条件不支持采用。它们是 Core 建议，不是工程成功证明。'],
  ['UNKNOWN · 尚无法确认','信息缺失或证据不足。不会被当成成功、失败或数量 0。'],
];

export const queryPrompt='开始工作前，请使用 Aevora 的 resolve_experience 查询适用经验，说明适用条件、证据和未知项；没有经验时继续正常分析。完成任务后，将有依据、可复用的结论提交为候选，并注明未验证部分，不自动发布。';
