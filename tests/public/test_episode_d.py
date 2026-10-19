"""Public service regressions. Run with unittest; no private evaluator import."""
from pathlib import Path
import multiprocessing
import tempfile
import unittest

from app.service import OrderFlow


def purchase_worker(database, prefix, count, barrier, outcomes):
    flow = OrderFlow(database)
    barrier.wait(timeout=10)
    try:
        for index in range(count):
            flow.create_order(f"{prefix}-{index}", "SKU-1", 1)
        outcomes.put((prefix, "completed"))
    except Exception as error:
        outcomes.put((prefix, type(error).__name__))


class PublicEpisodeDTest(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.database = str(Path(self.folder.name) / "orders.sqlite")
        self.flow = OrderFlow(self.database)
        self.flow.initialize({"SKU-1": 50, "SKU-2": 9})

    def test_retry_and_cancel_on_fresh_service_instance(self):
        self.flow.create_order("public-d-retry", "SKU-1", 3)
        fresh = OrderFlow(self.database)
        fresh.create_order("public-d-retry", "SKU-1", 3)
        self.assertEqual(fresh.get_inventory("SKU-1")["available"], 47)
        fresh.cancel_order("public-d-retry")
        self.flow.cancel_order("public-d-retry")
        self.assertEqual(self.flow.get_inventory("SKU-1")["available"], 50)

    def test_independent_worker_purchases(self):
        context = multiprocessing.get_context("spawn")
        barrier, outcomes = context.Barrier(4), context.Queue()
        workers = [context.Process(target=purchase_worker,
                    args=(self.database, f"public-d-{i}", 5, barrier, outcomes)) for i in range(4)]
        try:
            for worker in workers:
                worker.start()
            for worker in workers:
                worker.join(timeout=20)
                self.assertEqual(worker.exitcode, 0)
            self.assertEqual({outcomes.get(timeout=2)[1] for _ in workers}, {"completed"})
            inventory = self.flow.get_inventory("SKU-1")
            self.assertEqual(inventory["available"], 30)
            self.assertEqual(inventory["reserved"], 20)
        finally:
            for worker in workers:
                if worker.is_alive():
                    worker.kill()
                worker.join(timeout=2)
            outcomes.close()
            outcomes.join_thread()


if __name__ == "__main__":
    unittest.main()
