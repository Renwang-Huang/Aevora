# Aevora H4 Validation Report

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
5. G5 readonly3c307462-1941-4da3-93ad-5f10f7b09ddd：新Session 01a1344d-79cf-7dd0-ad4a-944734f645c7，634.031秒自然结束，19真实请求200、gpt-5.6-terra/max，两次可核查空候选响应，source不变，观测PASS，原ERROR/NO_PATCH，0VO。

新ordinary/readonly均single；不把历史Case A3个真实完整child当作新Run child。原始日志、typed摘要和raw lineSHA归档，不能从自然语言造协作/Outcome。H4不再发起不必要的付费挑战。

## 当前回归与保护

1802/1802PASS，原1714身份全保留。原业务/Hidden/Reference/Oracle与39真值逐字节不变；215589历史文件、79原测试源、25报告匹配。Smoke8/A14/D28正反以及D-v02五策略36项真实运行；ERROR/TIMEOUT、BC状态、Reset/JUnit保留。G5_PUBLIC_CONTROL四个独立真实负控只加无行为注释，验证补丁链，可在Audit-Lite独立校验，未削弱评分。

## 产品、验收入口和封存

公开SourceZIP SHA `fb282c5a7bbec8b6f90a16205d1683a1da7f9772c965f01066ae5bd9b86fbd03`，公开Commit `00c43f53ce8d2c04af956d6b88c601efc17dfa7b` / Tree `58cbeeab12598a9a7891a0104e81c4bfd944d567`；两包各wheel/sdist与本地Docker image均真实构建/安装/扫描。镜像实际Python3.12.14/SQLite3.46.1；Benchmark专用SQLite3.51.3，不混同环境指纹。SDK11检查、镜像浏览器8检查、实际DB503/REPLAY200、Gateway401、7000成员隐私扫描。README、Quickstart、Graph Schema/Cypher、License/SSPL dependency notice、AI disclosure、official checklist及Demo/录制指南均提供。

Full：`aevora_validation/H4-20261013T032951Z-7c8b693a-7f84-4e8b-b3c1-c2e9f37f48ef`。最终源码/命令索引/SECRET_SCAN/manifest在final/及根封存文件。Audit-Lite及独立verify/篡改/确定性导出/Full终态重哈希的最终收据位于Full外 `aevora_validation/audit_exports/H4-20261013T032951Z-7c8b693a-7f84-4e8b-b3c1-c2e9f37f48ef/FINAL_DELIVERY_RECEIPT.json`。最终封存确认以此真实收据为准；该报告不自行证明外部未执行步骤。

见 `AEVORA_H4_G5_RELEASE_REPORT.md` 完整argv/退出/SHA；`AEVORA_H4_TRACEABILITY_MATRIX.csv` 主张→源码→Run/原始证据；`AEVORA_H4_LIMITATIONS.md` UNVERIFIED列表。用户已明确暂不Git托管/外网部署，实际交付为本地产品。停止H4。

## 已执行的最终封存闭环

Full已实际停止写入并封存：20310份普通文件，1246990712字节；Manifest SHA `0fcb56a4c52ff5069dfbf8dccad23411759c14d269cadc32876ab752736368b2`，SHA256SUMS SHA `0251ea47ab840631a8f645f216f50228b8d0f55e610f75d4f46898e55e073380`。最终扫描3类真实Host secret及各自指纹零命中。Full内最终源码版本以 `release-g5-seal-tool-closure/SOURCE_MANIFEST.json` / `final/DELIVERY_SOURCE_MANIFEST_closure.json` 为准，不把封存后的导出选择/文档闭环代码倒归到原模型Session。

Lite v3：8285514字节，SHA `361b37b2cb9cbf2a8e55bea043b9d364ac0e091eb639b65e21c196a5f1a8dd97`，2209源文件，展开76432355字节扫描零secret/指纹和私有源码路径。实际独立stdlib verifier退出0，字节改动退出2，重算校验和后把FAIL改为PASS仍退出2。固定时间两次导出相同；Full全部20310文件复核未变。四个手动提交业务负控Report/JUnit/Oracle/公开补丁严格匹配，全部实际FAIL，完整必要suite；它们不是任务成功。三个完成native raw streams、一次中断official rollout、一次0请求startup失败均保持分类。Private reference bytes NOT_INCLUDED，正控报告只是支持，未放宽Verifier。

最终收据：`aevora_validation/audit_exports/H4-20261013T032951Z-7c8b693a-7f84-4e8b-b3c1-c2e9f37f48ef/FINAL_DELIVERY_RECEIPT.json`。PNG/浏览器trace不是原UTF-8 CAS格式，六份真实镜像截图和typed Native/MCP时间线单独以Full原SHA收录 `reviewer-supplement/`；没有修改旧Verifier支持二进制。

封存后导出失败记录：第一次裸Python3.10缺StrEnum；改用已有Python3.12.14运行时、断网/只读Full/无credential挂载，仍因误选PNG被原Verifier拒绝。选择只读文本证据，binary保留Full指针和独立补充。v1成功但缺首次startup失败原件，v2纳入；最终完整性检查发现旧名称规则漏选2份专项收据，保持失败断言，v3补入实际原件并通过。所有旧ZIP/命令/失败保持，Full从未修改。

Overall保持CONDITIONAL PASS：安全共享内核/RPO等限制仍在；本地产品P0闭环PASS，remote发布按用户选择暂缓。停止H4。
