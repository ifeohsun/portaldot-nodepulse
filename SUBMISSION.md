Project: NodePulse
One-liner: Health monitoring for Portaldot nodes with verifiable on-chain uptime attestations.
Track: Node Operations & Tooling
Repo: https://github.com/ifeohsun/portaldot-nodepulse

## Check-in (due 2026-10-24 12:00 UTC)

Current progress:
- Substrate + EVM JSON-RPC node monitor with 0–100 health score (peers, sync, block lag, latency).
- JSONL history, uptime stats, polling watch loop, degrade/recover alerts to Discord-compatible webhooks.
- NodePulseRegistry (Solidity) deployed on Portaldot V3 testnet; keyless ABI calldata builder for register()/report().
- On-chain verifier (nodepulse.status) and event timeline (nodepulse.events, eth_getLogs).
- Live, backend-free dashboard reading PulseReported events from the testnet RPC in the browser.
- Prometheus /metrics exporter (nodepulse.exporter) so operators can scrape NodePulse into Grafana.
- 33 unit tests (fake RPC, no network), all passing.
- Incident / SLA report (`nodepulse.incidents`): downtime windows, MTTR/MTBF, availability vs. SLA target and error budget, Markdown for status pages.

Outstanding:
- Worker that signs and posts report() every N minutes via an operator-held key/remote signer.
- Multi-node registry demo (several community RPC/validator nodes), score history charts.
- Substrate-side metrics (validator/session info) and network-security checks.

Testnet deployment:
- Contract: 0xEc531adADF19f263231A32310E9ACb3191B898D2 (Portaldot V3 testnet, EVM chain id 420420777)
- Deploy tx: 0x952dc3d097c46555e67067ea13232488bc38182862469a2d79fa3ab2ec16708b
- register() tx: 0x397257e3dfe3a174ec11f6845a98bb7206c4569c674d2af9227f9211bc028c57
- report() txs: 0x124b9992fdda1c384b841e5dda65fc015bfe58fbefd6c090d05b1c9dc2e664fd, 0xcb6086a3bddb22f187ae00e9d201697b5f5d794e750a7d9255171500d16b1970
- Explorer: https://node-console.portaldot.dev

Demo video: https://ifeohsun.github.io/portaldot-nodepulse/demo.mp4 (also https://github.com/ifeohsun/portaldot-nodepulse/raw/main/docs/demo.mp4)
Pitch deck: https://ifeohsun.github.io/portaldot-nodepulse/deck.html (PDF: https://ifeohsun.github.io/portaldot-nodepulse/deck.pdf)

Demo: live dashboard https://ifeohsun.github.io/portaldot-nodepulse/ (walkthrough in DEMO.md).
