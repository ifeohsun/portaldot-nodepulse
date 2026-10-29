"""History retention for NodePulse: keep recent raw samples, roll older ones into hourly buckets.

An always-on `watch` writes one line per node per interval, so a 60 s poll of 5 nodes is
~2.6 M lines a year. `compact` keeps the last `keep_hours` of raw samples untouched and
replaces older samples with one rollup record per (node, bucket):

    {"url", "ts" (bucket start), "rollup": true, "samples", "up", "errors",
     "score" (mean), "min_score", "max_best"}

Rollups stay compatible with `history.load` and carry enough to recompute uptime.
The rewrite is atomic (temp file + os.replace), so a crash never loses the history file.
Stdlib only."""
import argparse, json, os, tempfile, time
from . import history

def rollup(records, bucket=3600, threshold=60):
    """Aggregate raw (or already-rolled-up) records into per-node, per-bucket rollups."""
    agg = {}
    for r in records:
        key = (r["url"], int(r.get("ts", 0)) // bucket * bucket)
        a = agg.setdefault(key, {"samples": 0, "up": 0, "errors": 0, "score_sum": 0.0,
                                 "min_score": None, "max_best": None})
        if r.get("rollup"):
            n, up, err = r["samples"], r["up"], r["errors"]
            ssum, mn, best = r["score"] * n, r["min_score"], r.get("max_best")
        else:
            sc = r.get("score", 0)
            n, err = 1, 1 if "error" in r else 0
            up = 1 if (not err and sc >= threshold) else 0
            ssum, mn, best = sc, sc, r.get("best")
        a["samples"] += n; a["up"] += up; a["errors"] += err; a["score_sum"] += ssum
        a["min_score"] = mn if a["min_score"] is None else min(a["min_score"], mn)
        if best is not None:
            a["max_best"] = best if a["max_best"] is None else max(a["max_best"], best)
    out = []
    for (url, ts), a in sorted(agg.items(), key=lambda kv: (kv[0][1], kv[0][0])):
        out.append({"url": url, "ts": ts, "rollup": True, "samples": a["samples"], "up": a["up"],
                    "errors": a["errors"], "score": round(a["score_sum"] / a["samples"], 2),
                    "min_score": a["min_score"], "max_best": a["max_best"]})
    return out

def uptime(records, threshold=60):
    """Per-node uptime % over a mix of raw samples and rollups."""
    tot, up = {}, {}
    for r in records:
        if r.get("rollup"):
            n, u = r["samples"], r["up"]
        else:
            n = 1
            u = 1 if ("error" not in r and r.get("score", 0) >= threshold) else 0
        tot[r["url"]] = tot.get(r["url"], 0) + n
        up[r["url"]] = up.get(r["url"], 0) + u
    return {k: round(100.0 * up[k] / tot[k], 2) for k in tot}

def compact(path, keep_hours=24, bucket=3600, threshold=60, drop_days=None, now=None):
    """Rewrite `path` in place. Returns a summary dict."""
    now = int(time.time()) if now is None else now
    recs = history.load(path)
    cutoff = now - int(keep_hours * 3600)
    floor = now - int(drop_days * 86400) if drop_days else None
    old = [r for r in recs if r.get("ts", 0) < cutoff and (floor is None or r.get("ts", 0) >= floor)]
    recent = [r for r in recs if r.get("ts", 0) >= cutoff]
    dropped = len(recs) - len(old) - len(recent)
    rolled = rollup(old, bucket, threshold)
    d = os.path.dirname(os.path.abspath(path))
    fd, tmp = tempfile.mkstemp(dir=d, suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        for r in rolled + recent:
            f.write(json.dumps(r, sort_keys=True) + "\n")
    os.replace(tmp, path)
    return {"before": len(recs), "after": len(rolled) + len(recent), "rolled_from": len(old),
            "rollups": len(rolled), "kept_raw": len(recent), "dropped": dropped}

def main(argv=None):
    p = argparse.ArgumentParser(description="Compact NodePulse history: hourly rollups for old samples")
    p.add_argument("--db", default="nodepulse-history.jsonl")
    p.add_argument("--keep-hours", type=float, default=24, help="raw samples newer than this are kept as-is")
    p.add_argument("--bucket", type=int, default=3600, help="rollup bucket size in seconds")
    p.add_argument("--threshold", type=int, default=60)
    p.add_argument("--drop-days", type=float, help="delete anything older than N days entirely")
    a = p.parse_args(argv)
    print(json.dumps(compact(a.db, a.keep_hours, a.bucket, a.threshold, a.drop_days)))

if __name__ == "__main__":
    main()
