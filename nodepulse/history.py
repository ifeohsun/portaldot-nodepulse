"""Rolling sample history + uptime stats for NodePulse, plus a polling `watch` loop.

History is an append-only JSONL file (one sample per line, with a unix `ts`), so it can be
tailed, rotated or shipped to a dashboard without a database. Stdlib only.
"""
import argparse, csv, io, json, math, os, time
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

def percentile(values, q):
    """Nearest-rank percentile (q in 0..100) of a non-empty list; None if empty."""
    if not values:
        return None
    vs = sorted(values)
    k = max(0, min(len(vs) - 1, math.ceil(q / 100.0 * len(vs)) - 1))
    return vs[k]

def block_rate(rs):
    """Blocks produced per minute, from the first/last successful samples' best height.
    Returns None with fewer than two usable samples or zero elapsed time."""
    ok = sorted((r for r in rs if "error" not in r and r.get("best")), key=lambda r: r.get("ts", 0))
    if len(ok) < 2 or ok[-1]["ts"] <= ok[0]["ts"]:
        return None
    return round((ok[-1]["best"] - ok[0]["best"]) * 60.0 / (ok[-1]["ts"] - ok[0]["ts"]), 2)

def stats(records, threshold=60):
    """Per-node uptime %, average/min score, latency p50/p95/p99, block rate and last-seen."""
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
        lats = [r["latency_ms"] for r in rs if "error" not in r and "latency_ms" in r]
        res[url].update({"latency_p50_ms": percentile(lats, 50),
                         "latency_p95_ms": percentile(lats, 95),
                         "latency_p99_ms": percentile(lats, 99),
                         "blocks_per_min": block_rate(rs)})
    return res

STAT_COLS = ["samples", "uptime_pct", "avg_score", "min_score", "errors", "latency_p50_ms",
             "latency_p95_ms", "latency_p99_ms", "blocks_per_min", "last_ts"]

def render_stats(res, fmt="json"):
    """Render the dict from stats() as json, csv (one row per node) or a Markdown table.
    Missing values (e.g. no successful samples -> no latency) become empty cells, not 'None'."""
    if fmt == "json":
        return json.dumps(res, indent=2)
    rows = [[url] + ["" if res[url].get(c) is None else res[url][c] for c in STAT_COLS]
            for url in sorted(res)]
    head = ["node"] + STAT_COLS
    if fmt == "csv":
        buf = io.StringIO()
        w = csv.writer(buf, lineterminator="\n")
        w.writerow(head); w.writerows(rows)
        return buf.getvalue().rstrip("\n")
    if fmt == "md":
        esc = lambda v: str(v).replace("|", "\\|")
        lines = ["| " + " | ".join(head) + " |", "|" + "---|" * len(head)]
        lines += ["| " + " | ".join(esc(v) for v in r) + " |" for r in rows]
        return "\n".join(lines)
    raise ValueError("unknown format: %s" % fmt)

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
    st.add_argument("--format", choices=["json", "csv", "md"], default="json",
                    help="output format (csv/md: one row per node, ready for a spreadsheet or README)")
    a = p.parse_args(argv)
    if a.cmd == "watch":
        watch(a.urls, a.kind, a.db, a.interval, a.iterations, a.threshold, a.webhook,
              confirm=a.confirm, stall_after=a.stall_after)
    else:
        since = int(time.time() - a.hours * 3600) if a.hours else None
        print(render_stats(stats(load(a.db, since)), a.format))

if __name__ == "__main__":
    main()
