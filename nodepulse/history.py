"""Rolling sample history + uptime stats for NodePulse, plus a polling `watch` loop.

History is an append-only JSONL file (one sample per line, with a unix `ts`), so it can be
tailed, rotated or shipped to a dashboard without a database. Stdlib only.
"""
import argparse, json, os, time
from . import monitor, alerts

def append(path, samples, ts=None):
    ts = int(time.time()) if ts is None else ts
    with open(path, "a", encoding="utf-8") as f:
        for s in samples:
            f.write(json.dumps({**s, "ts": ts}, sort_keys=True) + "\n")

def load(path, since=None):
    if not os.path.exists(path):
        return []
    out = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue          # tolerate a torn final line after a crash
            if since is None or rec.get("ts", 0) >= since:
                out.append(rec)
    return out

def stats(records, threshold=60):
    """Per-node uptime %, average/min score and last-seen timestamp."""
    by = {}
    for r in records:
        by.setdefault(r["url"], []).append(r)
    res = {}
    for url, rs in by.items():
        scores = [r.get("score", 0) for r in rs]
        up = sum(1 for r in rs if "error" not in r and r.get("score", 0) >= threshold)
        res[url] = {
            "samples": len(rs),
            "uptime_pct": round(100.0 * up / len(rs), 2),
            "avg_score": round(sum(scores) / len(scores), 2),
            "min_score": min(scores),
            "errors": sum(1 for r in rs if "error" in r),
            "last_ts": max(r.get("ts", 0) for r in rs),
        }
    return res

def watch(urls, kind, path, interval, iterations=None, threshold=60, webhook=None,
          sampler=None, sleep=time.sleep, confirm=1, stall_after=None,
          deliver=None, outbox_max=50):
    """Poll nodes every `interval` seconds, persist samples, fire alerts on transitions.

    Alerts the webhook rejected stay in a bounded outbox and are retried next cycle,
    so a short Discord outage doesn't silently drop a degrade/recover notice."""
    sampler = sampler or monitor.run
    deliver = deliver or alerts.deliver
    state, n, outbox = {}, 0, []
    while iterations is None or n < iterations:
        samples = sampler(urls, kind)
        append(path, samples)
        fired, state = alerts.evaluate(samples, state, threshold, confirm, stall_after)
        for a in fired:
            print(json.dumps(a))
        if webhook and (fired or outbox):
            pending = [{k: v for k, v in a.items() if k != "delivery_error"} for a in outbox] + fired
            try:
                failed = deliver(pending, webhook)
            except Exception as e:          # never let a dead webhook stop monitoring
                failed = [dict(a, delivery_error=str(e)) for a in pending]
            for a in failed:
                print(json.dumps({"webhook_error": a["delivery_error"], "url": a["url"]}))
            outbox = failed[-outbox_max:]
        n += 1
        if iterations is None or n < iterations:
            sleep(interval)
    return state

def main(argv=None):
    p = argparse.ArgumentParser(description="NodePulse history: watch nodes or print uptime stats")
    sub = p.add_subparsers(dest="cmd", required=True)
    w = sub.add_parser("watch"); w.add_argument("urls", nargs="+")
    w.add_argument("--kind", choices=["substrate", "evm"], default="substrate")
    w.add_argument("--db", default="nodepulse-history.jsonl")
    w.add_argument("--interval", type=float, default=60)
    w.add_argument("--iterations", type=int)
    w.add_argument("--threshold", type=int, default=60)
    w.add_argument("--webhook")
    w.add_argument("--confirm", type=int, default=1, help="consecutive samples before alerting (flap suppression)")
    w.add_argument("--stall-after", type=int, help="alert when best height hasn't advanced for N samples")
    st = sub.add_parser("stats"); st.add_argument("--db", default="nodepulse-history.jsonl")
    st.add_argument("--hours", type=float, help="only the last N hours")
    a = p.parse_args(argv)
    if a.cmd == "watch":
        watch(a.urls, a.kind, a.db, a.interval, a.iterations, a.threshold, a.webhook,
              confirm=a.confirm, stall_after=a.stall_after)
    else:
        since = int(time.time() - a.hours * 3600) if a.hours else None
        print(json.dumps(stats(load(a.db, since)), indent=2))

if __name__ == "__main__":
    main()
