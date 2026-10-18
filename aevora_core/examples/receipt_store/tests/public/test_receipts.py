"""All example tests are PUBLIC; their results are EXTERNAL_UNVERIFIED."""
from concurrent.futures import ThreadPoolExecutor,ProcessPoolExecutor
from pathlib import Path
import multiprocessing
import sqlite3
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from app.receipts import ReceiptStore,ReceiptConflict


def record_job(args):
    path,i=args
    return ReceiptStore(path).record('receipt-'+str(i),'email',i%3+1)


class ReceiptContract(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.db=Path(self.temp.name)/'receipts.sqlite'
        self.store=ReceiptStore(self.db);self.store.initialize()
    def tearDown(self):self.temp.cleanup()
    def test_sequential_total(self):
        assert self.store.record('a','email',2)==2
        assert self.store.record('b','email',3)==5
        assert self.store.inspect('email')=={'channel':'email','total':5,'receipts':2}
    def test_idempotent_retry(self):
        first=self.store.record('a','email',2)
        self.store.record('b','email',3)
        assert self.store.record('a','email',2)==first
        assert self.store.inspect('email')['total']==5
    def test_conflicting_retry(self):
        self.store.record('a','email',2)
        with self.assertRaises(ReceiptConflict):self.store.record('a','email',3)
        assert self.store.inspect('email')['total']==2
    def test_input_rejection(self):
        for args in [('', 'email',1),('a','',1),('a','email',-1),('a','email',True)]:
            with self.assertRaises(ValueError):self.store.record(*args)
        assert self.store.inspect('email')['receipts']==0
    def test_threaded_totals(self):
        n=120
        with ThreadPoolExecutor(max_workers=12) as pool:list(pool.map(record_job,[(str(self.db),i) for i in range(n)]))
        assert self.store.inspect('email')=={'channel':'email','total':sum(i%3+1 for i in range(n)),'receipts':n}
    def test_independent_process_totals(self):
        n=80
        with ProcessPoolExecutor(max_workers=4,mp_context=multiprocessing.get_context('spawn')) as pool:
            list(pool.map(record_job,[(str(self.db),i) for i in range(n)]))
        assert self.store.inspect('email')=={'channel':'email','total':sum(i%3+1 for i in range(n)),'receipts':n}
    def test_persisted_ledger(self):
        self.store.record('a','email',2);self.store.record('b','sms',7)
        assert ReceiptStore(self.db).inspect('email')['total']==2
        with sqlite3.connect(self.db) as c:
            assert c.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
            assert c.execute('SELECT sum(amount) FROM receipts WHERE channel=?',('email',)).fetchone()[0]==2


if __name__=='__main__':unittest.main()
