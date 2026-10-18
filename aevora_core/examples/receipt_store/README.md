# Durable Receipt Store — controlled maintainer example

This is a newly authored independent Python engineering example for H3 external
integration. It is not an OrderFlow Episode, reference patch, or industrial
production claim. It has its own Git baseline when copied into a clean project.
It uses Python's standard SQLite DB-API; no dependency on Aevora, OrderFlow, or
their evaluators is present in its business code and tests.

The store records delivery receipts, idempotency keys and per-channel totals.
Sequential operations work; concurrent flushes may leave totals inconsistent
with persisted receipt amounts. Investigate and fix the implementation while
preserving the API, idempotency conflicts, durable records, threads and processes.
All seven tests are public. No correct strategy is pre-installed. Results from
this project are EXTERNAL_UNVERIFIED, not hidden-Oracle VerifiedOutcomes.

```sh
python -m unittest discover -s tests/public -p 'test_*.py' -v
python -m app.receipts /tmp/receipt-example.sqlite email
```

Design research used the [Python 3.12 SQLite documentation](https://docs.python.org/3.12/library/sqlite3.html)
and inspected [DiskCache's SQLite-backed design](https://github.com/grantjenks/python-diskcache).
This example does not vendor or claim to implement DiskCache.
