# Aevora H3-G1 — Experience Lifecycle

## Verdict: PASS

The actual functional chain exists: a fresh engineering Session proposed an immutable candidate, the Host verified sealed native/MCP/submission/Oracle evidence and explicitly approved bounded publication, and another fresh Session retrieved it. This is bounded provenance and engineering support, not proof of causal gain.

## Actual source and evidence

- Engineering Run: `405c481e-ae7a-420d-8502-fb1d9ede02e6`; lead `01a13027-d1e3-79b3-8c32-f53e3599cdd8`; source commit `9cde147199959ed5862c624739dc8a83283ae9f5`, epoch_02; 3 verified native children.
- Independent Episode A result: 14 collected, 14 PASS, zero skip/error/failure. Runtime exit 0; elapsed 904.798 s. Actual patch SHA256 `286a0f85933d35353a2cfe208d70a02fe21eaf03c756c0a2ba2761b7b7065197`.
- Candidate: `candidate:405c481e-ae7a-420d-8502-fb1d9ede02e6:sqlite-current-state-reservation`; body SHA256 `acbed37c43e2777810422bcfb862cc260983d830bb8cf04b4030788dfc17c2d2`.
- Published Experience: `experience:published:e872a71b53c3c417d33ccd0cabe688e496518285dd98d5cdb9b53303bdc7955c`. No Participant publish/admin tool exists. Host approval receipt records actual diff/body review. Unknown crash/journal/failure-domain facts are preserved; scope is not broadened to processes.
- Reader Run `c4cd6c0e-fb38-465f-bee1-63d3d50374a6`, thread `01a13036-d412-70b3-a9e0-48f61a03226f`: typed resolve, bundle and decision; one target bundle; unchanged source; complete native turn. Read-only NO_PATCH is the repair adapter's ERROR classification, not a task evaluation. Observation PASS; engineering evaluation NOT_EXECUTED.

## Real failures retained

First fresh Run `ac3e66ff-38c4-4a4c-90b8-ae635e836dcb` independently passed 14/14 but all 8 proposal calls failed: generic input schema did not explain factual condition dictionaries. No candidate was fabricated. The typed Pydantic SDK contract was added and a new independent Run executed. Previous compatibility failures (15), ExternalObservation return failure (1), scope failures (5), and local alias regression (6) remain in exclusive receipts; no old test assertions were deleted or relaxed.

First cold-recovery controller exited 1 because it did not create the Core-required private checkpoint directory. After adding mkdir(0700), new attempt exited 0. The failed SAVE/copy/publication command logs remain unchanged.

## Real graph controls and persistence

A separately owned cold RDB restore at 17690 has its own Volume. It preserves 44 schema constraints and the complete candidate/source/publication graph. A no-evidence fixture, explicitly controlled by Host, stays PENDING then REJECTED and never joins public retrieval. Actual candidate withdrawal on this replica changes new queries while the prior QuerySnapshot replays unchanged. SAVE, stop, actual unavailable SDK check, start and exact graph comparison pass. The production graph at 17689 remains PUBLISHED for ordinary-project validation.

Checkpoint manifest SHA256 `147a135b7ce10249c6c8925326975bc2805d2984c693c65c04511cb7107d8fe1`; actual RDB SHA256 `0a9a1dc2509c1b19cd916fc17d91fac052c6f009b31c62d5babc188d621b3680`. RPO is the last completed SAVE, not zero loss. No H1/H2 container or Volume was changed.

## Tests and limits

Current Core epoch_02 full developer regression: 1700/1700 PASS, all 1655 inherited identities retained. Real-graph lifecycle/scope/typed-SDK checks and 22 physical/proposal security checks pass. Shared-kernel hostile isolation, EOL, original Native UDS EPERM and AOF139 remain G0 PARTIAL. Publication staging is retryable and transitions are fenced; arbitrary multi-query inspections are not serializable snapshots. Local hashes do not attest a compromised graph administrator.

## Actual command receipts

- `g1-new-native-engineering-session-02`: exit 0, 919.68 s; command SHA256 `ad87a85ee2eaad96cbd4604bdb592b6687296ee39559e85db23cd90ec4d1ff90`. argv/start/end/stdout/stderr are in `aevora_validation/H3-20261012T082407Z-d0e93931-8fdf-4999-b05b-160b9ca20959/g1-new-native-engineering-session-02`.
- `g1-host-review-origin02`: exit 0, 0.587 s; command SHA256 `9cc19ed081c997e405a6aec643497457b291973293e9ba6660d52efb756e0bb0`. argv/start/end/stdout/stderr are in `aevora_validation/H3-20261012T082407Z-d0e93931-8fdf-4999-b05b-160b9ca20959/g1-host-review-origin02`.
- `g1-new-session-publication-readback`: exit 0, 380.998 s; command SHA256 `cd5a791d2fe93755ef74682f1805def574fcc21a00af9b556e5b6e40710a6d8b`. argv/start/end/stdout/stderr are in `aevora_validation/H3-20261012T082407Z-d0e93931-8fdf-4999-b05b-160b9ca20959/g1-new-session-publication-readback`.
- `g1-real-cold-recovery-attempt02`: exit 0, 4.466 s; command SHA256 `5935dcdb8a1e80f53075d9a072b12b616b8bcf0d190f314771fb5624b0981887`. argv/start/end/stdout/stderr are in `aevora_validation/H3-20261012T082407Z-d0e93931-8fdf-4999-b05b-160b9ca20959/g1-real-cold-recovery-attempt02`.
- `g1-cold-replica-lifecycle-controls`: exit 0, 0.901 s; command SHA256 `940d2ccb79e7aba45bfd52df85c0292c6b9c18c48fcd8bf1c148c8ce96691a58`. argv/start/end/stdout/stderr are in `aevora_validation/H3-20261012T082407Z-d0e93931-8fdf-4999-b05b-160b9ca20959/g1-cold-replica-lifecycle-controls`.
- `g1-actual-persistence-negative-control`: exit 0, 3.312 s; command SHA256 `a424dd05b102d3553a87584683d9a187c8d15a12de69056106de51b7758973cd`. argv/start/end/stdout/stderr are in `aevora_validation/H3-20261012T082407Z-d0e93931-8fdf-4999-b05b-160b9ca20959/g1-actual-persistence-negative-control`.

Example reusable execution: `python3 -m scripts.aevora_h3_recovery run --label <new-unique-label>`; SDK/graph commands use `scripts/aevora-h2-python` with explicitly owned H3 port and external credential file. Full exact argv are authoritative; no secret values are included.

### Post-seal observation qualification

Origin01 的三名子 Agent 是官方 exec 结构化 fallback 证据；其原 own-native summary=0/UNAVAILABLE（子 session_meta 缺 agent_path）。原 14/14 与 Runtime PASS 未修改。最终 Lite 以带限定 supporting attempt 保留该运行原报告/全部日志。Origin02 的三名 child 有完整 own-native 匹配链，是本 Gate 的自然 Candidate 来源。见 Full 外 `NATIVE_TRACE_QUALIFICATIONS.json`。
