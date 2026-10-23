import os, tempfile, threading, unittest, urllib.request
from nodepulse import exporter, history

SAMPLES = [
    {"url": "https://a", "peers": 4, "best": 100, "is_syncing": False, "latency_ms": 120, "score": 100},
    {"url": "https://b", "error": "timeout", "peers": 0, "best": 0, "score": 0},
]

class T(unittest.TestCase):
    def test_render_basic(self):
        out = exporter.render(SAMPLES, now=1000)
        self.assertIn('nodepulse_up{node="https://a"} 1', out)
        self.assertIn('nodepulse_up{node="https://b"} 0', out)
        self.assertIn('nodepulse_health_score{node="https://a"} 100', out)
        self.assertIn('nodepulse_rpc_latency_seconds{node="https://a"} 0.12', out)
        self.assertNotIn('nodepulse_peers{node="https://b"}', out)   # failed polls report no peers
        self.assertIn("# TYPE nodepulse_up gauge", out)
        self.assertTrue(out.endswith("nodepulse_scrape_timestamp_seconds 1000\n"))

    def test_label_escaping(self):
        out = exporter.render([{"url": 'x"y\\z', "peers": 1, "best": 1, "score": 50}], now=0)
        self.assertIn('node="x\\"y\\\\z"', out)

    def test_render_with_history_stats(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "h.jsonl")
            history.append(p, [SAMPLES[0]], ts=10); history.append(p, [SAMPLES[1]], ts=10)
            history.append(p, [{**SAMPLES[0], "score": 40}], ts=20)
            out = exporter.render(SAMPLES, history.stats(history.load(p)), now=0)
        self.assertIn('nodepulse_uptime_ratio{node="https://a"} 0.5', out)
        self.assertIn('nodepulse_poll_errors_total{node="https://b"} 1', out)
        self.assertIn("# TYPE nodepulse_poll_errors_total counter", out)

    def test_http_server(self):
        srv = exporter.make_server(["https://a", "https://b"], port=0, sampler=lambda u, k: SAMPLES)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        base = f"http://127.0.0.1:{srv.server_port}"
        try:
            r = urllib.request.urlopen(base + "/metrics", timeout=5)
            self.assertIn("text/plain", r.headers["Content-Type"])
            self.assertIn('nodepulse_up{node="https://a"} 1', r.read().decode())
            self.assertEqual(urllib.request.urlopen(base + "/healthz", timeout=5).read(), b"ok\n")
            with self.assertRaises(urllib.error.HTTPError):
                urllib.request.urlopen(base + "/nope", timeout=5)
        finally:
            srv.shutdown()

if __name__ == "__main__":
    unittest.main()
