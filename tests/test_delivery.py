import json, unittest
from nodepulse import alerts, history

A = [{"url": "http://a", "status": "degraded", "detail": "x"},
     {"url": "http://b", "status": "ok", "detail": "y"}]

class Opener:
    def __init__(self, fail_plan):
        self.fail_plan, self.calls = list(fail_plan), []
    def __call__(self, req, timeout=None):
        self.calls.append(json.loads(req.data))
        if self.fail_plan and self.fail_plan.pop(0):
            raise OSError("boom")

class DeliveryTest(unittest.TestCase):
    def test_all_ok(self):
        o = Opener([])
        self.assertEqual(alerts.deliver(A, "http://hook", opener=o, sleep=lambda s: None), [])
        self.assertEqual(len(o.calls), 2)
        self.assertIn("degraded", o.calls[0]["content"])

    def test_retry_then_success_with_backoff(self):
        waits = []
        o = Opener([True, True, False])
        failed = alerts.deliver(A[:1], "http://hook", opener=o, sleep=waits.append, retries=2, backoff=0.5)
        self.assertEqual(failed, [])
        self.assertEqual(waits, [0.5, 1.0])

    def test_failure_isolated_per_alert(self):
        o = Opener([True, True, False])   # first alert fails both tries, second succeeds
        failed = alerts.deliver(A, "http://hook", opener=o, sleep=lambda s: None, retries=1)
        self.assertEqual([f["url"] for f in failed], ["http://a"])
        self.assertEqual(failed[0]["delivery_error"], "boom")
        self.assertEqual(len(o.calls), 3)

    def test_watch_outbox_retries_next_cycle(self):
        seq = iter([[{"url": "u", "score": 10, "best": 1}], [{"url": "u", "score": 10, "best": 2}]])
        sent = []
        calls = {"n": 0}
        def deliver(pending, hook):
            calls["n"] += 1
            if calls["n"] == 1:
                return [dict(a, delivery_error="down") for a in pending]
            sent.extend(pending); return []
        import tempfile, os
        with tempfile.TemporaryDirectory() as d:
            history.watch(["u"], "evm", os.path.join(d, "h.jsonl"), 0, iterations=2,
                          webhook="h", sampler=lambda u, k: next(seq), sleep=lambda s: None,
                          deliver=deliver)
        self.assertEqual(len(sent), 1)
        self.assertEqual(sent[0]["status"], "degraded")
        self.assertNotIn("delivery_error", sent[0])

if __name__ == "__main__":
    unittest.main()
