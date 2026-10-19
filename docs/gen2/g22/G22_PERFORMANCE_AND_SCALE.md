# Performance and scale

## Fair64×8 comparison

Same exact3073node/3008edge snapshot and graph SHA `97512cab50aab7c2b6d6f53aafeec387519ceebd1361433315116aba5fd5ca0f`, pinnedFalkorDB4.20.4,1GiB/2CPU, Python3.12.14, existing full witness/Counter/catalogue checks. DB warm; first process sample cold.20 samples each; raw arrays and query receipts retained. These are observed samples, not a statistical SLO guarantee.

| Version | observed p50 | observed p95(nearest rank) | max |
|---|---:|---:|---:|
| frozenG21 | 5.263888s | 5.354567s | 5.417309s |
| currentG22 | 2.887304s | 2.970855s | 3.014390s |

All64 complete witness SHAs equal the old version; returned bytes remain17,851,534. No removal of Q04, Counter, catalogue, grant or epoch checks. Positive immutable-byte fact/scope proof memoization is bounded2048 and never stores mutable records/current authorization. Q11 uses indexed outgoing and explicitly bound reverse targets; the large-graph probe reduced that branch~86ms→~2ms with exact row-set equality. The initial UNION still scanned all nodes on its reverse branch; its slower7.5–9.1s large-graph runs remain archived. Initial full cProfile exceeded the unchanged30s safety bound and is retained; one-witness profiling decomposed it without changing the deadline.

`G22_PERF_PASS` in this declared Core workload, ≤5s. Whole compounded MCP snapshot stays8MiB and can explicitly reject a larger query even when Core resolve succeeds; no MCP frame budget was raised.

## Actual100k/300k

First trace-heavy graph reached exact100k/300k and exercised read/publish/withdraw. To avoid treating mostly ToolEvent growth as a complete distribution test, the accepted second graph has2048 Experiences,16384 Context/Task/Evidence/Outcome/Authority paths,1984 real synthetic counterpaths,9 scopes and only1679 filler ToolEvents. Actual indexes/constraints, raw seed Cypher, all distributions/counts, SAVE and read/write results are retained. These are synthetic capacity records, not16384 real engineering grades.

The accepted graph started at exactly100,000nodes/300,000edges. A real Host-controlled14-test outcome then published and withdrew. Full relevant64×8 discovery/witnesses and actual authorization passed. Pub→APPLY, withdrawal→ABSTAIN. Additional authority withdrawal succeeded despite2048 total experiences. Unknown all-scope recall and oversized document fail closed with CAPACITY_EXCEEDED.

Observed prepare 4.399s / final publish 9.133s;
withdraw prepare 4.212s / commit 8.660s;
authority prepare 4.139s / commit 8.556s.
These include lossless compressed raw logging and full closure pinning; they are not a write SLO. Growth after these actual operations: 100259nodes/300255edges.4GiB/2CPU owned DB. `G22_SCALE_PASS` for this declared graph shape; not a promise for100k simultaneously relevant candidates or unlimited fanout.

Limits retained:256 relevant candidates,1024 registered scope heads,512 paths/experience,16 revisions,8 supersession hops,8192 witness nodes/edges,8MiB documents/128chunks/64KiB chunks,20MiB reader return budget,30s resolver bound. Host final pin set≤16384, prepared document≤8MiB; oversized multi-scope governance rejects before visibility. A broad global authority may require smaller scoped registrations/operations; no silent partition migration or truncation.

## Durable Host pin path

Same exact64×8 graph,20 additional production lookup-only registry samples: observed p50 2.924274s, p95 3.015699s, max 3.054443s. No permission cache; full witnesses still equal the frozen baseline.
