"""Public single-thread regressions; private concurrency grading is separate."""

from pathlib import Path
import tempfile
import unittest

from app.service import OrderFlow


class PublicEpisodeATest(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.flow = OrderFlow(Path(self.folder.name) / "orders.sqlite")
        self.flow.initialize({"SKU-1": 50})

    def test_single_order_lifecycle(self):
        order = self.flow.create_order("public-a-1", "SKU-1", 3)
        self.assertEqual(order["status"], "reserved")
        self.assertEqual(self.flow.get_inventory("SKU-1")["available"], 47)
        self.flow.cancel_order("public-a-1")
        self.flow.cancel_order("public-a-1")
        self.assertEqual(self.flow.get_inventory("SKU-1")["available"], 50)

    def test_several_orders_and_cancellations(self):
        for index in range(3):
            self.flow.create_order(f"public-a-{index}", "SKU-1", 1)
        self.assertEqual(self.flow.get_inventory("SKU-1")["available"], 47)
        for index in range(2):
            self.flow.cancel_order(f"public-a-{index}")
        self.assertEqual(self.flow.get_inventory("SKU-1")["available"], 49)
        self.assertEqual(self.flow.get_inventory("SKU-1")["reserved"], 1)
        self.assertEqual(self.flow.get_order("public-a-2")["status"], "reserved")


if __name__ == "__main__":
    unittest.main()
