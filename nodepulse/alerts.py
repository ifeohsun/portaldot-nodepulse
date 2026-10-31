"""Threshold alerts for NodePulse samples: emits alerts when a node degrades or recovers.

Two production-grade guards on top of the plain score threshold:
  * flap suppression (`confirm=N`): a status change is only alerted after N consecutive
    samples agree, so one slow RPC response doesn't page anyone;
  * stall detection (`stall_after=N`): a node that answers RPC with peers but whose best
    block height hasn't advanced for N samples is treated as degraded ("height stuck"),
    the classic failure mode health scores miss.
Optional webhook delivery (Discord/Slack-compatible JSON {"content": ...})."""
import json, urllib.request

def _node(prev):
    if isinstance(prev, dict):
        return dict(prev)
    return {"status": prev or "ok", "pending": None, "streak": 0, "best": None, "stalled": 0}

def evaluate(samples, prev_state=None, threshold=60, confirm=1, stall_after=None):
    """Return (alerts, new_state). Alerts fire only on confirmed transitions.

    State maps url -> dict(status, pending, streak, best, stalled); legacy 'ok'/'degraded'
    string states are accepted."""
    prev_state = dict(prev_state or {})
    alerts, state = [], {}
    for s in samples:
        url = s["url"]
        n = _node(prev_state.get(url))
        best = s.get("best")
        if "error" not in s and best is not None and n["best"] is not None and best <= n["best"]:
            n["stalled"] += 1
        else:
            n["stalled"] = 0
        if "error" not in s and best is not None:
            n["best"] = best if n["best"] is None else max(best, n["best"])
        stuck = stall_after is not None and n["stalled"] >= stall_after
        observed = "degraded" if (s.get("score", 0) < threshold or stuck) else "ok"
        if observed == n["status"]:
            n["pending"], n["streak"] = None, 0
        else:
            n["streak"] = n["streak"] + 1 if n["pending"] == observed else 1
            n["pending"] = observed
            if n["streak"] >= confirm:
                if stuck and "error" not in s:
                    why = f"height stuck at {n['best']} for {n['stalled']} samples"
                else:
                    why = s.get("error") or f"score={s.get('score')} peers={s.get('peers')} best={best}"
                alerts.append({"url": url, "status": observed, "detail": why})
                n["status"], n["pending"], n["streak"] = observed, None, 0
        state[url] = n
    return alerts, state

def format_alert(a):
    icon = "\U0001F534" if a["status"] == "degraded" else "\U0001F7E2"
    return {"content": f"{icon} NodePulse {a['status']}: {a['url']} ({a['detail']})"}

def deliver(alerts, webhook_url, timeout=10, retries=2, backoff=1.0, opener=None, sleep=None):
    """POST each alert to the webhook with retry + exponential backoff.

    Failures are isolated per alert: one rejected message never blocks the rest.
    Returns the list of alerts that could not be delivered (empty on full success),
    so callers can keep them in an outbox and retry on the next cycle."""
    import time
    opener = opener or urllib.request.urlopen
    sleep = sleep or time.sleep
    failed = []
    for a in alerts:
        body = json.dumps(format_alert(a)).encode()
        for attempt in range(retries + 1):
            try:
                opener(urllib.request.Request(webhook_url, body, {"Content-Type": "application/json"}),
                       timeout=timeout)
                break
            except Exception as e:
                if attempt == retries:
                    failed.append(dict(a, delivery_error=str(e)))
                else:
                    sleep(backoff * (2 ** attempt))
    return failed
