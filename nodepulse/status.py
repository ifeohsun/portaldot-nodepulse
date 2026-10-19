"""Verify NodePulseRegistry deployment and on-chain register/report state (stdlib only).

Queries Portaldot EVM JSON-RPC for contract code, nodeCount, operatorOf, and latest
report for known nodes. Never holds keys — read-only eth_call / eth_getCode /
eth_getTransactionReceipt. Explorer URL helpers included for DoraHacks check-in.
"""
import argparse, json, urllib.request
from . import attest

DEFAULT_RPC = "https://test-evm-rpc-v3.portaldot.dev"
DEFAULT_CONTRACT = "0xEc531adADF19f263231A32310E9ACb3191B898D2"
DEFAULT_EXPLORER = "https://node-console.portaldot.dev"
# First live node registered on 2026-10-19
DEFAULT_LABEL = "https://test-evm-rpc-v3.portaldot.dev"

USER_AGENT = "nodepulse/0.1"


class RpcError(RuntimeError):
    pass


def rpc(url, method, params=None, timeout=15, opener=None):
    """JSON-RPC helper with User-Agent (Portaldot Cloudflare rejects bare urllib)."""
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params or []}).encode()
    req = urllib.request.Request(url, body, {"Content-Type": "application/json", "User-Agent": USER_AGENT})
    open_fn = opener or urllib.request.urlopen
    with open_fn(req, timeout=timeout) as r:
        out = json.loads(r.read())
    if "error" in out:
        raise RpcError(out["error"])
    return out["result"]


def explorer_address(addr, base=DEFAULT_EXPLORER):
    return f"{base.rstrip('/')}/address/{addr}"


def explorer_tx(tx_hash, base=DEFAULT_EXPLORER):
    return f"{base.rstrip('/')}/tx/{tx_hash}"


def _pad32(b: bytes) -> bytes:
    if len(b) > 32:
        raise ValueError("ABI word longer than 32 bytes")
    return b.rjust(32, b"\x00")


def encode_call(signature: str, *args_bytes: bytes) -> str:
    """ABI-encode a view call: selector + 32-byte words (caller supplies already-encoded words)."""
    return "0x" + (attest.selector(signature) + b"".join(_pad32(a) for a in args_bytes)).hex()


def eth_call(rpc_url, to, data, opener=None):
    return rpc(rpc_url, "eth_call", [{"to": to, "data": data}, "latest"], opener=opener)


def decode_uint(hexdata: str) -> int:
    raw = hexdata[2:] if hexdata.startswith("0x") else hexdata
    return int(raw or "0", 16)


def decode_address(hexdata: str) -> str:
    raw = hexdata[2:] if hexdata.startswith("0x") else hexdata
    return "0x" + raw[-40:].lower()


def decode_report(hexdata: str) -> dict:
    """Decode Report(uint64,uint32,uint16,uint64,address) from eth_call result."""
    raw = bytes.fromhex((hexdata[2:] if hexdata.startswith("0x") else hexdata).ljust(5 * 64, "0"))
    if len(raw) < 5 * 32:
        raise ValueError("report returndata too short")
    words = [raw[i:i + 32] for i in range(0, 5 * 32, 32)]
    return {
        "blockHeight": int.from_bytes(words[0], "big"),
        "peers": int.from_bytes(words[1], "big"),
        "score": int.from_bytes(words[2], "big"),
        "timestamp": int.from_bytes(words[3], "big"),
        "reporter": "0x" + words[4][-20:].hex(),
    }


