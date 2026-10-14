import json, threading, unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from nodepulse import monitor

class FakeNode(BaseHTTPRequestHandler):
    best = 100
    def do_POST(self):
        req = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        res = {"system_health": {"peers": 5, "isSyncing": False},
               "chain_getHeader": {"number": hex(self.best)}}[req["method"]]
        b = json.dumps({"jsonrpc": "2.0", "id": 1, "result": res}).encode()
        self.send_response(200); self.end_headers(); self.wfile.write(b)
    def log_message(self, *a): pass

class T(unittest.TestCase):
    def test_score(self):
        self.assertEqual(monitor.score({"peers": 5, "best": 10}, 10), 100)
        self.assertEqual(monitor.score({"peers": 0, "best": 0, "is_syncing": True}, 100), 0)
        self.assertEqual(monitor.score({"peers": 2, "best": 95}, 100), 80)
    def test_run_against_fake_node(self):
        srv = HTTPServer(("127.0.0.1", 0), FakeNode)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        url = f"http://127.0.0.1:{srv.server_port}"
        out = monitor.run([url, "http://127.0.0.1:1"])
        srv.shutdown()
        self.assertEqual(out[0]["best"], 100); self.assertEqual(out[0]["score"], 100)
        self.assertIn("error", out[1]); self.assertEqual(out[1]["score"], 0)

if __name__ == "__main__":
    unittest.main()
