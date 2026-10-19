# Aevora H3 Validation Report

## Verdict

**CONDITIONAL PASS**。交付阶段：`COMPLETE`。G0 平台/运行时限制保留；G1–G3 PASS；G4 功能 PASS，最终导出结论由 Full 外交付收据闭合。停止在 H3。

| Dimension | Result | Actual evidence |
|---|---|---|
| Release / Security / Known Limits | PARTIAL | 公共包/显式 MAINTAINER_ONLY；实际负控 22 PASS；UDS/EOL/shared kernel/RPO 未解决 |
| Candidate Lifecycle | PASS | 新自然多 Agent proposal → source验证 → Host bounded approval → PUBLISHED → 新 Session 阅读；拒绝/撤回/重启 |
| Core Governance | PASS | 真实 SDK/Cypher、1.2/44 constraints、未发布排除、实际边删除 APPLY→VERIFY→恢复 |
| External Codex MCP | PASS | 独立 Receipt 工程、新 single Session、真实 4 工具、干净 Core serve/SDK、撤销重连与空/断库 |
| Trusted Outcome | PASS | A 独立 14 测试 Outcome；外部 7 自测试结果不生成 VerifiedOutcome |
| Value Controls | PASS (exploratory) | 正/负/演化；Raw/Gov 同基线成功配对且保留 Provider 失败；causal UNKNOWN |
| Reproducibility & Audit | PASS | 当前全回归、原始新 Session、独立 verify、Full/Lite 及外部最终收据 |

## Current actual regression

- 最终开发者 **1714/1714 PASS**，无 skip/error/failure；JUnit `final/full-regression-final/JUNIT.xml`，SHA256 `fa4baadc393da6b7172e04d328b651775229e3e31a00c7d7c483306b837d1210`。
- 保留 1 条官方 SDK/Pydantic `lifespan` forward-reference warning；实际四工具目录与调用已验证，未 suppress warning 或修改依赖换取测试成绩。原始 stdout 保留全文。
- 原 H2 1655 个身份完整保留；74 个原测试源码、39 个业务/私有真值、195885 个历史证据文件逐字节一致，`final/INTEGRITY.json`。
- 第一完整回归 1708/1708；后续新增 6 个 verifier 负控并重新运行全部当前测试。旧断言未删除或放宽。
- 15 项实际 CLI exit/status/计数验证 PASS：Smoke 8、A14、D28 的正反；D flock 替代修复 PASS；B/C NOT_IMPLEMENTED(exit4)；invalid ERROR(exit2)；timeout(exit3)；prepare/report/reset。
- D-v02 新 Buggy `9180b1fd-4949-49ca-9b78-c9d9061264ed` FAIL，36 项中 8 个失败；Reference `c2381669-2410-46f3-922f-8214b63e1cde` 36/36 PASS；恢复矩阵 COMPLETE、reset 正常。控制程序 exit0 不把 Buggy 改成 PASS。
- 新干净公共 Core wheel、安装/依赖检查/真实空图查询/无 Benchmark imports/卸载 9 命令通过；wheel SHA `b1cccd27403fd4695aec492e443b2d093fda4709e726a5e0d69c08142814cdf3`。PUBLIC vs MAINTAINER_ONLY/sdist 扫描仍见 G0，最终 package 指纹见 final。

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

Full: `aevora_validation/H3-20261012T082407Z-d0e93931-8fdf-4999-b05b-160b9ca20959`. Final export/verification sidecar: `aevora_validation/audit_exports/H3-20261012T082407Z-d0e93931-8fdf-4999-b05b-160b9ca20959`. Full is immutable after seal; outside-Full receipts close circular delivery hashing. Frozen reports may show export-pending; current reports and final Source receipt explicitly identify the post-seal closure.

See [G0](AEVORA_H3_G0_READINESS_REPORT.md), [G1](AEVORA_H3_G1_EXPERIENCE_LIFECYCLE_REPORT.md), [G2](AEVORA_H3_G2_EXTERNAL_CODEX_INTEGRATION_REPORT.md), [G3](AEVORA_H3_G3_VALUE_CONTROLS_REPORT.md), [G4](AEVORA_H3_G4_OBSERVABILITY_REPORT.md), [limits](AEVORA_H3_LIMITATIONS.md), [traceability](AEVORA_H3_TRACEABILITY_MATRIX.csv), [release](AEVORA_H3_RELEASE_REPORT.md).

## Final delivery closure (post-seal)

Final Lite: `aevora-h3-audit-lite-v2.zip`, 6678503 bytes; SHA256 `c7d36870084a90b14e4fb11b8651a80d3bf5aef2e2a2b07690990826772aeeec`. Independent stdlib verify exit0; same-time re-export identical; one changed content byte rejected with exit2. All six original event streams and first original executed report remain included.

Full manifest SHA `60868e1a3b12c034712cda60f4b29903ad0889ada5c0e4f5c6c14014683e6dae`; Full SHA256SUMS `44117bffd2979405f14888583a8e5d25cc6f37f261d85cb280d3e33694b5bad7`. Full never changed after seal. Current document/source closure is separately versioned in the delivery directory.

Post-seal current-source regression: **1714/1714 PASS**, same 1655 required identities, one SDK warning, JUnit SHA `0dc764956dc7ca8eaffa70d3c8f59a55d866219e15c2fd08269da877cf677974` (`post-seal-current-source-regression`, exit0). The thin selector was corrected to retain first executed report as qualified support; no Evaluator/Oracle/business/legacy verifier assertion changed.

首轮 source Run `ac3e66ff-38c4-4a4c-90b8-ae635e836dcb` 的 exec 事件子 Agent=3，而原 own-native summary=0/UNAVAILABLE（缺少 agent_path）。原分数完整保留；它作为 supporting attempt，不能被 Lite 升级成 fully own-native verified 的 scored entry。只有 `405c481e-ae7a-420d-8502-fb1d9ede02e6` 进入严格 scored index（14/14、3 个完整身份链）。所有尝试仍在原分母与日志中。详细指纹见 `NATIVE_TRACE_QUALIFICATIONS.json`。

Post-seal exporter fixes and current report bytes are delivered as a separate public source/document supplement; the original Full/Lite frozen source snapshot is not falsely identified as containing these later bytes.
