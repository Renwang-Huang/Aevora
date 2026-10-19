"""Read stopped native receipts; do not rescore external public observations."""
import json
from scripts.aevora_h3_audit import ROOT,archive,write,digest,now


def main():
    A=archive();rows=[]
    for local in ['g2/external/governance_01','g2/external/governance_02','g3/external/raw_01']:
        d=A/local;r=json.loads((d/'RESULT.json').read_text());run=d/'runs'/r['run_id']
        m=json.loads((run/'runtime_metadata.json').read_text())
        r.update(runtime_seconds=m['elapsed_seconds'],native_exit=m['exit_code'],single_agent_verified=m.get('single_agent_verified'),model=m['model'],provider=m['provider'],exec_usage=m.get('exec_usage'),public_inputs_sha256=m['public_inputs_sha256'],result_reference=str((d/'RESULT.json').relative_to(A)),result_sha256=digest(d/'RESULT.json'),run_seal_sha256=digest(run/'run_evidence_manifest.json'))
        rows.append(r)
    corpus=json.loads((A/'g3/PILOT_PUBLIC_CORPUS.json').read_text())
    assert all(r['baseline_tree_sha256']==corpus['baseline_tree_sha256'] and r['runtime_result']=='PASS' and r['public_test_command_exit']==0 and r['verified_outcome_count']==0 for r in rows[1:])
    graph=json.loads((A/'g3/graph-checks/necessity_01/RESULT.json').read_text())
    assert graph['status']=='PASS' and len(graph['checks'])==5
    commands={}
    for p in A.glob('*/command.json'):
        v=json.loads(p.read_text());cmd=v.get('argv',[])
        if 'scripts.aevora_h3_external' in cmd or 'scripts.aevora_h3_graph_checks' in cmd:
            commands[str(p.relative_to(A))]={'argv':cmd,'exit_code':v['exit_code'],'sha256':digest(p)}
    result={'status':'PASS','at':now(),'comparison':'Exploratory n=1 paired successful sessions; retained provider-failed attempt; no causal/statistical inference','corpus_sha256':digest(A/'g3/PILOT_PUBLIC_CORPUS.json'),'baseline_tree_sha256':corpus['baseline_tree_sha256'],'attempts':rows,'commands':commands,'graph_control_check_names':[r['name'] for r in graph['checks']],'graph_control_receipt_sha256':digest(A/'g3/graph-checks/necessity_01/RESULT.json'),'new_experience_evolution':'G1 actual natural proposal / independent PASS / bounded host publication / new reader Session; controlled withdrawal on replica preserves old snapshots','causal_benefit':'UNKNOWN','engineering_comparison':'Both untouched original submissions pass the same 7 original public tests; no hidden Oracle in this external project','resources':'Completion-aware; no total wall/request threshold; original bounded concurrency/cgroup/network restrictions retained'}
    write(A/'g3/PILOT_COMPARISON_V2.json',result);write(A/'g3/GATE_V2.json',result)
    report='''# Aevora H3-G3 — 有限价值对照

结论：**PASS**（机制与证据完整性；探索性对照，不证明因果收益）。

## 真实图与来源

- 17690 独立冷恢复副本执行实际 SDK/Cypher 控制；主实例 17689 不改。真实前提下 APPLY；独立进程前提冲突时 ABSTAIN/VERIFY；不是按 Episode 名称选择。
- 选择实际支持路径中的一条 VERIFIES 边删除：节点数量不变，当前支持路径 1→0、APPLY→VERIFY；恢复相同边正文后 WHY 恢复。旧 QuerySnapshot 原样可回放。5 项实际检查全部 PASS。
- G1 新自然 Candidate 的限定发布、新 Session 阅读、受控撤回和冷恢复与本 Gate 一起证明演化路径。受控维护者图干预不是新 Agent Outcome。

## Raw Memory / Governance 原样对照

公开原始三条经验、事实上下文及业务基线在两种条件运行前冻结于 `g3/PILOT_PUBLIC_CORPUS.json`；相同 Receipt 工程、独立 Git、7 项原有公开测试、gpt-5.6-terra/max、single/new Session、completion-aware。Raw 仅提供原始正文与声明前提；Governance 实际查询 FalkorDB 的 WHEN/WHY。没有在 Prompt 指定正确修复。

| 尝试 | Run | Runtime | 公共测试重放 | 秒 |
|---|---|---|---|---|
'''
    for r in rows:
        grade='7/7 PASS' if r.get('public_test_command_exit')==0 else 'NOT_EXECUTED'
        report+=f"| {r['condition']} | `{r['run_id']}` | {r['runtime_result']} / {r.get('failure_kind') or 'NONE'} | {grade} | {r['runtime_seconds']:.3f} |\n"
    report+='''
Gov 首次 SSE/上游 TLS 故障完整保留，不能抹去失败分母。成功 Gov 实际 resolve=2、bundle=2、decision=1、propose=1。新 H3 经验出现在查询返回中，但显式 bundle 指向两条既有经验，不能声称采纳了新经验。Raw 实际产生不同 SQL 补丁；两份原样补丁均通过 7 项公开测试。外部观察仍 EXTERNAL_UNVERIFIED，VerifiedOutcome=0。

一次成功配对不足以估计成功率；协议开销、顺序运行和 Gateway 延迟不同，不是随机/统计对照。Token 仅引用 Runtime 官方 usage，费用/实际模型权重 UNVERIFIED。

## 可复核命令与产物

真实 argv、退出码、时间、stdout/stderr SHA 见 `g3/PILOT_COMPARISON_V2.json` 的 commands 引用及对应 command.json。Controller exit 0 表示归档闭合，Gov 首次的 Runtime ERROR 仍是 ERROR。

`g3/PILOT_COMPARISON_V2.json` 保存每次结果/封存哈希、资源、Patch SHA、Run；`g3/graph-checks/necessity_01/` 保存原始 Cypher、前后图、边正文与 5 项检查；G1 生命周期来源见独立报告。最终 Gate 为 `GATE_V2.json`，初版同名排版失败前已写入的汇总仍保留。

报告生成第一版对失败 Run 强取不存在的 `public_test_command_exit` 得到 KeyError，保留于 `g3/REPORT_BUILDER_FAILURE.json`；修复为未执行分支。第二次遭独占写入保护 FileExistsError（旧汇总不覆盖），保存 `g3-build-comparison-report`；最终新文件名生成，没有修改任何成绩。

新 Gate Commit/Tree 存于 `g3/SOURCE_COMMIT.json`；不得将 Gate 后续文档 Commit 归给已结束的 native Session epoch04。
'''
    (ROOT/'AEVORA_H3_G3_VALUE_CONTROLS_REPORT.md').write_text(report)
    print(json.dumps({'status':'PASS','attempts':len(rows),'successful_pair':2,'graph_checks':5}));return 0


if __name__=='__main__':raise SystemExit(main())
