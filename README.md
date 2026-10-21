# NodePulse — node health monitoring + on-chain attestations for Portaldot

**Live dashboard:** https://ifeohsun.github.io/portaldot-nodepulse/ · **Demo walkthrough:** [DEMO.md](DEMO.md)

Track: **Node Operations & Tooling** (Portaldot Hacker House 2026)

NodePulse polls Portaldot nodes over both the Substrate JSON-RPC and the EVM JSON-RPC
(Portaldot V3.0 runs WASM + EVM), computes a 0–100 health score (peers, sync state,
block lag vs. the best node, latency) and lets operators publish compact attestations to
the `NodePulseRegistry` Solidity contract on the Portaldot testnet so anyone can audit node
uptime on-chain.

## Architecture
```
 [Portaldot nodes] --system_health / chain_getHeader / eth_blockNumber--> [nodepulse.monitor]
                                                                               | score()
                                                                               v
                                         NodePulseRegistry.report(nodeId, height, peers, score)
                                                                               |
                                                     [dashboard / explorers read latest + events]
```

## Run
```bash
python3 -m nodepulse.monitor wss-or-https://<portaldot-rpc>  --kind substrate
python3 -m nodepulse.monitor https://<portaldot-evm-rpc>     --kind evm
python3 -m nodepulse.history watch <rpc-url> --kind evm --interval 60 --webhook <discord-webhook>
python3 -m nodepulse.history stats --hours 24   # uptime %, avg/min score per node
python3 -m nodepulse.attest register https://<portaldot-evm-rpc>   # node_id + register() calldata
python3 -m nodepulse.monitor <rpc> --kind evm > s.json && python3 -m nodepulse.attest samples s.json  # report() calldata
python3 -m unittest discover -s tests -t .      # tests use a local fake node, no network
python3 -m nodepulse.status                      # verify live deploy + register/report on-chain
python3 -m nodepulse.events --html snap.html     # on-chain attestation timeline (eth_getLogs) + HTML snapshot
```

## Deploy the contract (Portaldot testnet)
1. Get testnet POT from the Portaldot faucet (Discord) into a burner EVM wallet.
2. Open `contracts/NodePulseRegistry.sol` in Remix, compile with 0.8.20+, deploy via
   injected provider pointed at the Portaldot EVM testnet RPC.
3. Record the contract address + tx hash below.

| Item | Value |
|---|---|
| Network | Portaldot V3 testnet (EVM chain id 420420777, RPC `https://test-evm-rpc-v3.portaldot.dev`) |
| Contract address | `0xEc531adADF19f263231A32310E9ACb3191B898D2` |
| Deploy tx hash | `0x952dc3d097c46555e67067ea13232488bc38182862469a2d79fa3ab2ec16708b` (block 97193) |
| Deployer / operator | `0x001F79C06e2f58bd9861e4a8592b90DaCc1a82AB` (burner) |
| First `register()` | `0x397257e3dfe3a174ec11f6845a98bb7206c4569c674d2af9227f9211bc028c57` (node `https://test-evm-rpc-v3.portaldot.dev`) |
| First `report()` | `0x124b9992fdda1c384b841e5dda65fc015bfe58fbefd6c090d05b1c9dc2e664fd` (height 97196, 2 peers, score 75) |
| Live demo `report()` (2026-10-21) | `0xcb6086a3bddb22f187ae00e9d201697b5f5d794e750a7d9255171500d16b1970` (block 128200, height 128198, 2 peers, score 75) |
| Explorer | https://node-console.portaldot.dev (Portaldot node console) |

Compiled with solc 0.8.24 (optimizer 200 runs, EVM target cancun) and deployed as EVM bytecode
through the testnet's `eth-rpc` (pallet-revive). The register/report calldata came straight from
`nodepulse.attest`, from a live `nodepulse.monitor` sample.

## Roadmap
- [x] Polling worker with JSONL history + uptime stats (`nodepulse/history.py`)
- [x] ABI calldata for `register()`/`report()` from samples, pure-Python Keccak-256 (`nodepulse/attest.py`; NodePulse never holds keys, operators sign in their own wallet)
- [x] On-chain deployment / register / report verifier (`nodepulse/status.py`, explorer links)
- Post `report()` on-chain from the worker every N minutes
- [x] Event timeline + live static dashboard reading `NodeRegistered`/`PulseReported` events (`nodepulse/events.py`, `docs/index.html` on GitHub Pages)
- [x] Alerts on degrade/recover transitions (`nodepulse/alerts.py`, Discord-compatible webhook)

Dependencies: Python 3 stdlib only. Code written during the Hacker House (Oct 2026), with AI assistance.
License: MIT
