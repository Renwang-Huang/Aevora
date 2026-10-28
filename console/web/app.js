import cytoscape from 'cytoscape';
import {cases,pages,initial,visualState,graphElements,field,displayGraph} from './state.js';
import {pageGuides,metrics,projectGuide,queryResult,terms,queryPrompt} from './guidance.js';
import {candidatePresentation} from './candidates.js';
import './app.css';
const root=document.getElementById('app');let state=initial(location.search),data=null,error=null,loading=true,version=0,cy=null,focus=null,requestController=null,graphExpanded=false,graphResizeObserver=null;
let cursorHistory=[],autoRefresh=true,refreshing=false;
const expandedDetails=new Set(state.run||state.experience||state.cursor?['project-filters']:[]);
function el(tag,cls='',text=null){const n=document.createElement(tag);if(cls)n.className=cls;if(text!==null)n.textContent=text===''?'':field(text);return n;}
function add(parent,...children){for(const c of children.flat())if(c)parent.append(c);return parent;}
function button(text,action,cls='button'){const n=el('button',cls,text);n.type='button';n.addEventListener('click',action);return n;}
function badge(text,cls=''){return el('span','badge '+cls,text);}
function code(value){return el('code','identifier',value);}
function small(text){return el('p','muted small',text);}
function closeProofs(){for(const d of document.querySelectorAll('.proof-dialog'))d.close();}
function update(key,value){closeProofs();state[key]=value;if(['run','experience','limit'].includes(key))expandedDetails.add('project-filters');if(key==='case'||key==='mode'){state.stage='before';state.run='';state.experience='';}if(['case','mode','experience','run','limit'].includes(key)){focus=null;graphExpanded=false;state.cursor='';cursorHistory=[];}saveURL();load();}
function pageTo(cursor){cursorHistory.push(state.cursor);state.cursor=cursor;focus=null;saveURL();load();}
function pager(key,label){const p=data.pagination?.[key];if(state.mode!=='LIVE'||!p)return null;const row=el('div','graph-tools');add(row,small(label+' · 当前页按稳定标识排序'));if(p.has_more&&p.next_cursor)row.append(button('下一页 · '+label,()=>pageTo(p.next_cursor),'button quiet'));return row;}
function saveURL(){const p=new URLSearchParams();for(const [k,v] of Object.entries(state))if(v&&!(state.mode==='LIVE'&&['case','context','stage'].includes(k)))p.set(k,v);history.replaceState(null,'','?'+p.toString());}
function navigate(page){state.page=page;saveURL();render();}
function kv(label,value){return add(el('div','kv'),el('dt','',label),el('dd','',field(value)));}
function section(title,subtitle){return add(el('section','panel'),el('h2','',title),subtitle?small(subtitle):null);}
function dataText(value){return el('pre','data-text',JSON.stringify(value,null,2));}
function proof(name,candidate=null){
 const mode=state.mode,controller=new AbortController(),d=el('dialog','proof-dialog');
 if(candidate)d.dataset.candidate=candidate;
 add(d,add(el('div','panel-title'),el('h2','','公开证据'),button('关闭',()=>d.close(),'button quiet')),badge(mode,mode==='LIVE'?'live':'replay'),small(mode==='LIVE'?'当前候选的生命周期 · 读取自 Core':'历史参考 · 已固定校验的公共回放'));
 if(candidate)add(d,kv('候选（Candidate）',candidate));
 const content=el('div','proof-content');d.append(content);document.body.append(d);d.addEventListener('close',()=>{controller.abort();d.remove();});d.showModal();content.append(el('p','','正在读取证据…'));
 const q=new URLSearchParams({mode});if(candidate)q.set('candidate',candidate);
 fetch('/api/proof/'+encodeURIComponent(name)+'?'+q,{signal:controller.signal,cache:'no-store'}).then(async r=>{
  const body=await r.json();if(!d.open)return;content.replaceChildren();
  if(!r.ok){content.append(add(el('div','state-box danger'),badge(r.status===403?'FORBIDDEN':'UNAVAILABLE','danger'),dataText(body)));return;}
  if(body.mode!==mode||(candidate&&(body.data?.candidate?.id!==candidate||body.data?.head?.candidate_id!==candidate||!Array.isArray(body.data?.events)||body.data.events.some(e=>e.candidate_id!==candidate)|| (body.data.workbench&&(body.data.workbench.candidate_id!==candidate||body.data.workbench.state!==body.data.head.state||body.data.workbench.head_sha256!==body.data.head_sha256))))){
   content.append(add(el('div','state-box danger'),badge('UNAVAILABLE','danger'),small('证据与请求的模式或候选不一致，已停止展示。')));return;
  }
  if(body.data?.workbench){
   const plan=body.data.workbench;
   content.append(candidateCard(body.data.candidate,plan.state,plan,false));
   const source=section('独立来源核验','下列结果由 Core 检查记录中的来源与声明范围，不代表经验普适有效。');
   if(plan.source_checks?.length)for(const check of plan.source_checks)add(source,kv('来源',check.id),small(check.supports_declared_bounds?'来源支持当前声明范围；仍需显式审批。':'此来源尚不能支持当前声明范围。'),small('来源类型：'+check.origin));
   else source.append(small('尚未记录独立核验来源。可按计划准备受控验证器及授权产物。'));
   content.append(source,disclosure('raw-proof-'+candidate,'查看原始公开记录',dataText(body)));
  }else content.append(dataText(body));
 }).catch(e=>{if(e.name==='AbortError'||!d.open)return;content.replaceChildren(el('p','danger','DISCONNECTED · 无法读取公开证据。'));});
}
async function load(background=false){
 const current=++version;if(requestController)requestController.abort();requestController=new AbortController();refreshing=true;
 if(!background){loading=true;error=null;data=null;render();}
 const q=new URLSearchParams({mode:state.mode});
 if(state.mode==='REPLAY'){q.set('case',state.case);q.set('stage',state.stage);}
 else{if(state.run)q.set('run',state.run);if(state.experience)q.set('experience',state.experience);q.set('limit',state.limit);if(state.cursor)q.set('cursor',state.cursor);}
 try{
  const r=await fetch('/api/overview?'+q,{signal:requestController.signal,cache:'no-store'}),result=await r.json();
  if(current!==version)return;if(!r.ok){error={status:r.status,body:result};data=null;}else{data=result;error=null;}
 }catch(e){
  if(e.name==='AbortError'||current!==version)return;
  data=null;error={status:0,body:{status:'DISCONNECTED',error:'无法连接观察服务',fallback:false}};
 }
 if(error){focus=null;closeProofs();}
 else if(state.mode==='LIVE'){
  for(const d of document.querySelectorAll('.proof-dialog'))if(d.dataset.candidate&&!data.candidates?.some(c=>c.id===d.dataset.candidate))d.close();
 }
 loading=false;refreshing=false;render();if(state.proof){const name=state.proof;state.proof='';saveURL();proof(name);}
}
function disclosure(key,title,...children){
 const d=el('details','details-panel');d.dataset.detailsKey=key;d.open=expandedDetails.has(key);
 add(d,el('summary','',title),...children);d.addEventListener('toggle',()=>{if(d.isConnected){if(d.open)expandedDetails.add(key);else expandedDetails.delete(key);}});return d;
}
function shortID(value){return String(value||'UNKNOWN').split(':').at(-1).slice(0,8);}
function timeLabel(value){if(!value)return '时间未提供';const date=new Date(value);return Number.isNaN(date.getTime())?String(value):date.toLocaleString('zh-CN',{hour12:false});}
async function copyText(value,message){try{await navigator.clipboard.writeText(value);notify(message);}catch{if(value===queryPrompt){expandedDetails.add('getting-started');render();document.querySelector('.getting-started')?.scrollIntoView({block:'nearest'});notify('自动复制不可用，请在已展开的使用说明中手动复制提示。');}else notify('自动复制不可用，请在浏览器地址栏复制当前链接。');}}
function pageIntroduction(){const guide=pageGuides[state.page],p=el('div','page-introduction');add(p,el('p','page-purpose',guide.purpose));return p;}
function helpGuide(){
 const d=disclosure('getting-started','第一次使用？了解这三个步骤和常用术语');d.classList.add('getting-started');
 const steps=el('ol','journey');
 for(const [title,text] of [['在 Agent 中查询','开始实际任务时查询经验；查询和结果会记录在“活动与建议”。'],['核对条件与证据','在“经验库与证据”查看支持、反例和适用边界，再决定是否采用。'],['积累并核验经验','任务结束后提出候选，由可信 Host 核验并发布，在“核验与发布”跟踪进度。']])add(steps,add(el('li',''),el('strong','',title),small(text)));
 add(d,steps,el('h3','','可以复制给 Agent 的提示'),el('pre','data-text prompt-text',queryPrompt),button('复制查询提示',()=>copyText(queryPrompt,'已复制，可粘贴到接入 Aevora 的 Agent。'),'button quiet'));
 const glossary=el('dl','glossary');for(const [term,meaning] of terms)add(glossary,add(el('div',''),el('dt','',term),el('dd','',meaning)));add(d,glossary,small('此页面只读取记录。查询、候选提议和可信核验分别在 Agent / Host 中完成；浏览页面不会运行模型。'));return d;
}
function shell(){
 root.replaceChildren();const layout=el('div','layout'),side=el('aside','sidebar');
 add(side,add(el('a','brand','Aevora'),el('span','brand-mark','◈')),small('有条件地复用工程经验'),el('div','side-label','工作区'));
 for(const p of pages){const nav=button('',()=>navigate(p.id),'nav '+(state.page===p.id?'active':''));nav.setAttribute('aria-label',p.icon+' '+pageGuides[p.id].title);if(state.page===p.id)nav.setAttribute('aria-current','page');add(nav,el('span','nav-title',p.icon+'  '+pageGuides[p.id].title),el('span','nav-subtitle',p.id==='activity'?'查看查询与建议':p.id==='explorer'?'了解经验为何适用':'跟踪候选到发布'));side.append(nav);}
 add(side,el('div','side-label case-label','数据来源'),button('当前项目',()=>update('mode','LIVE'),'nav '+(state.mode==='LIVE'?'active':'')),button('查看演示回放',()=>update('mode','REPLAY'),'nav '+(state.mode==='REPLAY'?'active':'')));
 if(state.mode==='REPLAY'){add(side,el('div','side-label','历史演示案例'));for(const c of cases){const b=button('',()=>update('case',c.id),'case-button '+(state.case===c.id?'selected':''));add(b,el('span','act-label',c.act),el('strong','',c.title),el('span','case-subtitle',c.subtitle));side.append(b);}}
 add(side,add(el('div','side-footer'),badge('只读观察界面'),small('在 Agent 中查询和提出候选；由可信 Host 核验与发布。')));
 const main=el('main','main'),header=el('header','header'),page=pages.find(p=>p.id===state.page);
 add(header,add(el('div','heading'),el('div','eyebrow','AEVORA / '+page.title),el('h1','',pageGuides[state.page].title)));
 const controls=el('div','header-controls'),select=el('select','mode-select');select.setAttribute('aria-label','数据模式');
 for(const [mode,label] of [['LIVE','当前项目 · LIVE'],['REPLAY','演示回放 · REPLAY']]){const o=el('option','',label);o.value=mode;o.selected=state.mode===mode;select.append(o);}select.addEventListener('change',()=>update('mode',select.value));
 add(controls,select,button('刷新',()=>load(),'button quiet'),button('复制链接',()=>copyText(location.href,'已复制当前页面链接'),'button quiet'));
 add(header,controls);add(main,header);
 const modebar=el('div','modebar '+(state.mode==='LIVE'?'live':''));add(modebar,badge(state.mode,state.mode==='LIVE'?'live':'replay'),el('span','',state.mode==='LIVE'?'正在查看自己的项目记录':'正在查看历史演示，与自己的项目数据分开'),el('span','mode-detail',data?'观察时间：'+timeLabel(state.mode==='LIVE'?data.observed_at:data.captured_at):'等待读取'));
 if(state.mode==='LIVE'){const toggle=el('label','refresh-toggle'),input=el('input');input.type='checkbox';input.checked=autoRefresh;input.addEventListener('change',()=>{autoRefresh=input.checked;});add(toggle,input,el('span','','每 5 秒刷新'));modebar.append(toggle);}main.append(modebar);
 if(data&&state.mode==='REPLAY')main.append(add(el('div','archive-strip'),el('span','',data.archive),code(data.contract_sha256),button('核对回放来源',()=>proof('contract'),'text-button')));
 const content=el('div','content'),status=visualState(loading?'LOADING':'',data,error);
 content.append(pageIntroduction(),add(el('div','case-heading'),el('div','',state.mode==='LIVE'?'当前项目':cases.find(c=>c.id===state.case)?.title||'未知案例'),badge(status,status==='FORBIDDEN'||status==='DISCONNECTED'?'danger':status==='PARTIAL'?'warning':'')));
 if(loading)content.append(add(el('div','state-box loading'),el('h2','','正在读取项目记录'),small('读取所选来源，请稍候。')));
 else if(error)content.append(add(el('div','state-box danger'),el('h2','',status==='FORBIDDEN'?'当前来源无访问权限':'暂时无法读取当前数据'),badge(status,'danger'),small(error.body.error),small('请检查 Host 是否运行，然后重试。历史回放不会替代当前数据。'),button('重试',()=>load()),error.body.error==='GRAPH_READ_BUDGET_EXCEEDED'&&Number(state.limit)>1?button('缩小每页数量',()=>update('limit',String(Math.max(1,Math.floor(Number(state.limit)/2))))):null,disclosure('error-details','错误技术详情',dataText(error.body))));
 else if(data){
  if(state.mode==='LIVE')content.append(projectOverview());else if(data.status==='EMPTY'||data.status==='UNAVAILABLE')content.append(add(el('div','notice'),badge(data.status==='EMPTY'?'EMPTY':'UNKNOWN','warning'),small(data.case?.missing_source_reason||'此来源没有可显示记录。')));
  content.append(state.page==='activity'?activityPage():state.page==='explorer'?explorerPage():governancePage());
 }
 add(main,content,add(el('footer','footer'),el('span','','只读公共视图 · 仅展示有来源的记录'),el('span','','是否实际采纳、是否产生因果收益：尚未确认（UNKNOWN）')));add(layout,side,main);root.append(layout);return content;
}
function notify(message){const t=el('div','toast',message);document.body.append(t);setTimeout(()=>t.remove(),4000);}
function projectOverview(){
 const guide=projectGuide(data.project),p=section(guide.title,guide.text);p.classList.add('project-overview');p.dataset.projectState=data.project.state;
 const counts=el('div','project-counts');
 for(const metric of metrics){const value=data.project.counts[metric.key],card=el('div','metric');card.dataset.metric=metric.key;
  add(card,el('div','metric-label',metric.label),el('strong','',value===null||value===undefined?'待统计':value),el('span','metric-term',metric.term),small(metric.description));
  if(value===null||value===undefined){const loaded=data.project.loaded_counts?.[metric.key];if(loaded!==null&&loaded!==undefined)card.append(small('本页已核验 '+loaded+' 条；项目总数未知。'));}counts.append(card);
 }p.append(counts);
 const actions=el('div','overview-actions');
 if(guide.action==='governance')actions.append(button('查看待核验候选',()=>navigate('governance')));
 else if(guide.action==='explorer')actions.append(button('查看经验库',()=>navigate('explorer')));
 else actions.append(button('复制查询提示',()=>copyText(queryPrompt,'已复制，可粘贴到接入 Aevora 的 Agent。')));
 add(actions,button('了解完整流程',()=>{expandedDetails.add('getting-started');render();document.querySelector('.getting-started')?.scrollIntoView({block:'nearest'});},'button quiet'),small('查看记录不会运行模型，也不会发布经验。'));p.append(actions);
 p.append(helpGuide());
 const filters=el('div','project-filters');
 for(const [key,label,items,id,title] of [['run','任务记录（Run）',data.sessions,'run_id','run_id'],['experience','经验（Experience）',data.experiences,'id','title']]){const wrap=el('label','small',label),select=el('select','mode-select');select.setAttribute('aria-label',label);const all=el('option','',key==='run'?'全部任务记录':'全部经验');all.value='';select.append(all);
  for(const item of items){const o=el('option','',item[title]||item[id]);o.value=item[id];select.append(o);}if(state[key]&&!items.some(i=>i[id]===state[key])){const o=el('option','','未找到：'+state[key]);o.value=state[key];select.append(o);}select.value=state[key];select.addEventListener('change',()=>update(key,select.value));add(filters,add(wrap,select));
 }
 const filterBox=disclosure('project-filters','筛选记录与翻页'+(state.run||state.experience||state.cursor?' · 已应用筛选':''),small('指标统计整个项目；下方记录按 Run / 经验筛选。列表分别分页，当前页不代表全部历史。'),filters);
 if(data.selection.run_status==='NOT_FOUND'||data.selection.experience_status==='NOT_FOUND')add(filterBox,small('所选记录在此项目中未找到；清除筛选可查看当前记录。'));
 add(filterBox,pager('sessions','任务记录'),pager('experiences','经验'));
 const controls=el('div','graph-tools'),size=el('select','mode-select');size.setAttribute('aria-label','每页数量');
 for(const value of [...new Set(['1','5','10','20','50',state.limit])].sort((a,b)=>Number(a)-Number(b))){const o=el('option','',value+' 条 / 页');o.value=value;size.append(o);}size.value=state.limit;size.addEventListener('change',()=>update('limit',size.value));controls.append(size);
 if(state.cursor){controls.append(button('返回首页',()=>{state.cursor='';cursorHistory=[];saveURL();load();},'button quiet'));if(cursorHistory.length)controls.append(button('上一页',()=>{state.cursor=cursorHistory.pop();saveURL();load();},'button quiet'));}filterBox.append(controls);
 p.append(filterBox);
 const technical=disclosure('project-technical','连接状态与技术详情',add(el('div','inline'),badge('DATABASE CONNECTED','live'),badge(data.project.state)),kv('数据库',data.project.graph),small(data.project.summary));
 if(data.runtime){const r=data.runtime,b=r.budget||{};add(technical,el('h3','','本地 Host'),kv('状态',r.state),kv('观察时间',timeLabel(r.observed_at)),kv('运行周期（epoch）',r.epoch),kv('连接数',field(b.consumer_connections)+' / '+field(b.consumer_connection_limit)),kv('Run 数量',field(b.runs_active)+' 活动 · '+field(b.runs_total)+' / '+field(b.run_limit)+' 累计'),kv('协议帧',field(b.frames)+' / '+field(b.frame_limit)),kv('管理认证次数',field(b.management_nonces)+' / '+field(b.management_nonce_limit)),kv('已观察工具调用',r.tool_calls_observed),small('运行状态不证明 Agent 身份、实际采纳或工程结果。'));if(r.warnings?.length)add(technical,badge('BUDGET WARNING','warning'),small(r.warnings.join(' · ')),small('请关闭不用的连接。累计预算需显式重启 Host 并恢复任务，历史记录保留。'));}p.append(technical);return p;
}
function decisionCard(d){
 const meanings={APPLY:'可以考虑采用',VERIFY:'先核实关键条件',ABSTAIN:'当前条件不支持采用'};
 const p=section(d.decision,meanings[d.decision]||'判定含义尚未提供');p.classList.add('recommendation-card');add(p,small(d.reason),add(el('div','inline'),badge('Core 建议'),badge(state.mode==='LIVE'?'查询时的历史结果':d.context_name||state.context)));
 if(state.mode==='LIVE')add(p,small('记录于 '+timeLabel(d.created_at)+'。这是查询当时的结果；需要最新适用性时请发起新查询。'));
 add(p,kv('适用操作范围',d.current_operation_coverage),kv('下一步核验',d.verification_steps));
 const evidence=el('div','evidence-columns');add(evidence,add(el('div',''),el('h3','','适用条件 · WHEN'),dataText({matched:d.matched_premises,conflicting:d.conflicting_premises,unknown:d.unknown_premises,missing:d.missing_material_premises})),add(el('div',''),el('h3','','证据与反例 · WHY'),small((d.support_paths?.length||0)+' 条支持路径 · '+(d.counterexample_paths?.length||0)+' 条反例路径'),dataText({support:d.support_paths,counterexample:d.counterexample_paths})));
 add(p,disclosure('decision-'+d.query_id+'-'+d.experience_id,'查看适用条件、证据和记录标识',kv('Run',d.run_id),kv('Query',d.query_id),kv('经验（Experience）',d.experience_id),kv('Rule',d.rule_ids?.join(', ')),kv('结果来源',d.authority),evidence));
 if(state.mode==='REPLAY')p.append(button('核对建议来源',()=>proof(state.case==='case-c'?'evolution':'views'),'text-button'));return p;
}
function selectedDecisions(){return state.case==='case-c'&&state.mode==='REPLAY'?data.decisions.filter(d=>d.context_name===state.stage):data.decisions;}
function memoryLoopPanel(){
 const panel=section('自动记忆处理','当前 Host 的作业总览。普通来源自动积累，证据不足时保留观察；独立检查和常设策略决定能否晋升。');
 const memory=data.memory_loop;if(!memory){panel.append(small('处理状态暂未提供。'));return panel;}
 const names={PENDING:'待整理',RUNNING:'正在整理',RETRY:'等待重试',COMPLETED:'整理已处理',QUARANTINED:'重试预算已耗尽'};
 const reasons={WAITING_FOR_WORKER:'等待后台处理',MORE_ENGINEERING_EVIDENCE_REQUIRED:'缺少失败、完成的改动或成功检查；继续积累来源',CANDIDATE_READY:'候选已形成，等待独立检查与常设策略',SOURCE_SET_CHANGED:'来源发生变化，等待重新整理',RETRY_BUDGET_EXHAUSTED:'需要检查原始失败后恢复'};
 const entries=Object.entries(memory.states||{});if(!entries.length)panel.append(small('尚无工程整理作业。接入 memory codex 适配器后，真实事件会进入这里；配置存在不代表已采集。'));
 for(const [state,count]of entries)panel.append(small((names[state]||state)+'：'+count));
 const grouped=new Map();for(const job of memory.jobs||[]){const key=job.candidate_id||job.job_id,old=grouped.get(key);if(old){old.count++;old.attempts=Math.max(old.attempts,job.attempts);}else grouped.set(key,{...job,count:1});}
 const lifecycle={PUBLISHED:'经验已发布；下一次查询仍需核对适用条件',WITHDRAWN:'支持已失效或撤回；当前查询不再推荐',REJECTED:'候选已停止使用；原观察保留',ADMITTED_BOUNDED:'已完成有界准入，后续由常设策略处理'};
 for(const original of grouped.values()){const job={...original,candidate_state:original.verified_candidate_state||original.candidate_state};const row=el('article','event-mini');add(row,el('strong','',(job.project||'未知项目')+' · '+(job.candidate_state||names[job.state]||job.state)),small(lifecycle[job.candidate_state]||reasons[job.reason]||job.reason),small('此页关联作业：'+job.count+' · 最大尝试次数：'+job.attempts));if(job.candidate_id)row.append(code(job.candidate_id));panel.append(row);}
 if(memory.more)panel.append(small('当前展示有界的一页作业；完整巡检由 memory watch 持续分页完成。'));
 panel.append(small('整理已处理不等于核验通过；来源关联、自报使用与工程收益分别记录。'));return panel;
}
function activityPage(){
 const grid=el('div','activity-grid'),list=section('任务活动','先选择一条 Run 查看相关查询。Run 是授权活动分组，不代表任务已完成。');
 if(state.mode==='LIVE')list.append(button('查看全部任务记录',()=>update('run',''),'text-button'));
 for(const s of data.sessions){const card=button('',()=>{if(state.mode==='LIVE')update('run',s.run_id);else{state.run=s.run_id;saveURL();render();}},'session-card '+(state.run===s.run_id?'selected':''));card.setAttribute('aria-pressed',String(state.run===s.run_id));
  add(card,el('strong','session-title','Run · '+shortID(s.run_id)),small(s.status==='HOST_CHANNEL_OBSERVED'||s.status==='MCP_REQUESTS_OBSERVED'?'已观察到工具请求':s.status==='ERROR'?'运行记录包含错误':'已有活动记录'),code(s.run_id),small(state.mode==='LIVE'?field(s.query_count)+' 次查询 · '+field(s.candidate_count)+' 条候选':s.failure_kind?'失败类型：'+s.failure_kind:'评测状态：'+field(s.evaluation_status)));list.append(card);
 }
 if(!data.sessions.length)list.append(small(state.run||state.cursor?'当前筛选或分页下没有任务记录，可清除筛选或返回首页。':'还没有任务活动。在已接入 Aevora 的 Agent 中发起经验查询后，这里会显示 Run。'));
 const right=el('div','stack');if(state.mode==='LIVE')right.append(memoryLoopPanel());const selected=data.sessions.find(s=>s.run_id===state.run)||(state.mode==='REPLAY'?data.sessions[0]:null);
 if(selected){const p=section('所选任务记录','当前 Run 的活动与来源信息；运行状态不代表工程验证通过。');
  add(p,disclosure('session-'+selected.run_id,'运行标识与状态详情',kv('Run',selected.run_id),kv('Session',selected.session_id),kv('运行状态',selected.status),kv('结果权限',selected.authority),kv('评测',selected.evaluation_status),kv('失败类型',selected.failure_kind),kv('日志观察时间',timeLabel(selected.header_observed_at)),kv('进程存活检查',selected.process_liveness)));
  if(selected.native_children?.length){p.append(el('h3','','有记录的原生协作'));for(const child of selected.native_children)add(p,add(el('div','event-mini'),code(child.agent_id),small(child.agent_path),badge(child.completed?'COMPLETED':'UNKNOWN'),small('父线程：'+child.parent_thread_id),small('原始记录行 '+child.completion.line+' · '+child.completion.sha256)));}
  if(selected.tool_events?.length){p.append(el('h3','','工具调用记录 · MCP'));for(const [index,ev] of selected.tool_events.entries())add(p,disclosure('tool-'+selected.run_id+'-'+index,ev.tool+' · '+timeLabel(ev.timestamp),small('来源行 '+ev.line+' · '+ev.line_sha256)));}right.append(p);
 }
 if(state.mode==='LIVE'){
  const q=section('经验查询记录','每条记录表示一次检索。返回 0 条经验也会记录，不代表连接失败或已完成修复。');
  for(const row of data.activity_queries){const result=queryResult(row),item=el('article','event-mini query-card');add(item,add(el('div','query-heading'),el('strong','',result.title),el('time','',timeLabel(row.created_at))),small(result.text),disclosure('query-'+row.id,'查询标识与原始记录',kv('Query',row.id),kv('Run',row.run_id),kv('记录时间',row.created_at),kv('已保存结果快照数',result.count)));q.append(item);}
  if(!data.activity_queries.length)q.append(small(state.run||state.experience||state.cursor?'当前筛选或分页下没有查询；可清除筛选或返回首页查看。':'还没有查询记录。在 Agent 中调用 resolve_experience 后，刷新即可查看。'));
  add(q,pager('queries','查询'));right.append(q);
 }
 for(const d of selectedDecisions())right.append(decisionCard(d));
 if(!data.decisions.length){const p=section(state.mode==='LIVE'?'此处将显示适用性建议':'此来源没有可展示的建议');
  add(p,small(state.mode==='LIVE'?'当查询返回经验时，这里会展示 Core 的判断、条件和依据。当前选择没有已记录的建议。':'此来源未提供所选经验的权威建议。'),add(el('div','recommendation-legend'),small('APPLY · 可以考虑采用'),small('VERIFY · 先核实条件'),small('ABSTAIN · 当前不适用')),small('建议不证明 Agent 已采用，也不证明工程结果。'));right.append(p);
 }
 if(state.mode==='LIVE'&&data.recorded_decisions.length){const p=section('Agent 记录的选择','这是 Agent 的选择与理由声明，尚不证明实际采纳或可信结果。');for(const d of data.recorded_decisions)add(p,add(el('div','event-mini'),el('strong','',d.decision+' · '+d.reason),disclosure('claim-'+d.id,'声明来源与标识',code(d.id),badge(d.authority),small('Query：'+d.query_id))));add(p,pager('recorded_decisions','选择声明'));right.append(p);}
 add(grid,list,right);return grid;
}
function selectedExperience(){return state.mode==='LIVE'?data.selection.experience_id:data.case.experience_id;}
let observationText='',observationResults=null,observationError=null,observationBusy=false;
function observationSearch(){
 const panel=section('查找未核验观察','按具体关键词查找过去的排查线索。这里展示原始声明；适用性和可信结果仍需独立核验。');
 const form=el('form','graph-tools'),input=el('input','');input.type='search';input.value=observationText;input.placeholder='例如：MCP、重启、任务条件';input.setAttribute('aria-label','观察搜索关键词');
 const submit=el('button','button',observationBusy?'正在搜索…':'搜索观察');submit.type='submit';submit.disabled=observationBusy;
 form.append(input,submit);form.addEventListener('submit',async event=>{
  event.preventDefault();observationText=input.value;observationBusy=true;observationResults=null;observationError=null;render();
  try{const response=await fetch('/api/observations?'+new URLSearchParams({mode:'LIVE',query:observationText,limit:'10'}),{cache:'no-store'});const result=await response.json();
   if(!response.ok||result.authority!=='UNTRUSTED_OBSERVATIONS_ONLY'||!Array.isArray(result.observations))throw Error('观察检索当前不可用，请检查服务连接。');
   observationResults=result;
  }catch(error){observationResults=null;observationError='DISCONNECTED / UNAVAILABLE · '+error.message}
  finally{observationBusy=false;render();}
 });panel.append(form);
 if(observationError)panel.append(small(observationError));
 if(observationResults){
  panel.append(badge('UNTRUSTED · 仅作排查线索','warning'));
  if(!observationResults.observations.length)panel.append(small('没有匹配的观察。可换用具体关键词；未命中不代表没有已发布经验。'));
  for(const row of observationResults.observations)panel.append(candidateCard({...row,id:row.candidate_id},row.state,null));
 }
 return panel;
}
function captureSources(candidate,task=false){
 const controller=new AbortController(),d=el('dialog','proof-dialog capture-sources-dialog'),content=el('div','proof-content');
 add(d,add(el('div','panel-title'),el('h2','','诊断线索来源'),button('关闭',()=>d.close(),'button quiet')),small('来源中的项目、会话和回合标识尚未核验；同回合分组不证明相同根因。记录时间是接收时间。'),content);
 document.body.append(d);d.addEventListener('close',()=>{controller.abort();d.remove();});d.showModal();
 const history=[];
 async function load(after=''){
  content.replaceChildren(small('正在读取来源…'));
  try{
   const response=await fetch((task?'/api/task-sources?':'/api/capture-sources?')+new URLSearchParams({mode:'LIVE',candidate,after,limit:'10'}),{signal:controller.signal,cache:'no-store'}),result=await response.json();
   if(!d.open)return;
   if(!response.ok||result.mode!=='LIVE'||result.candidate_id!==candidate||result.authority!=='UNTRUSTED_SOURCES_ONLY'||!Array.isArray(result.sources))throw Error('来源读取不可用');
   content.replaceChildren(badge('UNTRUSTED · 来源线索','warning'),small('此页 '+result.sources.length+' 条，按稳定标识分页；新增较小标识需重新读取第一页。'));
   for(let source of result.sources){const row=section(source.event?.summary||source.signal,'项目提示：'+field(source.event?.project||source.project_hint));if(source.event)add(row,kv('动作类别',source.event.action),kv('完成状态',source.event.status),kv('退出状态',source.event.exit_code),kv('原始事件时间',source.event.occurred_at||'未知'),kv('声明版本',source.event.revision||'未知'));source={...source,session_ref:source.event?.session_ref||source.session_ref,turn_ref:source.event?.turn_ref||source.turn_ref,tool_ref:source.event?.item_ref||source.tool_ref};add(row,kv('会话',source.session_ref),kv('回合',source.turn_ref),kv('工具调用',source.tool_ref),kv('接收时间',source.recorded_at),code(source.observation_id));content.append(row);}
   const controls=el('div','graph-tools');
   if(history.length)controls.append(button('上一页',()=>load(history.pop()),'button quiet'));
   if(result.more&&result.next_cursor)controls.append(button('下一页',()=>{history.push(after);load(result.next_cursor);},'button quiet'));
   controls.append(button('重新读取',()=>{history.length=0;load();},'button quiet'));content.append(controls);
  }catch(error){if(error.name!=='AbortError'&&d.open)content.replaceChildren(small('DISCONNECTED / UNAVAILABLE · 来源读取失败，请关闭后重试。'));}
 }
 load();
}
function candidateCard(candidate,status,checklist,openProof=true){
 const view=candidatePresentation(candidate,checklist),card=el('article','candidate-card');
 card.dataset.candidate=candidate.id;
 add(card,add(el('div','candidate-heading'),el('h3','',view.title),badge(status||'UNKNOWN')),el('p','candidate-summary',view.summary),badge('原始候选声明 · 核验结果见独立来源','warning'));
 if(candidate.task_sources)add(card,small('工程任务来源已关联；动作与检查仍需独立核验。'),button('查看工程任务来源',()=>captureSources(candidate.id,true),'button quiet'));
 if(candidate.capture_sources){const s=candidate.capture_sources;add(card,small('自动诊断信号：'+field(s.source_record_count)+' 条 · 项目提示：'+field(s.project_hint)+'（未核验）'),small('会话：'+field(s.session_ref)+' · 回合：'+field(s.turn_ref)+' · 工具：'+field(s.tool_ref)),small('匹配词汇不证明真实失败或根因；请回原会话核对。'),button('查看全部来源',()=>captureSources(candidate.id),'button quiet'));}
 const next=add(el('div','candidate-next'),el('strong','',view.action),small(view.explanation));
 if(view.missing?.length)next.append(small('缺少：'+view.missing.join('、')));
 if(view.unknown?.length)next.append(small('待建立的关键事实：'+view.unknown.join('、')));
 card.append(next);
 const details=disclosure('candidate-'+candidate.id,'查看声明的条件、方法与来源标识');
 details.append(kv('方法',candidate.strategy));
 for(const [label,values] of [['必要条件',candidate.necessary_conditions],['适用范围',candidate.scope],['排除条件',candidate.inapplicable_conditions]]){
  const block=el('div','candidate-bounds');block.append(el('h4','',label));
  if(values&&Object.keys(values).length)for(const [key,allowed]of Object.entries(values))block.append(kv(key,Array.isArray(allowed)?allowed.map(v=>String(v)).join(' / '):'未提供'));
  else block.append(small('尚未声明'));
  details.append(block);
 }
 for(const limitation of candidate.limitations||[])details.append(small('限制：'+limitation));
 if(candidate.derived_from_candidate_id)details.append(kv('整理自原候选',candidate.derived_from_candidate_id));
 add(details,kv('候选标识',candidate.id),kv('内容校验摘要',candidate.body_sha256),small('是否实际采纳：UNKNOWN · 因果收益：UNKNOWN'));
 card.append(details);
 if(openProof)card.append(button('查看生命周期证据',()=>proof('lifecycle',candidate.id),'text-button'));
 else add(card,small('在已注册项目的工作目录，可用下列命令读取当前计划；其他目录请显式添加 --project。'),code('aevora candidate plan '+candidate.id));
 return card;
}
function graphPanel(){const shown=displayGraph(data.graph,selectedExperience(),graphExpanded);const p=section('证据关系图','查看已保存的真实关系；图只展示有限邻域，可展开下方列表逐条检查。');const tools=el('div','graph-tools');add(tools,button('−',()=>cy&&cy.zoom(cy.zoom()/1.2),'button quiet'),button('+',()=>cy&&cy.zoom(cy.zoom()*1.2),'button quiet'),button('适应画布',()=>cy&&cy.fit(undefined,45),'button quiet'),button(graphExpanded?'聚焦当前经验':'展开已加载关系',()=>{graphExpanded=!graphExpanded;render();},'button quiet'),badge(data.graph.status),small(shown.nodes.length+' 个已展示 / '+data.graph.nodes.length+' 个已加载 / '+field(data.graph.total_nodes)+' 个范围内节点 · '+data.graph.edges.length+' 条已加载关系'),pager('graph','关系记录'));
 const viewport=el('div','graph-viewport');viewport.id='evidence-graph';viewport.setAttribute('aria-label','实际证据关系子图');add(p,tools,viewport);
 const list=el('details','node-list');add(list,el('summary','','展开节点与关系列表'));for(const n of data.graph.nodes)list.append(button(n.label+' · '+n.id,()=>inspect(n),'node-row'));for(const e of data.graph.edges)list.append(button(e.relation+' · '+e.id,()=>inspect(e),'node-row edge-row'));p.append(list);
 queueMicrotask(()=>{if(!viewport.isConnected)return;if(graphResizeObserver)graphResizeObserver.disconnect();if(cy)cy.destroy();cy=cytoscape({container:viewport,elements:graphElements(shown),layout:{name:'breadthfirst',directed:true,spacingFactor:1.5,padding:45,animate:false},style:[{selector:'node',style:{label:'data(caption)','text-wrap':'wrap','font-size':10,'font-family':'sans-serif','text-valign':'center','background-color':'#dce8e5',color:'#183b40',width:85,height:49,shape:'roundrectangle','border-width':1,'border-color':'#8fb2aa'}},{selector:'node[label = "Experience"]',style:{'background-color':'#153b43',color:'#fff','border-color':'#153b43',width:112,height:58}},{selector:'node[label = "VerifiedOutcome"]',style:{'background-color':'#f1e3bc','border-color':'#c3a057'}},{selector:'node[label = "Rule"]',style:{'background-color':'#e0dded','border-color':'#aca1c4'}},{selector:'edge',style:{label:'data(label)','font-size':8,'curve-style':'bezier','target-arrow-shape':'triangle','line-color':'#aebfbd','target-arrow-color':'#aebfbd',width:1.4,'text-background-color':'#fafbf8','text-background-opacity':.8}},{selector:':selected',style:{'border-color':'#bb782b','border-width':3}}],minZoom:.25,maxZoom:2.5,wheelSensitivity:.2});cy.on('tap','node,edge',evt=>inspect(evt.target.data('record')));graphResizeObserver=new ResizeObserver(()=>{if(viewport.isConnected){cy.resize();cy.fit(undefined,45);}});graphResizeObserver.observe(viewport);});return p;}
