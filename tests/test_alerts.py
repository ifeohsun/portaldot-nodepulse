import unittest
from nodepulse import alerts
class T(unittest.TestCase):
    def test_transitions(self):
        a, st = alerts.evaluate([{"url": "n1", "score": 40, "peers": 0, "best": 1}])
        self.assertEqual(a[0]["status"], "degraded")
        a, st = alerts.evaluate([{"url": "n1", "score": 30}], st); self.assertEqual(a, [])
        a, st = alerts.evaluate([{"url": "n1", "score": 95}], st); self.assertEqual(a[0]["status"], "ok")
if __name__ == "__main__":
    unittest.main()
