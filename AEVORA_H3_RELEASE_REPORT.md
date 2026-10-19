# Aevora H3 Release Report

Stage: `COMPLETE`. Local authority only. Root index was not staged/reset; unrelated H1/H2/M1 dirty files were preserved. New release commits are made in the independent H3 source checkout.

Native source epochs, per-Gate releases, delivery source and document closure are distinct. Full `release-*`/SOURCE_MANIFEST records actual Git commit/tree and every file hash; `final/DELIVERY_SOURCE_MANIFEST.json` pins the pre-seal current source snapshot. Post-seal final report/source receipt is outside Full; no original Run or historical grade is rewritten.

Full `aevora_validation/H3-20261012T082407Z-d0e93931-8fdf-4999-b05b-160b9ca20959` → independent export `aevora_validation/audit_exports/H3-20261012T082407Z-d0e93931-8fdf-4999-b05b-160b9ca20959`. Authoritative delivered SHA256, ZIP sizes, exact actual re-export equality, independent verification/byte tamper checks, public/private scan, final Git/source identity and gate closure are sidecars. Verify with the separately trusted standard-library `benchmark/evidence_verify.py`, not arbitrary code inside a ZIP.

H3 Overall CONDITIONAL PASS; see validation report. No H4/B/C/dashboard/formal randomized experiment started. Host-only graph service continues at 17689; replicas 17690 (withdrawal/ablation) and 17691 (clean demo) retain independently owned Volumes. Do not remove or reinterpret them as historical baseline services. Secrets remain external mode0600/0700; serialized paths are not secret contents.

## Final delivery closure (post-seal)

Final Lite: `aevora-h3-audit-lite-v2.zip`, 6678503 bytes; SHA256 `c7d36870084a90b14e4fb11b8651a80d3bf5aef2e2a2b07690990826772aeeec`. Independent stdlib verify exit0; same-time re-export identical; one changed content byte rejected with exit2. All six original event streams and first original executed report remain included.

Full manifest SHA `60868e1a3b12c034712cda60f4b29903ad0889ada5c0e4f5c6c14014683e6dae`; Full SHA256SUMS `44117bffd2979405f14888583a8e5d25cc6f37f261d85cb280d3e33694b5bad7`. Full never changed after seal. Current document/source closure is separately versioned in the delivery directory.

Post-seal current-source regression: **1714/1714 PASS**, same 1655 required identities, one SDK warning, JUnit SHA `0dc764956dc7ca8eaffa70d3c8f59a55d866219e15c2fd08269da877cf677974` (`post-seal-current-source-regression`, exit0). The thin selector was corrected to retain first executed report as qualified support; no Evaluator/Oracle/business/legacy verifier assertion changed.

首轮 source Run `ac3e66ff-38c4-4a4c-90b8-ae635e836dcb` 的 exec 事件子 Agent=3，而原 own-native summary=0/UNAVAILABLE（缺少 agent_path）。原分数完整保留；它作为 supporting attempt，不能被 Lite 升级成 fully own-native verified 的 scored entry。只有 `405c481e-ae7a-420d-8502-fb1d9ede02e6` 进入严格 scored index（14/14、3 个完整身份链）。所有尝试仍在原分母与日志中。详细指纹见 `NATIVE_TRACE_QUALIFICATIONS.json`。

Post-seal exporter fixes and current report bytes are delivered as a separate public source/document supplement; the original Full/Lite frozen source snapshot is not falsely identified as containing these later bytes.