function inspect(record){focus=record;const target=document.getElementById('node-inspector');if(!target)return;target.replaceChildren(el('h2','','所选证据'),badge(record.label||record.relation),code(record.id),small(record.stored_payload_sha256?'记录校验摘要：'+record.stored_payload_sha256:'记录校验摘要未提供'),dataText(record));if(state.mode==='REPLAY')target.append(button('查看公开关系证明',()=>proof(state.case==='case-c'?'evolution':'graph'),'text-button'));}
function explorerPage(){const page=el('div','stack');const id=selectedExperience();const exp=data.experiences.find(e=>e.id===id);
 if(state.mode==='LIVE'&&!id){const library=section('项目经验库','已发布经验通过 Core 发布门禁。开始任务时，还需查询是否满足适用条件。');for(const e of data.experiences)add(library,add(el('div','event-mini'),button(e.title||e.id,()=>update('experience',e.id),'text-button'),code(e.id),badge(data.available_experience_ids.includes(e.id)?'AVAILABLE':'NOT ACTIVE'),small(e.public_summary)));if(!data.experiences.length)library.append(small('还没有已发布经验。可在“核验与发布”查看候选进度；完成实际任务后，先由 Agent 提出有依据的候选。'));page.append(library);}
 else{const title=section(exp?.title||'未找到所选经验',exp?.public_summary);add(title,add(el('div','inline'),badge(data.lifecycle?.head?.state||exp?.source_type||'UNKNOWN'),badge('是否实际采纳：UNKNOWN')),kv('经验（Experience）',id),kv('方法与适用原则',exp?.strategy),add(el('details','scope-limits'),el('summary','','适用范围与限制'),dataText(exp?.limitations)));page.append(title);}
 const switches=el('div','segmented');if(state.case==='case-c'&&state.mode==='REPLAY')for(const stage of ['before','after','restored'])switches.append(button(stage,()=>update('stage',stage),'segment '+(stage===state.stage?'active':'')));
 if(switches.childNodes.length)page.append(switches);
 const grid=el('div','explorer-grid');const graph=graphPanel();const inspector=section('证据详情','点击关系图中的节点或连线，查看对应记录和来源属性。');inspector.id='node-inspector';if(focus){add(inspector,badge(focus.label||focus.relation),code(focus.id),dataText(focus));}else add(inspector,small('节点表示记录，连线表示已保存的关系；图的布局不表示因果。缺少的关系保持缺失。'),kv('模式',data.mode),kv('来源权限',data.case?.classification||data.context_authority));add(grid,graph,inspector);page.append(grid);
 for(const d of selectedDecisions())page.append(decisionCard(d));if(data.candidates?.length){const p=section('待核验候选记录','候选内容尚未核验，此处仅展示公开记录。来源核验和审批由可信 Host 完成。');for(const c of data.candidates)p.append(candidateCard(c,data.candidate_heads.find(h=>h.candidate_id===c.id)?.state,data.candidate_guidance?.[c.id]?.checklist));page.append(p);}return page;}
