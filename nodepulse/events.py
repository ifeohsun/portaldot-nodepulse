"""Read NodePulseRegistry event history (NodeRegistered / PulseReported) via eth_getLogs.

Read-only and stdlib only. Builds a per-node timeline of on-chain health attestations and can
render a self-contained static HTML snapshot (the live dashboard lives in docs/index.html and
does the same decoding in the browser against the CORS-enabled Portaldot EVM RPC).

    python3 -m nodepulse.events                    # JSON timeline from the deployed registry
    python3 -m nodepulse.events --html snap.html   # static HTML snapshot
"""
import argparse, html, json, time
from . import attest, status

DEPLOY_BLOCK = 97193  # NodePulseRegistry deploy block on Portaldot V3 testnet
TOPIC_REGISTERED = "0x" + attest.keccak256(b"NodeRegistered(bytes32,address,string)").hex()
TOPIC_PULSE = "0x" + attest.keccak256(b"PulseReported(bytes32,uint64,uint32,uint16)").hex()


def _hex(s: str) -> bytes:
    return bytes.fromhex(s[2:] if s.startswith("0x") else s)


def decode_log(log: dict):
    """Decode one raw log into a dict, or None for unknown topics."""
    topics = [t.lower() for t in log.get("topics", [])]
    if not topics:
        return None
    base = {
        "tx": log.get("transactionHash"),
        "block": int(log.get("blockNumber", "0x0"), 16),
        "node_id": topics[1] if len(topics) > 1 else None,
    }
    data = _hex(log.get("data", "0x"))
    if topics[0] == TOPIC_PULSE:
        if len(data) < 96:
            raise ValueError("PulseReported data too short")
        w = [int.from_bytes(data[i:i + 32], "big") for i in (0, 32, 64)]
        return dict(base, event="PulseReported", blockHeight=w[0], peers=w[1], score=w[2])
    if topics[0] == TOPIC_REGISTERED:
        off = int.from_bytes(data[0:32], "big")
        ln = int.from_bytes(data[off:off + 32], "big")
        label = data[off + 32:off + 32 + ln].decode("utf-8", "replace")
        operator = "0x" + topics[2][-40:] if len(topics) > 2 else None
        return dict(base, event="NodeRegistered", operator=operator, label=label)
    return None


def fetch_logs(rpc_url, contract, from_block=DEPLOY_BLOCK, to_block="latest", opener=None):
    flt = {"address": contract, "fromBlock": hex(from_block), "toBlock": to_block,
           "topics": [[TOPIC_REGISTERED, TOPIC_PULSE]]}
    return status.rpc(rpc_url, "eth_getLogs", [flt], opener=opener) or []


def block_time(rpc_url, block, opener=None):
    """Block timestamp, or None when the node has pruned that block's state (pallet-revive
    eth-rpc returns "State already discarded" for old blocks on the public testnet RPC)."""
    try:
        b = status.rpc(rpc_url, "eth_getBlockByNumber", [hex(block), False], opener=opener)
    except status.RpcError:
        return None
    return int(b["timestamp"], 16) if b else None


def timeline(logs, times=None) -> dict:
    """Group decoded events per node: label/operator, reports (oldest first), stats."""
    nodes = {}
    for ev in sorted(filter(None, map(decode_log, logs)), key=lambda e: e["block"]):
        n = nodes.setdefault(ev["node_id"], {"node_id": ev["node_id"], "label": None,
                                             "operator": None, "registered_tx": None,
                                             "reports": []})
        if times and ev["block"] in times:
            ev["time"] = times[ev["block"]]
        if ev["event"] == "NodeRegistered":
            n.update(label=ev["label"], operator=ev["operator"], registered_tx=ev["tx"])
        else:
            n["reports"].append({k: ev.get(k) for k in
                                 ("block", "blockHeight", "peers", "score", "tx", "time")})
    for n in nodes.values():
        sc = [r["score"] for r in n["reports"]]
        n["stats"] = {"reports": len(sc), "avg_score": round(sum(sc) / len(sc), 1) if sc else None,
                      "min_score": min(sc) if sc else None,
                      "latest_score": sc[-1] if sc else None}
    return {"nodes": list(nodes.values())}


def collect(rpc_url=status.DEFAULT_RPC, contract=status.DEFAULT_CONTRACT,
            from_block=DEPLOY_BLOCK, with_times=True, opener=None) -> dict:
    logs = fetch_logs(rpc_url, contract, from_block, opener=opener)
    times = {}
    if with_times:
        for blk in sorted({int(l["blockNumber"], 16) for l in logs}):
            times[blk] = block_time(rpc_url, blk, opener=opener)
    out = timeline(logs, times)
    out.update(rpc=rpc_url, contract=contract, from_block=from_block)
    return out


def _fmt_time(ts):
    return time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime(ts)) if ts else "-"


def render_html(data: dict, explorer=status.DEFAULT_EXPLORER) -> str:
    e = html.escape
    rows = []
    for n in data["nodes"]:
        for r in reversed(n["reports"]):
            rows.append(
                f"<tr><td>{e(n['label'] or n['node_id'])}</td><td>{_fmt_time(r.get('time'))}</td>"
                f"<td>{r['blockHeight']}</td><td>{r['peers']}</td><td class=s>{r['score']}</td>"
                f"<td><a href='{e(status.explorer_tx(r['tx'], explorer))}'>{e(r['tx'][:10])}…</a></td></tr>")
    cards = "".join(
        f"<div class=card><b>{e(n['label'] or n['node_id'])}</b><br>operator {e(n['operator'] or '-')}"
        f"<br>reports {n['stats']['reports']} · latest {n['stats']['latest_score']} · "
        f"avg {n['stats']['avg_score']} · min {n['stats']['min_score']}</div>" for n in data["nodes"])
    return f"""<!doctype html><meta charset=utf-8><title>NodePulse snapshot</title>
<style>body{{font:14px system-ui;margin:2em;max-width:960px}}table{{border-collapse:collapse;width:100%}}
td,th{{border-bottom:1px solid #ddd;padding:4px 8px;text-align:left}}.card{{border:1px solid #ccc;
border-radius:6px;padding:8px;margin:6px 0}}.s{{font-weight:bold}}</style>
<h1>NodePulse — on-chain node health (Portaldot testnet)</h1>
<p>Registry <a href='{e(status.explorer_address(data['contract'], explorer))}'>{e(data['contract'])}</a>
 · RPC {e(data['rpc'])}</p>{cards}
<table><tr><th>Node</th><th>Time</th><th>Height</th><th>Peers</th><th>Score</th><th>Tx</th></tr>
{''.join(rows)}</table>"""


def main(argv=None):
    p = argparse.ArgumentParser(description="NodePulseRegistry event timeline (read-only)")
    p.add_argument("--rpc", default=status.DEFAULT_RPC)
    p.add_argument("--contract", default=status.DEFAULT_CONTRACT)
    p.add_argument("--from-block", type=int, default=DEPLOY_BLOCK)
    p.add_argument("--no-times", action="store_true", help="skip per-block timestamp lookups")
    p.add_argument("--html", help="write a static HTML snapshot to this path")
    a = p.parse_args(argv)
    data = collect(a.rpc, a.contract, a.from_block, with_times=not a.no_times)
    if a.html:
        with open(a.html, "w", encoding="utf-8") as f:
            f.write(render_html(data))
    print(json.dumps(data, indent=2))


if __name__ == "__main__":
    main()
