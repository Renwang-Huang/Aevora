// Presentation of Core checklist codes only. No admission or WHEN engine.
const actions={
 DECLARE_BOUNDS:['先整理适用条件','必要条件或适用范围尚未声明。保留原草稿，条件明确后生成新的有界候选。'],
 ESTABLISH_REQUIRED_FACTS:['先建立关键事实','声明中仍有未确定的必要事实，需要独立建立；填写条件不会自动核验它。'],
 REQUEST_EVIDENCE_REVIEW:['交由可信 Host 核验来源','适用条件已经声明，接下来进入来源核验流程；当前仍是待核验候选。'],
 VERIFY_SOURCE:['补充独立核验来源','由受控验证器检查固定提交，并通过可信 Host 导入授权产物。候选自测不能代替此步骤。'],
 REVIEW_ADMISSION:['审核有界准入','已有来源支持声明范围。由可信 Host 核对当前计划和范围，显式审核准入。'],
 REVIEW_PUBLICATION:['审核发布','由可信 Host 检查当前状态和证据后显式发布。发布操作不会在此页面自动执行。'],
 QUERY_NEW_TASK:['在新任务中查询适用性','此候选已发布。开始独立任务后仍需查询条件；是否实际采纳和工程收益保持未知。'],
 RETAIN_HISTORY:['保留历史记录','该记录已结束当前流程。新的结论或证据应提交为新的候选，不覆盖历史。'],
};
const fields={necessary_conditions:'必要条件',scope:'适用范围'};
export function candidatePresentation(candidate,checklist){
 const [action,explanation]=actions[checklist?.next_action]||['查看核验计划','尚未提供明确计划，请通过可信 Host 检查当前候选。'];
 return {title:candidate.title||'候选内容尚未提供',summary:candidate.public_summary||'未提供公开摘要；可检查原始候选标识。',
  action,explanation,missing:Array.isArray(checklist?.missing_fields)?checklist.missing_fields.map(k=>fields[k]||k):null,
  unknown:Array.isArray(checklist?.unknown_required_facts)?checklist.unknown_required_facts:null};
}
