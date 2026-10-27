import unittest
from nodepulse import incidents as inc

def r(ts, score, url="n", err=None):
    d = {"url": url, "score": score, "ts": ts}
    if err: d["error"] = err
    return d

class T(unittest.TestCase):
    def test_windows_mttr_mtbf_availability(self):
        recs = [r(0, 90), r(60, 30), r(120, 0, err="timeout"), r(180, 95), r(240, 90),
                r(300, 20), r(360, 85), r(420, 90)]
        v = inc.incidents(recs)["n"]
        self.assertEqual(len(v["incidents"]), 2)
        a, b = v["incidents"]
        self.assertEqual((a["start"], a["end"], a["duration_s"], a["worst_score"], a["errors"]), (60, 180, 120, 0, 1))
        self.assertEqual(a["first_error"], "timeout")
        self.assertEqual((b["start"], b["end"], b["duration_s"]), (300, 360, 60))
        self.assertEqual(v["downtime_s"], 180); self.assertEqual(v["availability_pct"], 57.143)
        self.assertEqual(v["mttr_s"], 90.0); self.assertEqual(v["mtbf_s"], 120.0)

    def test_open_incident_and_per_node_and_unsorted(self):
        recs = [r(200, 10, "a"), r(100, 90, "a"), r(0, 99, "b"), r(100, 99, "b")]
        rep = inc.incidents(recs, now=400)
        e = rep["a"]["incidents"][0]
        self.assertTrue(e["open"]); self.assertIsNone(e["end"]); self.assertEqual(e["duration_s"], 200)
        self.assertIsNone(rep["a"]["mttr_s"]); self.assertEqual(rep["a"]["availability_pct"], 33.333)
        self.assertEqual(rep["b"]["incidents"], []); self.assertEqual(rep["b"]["availability_pct"], 100.0)

    def test_sla_and_markdown(self):
        rep = inc.check_sla(inc.incidents([r(0, 90), r(3600, 10), r(3660, 90), r(7200, 90)]), 99.5)
        v = rep["n"]
        self.assertFalse(v["sla_met"]); self.assertEqual(v["budget_left_s"], -24.0); self.assertEqual(v["availability_pct"], 99.167)
        md = inc.to_markdown(rep)
        self.assertIn("SLA 99.5% MISSED", md); self.assertIn("| 1970-01-01 01:00 UTC | 1970-01-01 01:01 UTC | 1m00s | 10 | 0 |", md)
        self.assertTrue(inc.check_sla(inc.incidents([r(0, 90), r(60, 90)]), 99.9)["n"]["sla_met"])

if __name__ == "__main__":
    unittest.main()
