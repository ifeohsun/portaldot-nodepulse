import os, tempfile, unittest
from nodepulse import history

class T(unittest.TestCase):
    def setUp(self):
        fd, self.db = tempfile.mkstemp(suffix=".jsonl"); os.close(fd); os.remove(self.db)
    def tearDown(self):
        if os.path.exists(self.db): os.remove(self.db)

    def test_append_load_since_and_torn_line(self):
        history.append(self.db, [{"url": "n1", "score": 90}], ts=100)
        history.append(self.db, [{"url": "n1", "score": 50}], ts=200)
        with open(self.db, "a") as f: f.write('{"url": "n1", "sc')   # simulated crash
        self.assertEqual(len(history.load(self.db)), 2)
        self.assertEqual([r["ts"] for r in history.load(self.db, since=150)], [200])
        self.assertEqual(history.load(self.db + ".missing"), [])

    def test_stats(self):
        recs = [{"url": "a", "score": 100, "ts": 1}, {"url": "a", "score": 40, "ts": 2},
                {"url": "a", "score": 0, "error": "timeout", "ts": 3}, {"url": "a", "score": 80, "ts": 4},
                {"url": "b", "score": 70, "ts": 4}]
        s = history.stats(recs)
        self.assertEqual(s["a"]["samples"], 4); self.assertEqual(s["a"]["uptime_pct"], 50.0)
        self.assertEqual(s["a"]["errors"], 1); self.assertEqual(s["a"]["min_score"], 0)
        self.assertEqual(s["a"]["avg_score"], 55.0); self.assertEqual(s["a"]["last_ts"], 4)
        self.assertEqual(s["b"]["uptime_pct"], 100.0)

    def test_watch_loop_persists_and_alerts(self):
        seq = iter([[{"url": "n", "score": 95}], [{"url": "n", "score": 20}], [{"url": "n", "score": 90}]])
        sleeps = []
        state = history.watch(["n"], "evm", self.db, 5, iterations=3,
                              sampler=lambda u, k: next(seq), sleep=sleeps.append)
        self.assertEqual(state["n"]["status"], "ok"); self.assertEqual(sleeps, [5, 5])
        self.assertEqual([r["score"] for r in history.load(self.db)], [95, 20, 90])

if __name__ == "__main__":
    unittest.main()
