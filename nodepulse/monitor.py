"""NodePulse: health monitor for Portaldot (Substrate + EVM) nodes. Stdlib only."""
import json, sys, time, urllib.request, argparse

def rpc(url, method, params=None, timeout=10):
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params or []}).encode()
    req = urllib.request.Request(url, body, {"Content-Type": "application/json", "User-Agent": "nodepulse/0.1"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        out = json.loads(r.read())
    if "error" in out:
        raise RuntimeError(out["error"])
    return out["result"]

def score(sample, reference_height=None):
    """Compute a 0-100 health score from a sample dict."""
    s = 100
    if sample.get("is_syncing"):
        s -= 30
    peers = sample.get("peers", 0)
    if peers == 0:
        s -= 40
    elif peers < 3:
        s -= 15
    if reference_height is not None:
        lag = max(0, reference_height - sample.get("best", 0))
        s -= min(30, lag)          # 1 point per block behind, capped
    lat = sample.get("latency_ms", 0)
    if lat > 1000:
        s -= 10
    return max(0, min(100, s))

def sample_substrate(url):
    t0 = time.time()
    health = rpc(url, "system_health")
    header = rpc(url, "chain_getHeader")
    return {
        "url": url,
        "peers": health.get("peers", 0),
        "is_syncing": health.get("isSyncing", False),
        "best": int(header["number"], 16),
        "latency_ms": int((time.time() - t0) * 1000),
    }

def sample_evm(url):
    t0 = time.time()
    best = int(rpc(url, "eth_blockNumber"), 16)
    peers = int(rpc(url, "net_peerCount"), 16)
    syncing = rpc(url, "eth_syncing")
    return {"url": url, "peers": peers, "is_syncing": bool(syncing), "best": best,
            "latency_ms": int((time.time() - t0) * 1000)}

def run(urls, kind="substrate"):
    fn = sample_substrate if kind == "substrate" else sample_evm
    samples = []
    for u in urls:
        try:
            samples.append(fn(u))
        except Exception as e:
            samples.append({"url": u, "error": str(e), "peers": 0, "best": 0})
    ref = max((s["best"] for s in samples), default=0)
    for s in samples:
        s["score"] = 0 if "error" in s else score(s, ref)
    return samples

def main(argv=None):
    p = argparse.ArgumentParser(description="Portaldot node health monitor")
    p.add_argument("urls", nargs="+")
    p.add_argument("--kind", choices=["substrate", "evm"], default="substrate")
    a = p.parse_args(argv)
    print(json.dumps(run(a.urls, a.kind), indent=2))

if __name__ == "__main__":
    main()
