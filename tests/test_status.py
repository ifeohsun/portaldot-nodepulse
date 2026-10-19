"""Unit tests for nodepulse.status — fake JSON-RPC, no network."""
import json, unittest
from nodepulse import status, attest


class FakeOpener:
    """urllib-compatible opener that returns canned JSON-RPC results by method."""

    def __init__(self, responses):
        self.responses = responses
        self.calls = []

    def __call__(self, req, timeout=None):
        body = json.loads(req.data.decode())
        method = body["method"]
        self.calls.append((method, body.get("params")))
        # eth_call dispatch by selector nibble
        if method == "eth_call":
            data = body["params"][0]["data"]
            key = "eth_call:" + data[:10]
            payload = self.responses.get(key) or self.responses.get("eth_call")
        else:
            payload = self.responses[method]
        raw = json.dumps({"jsonrpc": "2.0", "id": 1, "result": payload}).encode()
        return _Resp(raw)


class _Resp:
    def __init__(self, raw):
        self._raw = raw

    def __enter__(self):
        return self

    def __exit__(self, *a):
        pass

    def read(self):
        return self._raw


def _word(n: int) -> str:
    return f"{n:064x}"


class T(unittest.TestCase):
    def test_explorer_helpers(self):
        self.assertEqual(
            status.explorer_address("0xabc", "https://ex.example"),
            "https://ex.example/address/0xabc",
        )
        self.assertTrue(status.explorer_tx("0x1").endswith("/tx/0x1"))

    def test_encode_call_selector(self):
        # nodeCount() selector = keccak("nodeCount()")[:4]
        cd = status.encode_call("nodeCount()")
        self.assertEqual(cd, "0x" + attest.selector("nodeCount()").hex())
        nid = bytes(range(32))
        cd2 = bytes.fromhex(status.encode_call("operatorOf(bytes32)", nid)[2:])
        self.assertEqual(cd2[:4], attest.selector("operatorOf(bytes32)"))
        self.assertEqual(cd2[4:], nid)

    def test_decode_report(self):
        # five words: height=100, peers=2, score=75, ts=1700000000, reporter=0x00..01F
        hexdata = "0x" + _word(100) + _word(2) + _word(75) + _word(1700000000) + ("00" * 12) + ("01" * 20)
        r = status.decode_report(hexdata)
        self.assertEqual(r["blockHeight"], 100)
        self.assertEqual(r["peers"], 2)
        self.assertEqual(r["score"], 75)
        self.assertEqual(r["timestamp"], 1700000000)
        self.assertEqual(r["reporter"], "0x" + "01" * 20)

    def test_verify_ok_with_fake_rpc(self):
        label = "https://rpc.example"
        nid = attest.node_id(label)
        operator = "0x001f79c06e2f58bd9861e4a8592b90dacc1a82ab"
        op_word = ("00" * 12) + operator[2:]
        report_hex = "0x" + _word(97196) + _word(2) + _word(75) + _word(1729000000) + op_word
        op_sel = "0x" + attest.selector("operatorOf(bytes32)").hex()
        latest_sel = "0x" + attest.selector("latest(bytes32)").hex()
        count_sel = "0x" + attest.selector("nodeCount()").hex()
        nodes_sel = "0x" + attest.selector("nodes(uint256)").hex()
        responses = {
            "eth_getCode": "0x" + "ab" * 200,
            "eth_call:" + count_sel: "0x" + _word(1),
            "eth_call:" + nodes_sel: "0x" + nid.hex(),
            "eth_call:" + op_sel: "0x" + op_word,
            "eth_call:" + latest_sel: report_hex,
            "eth_getTransactionReceipt": {
                "status": "0x1",
                "blockNumber": "0x17b99",
                "contractAddress": "0xEc531adADF19f263231A32310E9ACb3191B898D2",
            },
        }
        opener = FakeOpener(responses)
        out = status.verify(
            rpc_url="http://fake",
            contract="0xEc531adADF19f263231A32310E9ACb3191B898D2",
            label=label,
            deploy_tx="0xdead",
            opener=opener,
        )
        self.assertTrue(out["ok"])
        self.assertTrue(out["code"]["has_code"])
        self.assertEqual(out["node_count"], 1)
        self.assertTrue(out["node"]["registered"])
        self.assertTrue(out["node"]["has_report"])
        self.assertEqual(out["node"]["latest"]["score"], 75)
        self.assertEqual(out["node"]["node_id"], "0x" + nid.hex())
        self.assertTrue(out["receipts"]["deploy"]["ok"])

    def test_verify_fails_without_code(self):
        responses = {
            "eth_getCode": "0x",
            "eth_call:" + ("0x" + attest.selector("nodeCount()").hex()): "0x" + _word(0),
            "eth_call:" + ("0x" + attest.selector("operatorOf(bytes32)").hex()): "0x" + "0" * 64,
            "eth_call:" + ("0x" + attest.selector("latest(bytes32)").hex()): "0x" + "0" * 320,
        }
        out = status.verify(rpc_url="http://fake", contract="0x0", label="x", opener=FakeOpener(responses))
        self.assertFalse(out["ok"])
        self.assertFalse(out["code"]["has_code"])


if __name__ == "__main__":
    unittest.main()
