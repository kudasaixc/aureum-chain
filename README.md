# Aureum Chain

Aureum Chain is a Python blockchain project inspired by Bitcoin. It ships as a node and CLI, using a UTXO model, proof-of-work, and signed transactions.

## Key features

- UTXO model with ECDSA (SECP256K1) signatures.
- Proof-of-work with configurable difficulty.
- Mempool with fee-based transaction selection.
- HTTP API for transactions, mining, syncing, and peers.
- Local wallet (private key + address) with JSON export.

## Requirements

- Python 3.10+

## Installation

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -e .
```

## Quick start

1. **Initialize the chain**

```bash
aureum-chain --data-dir ~/.aureum_chain init
```

2. **Create a wallet**

```bash
aureum-chain wallet --path ~/.aureum_chain/wallet.json create
```

3. **Start a node**

```bash
aureum-chain --data-dir ~/.aureum_chain node --host 0.0.0.0 --port 8332
```

4. **Mine a block**

```bash
aureum-chain mine <MINER_ADDRESS>
```

5. **Send a transaction**

```bash
aureum-chain tx <RECIPIENT_ADDRESS> <AMOUNT>
```

## Networking

- **Add peers**

```bash
aureum-chain peers http://127.0.0.1:8333 http://127.0.0.1:8334
```

- **Sync**

```bash
aureum-chain sync
```

## HTTP API (excerpt)

- `GET /status` → node status (height, hash, mempool)
- `GET /chain` → full chain
- `POST /transactions/new` → submit a transaction
- `POST /mine` → manual mining
- `POST /sync` → sync with peers

## Deployment

For a simple deployment, run a service or container that launches:

```bash
export AUREUM_DATA_DIR=~/.aureum_chain
uvicorn aureum_chain.node:create_app --factory --host 0.0.0.0 --port 8332 --proxy-headers
```

Mount a persistent volume for `~/.aureum_chain` to keep the chain and mempool.

## Deterministic testnet genesis

Testnet uses a fixed genesis block. If the data directory contains a different genesis block, the node refuses to start to prevent network splits.

The coinbase message is stored in `extra_data` and is part of consensus (it affects the coinbase txid, Merkle root, and genesis hash).

## Consensus notes (coinbase, supply, version bits)

- **Coinbase + height**: each coinbase transaction must include the block height in `extra_data` (deterministic format `height=<N>`), including genesis.
- **Max supply**: total issuance is capped at `MAX_SUPPLY`; coinbase reward is limited by remaining supply.
- **Version bits**: header `version` accepts soft-fork-style signaling flags; unknown bits remain valid.

### Manual checks (acceptance)

1. **Remove two data directories**

```bash
rm -rf ~/.aureum_chain_node1 ~/.aureum_chain_node2
```

2. **Start two nodes with empty data dirs**

```bash
aureum-chain --data-dir ~/.aureum_chain_node1 node --host 0.0.0.0 --port 8332
aureum-chain --data-dir ~/.aureum_chain_node2 node --host 0.0.0.0 --port 8333
```

3. **Compare the genesis hash**

```bash
curl http://127.0.0.1:8332/status
curl http://127.0.0.1:8333/status
```

4. **Mine on node 1 and confirm node 2 accepts it**

```bash
curl -X POST http://127.0.0.1:8332/mine -H "Content-Type: application/json" -d '{"address": "<MINER_ADDRESS>"}'
curl http://127.0.0.1:8333/status
```

5. **Start a node with an old data directory**

If the genesis does not match testnet, startup must fail with a clear network mismatch message.

## Manual test (automatic propagation)

1. **Start two nodes with separate data dirs**

```bash
aureum-chain --data-dir ~/.aureum_chain_node1 node --host 0.0.0.0 --port 8332
aureum-chain --data-dir ~/.aureum_chain_node2 node --host 0.0.0.0 --port 8333
```

2. **Add peers**

```bash
curl -X POST http://127.0.0.1:8332/peers/add -H "Content-Type: application/json" -d '{"peers": ["http://127.0.0.1:8333"]}'
curl -X POST http://127.0.0.1:8333/peers/add -H "Content-Type: application/json" -d '{"peers": ["http://127.0.0.1:8332"]}'
```

3. **Submit a transaction and verify propagation**

```bash
curl -X POST http://127.0.0.1:8332/transactions/new -H "Content-Type: application/json" -d '<TX_JSON>'
curl http://127.0.0.1:8333/status
```

4. **Mine on node 1 and verify block propagation**

```bash
curl -X POST http://127.0.0.1:8332/mine -H "Content-Type: application/json" -d '{"address": "<MINER_ADDRESS>"}'
curl http://127.0.0.1:8333/status
```
