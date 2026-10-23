"""Prometheus / OpenMetrics exporter for NodePulse. Stdlib only.

Serves the latest health samples (and, optionally, rolling uptime stats from a history
JSONL file) on `/metrics` in the Prometheus text exposition format, so Portaldot node
operators can scrape NodePulse with an existing Prometheus + Grafana stack.

    python3 -m nodepulse.exporter https://test-evm-rpc-v3.portaldot.dev --kind evm --port 9617
    python3 -m nodepulse.exporter <rpc> --history nodepulse.jsonl --hours 24
"""
import argparse, threading, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from . import monitor, history

def _esc(v):
    return str(v).replace("\\", "\\\\").replace("\n", "\\n").replace('"', '\\"')

def render(samples, stats=None, now=None):
    """Render samples (+ optional history.stats output) as Prometheus text format."""
    now = time.time() if now is None else now
    lines = []
    def metric(name, typ, help_, rows):
        lines.append(f"# HELP {name} {help_}")
        lines.append(f"# TYPE {name} {typ}")
        for labels, val in rows:
            lab = ",".join(f'{k}="{_esc(v)}"' for k, v in labels.items())
            lines.append(f"{name}{{{lab}}} {val}")
    def node(s):
        return {"node": s["url"]}
    metric("nodepulse_up", "gauge", "1 if the last poll of the node succeeded, else 0",
           [(node(s), 0 if "error" in s else 1) for s in samples])
    ok = [s for s in samples if "error" not in s]
    metric("nodepulse_health_score", "gauge", "NodePulse 0-100 health score",
           [(node(s), s.get("score", 0)) for s in samples])
    metric("nodepulse_peers", "gauge", "Connected peer count", [(node(s), s.get("peers", 0)) for s in ok])
    metric("nodepulse_best_block", "gauge", "Best block height", [(node(s), s.get("best", 0)) for s in ok])
    metric("nodepulse_syncing", "gauge", "1 if the node reports it is syncing",
           [(node(s), int(bool(s.get("is_syncing")))) for s in ok])
    metric("nodepulse_rpc_latency_seconds", "gauge", "RPC round-trip latency of the last poll",
           [(node(s), round(s.get("latency_ms", 0) / 1000.0, 3)) for s in ok])
    if stats:
        metric("nodepulse_uptime_ratio", "gauge", "Share of history samples with score >= threshold",
               [({"node": u}, round(v["uptime_pct"] / 100.0, 4)) for u, v in sorted(stats.items())])
        metric("nodepulse_avg_health_score", "gauge", "Average health score over the history window",
               [({"node": u}, v["avg_score"]) for u, v in sorted(stats.items())])
        metric("nodepulse_poll_errors_total", "counter", "Failed polls in the history window",
               [({"node": u}, v["errors"]) for u, v in sorted(stats.items())])
    lines.append("# HELP nodepulse_scrape_timestamp_seconds Unix time of this scrape")
    lines.append("# TYPE nodepulse_scrape_timestamp_seconds gauge")
    lines.append(f"nodepulse_scrape_timestamp_seconds {int(now)}")
    return "\n".join(lines) + "\n"

def make_server(urls, kind="evm", host="127.0.0.1", port=9617, history_path=None, hours=24,
                sampler=None):
    sampler = sampler or monitor.run
    class H(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path.split("?")[0] == "/healthz":
                body, ctype = b"ok\n", "text/plain"
            elif self.path.split("?")[0] == "/metrics":
                samples = sampler(urls, kind)
                st = None
                if history_path:
                    st = history.stats(history.load(history_path, since=time.time() - hours * 3600))
                body = render(samples, st).encode()
                ctype = "text/plain; version=0.0.4; charset=utf-8"
            else:
                self.send_response(404); self.end_headers(); return
            self.send_response(200)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers(); self.wfile.write(body)
        def log_message(self, *a): pass
    return ThreadingHTTPServer((host, port), H)

def main(argv=None):
    p = argparse.ArgumentParser(description="NodePulse Prometheus exporter")
    p.add_argument("urls", nargs="+")
    p.add_argument("--kind", choices=["substrate", "evm"], default="evm")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=9617)
    p.add_argument("--history", help="history JSONL from `nodepulse.history watch` for uptime gauges")
    p.add_argument("--hours", type=float, default=24)
    p.add_argument("--once", action="store_true", help="print one scrape to stdout and exit")
    a = p.parse_args(argv)
    if a.once:
        st = history.stats(history.load(a.history, since=time.time() - a.hours * 3600)) if a.history else None
        print(render(monitor.run(a.urls, a.kind), st), end="")
        return
    srv = make_server(a.urls, a.kind, a.host, a.port, a.history, a.hours)
    print(f"NodePulse exporter on http://{a.host}:{srv.server_port}/metrics")
    srv.serve_forever()

if __name__ == "__main__":
    main()
