"""Public synthetic example and independent SQLite check; NOT OrderFlow's Oracle.

No native model, hidden assertions, maintainer source or production credentials.
The check reads actual persisted rows after all public example threads finish.
"""
from concurrent.futures import ThreadPoolExecutor
import hashlib
from pathlib import Path
import sqlite3
import tempfile
import threading


def verify():
    with tempfile.TemporaryDirectory(prefix="aevora-public-example-") as directory:
        db = Path(directory) / "stock.sqlite"
        with sqlite3.connect(db) as c:
            c.executescript("CREATE TABLE stock(available INTEGER NOT NULL CHECK(available>=0));"
                            "CREATE TABLE reservations(id INTEGER PRIMARY KEY);INSERT INTO stock VALUES(10);")
        guard = threading.RLock()
        def purchase(i):
            with guard:
                with sqlite3.connect(db) as c:
                    available = c.execute("SELECT available FROM stock").fetchone()[0]
                    if available == 0:
                        return "INSUFFICIENT"
                    c.execute("UPDATE stock SET available=?", (available - 1,))
                    c.execute("INSERT INTO reservations VALUES(?)", (i,))
                    return "RESERVED"
        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(purchase, range(32)))
        with sqlite3.connect(db) as audit:
            stock = audit.execute("SELECT available FROM stock").fetchone()[0]
            reserved = audit.execute("SELECT count(*) FROM reservations").fetchone()[0]
            integrity = audit.execute("PRAGMA integrity_check").fetchone()[0]
        passed = (results.count("RESERVED") == 10 and results.count("INSUFFICIENT") == 22
                  and stock == 0 and reserved == 10 and stock + reserved == 10 and integrity == "ok")
        return dict(origin="LIVE_SYNTHETIC_PUBLIC_VERIFIER", verdict="PASS" if passed else "FAIL",
                    model_execution=False, independent_orderflow_oracle=False,
                    source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                    requests=len(results), workers=8, initial_stock=10, available=stock,
                    reservations=reserved, insufficient=results.count("INSUFFICIENT"), integrity=integrity)

if __name__ == "__main__":
    import json
    result=verify();print(json.dumps(result,sort_keys=True));raise SystemExit(0 if result["verdict"]=="PASS" else 1)
