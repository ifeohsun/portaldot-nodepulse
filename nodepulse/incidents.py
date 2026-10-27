"""Incident + SLA report from NodePulse JSONL history.

Turns the raw sample stream into operator-facing facts: each downtime window (first bad sample
to first good sample after it), its duration and worst score, plus MTTR, MTBF and time-weighted
availability per node, checked against an SLA target. Output is JSON or Markdown, so it can be
pasted into a status page or a weekly ops report. Stdlib only.

    python3 -m nodepulse.incidents --db nodepulse-history.jsonl --hours 168 --sla 99.5 --md
"""
import argparse, json, sys, time
from . import history

def _bad(r, threshold):
    return "error" in r or r.get("score", 0) < threshold

def incidents(records, threshold=60, now=None):
    """Group samples per node and return {url: summary} with a list of incident windows.

    Time between two samples is attributed to the state of the earlier sample. An incident that
    is still open at the last sample is closed at `now` (defaults to the last sample's ts).
    """
    by = {}
    for r in sorted(records, key=lambda r: r.get("ts", 0)):
        by.setdefault(r["url"], []).append(r)
    out = {}
    for url, rs in by.items():
        end = rs[-1]["ts"] if now is None else max(now, rs[-1]["ts"])
        span = max(end - rs[0]["ts"], 0)
        evs, cur, down = [], None, 0
        for i, r in enumerate(rs):
            nxt = rs[i + 1]["ts"] if i + 1 < len(rs) else end
            if _bad(r, threshold):
                down += nxt - r["ts"]
                if cur is None:
                    cur = {"start": r["ts"], "worst_score": r.get("score", 0), "errors": 0, "samples": 0}
                cur["worst_score"] = min(cur["worst_score"], r.get("score", 0))
                cur["errors"] += "error" in r
                cur["samples"] += 1
                if "error" in r:
                    cur.setdefault("first_error", r["error"])
            elif cur is not None:
                cur["end"] = r["ts"]; cur["duration_s"] = r["ts"] - cur["start"]; evs.append(cur); cur = None
        if cur is not None:
            cur["end"] = None; cur["duration_s"] = end - cur["start"]; cur["open"] = True; evs.append(cur)
        closed = [e for e in evs if not e.get("open")]
        avail = 100.0 if span == 0 else round(100.0 * (span - down) / span, 3)
        out[url] = {
            "from": rs[0]["ts"], "to": end, "samples": len(rs),
            "availability_pct": avail, "downtime_s": down, "incidents": evs,
            "mttr_s": round(sum(e["duration_s"] for e in closed) / len(closed), 1) if closed else None,
            "mtbf_s": round((span - down) / len(evs), 1) if evs else None,
        }
    return out

def check_sla(report, target):
    """Annotate each node with sla_target/sla_met and the downtime budget left in its window."""
    for v in report.values():
        span = v["to"] - v["from"]
        budget = span * (100.0 - target) / 100.0
        v.update(sla_target=target, sla_met=v["availability_pct"] >= target,
                 budget_left_s=round(budget - v["downtime_s"], 1))
    return report

def _dur(s):
    if s is None:
        return "-"
    s = int(s); h, m = divmod(s // 60, 60)
    return f"{h}h{m:02d}m" if h else f"{m}m{s % 60:02d}s"

def _t(ts):
    return "ongoing" if ts is None else time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime(ts))

def to_markdown(report):
    lines = ["# NodePulse incident report", ""]
    for url, v in report.items():
        sla = ""
        if "sla_target" in v:
            sla = f" · SLA {v['sla_target']}% {'met' if v['sla_met'] else 'MISSED'} (budget left {_dur(max(v['budget_left_s'], 0))})"
        lines += [f"## {url}", "",
                  f"Window {_t(v['from'])} → {_t(v['to'])} · availability **{v['availability_pct']}%** · "
                  f"{len(v['incidents'])} incident(s) · MTTR {_dur(v['mttr_s'])} · MTBF {_dur(v['mtbf_s'])}{sla}", ""]
        if v["incidents"]:
            lines += ["| start | end | duration | worst score | errors |", "|---|---|---|---|---|"]
            for e in v["incidents"]:
                lines.append(f"| {_t(e['start'])} | {_t(e['end'])} | {_dur(e['duration_s'])} | {e['worst_score']} | {e['errors']} |")
            lines.append("")
    return "\n".join(lines)

def main(argv=None):
    p = argparse.ArgumentParser(description="NodePulse incident / SLA report from history JSONL")
    p.add_argument("--db", default="nodepulse-history.jsonl")
    p.add_argument("--hours", type=float, help="only the last N hours")
    p.add_argument("--threshold", type=int, default=60)
    p.add_argument("--sla", type=float, help="availability target in percent, e.g. 99.5")
    p.add_argument("--md", action="store_true", help="Markdown instead of JSON")
    a = p.parse_args(argv)
    since = int(time.time() - a.hours * 3600) if a.hours else None
    rep = incidents(history.load(a.db, since=since), a.threshold)
    if a.sla is not None:
        check_sla(rep, a.sla)
    print(to_markdown(rep) if a.md else json.dumps(rep, indent=2))
    return 1 if a.sla is not None and not all(v["sla_met"] for v in rep.values()) else 0

if __name__ == "__main__":
    sys.exit(main())
