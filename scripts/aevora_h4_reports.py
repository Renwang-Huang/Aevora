"""Build H4 gate and delivery documents from actual immutable command receipts."""
import csv,json,shutil
from pathlib import Path
from scripts.aevora_h4_audit import ROOT,archive,write,digest,now
from tools.history_paths import write_phase_report


def main():
    A=archive();load=lambda p:json.loads((A/p).read_text());new=load('g5/FRESH_NATIVE_FACT_CHECK.json');public=load('g5/public-product-final/RESULT.json');safety=load('g5/public-safety-final/RESULT.json');tests=load('g5/EMPTY_BRIDGE_FINAL_JUNIT_CHECK.json');security=load('g1/security-empty-bridge-final/summary.json');history=load('g5/history-preservation-02/RESULT.json');sdk=load('g5/fresh-product-protocol-02/RESULT.json');install=load('g5/distribution-install/RESULT.json');browser=load('g5/public-image-browser-final/RESULT.json');fault=load('g5/public-image-database-disconnected/RESULT.json');denial=load('g5/provider-auth-denial/RESULT.json');controls=load('g5/lite-negative-controls-02/RESULT.json');dv=load('g5/dv02-regression/SUMMARY.json');cli=load('g5/cli-regression/summary.json')
    for v in [new,public,safety,tests,security,history,sdk,install,browser,fault,denial,controls,dv,cli]:
        if v['status']!='PASS':raise ValueError('Final actual evidence gate not satisfied')
    assert tests['current']==1802 and tests['required']==1714 and new['runtime_result']=='ERROR' and new['failure_kind']=='NO_PATCH' and new['native_exit_code']==0 and new['verified_outcomes']==0
    commands=['g5-empty-bridge-full-regression-01','g5-empty-bridge-security-01','g5-inherited-cli-regression-01','g5-dv02-regression-01','g5-fresh-public-image-sdk-02','g5-public-product-final-build-01','g5-public-image-final-build-01','g5-public-distribution-install-01','g5-public-image-browser-final','g5-public-image-database-disconnected-01','g5-real-provider-denial-01','g5-final-public-artifact-safety-01','g5-history-preservation-02','g5-native-fresh-readonly-02','g5-lite-real-negative-controls-02']
    receipts={label:load(label+'/command.json') for label in commands};assert all(v['exit_code']==0 for v in receipts.values())
    command_table='\n'.join('| `'+name+'` | `'+json.dumps(v['argv'],ensure_ascii=False).replace('|','\\|')+'` | '+str(v['exit_code'])+' | '+v['stdout_sha256']+' | '+v['stderr_sha256']+' |' for name,v in receipts.items())
    prefix=str(A.relative_to(ROOT));g5=f'''# Aevora H4-G5 Release / Local Delivery

**Gate结论：PASS（用户授权的本地产品交付范围）**。H4总体CONDITIONAL PASS，继承的安全/RPO限制没有升级。远程Git托管、外网部署、官方提交和视频未完成；用户明确要求暂不发布。

## 真实陌生用户路径

公开源码自身Git commit `{public['source_commit']}` / Tree `{public['source_tree']}`。110个公开源码文件；源码ZIP {public['source_zip_bytes']}字节，SHA256 `{public['source_zip_sha256']}`，两次固定时间/排序导出字节一致。Core/Console各wheel和sdist真实构建成功，真实安装了两组包，实际源码字节与公开选择一致。Python {install['python']} / SQLite {install['sqlite']}。依赖版本以 `g5/distribution-install/ACTUAL_DEPENDENCIES.txt` 为准，不伪装完全锁定全部间接依赖。

新FalkorDB Volume17693（H4维护者库17692、H1-H3旧Volume不变）；公开CLI `aevora init`后真实四工具SDK {len(sdk['checks'])}检查PASS。空查询、缺失包错误、untrusted proposal、非法字段和Host publish拒绝、真实请求header、关闭Owner移除grant/socket、零Experience/VerifiedOutcome/SourceVerification，均检查了真实图。明确fixture候选不是自然模型产物。

正式新只读Run `{new['run_id']}`，Session `{new['session_id']}`，自然完成 {new['elapsed_seconds']:.3f}秒；原生退出0，**原Runtime ERROR/NO_PATCH保留**，观测PASS；两次实际AVAILABLE响应均零候选，不编造bundle、hit或工程提交。源epoch `{new['source_commit']}` / Tree `{new['source_tree']}`。Gateway实际19次请求200，观察gpt-5.6-terra/max；真实token总量240458（含缓存，非费用）；权重和费用UNVERIFIED。实际Model/Native/MCP raw JSONL、摘要、源pin和Run seal保留。single模式，未冒充新增Multi-Agent。

最终公共镜像ID `sha256:65c4c308ded5e575f423d39bc5c1dac3242c424b9645524ebdd504d05743164c`；从公开选择源码真实docker build。UID1000、只读根、单项DB secret挂载给可信Owner，Agent不持有该文件。实际镜像运行三页浏览器检查{len(browser['checks'])}PASS，{len(browser['responses'])}个真实API收据，零脚本错误；LIVE空图、MCP请求header、三幕REPLAY、节点点击、Timeline、Proof、越权403和断网清空通过。镜像实际DB关闭端口控制503/no fallback，REPLAY独立200。真实Gateway错误鉴权401归类UPSTREAM_AUTHENTICATION_ERROR，0模型生成。

## 回归、安全及历史

- 1802/1802开发者PASS，2上游warning；1714旧身份完整、零缺失/重复/失败/skip/error。实际JUNIT SHA `{tests['junit_sha256']}`。
- 15继承CLI checks PASS：Smoke8、A14、D28正反，flock正控，BC NOT_IMPLEMENTED，ERROR2/TIMEOUT3/归档/重置。D-v02另5个真实独立Run，各36项：buggy FAIL/reference PASS/flock PASS/local_lock FAIL/blind_cleanup FAIL，恢复覆盖COMPLETE。没有重新开启D开发。
- 22实际安全检查PASS，整体Security PARTIAL_SHARED_KERNEL，未放宽宿主/Participant挂载边界。
- 历史215589文件、79测试源、39任务真值、25旧报告逐字节匹配。当前Renderer/UI/MCP/文档改动不倒归给旧Live epoch。
- 最终公共源/ZIP/wheel/sdist、实际Docker层、前端、实际HTTP：7000成员、174054419展开字节，3类实际secret及各自hex/binary SHA模式零匹配，私有路径或私有源码精确拷贝零匹配。该扫描不等于完全敌对安全证明。

## 原始失败保持

SDK01脚本错误使用旧GraphRepository默认Schema，而不是公开CLI init；真实缺少Schema1.2、GraphRecordError/退出1保持。SDK02按文档初始化新独立图，完整response先归档再断言通过。模型新attempt01 `{load('g1/native/fresh_empty_readonly_01/RESULT.json')['run_id']}` 在模型调用前AEVORA_STARTUP_FAILED，0请求，无Session/补丁；原生Bridge错误地拒绝合法空图，已修复，新增真实空图/断库两项测试并重跑全量后另开新Session。未升级旧attempt。

G4普通Session三次提议原始GraphRecordError仍保留；当前只读检查维护者fixture库确实没有生命周期Schema1.2，公开新用户CLI初始化已通过。at-time共同根因UNVERIFIED，不重写原成绩，也不伪装已产生自然候选。后续使用提议必须遵循可信初始化步骤。

历史保护脚本第一次误读报告索引外层结构而KeyError，第二次完整重哈希通过。Lite公开注释负控第一次错误指定Smoke v01，退出1；改为已注册的默认variant，四个新Run均独立FAIL且补丁保真PASS。新公共diff只添加payments注释；供Audit-Lite验证，不披露私有参考修复。独立Verifier原逻辑未修改。

## 实际命令及日志哈希

以下路径相对 `{prefix}`。所有完整UTC/耗时/退出/日志SHA在对应command.json；helper退出0只表示验收断言成立，业务负控原pytest退出1保留。

| Receipt directory | 实际argv | Exit | stdout SHA256 | stderr SHA256 |
|---|---|---:|---|---|
{command_table}

## 公开包与审计边界

产品：`g5/public-product-final/aevora-h4-public-source.zip`、`dist/`、`g5/public-image-final/aevora-h4-image.tar`，可本地复制/load。审计：H4 Full与独立MAINTAINER_AUDIT Lite，不能交Participant。封存、Lite独立verify/篡改负控/固定时间重导出收据位于Full外 `aevora_validation/audit_exports/{A.name}/`；最终验收须结合外部FINAL_DELIVERY_RECEIPT，不凭此文自称已封存。

使用：公开README→QUICKSTART→CODEX_MCP_SETUP→DEMO_WALKTHROUGH；`examples/observatory/deploy/README.md`给出实际验证的平台/UID边界。全量private Benchmark不是普通产品依赖。公开official checklist保留真实页面/日期，按用户要求不以开赛时间限制开发，不作参赛资格证明。
'''
    limitations='''# Aevora H4 Remaining Limits

- Security整体PARTIAL：共享内核/同UID本地owner不是敌对进程隔离；Flatpak24.08 EOL。DB credential仅可信Host，模型key仅Gateway Broker；不能推断完全prompt-injection免疫。
- FalkorDB4.20.4 AOF reload139仍未解决；本轮不升级引擎或删旧证据。RDB最近完成SAVE/graceful stop；未保存crash tail、断电RPO、全局多步骤图原子性UNVERIFIED。
- H2/H3原生D-v02的六UDS EPERM限制保持，H4不重启该挑战。B/C仍PLANNED，经验因果提升、Agent采纳、统计胜率没有本轮证明。
- G4原首次中断Run81d8...终态/退出UNAVAILABLE、根因UNVERIFIED，停止原始pending/官方rollout保持，不填假终态。三次提议失败未人工替换。
- H4新ordinary repair真实7公开测试PASS/补丁保真；EXTERNAL_UNVERIFIED、零VerifiedOutcome。新readonly native exit0、观测PASS，原ERROR/NO_PATCH，不是任务修复PASS。H4三名真正历史subagent来自H3 Case A，未宣称新H4 single运行有协作。
- Header读取有界；未知/完整畸形数据失败关闭，未完成JSONL尾PARTIAL。进程liveness未被探测时UNAVAILABLE；Query不是采用，Decision是Agent未可信主张。
- 公共版本0.1.0为本地交付，实际制品/sourceSHA识别版本；未发布PyPI。源ZIP同工具链确定性通过，但依赖全间接锁定、跨压缩库/平台字节确定性不宣称。
- 公开镜像实际LinuxAMD64/UID1000/Python3.12.14，其他平台和UID安排未验证。源/Core与镜像SQLite运行版本不同且真实记录。
- Remote Git/public deployment/官方提交/视频未完成，当前用户要求只本地验证；提供视频脚本和可重复Demo。官方日期/eligibility未豁免，不能当作参赛认证。
- Full/Lite与源码SHA为本地一致性，非外部存证；私有Reference/Oracle源码不进产品。Lite私有参考repair bytes NOT_INCLUDED，正控报告为支持材料，完整修复复核需授权Full。不能把selection哈希当作不可见原始证据已检验。
- 新原生桥合法空图缺陷已修复，但维护者旧fixture库未初始化lifecycle时，提议失败仍真实可见；使用公开aevora init，不能静默制造经验来掩盖配置问题。

停止H4，不自动进入H5、B/C、新Benchmark、GraphSwarm/FalkorDB重建或正式对照实验。
'''
    summary=f'''# Aevora H4 Validation Report

**Overall：CONDITIONAL PASS。G0–G5在用户授权的本地交付范围PASS；继承的安全、持久化和外部发布限制保持。**

| Gate | 实际结论 | 主证据 |
|---|---|---|
| G0 Hero Evidence Contract | PASS | 34测试、3重哈希语义篡改拒绝、10次重建一致；三幕不同来源 |
| G1 独立普通项目接入 | PASS | 干净安装、真实SDK、安全22、真实新只读Session |
| G2 受控API | PASS | 实际Core/FalkorDB只读、32API测试、13TCP检查 |
| G3 三页Console | PASS | Playwright独立Chromium17检查、6前端测试、响应及截图 |
| G4 差异化演示 | PASS | 原生修复238caf...、7原公开PASS、真实图删边/恢复、8次LIVE更新 |
| G5 本地产品交付 | PASS | 新Volume、新Session3c307...、四工具、包安装/镜像浏览器、安全扫描1802回归 |

H3 baseline/source/old outcomes以 `AEVORA_H4_BASELINE.md` 为准。新Hero契约SHA `c460d927331db3e2b262c848337afd3bb5b93007538941c546827b895bd86776`；各Gate版本提交与新源码epoch均单独归档。每个Gate报告有真实命令、错误和限制，不将后续源码套到旧模型Run。

## 本轮真实模型与成绩

1. G1 readonly231d9138...：新Session，exit0，observation PASS，原ERROR/NO_PATCH、0VO。
2. G4 first81d8c54f...：INCOMPLETE_COLLECTION，终态/exit UNAVAILABLE；原始pending及official rollout保留。
3. G4 repair238caf3b...：原Runtime PASS，1065.023秒，27 Gateway请求；实际Agent补丁SHA1251fae358b9f637281165422d069006b2fa0143f95dee77bce2b0594022fd90，严格重放7公开测试PASS，0VO。3次提议失败原样保持。
4. G5 firstbc47e91e...：AEVORA_STARTUP_FAILED，0模型调用、无nativeSession；合法空图限制修复后独立重开。
5. G5 readonly{new['run_id']}：新Session {new['session_id']}，634.031秒自然结束，19真实请求200、gpt-5.6-terra/max，两次可核查空候选响应，source不变，观测PASS，原ERROR/NO_PATCH，0VO。

新ordinary/readonly均single；不把历史Case A3个真实完整child当作新Run child。原始日志、typed摘要和raw lineSHA归档，不能从自然语言造协作/Outcome。H4不再发起不必要的付费挑战。

## 当前回归与保护

1802/1802PASS，原1714身份全保留。原业务/Hidden/Reference/Oracle与39真值逐字节不变；215589历史文件、79原测试源、25报告匹配。Smoke8/A14/D28正反以及D-v02五策略36项真实运行；ERROR/TIMEOUT、BC状态、Reset/JUnit保留。G5_PUBLIC_CONTROL四个独立真实负控只加无行为注释，验证补丁链，可在Audit-Lite独立校验，未削弱评分。

## 产品、验收入口和封存

公开SourceZIP SHA `{public['source_zip_sha256']}`，公开Commit `{public['source_commit']}` / Tree `{public['source_tree']}`；两包各wheel/sdist与本地Docker image均真实构建/安装/扫描。镜像实际Python3.12.14/SQLite3.46.1；Benchmark专用SQLite3.51.3，不混同环境指纹。SDK12检查（详见实际计数）、镜像浏览器8检查、实际DB503/REPLAY200、Gateway401、7000成员隐私扫描。README、Quickstart、Graph Schema/Cypher、License/SSPL dependency notice、AI disclosure、official checklist及Demo/录制指南均提供。

Full：`{prefix}`。最终源码/命令索引/SECRET_SCAN/manifest在final/及根封存文件。Audit-Lite及独立verify/篡改/确定性导出/Full终态重哈希的最终收据位于Full外 `aevora_validation/audit_exports/{A.name}/FINAL_DELIVERY_RECEIPT.json`。最终封存确认以此真实收据为准；该报告不自行证明外部未执行步骤。

见 `AEVORA_H4_G5_RELEASE_REPORT.md` 完整argv/退出/SHA；`AEVORA_H4_TRACEABILITY_MATRIX.csv` 主张→源码→Run/原始证据；`AEVORA_H4_LIMITATIONS.md` UNVERIFIED列表。用户已明确暂不Git托管/外网部署，实际交付为本地产品。停止H4。
'''
    summary=summary.replace('SDK12检查（详见实际计数）','SDK'+str(len(sdk['checks']))+'检查')
    for name,text in [('AEVORA_H4_G5_RELEASE_REPORT.md',g5),('AEVORA_H4_LIMITATIONS.md',limitations),('AEVORA_H4_VALIDATION_REPORT.md',summary)]:
        write_phase_report(A,name,text)
    matrix=[('G0','Three distinct honest cases, pinned verifier','examples/observatory/verify_hero.py','g0/GATE.json','PASS','Local source hashes, not external attestation'),('G1','Standalone Core official SDK','aevora_core/src/aevora/mcp_connect.py','g1/GATE.json','PASS','Same UID owner, Security PARTIAL'),('G2','Actual current Core/Graph read-only API','console/src/aevora_observatory/projection.py','g2/GATE.json','PASS','Bounded actual graph'),('G3','Three pages and six actual UI states','console/web/app.js','g3/browser-validation-07/RECEIPT.json','PASS','Playwright isolated Chromium'),('G4','Actual new untouched Agent patch','scripts/aevora_h4_native.py','g4/NATIVE_REPAIR_02_FACT_CHECK.json','PASS','EXTERNAL_UNVERIFIED, not trusted outcome'),('G4','Current support edge necessity','scripts/aevora_h4_graph_demo.py','g4/actual-necessity-02/RESULT.json','PASS','Maintainer-controlled, adoption UNKNOWN'),('G5','Zero-corpus native bridge','integrations/aevora.py','g5/FRESH_NATIVE_FACT_CHECK.json','PASS','Original ERROR/NO_PATCH retained'),('G5','Public package install and provenance','scripts/aevora_h4_distribution_check.py','g5/INSTALLED_SOURCE_BYTE_CHECK.json','PASS','LinuxAMD64/UID1000'),('G5','Actual public Docker/browser/no fallback','console/browser/product.mjs','g5/public-image-browser-final/RESULT.json','PASS','Actual browser/API bytes'),('G5','Exact secret/private-copy scan','scripts/aevora_h4_delivery.py','g5/public-safety-final/RESULT.json','PASS','3 actual classes, not hostile isolation proof'),('G5','Full regressions preserve H3 identities','scripts/aevora_h4_tests.py','g5/EMPTY_BRIDGE_FINAL_JUNIT_CHECK.json','PASS','1802/1714 zero missing/skip/error'),('G5','Historical bytes preserved','scripts/aevora_h4_delivery.py','g5/history-preservation-02/RESULT.json','PASS','215589 history/79 tests/39 truth/25 reports'),('G5','Strict Lite public benign patch controls','scripts/aevora_h4_lite_control.py','g5/lite-negative-controls-02/RESULT.json','PASS','Four hidden FAIL controls; not task success'),('G5','Stopped Full and independent Lite export','scripts/aevora_h4_export.py','OUTSIDE_FULL/FINAL_DELIVERY_RECEIPT.json','PENDING_FINAL_RECEIPT','Full pointers NOT_INCLUDED remain unverified bytes')]
    with (A/'reports/AEVORA_H4_TRACEABILITY_MATRIX.csv').open('x') as f:
        writer=csv.writer(f);writer.writerow(['gate','claim','source','evidence','status','qualification']);writer.writerows(matrix)
    reports=A/'reports';reports.mkdir(mode=0o700,exist_ok=True)
    for p in (ROOT/'docs/history/h1-h4').glob('AEVORA_H4_*'):
        if p.is_file() and not (reports/p.name).exists():shutil.copyfile(p,reports/p.name)
    write(A/'g5/GATE.json',{'gate':'G5','status':'PASS_LOCAL_PRODUCT_FUNCTIONAL_REQUIREMENTS','overall':'CONDITIONAL_PASS_INHERITED_LIMITATIONS','at':now(),'developer_tests':1802,'inherited_required':1714,'public_product_source_commit':public['source_commit'],'public_product_source_tree':public['source_tree'],'public_source_zip_sha256':public['source_zip_sha256'],'new_native_run':new['run_id'],'native_observation':'PASS','original_native_runtime':'ERROR/NO_PATCH','new_trusted_outcomes':0,'security':'PARTIAL_SHARED_KERNEL','remote_publication':'DEFERRED_USER_REQUEST','final_seal_and_lite':'REQUIRED_OUTSIDE_FULL_FINAL_DELIVERY_RECEIPT','evidence':{name+'/command.json':digest(A/name/'command.json') for name in commands}})
    print(json.dumps({'status':'PASS_REPORTS_FROM_ACTUAL_RECEIPTS','reports':len(list(reports.iterdir())),'gate':'G5 local function gate; final delivery receipt still required'}))

if __name__=='__main__':main()
