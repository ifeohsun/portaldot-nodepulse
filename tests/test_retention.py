import json, os, tempfile, unittest
from nodepulse import history, retention

class T(unittest.TestCase):
    def setUp(self):
        fd, self.db = tempfile.mkstemp(suffix=".jsonl"); os.close(fd); os.remove(self.db)
    def tearDown(self):
        if os.path.exists(self.db): os.remove(self.db)

    def test_rollup_aggregates_per_node_bucket(self):
        recs = [{"url": "a", "ts": 10, "score": 100, "best": 5}, {"url": "a", "ts": 20, "score": 40, "best": 7},
                {"url": "a", "ts": 30, "score": 0, "error": "timeout"}, {"url": "b", "ts": 15, "score": 80},
                {"url": "a", "ts": 3700, "score": 90}]
        r = retention.rollup(recs)
        a0 = [x for x in r if x["url"] == "a" and x["ts"] == 0][0]
        self.assertEqual((a0["samples"], a0["up"], a0["errors"]), (3, 1, 1))
        self.assertEqual(a0["score"], 46.67); self.assertEqual(a0["min_score"], 0); self.assertEqual(a0["max_best"], 7)
        self.assertEqual(len(r), 3)

    def test_rollup_is_idempotent_on_rollups(self):
        recs = [{"url": "a", "ts": t, "score": s} for t, s in [(1, 100), (2, 50), (3, 70)]]
        once = retention.rollup(recs); twice = retention.rollup(once)
        self.assertEqual(once, twice)

    def test_compact_preserves_uptime_and_keeps_recent_raw(self):
        now = 100 * 3600
        for h in range(48):
            for m in range(6):
                ts = now - (48 - h) * 3600 + m * 600
                history.append(self.db, [{"url": "n", "score": 30 if m == 0 else 90}], ts=ts)
        before = retention.uptime(history.load(self.db))
        s = retention.compact(self.db, keep_hours=24, now=now)
        after_recs = history.load(self.db)
        self.assertEqual(retention.uptime(after_recs), before)
        self.assertEqual(s["before"], 288); self.assertEqual(s["kept_raw"], 144); self.assertEqual(s["rollups"], 24)
        self.assertEqual(len(after_recs), 168)
        self.assertTrue(all(not r.get("rollup") for r in after_recs if r["ts"] >= now - 24 * 3600))

    def test_compact_drop_days(self):
        now = 10 * 86400
        history.append(self.db, [{"url": "n", "score": 90}], ts=now - 8 * 86400)
        history.append(self.db, [{"url": "n", "score": 90}], ts=now - 2 * 86400)
        history.append(self.db, [{"url": "n", "score": 90}], ts=now - 60)
        s = retention.compact(self.db, keep_hours=24, drop_days=7, now=now)
        self.assertEqual((s["dropped"], s["rollups"], s["kept_raw"]), (1, 1, 1))

if __name__ == "__main__":
    unittest.main()
