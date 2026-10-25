import unittest
from nodepulse import alerts
class T(unittest.TestCase):
    def test_transitions(self):
        a, st = alerts.evaluate([{"url": "n1", "score": 40, "peers": 0, "best": 1}])
        self.assertEqual(a[0]["status"], "degraded")
        a, st = alerts.evaluate([{"url": "n1", "score": 30, "best": 2}], st); self.assertEqual(a, [])
        a, st = alerts.evaluate([{"url": "n1", "score": 95, "best": 3}], st); self.assertEqual(a[0]["status"], "ok")

    def test_legacy_string_state(self):
        a, st = alerts.evaluate([{"url": "n1", "score": 95, "best": 5}], {"n1": "degraded"})
        self.assertEqual(a[0]["status"], "ok")
        self.assertEqual(st["n1"]["status"], "ok")

    def test_flap_suppression(self):
        st = None
        a, st = alerts.evaluate([{"url": "n1", "score": 10, "best": 1}], st, confirm=3); self.assertEqual(a, [])
        a, st = alerts.evaluate([{"url": "n1", "score": 90, "best": 2}], st, confirm=3); self.assertEqual(a, [])  # blip resets
        for h in (3, 4):
            a, st = alerts.evaluate([{"url": "n1", "score": 10, "best": h}], st, confirm=3); self.assertEqual(a, [])
        a, st = alerts.evaluate([{"url": "n1", "score": 10, "best": 5}], st, confirm=3)
        self.assertEqual([x["status"] for x in a], ["degraded"])

    def test_stall_detection(self):
        st = None
        for _ in range(3):
            a, st = alerts.evaluate([{"url": "n1", "score": 100, "peers": 5, "best": 42}], st, stall_after=3)
            self.assertEqual(a, [])
        a, st = alerts.evaluate([{"url": "n1", "score": 100, "peers": 5, "best": 42}], st, stall_after=3)
        self.assertEqual(a[0]["status"], "degraded")
        self.assertIn("height stuck at 42", a[0]["detail"])
        a, st = alerts.evaluate([{"url": "n1", "score": 100, "peers": 5, "best": 43}], st, stall_after=3)
        self.assertEqual(a[0]["status"], "ok")

    def test_errors_do_not_count_as_progress(self):
        a, st = alerts.evaluate([{"url": "n1", "score": 100, "best": 10}], stall_after=2)
        a, st = alerts.evaluate([{"url": "n1", "score": 0, "best": 0, "error": "timeout"}], st, stall_after=2)
        self.assertEqual(a[0]["detail"], "timeout")
        self.assertEqual(st["n1"]["best"], 10)
if __name__ == "__main__":
    unittest.main()
