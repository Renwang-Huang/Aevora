# H2 D-v02 implementation contract

Version 1.0.2. This is a **maintainer specification**, not Participant input.
Implementation and dynamic acceptance remain UNVERIFIED until the G2 receipts
exist. The original `EPISODE_D_V02_DESIGN.md` 0.3.0 remains unchanged and correctly
describes the historical design-only stage.

## Design decisions and provenance

H2 implements the original recommended L (request lease/authority) scenario.
The backup-generation S alternative remains unimplemented. OrderFlow A and
D-v01 retain their source, API, private manifests and original evaluation truth.
SQLite transactions and capacity constraints remain present in the new buggy
fixture. A transaction protecting inventory alone does not certify that a
previous request handle is still authorized to publish a result.

The new challenge is registered as `D-V02`, family D, variant `v02`. This new
ID avoids changing the meaning of the existing `D/v01` registration. An additive
trusted `benchmark.h2_cli` bootstrap activates the new registry and suite using
the existing registration protocol. It delegates the complete lifecycle to the
existing Runner and CLI. It is not an Agent orchestrator. The unchanged ordinary
CLI continues to support existing scenarios; use the H2 entry point for D-V02.

New request modules are fixture templates outside root `app/`. They are copied
only into D-V02 workspaces. The existing fixture factories copy root `app/`, so
adding request code there would unnecessarily contaminate old challenges.

The API, state machine and minimum persistence contract below must be public
through the manifest/TASK, source docstrings and public tests. Maintainer root
cause analysis, reference patches, private timing and Oracle assertions are not
copied into Participant inputs.

## Public operations and outcomes

The eight existing OrderFlow methods retain their normal semantics. New methods:

| Method | Contract |
|---|---|
| `claim_request(request_id, order_id, sku, quantity, ttl)` | Establish/discover immutable payload. A PENDING request without a valid claim grants an opaque handle. Claiming does not create an order or reserve inventory. A live claim returns CLAIM_BUSY without its token. A terminal request returns its persisted receipt. |
| `renew_request(handle, ttl)` | Extend only the current unexpired PENDING claim to at least `max(old_deadline, now + ttl)`. A stale claim cannot change a new claim, receipt or terminal state. |
| `complete_request(handle)` | Publish the matching order/reservation and a persistent receipt under current authorization. Retry has no additional reservation or ledger effect. |
| `cancel_request(request_id)` | Atomically cancel an unfinished intent and revoke its claim. Completed-first returns ALREADY_COMPLETED and the original receipt. It does not cancel an already existing order. |
| `get_request(request_id)` | Return persisted payload, status, deadline and receipt. It does not disclose the current opaque token or reconstruct a success from memory. |

`handle` is an object with nonempty `request_id` and `token` strings. Tokens are
unique across claim history. They are not forced to be numeric fencing values,
PIDs, worker names or any particular repair mechanism.

RequestNotFound and RequestConflict are explicit business errors. Invalid input,
transport, Clock and SQLite failures retain their distinct classifications.
Quantity and TTL are positive integers, excluding booleans; valid large TTLs
are not rejected just because SQLite INTEGER has a smaller range.
Payload equality is checked before returning a terminal receipt: a terminal
request ID with a different order ID/SKU/quantity still raises RequestConflict.

PENDING, COMPLETED and CANCELLED are the request states. COMPLETED/CANCELLED are
terminal; the persisted terminal receipt is immutable. A request ID always maps
to one order ID/SKU/quantity payload. Independent request IDs may legitimately
refer to the same existing order with identical payload.

