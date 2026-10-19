# Inventory incident after service expansion

After expansion to independent service workers sharing one persistent SQLite database, concurrent purchases sometimes leave inventory, orders and reservation records inconsistent. Single-worker operations usually work. Some requests time out or are retried after a worker exits. Investigate the cause, repair the business code and add useful public regressions. Preserve all current API semantics and service capacity.

## Service requirements

- Each worker runs in its own OS process and all workers share the same SQLite database directory. Support at least 2 and 4 workers with concurrent requests.
- Preserve create_order, reserve_inventory, cancel_order, release_inventory, get_order and get_inventory APIs and their normal business errors.
- Every order has a client-supplied unique ID. Identical retries must not reserve twice; conflicting payloads for the same ID must be rejected.
- Successful reservation, inventory and persistent order/ledger records must agree. Insufficient stock must roll back the operation. Cancellation and repeated cancellation must be safe.
- Worker interruption may occur before a response is delivered. Persisted state must remain consistent and an identical retry after restart must have an auditable idempotent outcome.
- Keep SQLite persistence and support its normal rollback-journal and WAL modes. Do not disable concurrency, reject otherwise valid traffic, fabricate state or change tests to avoid the incident.
- Submit app Python source changes; public regression tests can be added separately. No private evaluation files or prior runs are available.

Run the supplied public tests with `python -m unittest discover -s tests/public -v`. You may create additional diagnostics using the public business API.
