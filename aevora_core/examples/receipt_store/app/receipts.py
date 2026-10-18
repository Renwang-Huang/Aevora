"""Small durable delivery-receipt store with idempotency and total aggregation."""
import json
import sqlite3


class ReceiptConflict(ValueError): pass


class ReceiptStore:
    def __init__(self, path): self.path = str(path)

    def initialize(self):
        with sqlite3.connect(self.path) as c:
            c.executescript('CREATE TABLE IF NOT EXISTS totals(channel TEXT PRIMARY KEY,total INTEGER NOT NULL CHECK(total>=0));'
                'CREATE TABLE IF NOT EXISTS receipts(key TEXT PRIMARY KEY,channel TEXT NOT NULL,amount INTEGER NOT NULL CHECK(amount>0),total INTEGER NOT NULL);')

    def record(self, key, channel, amount):
        if not isinstance(key,str) or not key or not isinstance(channel,str) or not channel or type(amount) is not int or amount<=0:
            raise ValueError('Nonempty identity/channel and positive integer amount required')
        c=sqlite3.connect(self.path,timeout=20,isolation_level=None)
        try:
            existing=c.execute('SELECT channel,amount,total FROM receipts WHERE key=?',(key,)).fetchone()
            if existing:
                if existing[:2]!=(channel,amount): raise ReceiptConflict('Idempotency identity reused with different payload')
                return existing[2]
            row=c.execute('SELECT total FROM totals WHERE channel=?',(channel,)).fetchone()
            total=(row[0] if row else 0)+amount
            c.execute('BEGIN IMMEDIATE')
            c.execute('INSERT INTO receipts VALUES(?,?,?,?)',(key,channel,amount,total))
            c.execute('INSERT INTO totals VALUES(?,?) ON CONFLICT(channel) DO UPDATE SET total=excluded.total',(channel,total))
            c.commit();return total
        except BaseException:
            c.rollback();raise
        finally:c.close()

    def inspect(self, channel):
        with sqlite3.connect(self.path) as c:
            row=c.execute('SELECT total FROM totals WHERE channel=?',(channel,)).fetchone()
            return {'channel':channel,'total':row[0] if row else 0,'receipts':c.execute('SELECT count(*) FROM receipts WHERE channel=?',(channel,)).fetchone()[0]}


if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('db');p.add_argument('channel');a=p.parse_args()
    store=ReceiptStore(a.db);store.initialize();print(json.dumps(store.inspect(a.channel)))
