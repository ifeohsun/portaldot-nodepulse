"""Unit tests for nodepulse.events — canned logs, no network."""
import unittest
from nodepulse import events, attest
from tests.test_status import FakeOpener

NID = "0x" + attest.node_id("https://node.example").hex()
OP = "0x" + "11" * 20


def _w(n):
    return f"{n:064x}"


def reg_log(block=0x10, tx="0xaa"):
    label = b"https://node.example"
    data = "0x" + _w(32) + _w(len(label)) + label.hex().ljust(64, "0")
    return {"topics": [events.TOPIC_REGISTERED, NID, "0x" + "0" * 24 + OP[2:]],
            "data": data, "blockNumber": hex(block), "transactionHash": tx}


def pulse_log(block, height, peers, score, tx):
    return {"topics": [events.TOPIC_PULSE, NID], "data": "0x" + _w(height) + _w(peers) + _w(score),
            "blockNumber": hex(block), "transactionHash": tx}


class T(unittest.TestCase):
    def test_topic_hashes_match_known_onchain_values(self):
        self.assertEqual(events.TOPIC_PULSE,
                         "0x2d13cdbfdb6e7eb308b1e2929ee53ba5ba68019f160e3150c87574373f13c3cb")
        self.assertEqual(events.TOPIC_REGISTERED,
                         "0x8326de45f66576db8724d4b3fca6bd518de1924e3dd3a2a62722d49e2ed34183")

    def test_decode_register_and_pulse(self):
        r = events.decode_log(reg_log())
        self.assertEqual((r["event"], r["label"], r["operator"]),
                         ("NodeRegistered", "https://node.example", OP))
        p = events.decode_log(pulse_log(0x20, 97196, 2, 75, "0xbb"))
        self.assertEqual((p["blockHeight"], p["peers"], p["score"], p["block"]), (97196, 2, 75, 0x20))
        self.assertIsNone(events.decode_log({"topics": ["0x" + "ff" * 32], "data": "0x"}))

    def test_timeline_orders_and_stats(self):
        logs = [pulse_log(0x30, 200, 3, 60, "0xcc"), reg_log(), pulse_log(0x20, 100, 2, 80, "0xbb")]
        tl = events.timeline(logs, {0x20: 1000})
        n = tl["nodes"][0]
        self.assertEqual(n["label"], "https://node.example")
        self.assertEqual([r["score"] for r in n["reports"]], [80, 60])
        self.assertEqual(n["reports"][0]["time"], 1000)
        self.assertEqual(n["stats"], {"reports": 2, "avg_score": 70.0, "min_score": 60, "latest_score": 60})

    def test_collect_uses_getlogs_and_block_times(self):
        op = FakeOpener({"eth_getLogs": [reg_log(), pulse_log(0x20, 100, 2, 80, "0xbb")],
                         "eth_getBlockByNumber": {"timestamp": hex(1700000000)}})
        data = events.collect("http://fake", "0xC0", from_block=5, opener=op)
        methods = [m for m, _ in op.calls]
        self.assertEqual(methods[0], "eth_getLogs")
        self.assertEqual(op.calls[0][1][0]["fromBlock"], "0x5")
        self.assertEqual(methods.count("eth_getBlockByNumber"), 2)
        self.assertEqual(data["nodes"][0]["reports"][0]["time"], 1700000000)

    def test_block_time_tolerates_pruned_state(self):
        class Pruned(FakeOpener):
            def __call__(self, req, timeout=None):
                import json
                from tests.test_status import _Resp
                return _Resp(json.dumps({"jsonrpc": "2.0", "id": 1, "error": {
                    "code": -32000, "message": "State already discarded"}}).encode())
        self.assertIsNone(events.block_time("http://fake", 5, opener=Pruned({})))

    def test_render_html_escapes_and_links(self):
        logs = [reg_log(), pulse_log(0x20, 100, 2, 80, "0xbb" + "0" * 62)]
        d = events.timeline(logs)
        d.update(rpc="http://fake", contract="0xC0")
        h = events.render_html(d, explorer="https://ex.example")
        self.assertIn("https://ex.example/tx/0xbb", h)
        self.assertIn("<td class=s>80</td>", h)
        d["nodes"][0]["label"] = "<script>"
        self.assertNotIn("<script>", events.render_html(d))


if __name__ == "__main__":
    unittest.main()