| Outcome | Meaning |
|---|---|
| COMPLETE_RESERVED | A matching active reservation exists and the intent completed. |
| COMPLETE_DISCOVERED_CANCELLED | The matching order was already cancelled; complete the intent without reserving or describing it as a new reservation. |
| REQUEST_CANCELLED | The unfinished intent was durably cancelled. |
| INSUFFICIENT_INVENTORY_RETRYABLE | No new order/reserve side effect; keep the intent PENDING and release this claim so a later ordinary claim can retry. |
| STALE_HANDLE | The claim is not current/valid. No business side effect; discovering an existing terminal receipt read-only is also permitted. |
| ALREADY_COMPLETED | Cancellation discovered completion first; return its original receipt. |

A later ordinary `cancel_order` does not invalidate an earlier successful request
receipt. Existing legitimate orders must not be deleted as compensation. An
existing unreserved matching order can be reserved normally. A cancelled order
must not be resurrected by a new intent.

The public request object has `request_id`, `order_id`, `sku`, `quantity`, `status`,
`deadline` (integer/null) and `receipt` (object/null). A receipt contains the five
fields `outcome`, `request_id`, `order_id`, `sku`, `quantity`; implementations may
add compatible fields. Successful claim returns `{outcome: CLAIM_GRANTED,
handle: {request_id, token}, request: <public object>}`. A busy claim returns
`{outcome: CLAIM_BUSY, request: <public object>}` without a handle. Successful
renewal returns CLAIM_RENEWED, the same handle and the public request object.
Completion/terminal discovery returns the persisted receipt directly. A stale
handle response contains STALE_HANDLE and request_id, or the original terminal
receipt without mutation. Completed-first cancellation returns
`{outcome: ALREADY_COMPLETED, request_id, receipt: <original receipt>}`.
Repeated cancellation returns the original REQUEST_CANCELLED receipt.

## Time and linearization

Workers read a shared authoritative Clock via a public abstraction. Production
uses monotonic integer ticks; controlled tests advance a host-owned Clock only
between ordinary calls unless a test explicitly accepts overlapping legal
histories. Equality with deadline is expired: current token, PENDING state and
`now < deadline` must hold at an allowed authorization/publication point.
The default production unit is one millisecond (`monotonic_ns() // 1_000_000`).
`ORDERFLOW_CLOCK_QUERY` selects the public Unix query socket in controlled worker
environments. Its strict request is the bytes `NOW\n`; the response is one JSON
line with `tick` as a canonical nonnegative decimal string. The public
`app.request_clock.now()` abstraction returns its integer value. Equivalent
implementations may use the same documented channel; no private service helper
is required. Clock disconnection is a distinct infrastructure error, not stock
exhaustion. These details must be in the actual Participant task/source inputs.

No test rejects a legal operation merely because its COMMIT wall time crosses a
deadline after valid authorization while conflicting writers cannot intervene.
The Oracle uses acknowledged happens-before boundaries and permits either winner
for genuinely overlapping complete/cancel operations.

Deadline/tick storage uses canonical nonnegative decimal TEXT with Python integer
comparison; no lexical timestamp comparison. The Clock query socket accepts only
NOW. A read-only socket mount alone is not sufficient: its actual protocol must
reject time mutation, malformed messages and unauthorized commands. Candidate
gets only this socket, never its parent control directory or private event log.
Clock events retain kernel peer identity and host timestamps. Reset starts an
independent Clock/DB/Worker pool with a new Run ID.

## Minimum public persistence records

The public base table `requests` retains request_id (primary key), order_id, sku,
quantity, status, nullable current_token, nullable deadline and nullable
receipt_json. The base table `request_claims` retains unique token (primary key),
request_id (foreign key to requests), order_id, sku, quantity, issued_tick and
issued_deadline. Tick/deadline columns are canonical decimal TEXT. The SKU and
positive quantity constraints remain real database constraints. Claim issuance
does not require an order row to already exist. issued_deadline is the immutable
issuance history; renewal changes the current deadline and does not rewrite the
historical deadline or imply their equality. Public
business inventory/orders/ledger remain their existing base tables and constraints.
Candidate may add tables, columns and modules; the public audit records cannot be
replaced by candidate-generated views or a fabricated audit() response.

