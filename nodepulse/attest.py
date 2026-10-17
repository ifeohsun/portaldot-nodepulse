"""Build NodePulseRegistry calldata from monitor samples (stdlib only, no signing).

NodePulse never holds keys: this module turns a health sample into the exact ABI-encoded
`register(bytes32,string)` / `report(bytes32,uint64,uint32,uint16)` calldata, which an
operator pastes into their own wallet / Remix "transact" (or pipes to a signer of choice).
Includes a small pure-Python Keccak-256 because hashlib's sha3_256 uses different padding.
"""
import argparse, json

_RC = [0x0000000000000001, 0x0000000000008082, 0x800000000000808A, 0x8000000080008000,
       0x000000000000808B, 0x0000000080000001, 0x8000000080008081, 0x8000000000008009,
       0x000000000000008A, 0x0000000000000088, 0x0000000080008009, 0x000000008000000A,
       0x000000008000808B, 0x800000000000008B, 0x8000000000008089, 0x8000000000008003,
       0x8000000000008002, 0x8000000000000080, 0x000000000000800A, 0x800000008000000A,
       0x8000000080008081, 0x8000000000008080, 0x0000000080000001, 0x8000000080008008]
_ROT = [[0, 36, 3, 41, 18], [1, 44, 10, 45, 2], [62, 6, 43, 15, 61],
        [28, 55, 25, 21, 56], [27, 20, 39, 8, 14]]
_M = (1 << 64) - 1

def _rol(v, n):
    return ((v << n) | (v >> (64 - n))) & _M if n else v

def _f(A):
    for rc in _RC:
        C = [A[x][0] ^ A[x][1] ^ A[x][2] ^ A[x][3] ^ A[x][4] for x in range(5)]
        D = [C[(x - 1) % 5] ^ _rol(C[(x + 1) % 5], 1) for x in range(5)]
        A = [[A[x][y] ^ D[x] for y in range(5)] for x in range(5)]
        B = [[0] * 5 for _ in range(5)]
        for x in range(5):
            for y in range(5):
                B[y][(2 * x + 3 * y) % 5] = _rol(A[x][y], _ROT[x][y])
        A = [[B[x][y] ^ (~B[(x + 1) % 5][y] & B[(x + 2) % 5][y]) for y in range(5)] for x in range(5)]
        A[0][0] ^= rc
    return A

def keccak256(data: bytes) -> bytes:
    rate = 136
    msg = bytearray(data) + b"\x01"
    msg += b"\x00" * (-len(msg) % rate)
    msg[-1] |= 0x80
    A = [[0] * 5 for _ in range(5)]
    for off in range(0, len(msg), rate):
        block = msg[off:off + rate]
        for i in range(rate // 8):
            x, y = i % 5, i // 5
            A[x][y] ^= int.from_bytes(block[8 * i:8 * i + 8], "little")
        A = _f(A)
    out = b"".join(A[i % 5][i // 5].to_bytes(8, "little") for i in range(4))
    return out

def selector(signature: str) -> bytes:
    return keccak256(signature.encode())[:4]

def node_id(label: str) -> bytes:
    """Stable bytes32 id for a node: keccak256 of its URL/label."""
    return keccak256(label.encode())

def _uint(v, bits):
    if not 0 <= v < (1 << bits):
        raise ValueError(f"value {v} does not fit uint{bits}")
    return v.to_bytes(32, "big")

def encode_register(nid: bytes, label: str) -> str:
    raw = label.encode()
    body = nid + _uint(64, 256) + _uint(len(raw), 256) + raw + b"\x00" * (-len(raw) % 32)
    return "0x" + (selector("register(bytes32,string)") + body).hex()

def encode_report(nid: bytes, height: int, peers: int, score: int) -> str:
    if score > 100:
        raise ValueError("score must be <= 100 (contract reverts otherwise)")
    body = nid + _uint(height, 64) + _uint(peers, 32) + _uint(score, 16)
    return "0x" + (selector("report(bytes32,uint64,uint32,uint16)") + body).hex()

def from_sample(sample: dict) -> dict:
    """Calldata for one monitor sample; errored samples are reported with score 0."""
    nid = node_id(sample["url"])
    return {"url": sample["url"], "node_id": "0x" + nid.hex(),
            "calldata": encode_report(nid, sample.get("best", 0), sample.get("peers", 0),
                                      0 if "error" in sample else sample.get("score", 0))}

def main(argv=None):
    p = argparse.ArgumentParser(description="Encode NodePulseRegistry calldata (no keys, no signing)")
    sub = p.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("register"); r.add_argument("url"); r.add_argument("--label")
    s = sub.add_parser("samples", help="read monitor JSON (list of samples) from a file")
    s.add_argument("file")
    a = p.parse_args(argv)
    if a.cmd == "register":
        nid = node_id(a.url)
        print(json.dumps({"node_id": "0x" + nid.hex(),
                          "calldata": encode_register(nid, a.label or a.url)}, indent=2))
    else:
        with open(a.file, encoding="utf-8") as f:
            print(json.dumps([from_sample(x) for x in json.load(f)], indent=2))

if __name__ == "__main__":
    main()
