"""M1 current-state regression, exact prior strategies and anti-bypass probes."""
from pathlib import Path
import argparse
import difflib
import json
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from benchmark.episodes.episode_a import create_episode_a
from benchmark.episodes.episode_d import build_episode_d_fixture
from benchmark.runner import apply_patch
from scripts.reproduce_episode_d import run_record


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive",type=Path)
    parser.add_argument("--only",help="comma-separated case labels, for a separately recorded correction")
    selected=parser.parse_args()
    archive=selected.archive.resolve()
    archive.mkdir(parents=True,exist_ok=False)
    locked=create_episode_a(archive/"a-local-lock")
    source=locked/"app/service.py"
    # Exact maintainer seed mechanism from validate_phase2.py, no Agent claim.
    source.write_text(source.read_text()+'''\nimport threading
_create_lock = threading.RLock()
_unlocked_create = OrderFlow.create_order
def _serialized_create(self, *args, **kwargs):
    with _create_lock:
        return _unlocked_create(self, *args, **kwargs)
OrderFlow.create_order = _serialized_create
''')
    atomic=create_episode_a(archive/"a-atomic-alternate")
    source=atomic/"app/service.py"
    source.write_text(source.read_text().replace("self.inventory.reserve(connection, order_id, snapshot=snapshot)",
                                               "self.inventory.reserve(connection, order_id)"))
    natural=create_episode_a(archive/"a-natural-original")
    historical_patch=ROOT/"runs/339f7d73-29df-4242-8920-9e566bce8a9c/submission.diff"
    apply_patch(natural,historical_patch)
    custom=build_episode_d_fixture(archive/"custom-transaction",strategy="reference")
    source=custom/"app/service.py"
    source.write_text(source.read_text().replace("with self.persistence.transaction() as connection:",
        "with _direct_transaction(self.persistence) as connection:")+'''\nfrom contextlib import contextmanager
@contextmanager
def _direct_transaction(persistence):
    with persistence.connection() as connection:
        connection.execute("BEGIN IMMEDIATE")
        try:
            yield connection
            connection.commit()
        except BaseException:
            connection.rollback()
            raise
''')
    spoof=build_episode_d_fixture(archive/"spoof-success",strategy="reference")
    source=spoof/"app/service.py"
    text=source.read_text(); start=text.index("    def create_order("); end=text.index("    def reserve_inventory(",start)
    text=text[:start]+'''    def create_order(self, order_id, sku, quantity, reserve=True):
        return {"order_id":order_id,"sku":sku,"quantity":quantity,
                "status":"reserved","reservation_state":"active"}

'''+text[end:]
    source.write_text(text)
    refusal=build_episode_d_fixture(archive/"refuse-workers",strategy="reference")
    source=refusal/"app/service.py"
    source.write_text(source.read_text()+'''\nimport os
from app.errors import InsufficientInventory
_original_init = OrderFlow.__init__
def _choose_leader(self, db_path):
    _original_init(self, db_path)
    try:
        fd = os.open(str(self.persistence.db_path)+".leader", os.O_CREAT|os.O_EXCL|os.O_WRONLY, 0o600)
        os.close(fd)
        self._accept_traffic = True
    except FileExistsError:
        self._accept_traffic = False
_original_create = OrderFlow.create_order
def _refuse_other_workers(self, *args, **kwargs):
    if not self._accept_traffic:
        raise InsufficientInventory("Only one worker accepts writes")
    return _original_create(self, *args, **kwargs)
OrderFlow.__init__ = _choose_leader
OrderFlow.create_order = _refuse_other_workers
''')
    cases=[("smoke-buggy","SMOKE-001",None,1),
           ("smoke-reference","SMOKE-001",ROOT/"evaluator/reference_patches/SMOKE-001-current.diff",0),
           ("a-buggy","A",None,1),("a-reference","A",ROOT/"evaluator/reference_patches/A-v01.diff",0),
           ("a-local-lock","A",locked,0),("a-atomic-alternate","A",atomic,0),
           ("a-original-natural-replay","A",natural,0),
           ("d-exact-a-local-lock-transfer","D",locked,1),
           ("d-exact-a-natural-transfer","D",natural,0),
           ("d-custom-transaction-fairness","D",custom,0),
           ("d-spoof-success","D",spoof,1),("d-refuse-workers","D",refusal,1),
           ("b-planned","B",None,4),("c-planned","C",None,4)]
    records=[]
    only=set(selected.only.split(",")) if selected.only else {c[0] for c in cases}
    if not only <= {c[0] for c in cases}:
        parser.error("Unknown case label")
    for label,episode,submission,expected in cases:
        if label not in only:continue
        args=[sys.executable,"-m","benchmark.cli","--runs-root",str(archive/"runs"),"evaluate","--episode",episode]
        if submission is not None:args += ["--submission",str(submission)]
        receipt,report=run_record(archive/("command-"+label),args)
        tests=report.get("test_results") or {}
        valid=receipt["exit_code"]==expected and not tests.get("errors",0) and not tests.get("skipped",0)
        records.append({"label":label,"expected_exit":expected,"checks_pass":valid,"command":receipt,
                        "evaluated_sha256":(report.get("submission") or {}).get("evaluated_sha256")})
        (archive/"summary.json").write_text(json.dumps({"commands":records,
            "selected_case_labels":sorted(only),
            "result":"PASS" if all(r["checks_pass"] for r in records) else "FAIL"},indent=2)+"\n")
        print(json.dumps({"label":label,"run_id":receipt["run_id"],"status":receipt["status"],
             "exit_code":receipt["exit_code"],"checks_pass":valid}),flush=True)
    transfer={}
    for left,right in [("a-local-lock","d-exact-a-local-lock-transfer"),
                       ("a-original-natural-replay","d-exact-a-natural-transfer")]:
        if not {left,right} <= only:continue
        first=next(r for r in records if r["label"]==left)
        second=next(r for r in records if r["label"]==right)
        transfer[left]={"source_run_id":first["command"]["run_id"],"target_run_id":second["command"]["run_id"],
                       "source_sha256":first["evaluated_sha256"],"target_sha256":second["evaluated_sha256"],
                       "identical_source":first["evaluated_sha256"]==second["evaluated_sha256"],
                       "source_status":first["command"]["status"],"target_status":second["command"]["status"],
                       "origin":"maintainer_seed" if left=="a-local-lock" else "natural"}
    (archive/"exact-strategy-transfer.json").write_text(json.dumps(transfer,indent=2)+"\n")
    return 0 if all(r["checks_pass"] for r in records) and all(r["identical_source"] for r in transfer.values()) else 1


if __name__=="__main__":raise SystemExit(main())