function governancePage(){const page=el('div','stack');const p=section('经验的核验与发布过程','从候选提出到来源核验、准入、发布或撤回，按已保存的事件查看进度；事件不证明因果收益。');
 if(state.mode==='LIVE')page.append(observationSearch());
 if(state.mode==='LIVE'){
  for(const candidate of data.candidates||[])p.append(candidateCard(candidate,data.candidate_heads?.find(h=>h.candidate_id===candidate.id)?.state,data.candidate_guidance?.[candidate.id]?.checklist));
  if(!data.candidates?.length)p.append(small('当前页没有候选记录。Agent 在实际任务后提出候选，随后由可信 Host 核验和发布。'));add(p,pager('candidates','候选'));
 }
 if(data.timeline.length)for(const event of data.timeline){const card=el('article','timeline-event');add(card,el('span','event-dot'),add(el('div',''),badge(event.to_state||event.event_type||'RECORDED EVENT'),el('h3','',event.reason||event.public_reason||event.event_type||event.id),code(event.id),small('UTC 时间：'+field(event.created_at)),small('来源权限：'+field(event.authority)),event.principal?small('Host 主体：'+event.principal):null,event.cypher?dataText({cypher:event.cypher,line:event.line,line_sha256:event.line_sha256}):null));p.append(card);}else p.append(small('当前选择没有生命周期或活动事件。可切换 Run 或返回首页查看。'));
 add(p,pager('timeline','事件'));if(state.mode==='REPLAY'&&(state.case==='case-c'||data.lifecycle))p.append(button('查看生命周期与查询证明',()=>proof(state.case==='case-c'?'queries':'lifecycle',data.lifecycle?.candidate?.id),'text-button'));page.append(p);
 if(data.evolution){const e=data.evolution;const comparison=section('历史快照与受控查询对照','同一经验和规则的支持关系发生变化；以下是 Host 控制的副本读取结果。');const table=el('table','comparison-table');const head=el('tr');for(const name of ['视图','建议','支持路径数','检索校验摘要'])head.append(el('th','',name));table.append(head);for(const name of ['before','after','restored']){const d=e[name],row=el('tr');add(row,el('td','',name),el('td','',d.decision),el('td','',d.support_paths.length),add(el('td',''),code(d.retrieval_snapshot_sha256)));table.append(row);}add(comparison,table,kv('实际移除的关系',e.selected_edge.id),kv('历史快照',e.historical_replay.query_snapshot_id),small('历史查询保持不可变。受控关系变更不代表新的 Agent 工程结果。'),button('查看演变证明',()=>proof('evolution'),'text-button'));page.append(comparison);}
 const outcomes=section('结果与验证依据','项目自测记录与可信验证结果分开显示；自测通过不会自动成为 VerifiedOutcome。');for(const o of data.outcomes.trusted)add(outcomes,add(el('div','outcome-row'),badge('VERIFIED · '+o.verdict),code(o.run_id),small(o.test_count+' 项必要测试 · 因果归因 UNKNOWN')));
 if(data.comparison){add(outcomes,el('h3','','已记录的普通项目试验'),small('Governance: '+data.comparison.governance.passed+'/7 public tests · Raw Memory: '+data.comparison.raw_memory.passed+'/7 public tests'),badge('BOTH EXTERNAL_UNVERIFIED','warning'),small(data.comparison.limitation),small('Provider-failed attempt retained: '+data.comparison.failed_attempt_run_id));}
 if(Array.isArray(data.outcomes.external))for(const o of data.outcomes.external)add(outcomes,add(el('div','outcome-row'),badge(o.record_kind==='OBSERVATION_USE_CLAIM'?'使用反馈 · 未核验':'EXTERNAL_UNVERIFIED','warning'),code(o.run_id),o.candidate_id?code(o.candidate_id):null,small(o.public_summary)));add(outcomes,pager('trusted','可信验证结果'),pager('external','外部观察'));page.append(outcomes);return page;}
function render(){shell();}window.addEventListener('popstate',()=>{closeProofs();cursorHistory=[];state=initial(location.search);load();});saveURL();load();setInterval(()=>{if(state.mode==='LIVE'&&autoRefresh&&!loading&&!refreshing&&!document.hidden&&!document.querySelector('dialog[open]')&&!['SELECT','INPUT'].includes(document.activeElement?.tagName))load(true);},5000);