def check_code(rpc_url, contract, opener=None) -> dict:
    code = rpc(rpc_url, "eth_getCode", [contract, "latest"], opener=opener) or "0x"
    deployed = code not in ("0x", "0x0", "")
    return {"contract": contract, "has_code": deployed, "code_bytes": max(0, (len(code) - 2) // 2)}


def check_node(rpc_url, contract, label, opener=None) -> dict:
    nid = attest.node_id(label)
    nid_hex = "0x" + nid.hex()
    op_data = encode_call("operatorOf(bytes32)", nid)
    latest_data = encode_call("latest(bytes32)", nid)
    operator = decode_address(eth_call(rpc_url, contract, op_data, opener=opener))
    report = decode_report(eth_call(rpc_url, contract, latest_data, opener=opener))
    registered = operator != "0x" + "0" * 40
    return {
        "label": label,
        "node_id": nid_hex,
        "operator": operator,
        "registered": registered,
        "latest": report,
        "has_report": registered and report["timestamp"] > 0,
    }


def check_count(rpc_url, contract, opener=None) -> int:
    data = encode_call("nodeCount()")
    return decode_uint(eth_call(rpc_url, contract, data, opener=opener))


def list_nodes(rpc_url, contract, opener=None) -> list:
    """Return all registered nodeIds via nodes(i) for i in range(nodeCount)."""
    n = check_count(rpc_url, contract, opener=opener)
    out = []
    for i in range(n):
        data = encode_call("nodes(uint256)", i.to_bytes(32, "big"))
        raw = eth_call(rpc_url, contract, data, opener=opener)
        out.append("0x" + bytes.fromhex(raw[2:].rjust(64, "0")).hex())
    return out


def check_receipt(rpc_url, tx_hash, opener=None, explorer_base=DEFAULT_EXPLORER) -> dict:
    rcpt = rpc(rpc_url, "eth_getTransactionReceipt", [tx_hash], opener=opener)
    if not rcpt:
        return {"tx": tx_hash, "found": False, "explorer": explorer_tx(tx_hash, explorer_base)}
    status = rcpt.get("status", "0x0")
    return {
        "tx": tx_hash,
        "found": True,
        "ok": status in ("0x1", "0x01", 1, "1"),
        "block": int(rcpt.get("blockNumber", "0x0"), 16),
        "contractAddress": rcpt.get("contractAddress"),
        "explorer": explorer_tx(tx_hash, explorer_base),
    }


def verify(rpc_url=DEFAULT_RPC, contract=DEFAULT_CONTRACT, label=DEFAULT_LABEL,
           deploy_tx=None, register_tx=None, report_tx=None, explorer_base=DEFAULT_EXPLORER,
           opener=None) -> dict:
    """Full deployment health snapshot used by CLI and tests."""
    nodes = list_nodes(rpc_url, contract, opener=opener)
    out = {
        "rpc": rpc_url,
        "contract": contract,
        "explorer_contract": explorer_address(contract, explorer_base),
        "code": check_code(rpc_url, contract, opener=opener),
        "node_count": len(nodes),
        "nodes": nodes,
        "node": check_node(rpc_url, contract, label, opener=opener),
        "receipts": {},
    }
    for name, tx in (("deploy", deploy_tx), ("register", register_tx), ("report", report_tx)):
        if tx:
            out["receipts"][name] = check_receipt(
                rpc_url, tx, opener=opener, explorer_base=explorer_base
            )
    out["ok"] = (
        out["code"]["has_code"]
        and out["node"]["registered"]
        and out["node"]["has_report"]
        and out["node_count"] >= 1
    )
    return out


def main(argv=None):
    p = argparse.ArgumentParser(description="Verify NodePulseRegistry on-chain state (read-only)")
    p.add_argument("--rpc", default=DEFAULT_RPC)
    p.add_argument("--contract", default=DEFAULT_CONTRACT)
    p.add_argument("--label", default=DEFAULT_LABEL)
    p.add_argument("--deploy-tx", default="0x952dc3d097c46555e67067ea13232488bc38182862469a2d79fa3ab2ec16708b")
    p.add_argument("--register-tx", default="0x397257e3dfe3a174ec11f6845a98bb7206c4569c674d2af9227f9211bc028c57")
    p.add_argument("--report-tx", default="0x124b9992fdda1c384b841e5dda65fc015bfe58fbefd6c090d05b1c9dc2e664fd")
    p.add_argument("--explorer", default=DEFAULT_EXPLORER)
    a = p.parse_args(argv)
    result = verify(
        rpc_url=a.rpc, contract=a.contract, label=a.label,
        deploy_tx=a.deploy_tx, register_tx=a.register_tx, report_tx=a.report_tx,
        explorer_base=a.explorer,
    )
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result["ok"] else 1)


if __name__ == "__main__":
    main()
