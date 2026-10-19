"""Public regression: normal cancellation. Hidden grading runs independently."""
from pathlib import Path
import tempfile
import unittest
from app.service import OrderFlow


class PublicOrderTest(unittest.TestCase):
    def test_create_and_cancel(self):
        with tempfile.TemporaryDirectory() as folder:
            flow = OrderFlow(Path(folder) / "orders.sqlite")
            flow.initialize({"SKU-1": 10})
            flow.create_order("public-1", "SKU-1", 3)
            self.assertEqual(flow.get_inventory("SKU-1")["available"], 7)
            flow.cancel_order("public-1")
            self.assertEqual(flow.get_inventory("SKU-1")["available"], 10)
            self.assertTrue(flow.audit()["consistent"])


if __name__ == "__main__":
    unittest.main()
