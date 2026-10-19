"""Generate H3 reports from actual completed receipts; no grading or model calls."""
import argparse
import ast
import csv
import json
from pathlib import Path
import xml.etree.ElementTree as ET
from scripts.aevora_h3_audit import archive,ROOT,digest,now,write

from tools.history_paths import write_phase_report


def main(delivered=False):
    A=archive();E=ROOT/'aevora_validation/audit_exports'/A.name
    def read(p):return json.loads((A/p).read_text())
    cases=list(ET.parse(A/'final/full-regression-final/JUNIT.xml').getroot().iter('testcase'))
    assert len(cases)>=1714 and not any(list(c) for c in cases if any(c.find(k) is not None for k in ['failure','error','skipped']))
    integrity=read('final/INTEGRITY.json');assert integrity['status']=='PASS'
    cli=read('final/cli/summary.json');assert len(cli['commands'])==15 and cli['status']=='PASS'
    d2=read('final/dv02/SUMMARY.json');assert d2['status']=='PASS' and len(d2['rows'])==2
    install=read('final/standalone-install/RESULT.json');assert install['status']=='PASS'
    security=read('final/security/summary.json');assert security['status']=='PASS' and len(security['checks'])==22
    assert read('g4/DEMO_REPEATABILITY.json')['status']=='PASS'
    references=read('g4/EVENT_REFERENCE_VERIFICATION.json');assert references['status']=='PASS'
    comparison=read('g3/PILOT_COMPARISON_V2.json');assert comparison['status']=='PASS'
    receipt=json.loads((E/'DELIVERY_CHECKS.json').read_text()) if delivered else None
    if delivered:assert receipt['status']=='PASS'
    stage='COMPLETE' if delivered else 'FULL_PAYLOAD_PREPARED; FINAL EXPORT RECEIPT PENDING'
    gate={'gate':'H3-G4','status':'PASS' if delivered else 'PARTIAL','functional_status':'PASS','delivery_stage':stage,'at':now(),
          'real_demo_port':17691,'independent_demo_verify':'PASS','byte_tamper_rejected':True,
          'actual_native_sessions':references['sessions'],'event_lines_checked':references['complete_original_event_lines_checked'],
          'key_actual_cypher_queries':references['actual_key_queries'],'negative_parser_contracts':14,
          'audit_delivery_receipt':str(E/'DELIVERY_CHECKS.json'),'local_authority_only':True,'causal_benefit':'UNKNOWN'}
    if delivered:write(E/'G4_FINAL_GATE.json',gate)
    elif not (A/'g4/GATE.json').exists():write(A/'g4/GATE.json',gate)
    else:
        previous=read('g4/GATE.json')
        assert previous['functional_status']==gate['functional_status'] and previous['event_lines_checked']==gate['event_lines_checked']
    g4=f'''# Aevora H3-G4 — Observation, Demo & Independent Audit

结论：**{'PASS' if delivered else 'PARTIAL（功能 PASS，等待 Full 外最终导出收据）'}**。

新 SAVE/checkpoint → 独立 Volume / 17691 → 真实 SDK 验证恢复 → H3-demo → 独立 stdlib H3-verify 已实际完成。源/目标容器、镜像 digest、RDB 与图哈希见 `g4/demo-deployment`。未替换 17689 主实例或 17690 撤回控制库。

## 观察与验证

- 实际候选、5 个审查/发布事件、自然来源核验节点及独立 PASS Outcome；关系边和显示的正向 WHY 路径逐条校验。
- 同一外部工程 Run 的 EXTERNAL_UNVERIFIED / NOT_CREATED；VerifiedOutcome=0。独立进程前提冲突负迁移仍 ABSTAIN/VERIFY。
- 两次只读重放，4 份数据文件字节一致；WHEN/WHY 仅实际 as_of 时刻不同，其余语义完全一致。保留所有实际时刻，没有改写数据获取字节 PASS。
- 原始时间线覆盖 {references['sessions']} 个真实 Session、{references['complete_original_event_lines_checked']} 条完整原始事件行，逐行 SHA 与 Full 一致。{references['actual_key_queries']} 条关键实际 SDK Cypher 保存原语句与行引用。
- 独立校验不导入 Aevora 或 Benchmark；对真实目录校验通过，对单字节改动 exit1。14 项负控覆盖额外/缺失文件、链接/硬链接/FIFO、大文件、重复/非有限 JSON、错误外部 manifest pin。

## 可执行入口与命令证据

`aevora_core/scripts/h3_demo.py` 与 `h3_verify.py`，部署、配置、权限和独立校验说明见 `aevora_core/docs/H3_OBSERVABILITY.md`。

Full 内 `g4-fresh-demo-deployment`、`g4-actual-demo`、`g4-final-independent-demo-verify`、`g4-observation-dynamic-controls`、`g4-complete-event-and-cypher-references` 的 command.json 记录真实 argv、退出与流 SHA；原型比较 AssertionError 和后续限定比较原样保留。

Audit-Lite 使用原有 CAS/脱敏/完整行引用及标准库 verifier。工程 A Run 进入 scored index；只读和外部 Session 仅 supporting，Prepared 报告不伪装评测。私有 Oracle、Reference、原始拓扑和凭据不公开；NOT_INCLUDED 仅是原始 SHA 指针。

最终分发/确定性/独立 verify/篡改/脱敏结果以 Full 外 `{E.relative_to(ROOT)}/DELIVERY_CHECKS.json` 为准。Full 内冻结的 G4 报告如处于 export-pending，是封存前阶段；最终 G4_FINAL_GATE 与当前报告在交付侧独立保存，绝不补写封存 Full。

没有 Dashboard、外部密码学存证、全局原子图快照或因果收益声明。
'''
    write_phase_report(A, 'AEVORA_H3_G4_OBSERVABILITY_REPORT.md', g4)
    limitations='''# Aevora H3 — Remaining Limits

1. **PARTIAL**：共享 Linux 内核、采样资源限额，不能证明 hostile-kernel/VM 级隔离。22 项新物理/权限/SDK 负控通过，未因此升级安全结论。
2. **PARTIAL**：原 Native UDS bind EPERM 保留（6 个 setup ERROR）。安全的 in-process 公开入口保留原 6 项业务断言且 host/outer/native 通过，不能证明跨进程 Clock transport。
3. **UNVERIFIED**：AOF reload exit139 未修复；当前仅最后完成 RDB SAVE/checkpoint 的恢复边界，未保存尾部/断电零损失不成立。旧故障未删除。
4. **PARTIAL**：Flatpak24.08 基础运行时 EOL 保留；未虚报升级。下一步应在独立基础镜像重跑 kernel/UDS/业务/SDK/模型门禁后再切换，不能原地重写历史。
5. **UNKNOWN**：Query/decision/proposal/Outcome PASS 不能证明策略采纳或因果增益；一个有限 paired pilot 不支持成功率或显著性。协议、时间、Provider 负载不同。
6. **EXTERNAL_UNVERIFIED**：Receipt 示例 7 项公开测试不是独立 hidden Oracle。Source Candidate 可停 PENDING，ExternalObservation 无 VerifiedOutcome；没有自动为任意项目构建可信评测机制。
7. **UNAVAILABLE**：per-run MCP 身份不能识别具体哪个 Subagent 作者。只归属真实 Run/连接/native typed event；没有从自然语言生成关系或缺失时间。
8. **UNVERIFIED**：Gateway 公开请求模型名/推理强度兼容且完成，实际后端权重、计费和价格没有独立证明。
9. **LIMITED**：单次 head 转移有实际 GRAPH.QUERY fence；多语句 staging/source inspection/snapshot collection 不构成全局串行化事务。Host 检查并重试/撤回 staged publication；管理员妥协不在当前敌对证明范围。
10. **LOCAL_AUTHORITY**：SHA、Git 与本机证据验证是本地一致性，非第三方存证。独立 verifier 应从另一个可信渠道取得并外部 pin。
11. **LIMITED**：输入边界和 text-as-data 防护不证明通用 prompt-injection 免疫。普通安装本身不产生隔离，需保持 Host/Consumer 物理挂载与最小 capability 边界。
12. H3 完成后停止。没有 H4 Dashboard、完整 B/C、新 Agent orchestrator、多租户 SaaS、其它 Runtime SDK 或正式随机 G0–G3 实验。
'''
    write_phase_report(A, 'AEVORA_H3_LIMITATIONS.md', limitations)
    report=f'''# Aevora H3 Validation Report

## Verdict

**{'CONDITIONAL PASS' if delivered else 'PREPARED — 功能门禁完成，最终 Full/Lite 验证待执行'}**。交付阶段：`{stage}`。G0 平台/运行时限制保留；G1–G3 PASS；G4 功能 PASS，最终导出结论由 Full 外交付收据闭合。停止在 H3。

| Dimension | Result | Actual evidence |
|---|---|---|
| Release / Security / Known Limits | PARTIAL | 公共包/显式 MAINTAINER_ONLY；实际负控 22 PASS；UDS/EOL/shared kernel/RPO 未解决 |
| Candidate Lifecycle | PASS | 新自然多 Agent proposal → source验证 → Host bounded approval → PUBLISHED → 新 Session 阅读；拒绝/撤回/重启 |
| Core Governance | PASS | 真实 SDK/Cypher、1.2/44 constraints、未发布排除、实际边删除 APPLY→VERIFY→恢复 |
| External Codex MCP | PASS | 独立 Receipt 工程、新 single Session、真实 4 工具、干净 Core serve/SDK、撤销重连与空/断库 |
| Trusted Outcome | PASS | A 独立 14 测试 Outcome；外部 7 自测试结果不生成 VerifiedOutcome |
| Value Controls | PASS (exploratory) | 正/负/演化；Raw/Gov 同基线成功配对且保留 Provider 失败；causal UNKNOWN |
| Reproducibility & Audit | {'PASS' if delivered else 'PENDING_EXPORT'} | 当前全回归、原始新 Session、独立 verify、Full/Lite 及外部最终收据 |

## Current actual regression

- 最终开发者 **{len(cases)}/{len(cases)} PASS**，无 skip/error/failure；JUnit `final/full-regression-final/JUNIT.xml`，SHA256 `{digest(A/'final/full-regression-final/JUNIT.xml')}`。
- 保留 1 条官方 SDK/Pydantic `lifespan` forward-reference warning；实际四工具目录与调用已验证，未 suppress warning 或修改依赖换取测试成绩。原始 stdout 保留全文。
- 原 H2 1655 个身份完整保留；74 个原测试源码、39 个业务/私有真值、195885 个历史证据文件逐字节一致，`final/INTEGRITY.json`。
- 第一完整回归 1708/1708；后续新增 6 个 verifier 负控并重新运行全部当前测试。旧断言未删除或放宽。
- 15 项实际 CLI exit/status/计数验证 PASS：Smoke 8、A14、D28 的正反；D flock 替代修复 PASS；B/C NOT_IMPLEMENTED(exit4)；invalid ERROR(exit2)；timeout(exit3)；prepare/report/reset。
- D-v02 新 Buggy `{d2['rows'][0]['run_id']}` FAIL，36 项中 8 个失败；Reference `{d2['rows'][1]['run_id']}` 36/36 PASS；恢复矩阵 COMPLETE、reset 正常。控制程序 exit0 不把 Buggy 改成 PASS。
- 新干净公共 Core wheel、安装/依赖检查/真实空图查询/无 Benchmark imports/卸载 9 命令通过；wheel SHA `{install['wheel_sha256']}`。PUBLIC vs MAINTAINER_ONLY/sdist 扫描仍见 G0，最终 package 指纹见 final。

## Fresh native attempts and fidelity

| Purpose | Run | Runtime / evaluation |
|---|---|---|
| Initial typed-proposal integration | ac3e66ff-38c4-4a4c-90b8-ae635e836dcb | runtime PASS; 14/14 Oracle PASS; 8 proposal requests rejected — lifecycle failure retained |
| New candidate origin | 405c481e-ae7a-420d-8502-fb1d9ede02e6 | runtime PASS; 3 verified completed native children; 14/14 independent PASS |
| Different read-only Session | c4cd6c0e-fb38-465f-bee1-63d3d50374a6 | native exit0; Adapter ERROR/NO_PATCH expected; observation PASS; NOT_EXECUTED |
| External Gov attempt1 | af26fb0c-865d-472c-97e3-c2a2c73fd597 | ERROR/PROVIDER_FAILURE; native exit1; no patch/test/VerifiedOutcome |
| External Governance | c8a6a7ae-fb65-4b2d-98ea-0651eb939a7b | runtime PASS; original 7 public tests PASS; EXTERNAL_UNVERIFIED |
| Raw Memory | f4406efc-d94d-4d21-b30f-d350248f3d4e | runtime PASS; same 7 public tests PASS; EXTERNAL_UNVERIFIED |

New actual patch SHA:

- natural origin: `286a0f85933d35353a2cfe208d70a02fe21eaf03c756c0a2ba2761b7b7065197`;
- Governance: `1504f1196a4b95e09c5062b324e7ead535054bf195bbd09e7e3dc8b27dcc0ed0`;
- Raw: `a80f114932bf87203a71925903696fb406027cb2781ad2055a34f6d8165e9300`.

No reference replacement/manual rewrite of Agent submissions. Natural lead `01a13027-d1e3-79b3-8c32-f53e3599cdd8`; three verified children `01a13028-c715-78b0-b0b0-3c4730a2a954`, `01a13028-e17b-7322-b03b-733968577c91`, `01a1302f-270a-7190-9c14-95312c905a34`. Typed raw spawn/task/completion/parent-receipt references remain in native evidence, not prose assertions.

Candidate `candidate:405c481e-ae7a-420d-8502-fb1d9ede02e6:sqlite-current-state-reservation`; body SHA `acbed37c43e2777810422bcfb862cc260983d830bb8cf04b4030788dfc17c2d2`. Experience `experience:published:e872a71b53c3c417d33ccd0cabe688e496518285dd98d5cdb9b53303bdc7955c`. Actual source Outcome `orderflow:405c481e-ae7a-420d-8502-fb1d9ede02e6` supports bounded admission, not causal validity. Host approval is documented independent maintainer review, not a claim of human approval.

## Source epochs and actual commands

Candidate origin02 used epoch02 commit `9cde147199959ed5862c624739dc8a83283ae9f5`; external conditions used epoch04 `1ddd0de4e9a5c52ef1fbcac8df02ba0bfecc69ad`. Later G4 scripts/docs/verifier releases cannot be attributed to those sessions. Gate Commit/Tree records and original trust manifests are separate from final delivery Source.

Every actual command argv/UTC/exit/stdout/stderr SHA is retained in command.json; `final/COMMAND_INDEX.json` indexes completed operations. Example exact tested modules: `scripts.aevora_h3_tests`, `scripts.aevora_h2_cli_regression --cli-module benchmark.h2_cli`, `scripts.aevora_h2_dv02_validation --repetitions 1 --strategy buggy --strategy reference`, H3-demo/H3-verify and original native helpers. Runtime wrapper parameters/password **paths** are in trusted command receipts; actual secrets or individual secret hashes are never delivery data.

## Failures / unknowns / delivery

All proposal schema failures, Source contract failures during development, SDK context errors, pytest-not-found, TLS/SSE Provider failure, first cold checkpoint directory error, first report KeyError/FileExistsError and byte-stability time AssertionError are retained. Corrections create new attempts; historical H1/H2/M1/Phase grades unchanged.

Full: `{A.relative_to(ROOT)}`. Final export/verification sidecar: `{E.relative_to(ROOT)}`. Full is immutable after seal; outside-Full receipts close circular delivery hashing. Frozen reports may show export-pending; current reports and final Source receipt explicitly identify the post-seal closure.

See [G0](AEVORA_H3_G0_READINESS_REPORT.md), [G1](AEVORA_H3_G1_EXPERIENCE_LIFECYCLE_REPORT.md), [G2](AEVORA_H3_G2_EXTERNAL_CODEX_INTEGRATION_REPORT.md), [G3](AEVORA_H3_G3_VALUE_CONTROLS_REPORT.md), [G4](AEVORA_H3_G4_OBSERVABILITY_REPORT.md), [limits](AEVORA_H3_LIMITATIONS.md), [traceability](AEVORA_H3_TRACEABILITY_MATRIX.csv), [release](AEVORA_H3_RELEASE_REPORT.md).
'''
    write_phase_report(A, 'AEVORA_H3_VALIDATION_REPORT.md', report)
    release=f'''# Aevora H3 Release Report

Stage: `{stage}`. Local authority only. Root index was not staged/reset; unrelated H1/H2/M1 dirty files were preserved. New release commits are made in the independent H3 source checkout.

Native source epochs, per-Gate releases, delivery source and document closure are distinct. Full `release-*`/SOURCE_MANIFEST records actual Git commit/tree and every file hash; `final/DELIVERY_SOURCE_MANIFEST.json` pins the pre-seal current source snapshot. Post-seal final report/source receipt is outside Full; no original Run or historical grade is rewritten.

Full `{A.relative_to(ROOT)}` → independent export `{E.relative_to(ROOT)}`. Authoritative delivered SHA256, ZIP sizes, exact actual re-export equality, independent verification/byte tamper checks, public/private scan, final Git/source identity and gate closure are sidecars. Verify with the separately trusted standard-library `benchmark/evidence_verify.py`, not arbitrary code inside a ZIP.

H3 Overall {'CONDITIONAL PASS' if delivered else 'awaits final delivery validation'}; see validation report. No H4/B/C/dashboard/formal randomized experiment started. Host-only graph service continues at 17689; replicas 17690 (withdrawal/ablation) and 17691 (clean demo) retain independently owned Volumes. Do not remove or reinterpret them as historical baseline services. Secrets remain external mode0600/0700; serialized paths are not secret contents.
'''
    write_phase_report(A, 'AEVORA_H3_RELEASE_REPORT.md', release)
    requirements=[
        ('G0-public-build-boundary','scripts/aevora_build_backend.py','_guard','g0/packages-v2/RESULT.json','g0-clean-packages-v2','PARTIAL',''),
        ('G0-Native-UDS-compatible-business','tests/public/dv02_inprocess_contract.py','main','g0/native/RESULT.json','g0-native-compatibility','PARTIAL',''),
        ('G1-native-proposal','aevora_core/src/aevora/candidate.py','propose','g1/live/candidate_origin_02/runs/405c481e-ae7a-420d-8502-fb1d9ede02e6/evaluation_report.json','g1-new-native-engineering-session-02','PASS','405c481e-ae7a-420d-8502-fb1d9ede02e6'),
        ('G1-source-authority','aevora_core/src/aevora/admission.py','verify_orderflow_candidate','g1/review/origin02/0/SOURCE_VERIFICATION.json','g1-host-review-origin02','PASS','candidate:405c481e-ae7a-420d-8502-fb1d9ede02e6:sqlite-current-state-reservation'),
        ('G1-fenced-admission-publication','aevora_core/src/aevora/candidate.py','transition','g1/review/origin02/RESULT.json','g1-host-review-origin02','PASS',''),
        ('G1-different-Session-readback','scripts/aevora_h3_observe.py','main','g1/readback/publication_01/RESULT.json','g1-new-session-publication-readback','PASS','c4cd6c0e-fb38-465f-bee1-63d3d50374a6'),
        ('G1-withdrawal-snapshot-recovery','scripts/aevora_h3_graph_checks.py','main','g1/graph-checks/lifecycle_01/RESULT.json','g1-cold-replica-lifecycle-controls','PASS',''),
        ('G1-disconnect-no-fallback','scripts/aevora_h3_persistence_checks.py','main','g1/persistence-controls/RESULT.json','g1-actual-persistence-negative-control','PASS',''),
        ('G2-clean-Core-only-install','scripts/aevora_h3_install.py','main','final/standalone-install/RESULT.json','final-clean-public-core-install-and-uninstall','PASS',''),
        ('G2-ordinary-native-MCP','scripts/aevora_h3_external.py','main','g2/external/governance_02/RESULT.json','g2-new-independent-project-session-attempt02','PASS','c8a6a7ae-fb65-4b2d-98ea-0651eb939a7b'),
        ('G2-scope-revoke-reconnect','aevora_core/src/aevora/connection.py','serve','g2/core-connection/RESULT.json','g2-independent-core-connection-checks','PASS',''),
        ('G2-untrusted-external-result','aevora_core/src/aevora/admission.py','record_external_observation','g2/external-candidate-review/RESULT.json','g2-external-candidate-pending-control','PASS',''),
        ('G3-real-material-edge-necessity','scripts/aevora_h3_graph_checks.py','main','g3/graph-checks/necessity_01/RESULT.json','g3-real-graph-necessity-controls','PASS',''),
        ('G3-Raw-Gov-paired-pilot','scripts/aevora_h3_g3_report.py','main','g3/PILOT_COMPARISON_V2.json','g3-build-comparison-report-v2','PASS','f4406efc-d94d-4d21-b30f-d350248f3d4e'),
        ('G4-cold-deploy-actual-demo','aevora_core/scripts/h3_demo.py','main','g4/demo/MANIFEST.json','g4-actual-demo','PASS',''),
        ('G4-independent-readonly-verify','aevora_core/scripts/h3_verify.py','verify','g4-final-independent-demo-verify/command.json','g4-final-independent-demo-verify','PASS',''),
        ('G4-complete-native-line-SHA','scripts/aevora_h3_g4_receipts.py','main','g4/EVENT_REFERENCE_VERIFICATION.json','g4-complete-event-and-cypher-references','PASS',''),
        ('G4-public-Lite-independent-verify','scripts/aevora_h3_export.py','worker',str(E/'DELIVERY_CHECKS.json'),str(E/'independent-final-v2-verification'),'PASS' if delivered else 'PENDING',''),
        ('Regression-all-current-and-1655','scripts/aevora_h3_tests.py','main','final/full-regression-final/JUNIT.xml','final-all-current-developer-regression','PASS',''),
        ('Regression-history-test-source-truth','scripts/aevora_h3_audit.py','integrity','final/INTEGRITY.json','final-preserved-history-and-truth','PASS',''),
        ('Security-actual-physical-and-SDK','scripts/aevora_h2_security.py','physical_probes','final/security/summary.json','final-physical-and-proposal-sdk-isolation','PARTIAL','')]
    with (A/'reports/AEVORA_H3_TRACEABILITY_MATRIX.csv').open('x',newline='') as f:
        writer=csv.writer(f);writer.writerow(['requirement','source_function_line','actual_command_receipt','run_query_candidate_reference','evidence_file','evidence_exists','evidence_sha256','gate_verdict'])
        for name,path,fn,evidence,command,status,identity in requirements:
            source=ROOT/path;line='UNAVAILABLE'
            if source.exists():
                nodes=[n for n in ast.walk(ast.parse(source.read_text())) if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)) and n.name==fn]
                if nodes:line=nodes[0].lineno
            ep=Path(evidence) if Path(evidence).is_absolute() else A/evidence
            cp=(Path(command) if Path(command).is_absolute() else A/command)/'command.json'
            if status in {'PASS','PARTIAL'}:
                assert line!='UNAVAILABLE' and ep.is_file(), 'Traceability must name actual source and evidence: '+name
                assert cp.is_file(), 'Actual command receipt missing: '+name
            # Find actual receipt names by their unique module/argument when
            # historical collector labels differ; no invented command proof.
            writer.writerow([name,f'{path}:{line} ({fn})',str(cp.relative_to(ROOT)) if cp.exists() else 'SEE_ACTUAL_COMMAND_INDEX / '+command,identity,evidence,str(ep.is_file()),digest(ep) if ep.is_file() else 'UNAVAILABLE',status])
    print(json.dumps({'stage':stage,'developer_tests':len(cases),'reports':5,'traceability_rows':len(requirements)}));return 0


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--delivered',action='store_true');args=p.parse_args();raise SystemExit(main(args.delivered))
