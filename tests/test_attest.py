import unittest
from nodepulse import attest

class T(unittest.TestCase):
    def test_keccak_vectors(self):
        self.assertEqual(attest.keccak256(b"").hex(),
                         "c5d2460186f7233c927e7db2dcc703c0e500b653ca82273b7bfad8045d85a470")
        self.assertEqual(attest.keccak256(b"abc").hex(),
                         "4e03657aea45a94fc7d47ba826c8d667c0d1e6e33a64a036ec44f58fa12d6c45")
        self.assertEqual(len(attest.keccak256(b"x" * 300)), 32)   # multi-block absorb

    def test_known_selectors(self):
        self.assertEqual(attest.selector("transfer(address,uint256)").hex(), "a9059cbb")
        self.assertEqual(attest.selector("balanceOf(address)").hex(), "70a08231")

    def test_report_layout(self):
        nid = bytes(range(32))
        cd = bytes.fromhex(attest.encode_report(nid, 12345, 7, 88)[2:])
        self.assertEqual(len(cd), 4 + 4 * 32)
        self.assertEqual(cd[4:36], nid)
        self.assertEqual(int.from_bytes(cd[36:68], "big"), 12345)
        self.assertEqual(int.from_bytes(cd[68:100], "big"), 7)
        self.assertEqual(int.from_bytes(cd[100:132], "big"), 88)
        with self.assertRaises(ValueError):
            attest.encode_report(nid, 1, 1, 101)
        with self.assertRaises(ValueError):
            attest.encode_report(nid, 1 << 64, 1, 1)

    def test_register_dynamic_string(self):
        nid = attest.node_id("https://rpc.example")
        cd = bytes.fromhex(attest.encode_register(nid, "a" * 33)[2:])
        self.assertEqual(int.from_bytes(cd[36:68], "big"), 64)     # string offset
        self.assertEqual(int.from_bytes(cd[68:100], "big"), 33)    # length
        self.assertEqual((len(cd) - 4) % 32, 0)                    # padded to word

    def test_from_sample_errors_score_zero(self):
        out = attest.from_sample({"url": "n", "error": "timeout", "best": 0, "peers": 0, "score": 77})
        self.assertTrue(out["calldata"].endswith("0" * 64))

if __name__ == "__main__":
    unittest.main()
