# NodePulse demo (check-in, ≤ 3 min)

Live dashboard (no backend, reads the Portaldot testnet from your browser):
**https://ifeohsun.github.io/portaldot-nodepulse/** (source: `docs/index.html`).
Screenshot: [`docs/dashboard.png`](docs/dashboard.png).

## Core flow shown: monitor → score → on-chain attestation → public read-back

All commands are stdlib Python 3, run from the repo root.

| Step | Command | What it shows |
|---|---|---|
| 1. Sample a node | `python3 -m nodepulse.monitor https://test-evm-rpc-v3.portaldot.dev --kind evm > s.json` | height, peers, sync state, latency → 0–100 score |
| 2. Build calldata | `python3 -m nodepulse.attest samples s.json` | exact `report(bytes32,uint64,uint32,uint16)` calldata; NodePulse holds no keys |
| 3. Operator signs | paste calldata into Remix / wallet, or `cast send --rpc-url https://test-evm-rpc-v3.portaldot.dev --private-key $OPERATOR_KEY --legacy 0xEc531adADF19f263231A32310E9ACb3191B898D2 <calldata>` | `PulseReported` event on Portaldot testnet |
| 4. Verify state | `python3 -m nodepulse.status` | contract code, nodeCount, operator, latest report, receipts (`ok: true`) |
| 5. Event history | `python3 -m nodepulse.events --html snapshot.html` | per-node attestation timeline + uptime stats from `eth_getLogs` |
| 6. Dashboard | open the live dashboard link above | same events, decoded in the browser, auto-refresh every 60 s |

## Live run, 2026-10-21 (Portaldot V3 testnet)

Step 1 sample: `{"url": "https://test-evm-rpc-v3.portaldot.dev", "peers": 2, "is_syncing": false, "best": 128198, "latency_ms": 1957, "score": 75}`
(score 75 = 100 − 15 for < 3 peers − 10 for > 1 s latency).

Step 3 tx: `0xcb6086a3bddb22f187ae00e9d201697b5f5d794e750a7d9255171500d16b1970`
(status 1, block 128200, 06:45:30 UTC, signed by operator burner `0x001F79C06e2f58bd9861e4a8592b90DaCc1a82AB`).

Step 5 output (abridged):
```json
{"label": "https://test-evm-rpc-v3.portaldot.dev",
 "operator": "0x001f79c06e2f58bd9861e4a8592b90dacc1a82ab",
 "reports": [
   {"block": 97202,  "blockHeight": 97196,  "peers": 2, "score": 75, "tx": "0x124b9992…"},
   {"block": 128200, "blockHeight": 128198, "peers": 2, "score": 75, "tx": "0xcb6086a3…", "time": 1792565130}],
 "stats": {"reports": 2, "avg_score": 75.0, "min_score": 75, "latest_score": 75}}
```
`time` is `null` for older blocks because the public eth-rpc has pruned their state
("State already discarded"); NodePulse tolerates that and still shows the report.

## Video script (captions-only, ~2 min)
1. (0:00) Title: "NodePulse — verifiable node health for Portaldot". Show architecture diagram in README.
2. (0:15) Terminal: step 1 monitor JSON; caption explains the score.
3. (0:40) Step 2 calldata → step 3 `cast send` → tx hash.
4. (1:05) Step 4 `nodepulse.status` → `"ok": true`.
5. (1:25) Browser: live dashboard, new row appears with the tx link.
6. (1:45) Tests: `python3 -m unittest discover -s tests -t .` → all pass. Roadmap slide.