The reference uses current persisted authority and terminal-state checks within
short transactions. A genuinely different legal control uses a cooperative stable
inode file lock around short authority verification/publication; pauses occur
between calls, so this is not a long lock over the preparation phase. All related
writers participate. No hidden test requires either repair strategy.

The defect is omitted current-generation/terminal verification when publishing
from historical claim data, plus cleanup that does not condition on its own
generation. It must produce actual stale writes while preserving normal single
handler paths and existing capacity constraints. A local-lock or inventory-only
strategy is rejected by observed authority violations, not source spelling.

## Trusted evaluation and scheduling

Reuse the existing isolated BusinessRPC, WorkerControl, SQLiteObserver,
WorkerSupervisor, cgroup/resource cleanup and independent pytest evaluator.
Add a thin endpoint for the five ordinary request APIs and Clock injection; it
contains no assertions or expected outcomes. Its sandbox mounts only the old
generic endpoint, new endpoint and this Run's Clock query socket.

At least two/four distinct actual OS workers share the same device/inode DB.
Each worker performs real ample-stock writes. After claim ACK, a kernel-identified
worker can be SIGSTOPped outside a business operation; another worker takes over
or cancels, then SIGCONT permits a late call. This cannot deadlock a correct
transaction by requiring a barrier while holding a write lock.

Raw host database checks, Clock events, call intervals, ACKs and process/FD
witnesses determine truth. Capture intermediate acknowledged states before later
operations so a resurrection followed by repair cannot disappear from evidence.
Candidate audit(), self-reported PID/time and Agent narration are auxiliary only.

Crash coverage must distinguish method and phase: claim before actual write
commit; claim commit/response lost; complete before actual write commit; complete
commit/response lost; stale cleanup and restart. Stop at actual generic observer
events and verify kernel identity, write/inode observations, response absence,
recovery and identical retry. Unsupported observability is
ERROR/RECOVERY_EVIDENCE_UNVERIFIED, not a simulated business failure or PASS.
Do not force a particular private helper, SQL statement spelling or token name.

## Acceptance and freeze order

1. Public contract review, independent Oracle review and design decisions precede
   business implementation; all original specifications remain preserved.
2. Buggy, reference, distinct legal alternative and representative invalid strategy
   run at least ten independent initializations each. All attempts, counts, Run
   IDs, failures and resets are retained, including any infrastructure errors.
3. Exercise differing capacity/quantity/SKU, renewal/expiry/ABA, cancellation,
   insufficient rollback, WAL/DELETE, crash/retry and old business regression.
4. Verify the new Clock mount and control protocol, plus all three existing
   isolation layers; no model challenge before source/Oracle/public/corpus and
   safety fingerprints are frozen.
5. Old 1214 test identities, old test source, 57 task truth files and all protected
   historical evidence remain exact. New counts are measured from actual JUnit.
6. G3 uses fresh native Codex sessions and untouched extracted submissions. This
   is a D-family generalization check, not proof across B/C or all fault families.

## Mature references

The design reuses SQLite's documented transaction/isolation guarantees and the
existing OS-worker supervisor. Owner-specific lease renewal/release follows the
established principle that a late owner must not modify a later owner's grant;
no Redis-based business database or new lock service is introduced.

- [SQLite transactions](https://www.sqlite.org/lang_transaction.html)
- [SQLite isolation](https://www.sqlite.org/isolation.html)
- [Redis distributed-lock ownership and renewal](https://github.com/redis/redis-doc/blob/master/docs/manual/patterns/distributed-locks.md)
- [Original D-v02 design](../../EPISODE_D_V02_DESIGN.md)
- [Original independent design review](../../EPISODE_D_V02_DESIGN_REVIEW.md)

This document freezes the implementation contract. It does not certify a tested
fixture, stable failure, legal alternative, solving difficulty or governance gain.
