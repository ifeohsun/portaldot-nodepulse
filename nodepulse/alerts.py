"""Threshold alerts for NodePulse samples: emits alerts when a node degrades or recovers.
Optional webhook delivery (Discord/Slack-compatible JSON {"content": ...})."""
import json, urllib.request

def evaluate(samples, prev_state=None, threshold=60):
    """Return (alerts, new_state). State maps url -> 'ok'|'degraded'; alerts only on transitions."""
    prev_state = dict(prev_state or {})
    alerts, state = [], {}
    for s in samples:
        status = "degraded" if s.get("score", 0) < threshold else "ok"
        state[s["url"]] = status
        before = prev_state.get(s["url"], "ok")
        if status != before:
            why = s.get("error") or f"score={s.get('score')} peers={s.get('peers')} best={s.get('best')}"
            alerts.append({"url": s["url"], "status": status, "detail": why})
    return alerts, state

def deliver(alerts, webhook_url, timeout=10):
    for a in alerts:
        icon = "🔴" if a["status"] == "degraded" else "🟢"
        body = json.dumps({"content": f"{icon} NodePulse {a['status']}: {a['url']} ({a['detail']})"}).encode()
        urllib.request.urlopen(urllib.request.Request(webhook_url, body, {"Content-Type": "application/json"}),
                               timeout=timeout)
