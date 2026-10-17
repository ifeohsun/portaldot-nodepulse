# NodePulse — node health monitoring + on-chain attestations for Portaldot

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
```

## Deploy the contract (Portaldot testnet)
1. Get testnet POT from the Portaldot faucet (Discord) into a burner EVM wallet.
2. Open `contracts/NodePulseRegistry.sol` in Remix, compile with 0.8.20+, deploy via
   injected provider pointed at the Portaldot EVM testnet RPC.
3. Record the contract address + tx hash below.

| Item | Value |
|---|---|
| Contract address | _TBD_ |
| Deploy tx hash | _TBD_ |

## Roadmap
- [x] Polling worker with JSONL history + uptime stats (`nodepulse/history.py`)
- [x] ABI calldata for `register()`/`report()` from samples, pure-Python Keccak-256 (`nodepulse/attest.py`; NodePulse never holds keys, operators sign in their own wallet)
- Post `report()` on-chain from the worker every N minutes
- Static dashboard reading `PulseReported` events
- [x] Alerts on degrade/recover transitions (`nodepulse/alerts.py`, Discord-compatible webhook)

Dependencies: Python 3 stdlib only. Code written during the Hacker House (Oct 2026), with AI assistance.
License: MIT
