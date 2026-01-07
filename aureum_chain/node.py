from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import requests
from fastapi import FastAPI, HTTPException

from aureum_chain.chain import Blockchain
from aureum_chain.config import ChainConfig, NodeConfig
from aureum_chain.storage import Storage
from aureum_chain.tx import Transaction, TxInput, TxOutput
from aureum_chain.crypto import pubkey_hash_from_address


@dataclass
class Node:
    chain: Blockchain
    peers: list[str]
    storage: Storage

    def save_state(self) -> None:
        self.chain.save(self.storage.config.chain_path)
        self.storage.save_mempool(self.chain.mempool)
        self.storage.save_peers(self.peers)

    def add_peer(self, peer: str) -> None:
        if peer not in self.peers:
            self.peers.append(peer)

    def sync(self) -> bool:
        best_chain = None
        for peer in self.peers:
            try:
                response = requests.get(f"{peer}/chain", timeout=5)
                response.raise_for_status()
            except Exception:
                continue
            data = response.json()
            blocks = data.get("blocks", [])
            if best_chain is None or len(blocks) > len(best_chain.get("blocks", [])):
                best_chain = data
        if best_chain:
            path = self.storage.config.chain_path
            path.write_text(json.dumps(best_chain, indent=2))
            self.chain = Blockchain.load(path, self.chain.config)
            return True
        return False


def transaction_from_dict(data: dict[str, Any]) -> Transaction:
    inputs = [TxInput(**inp) for inp in data.get("inputs", [])]
    outputs = [TxOutput(**out) for out in data.get("outputs", [])]
    return Transaction(inputs=inputs, outputs=outputs, locktime=data.get("locktime", 0))


def create_app(data_dir: Path | None = None, host: str = "0.0.0.0", port: int = 8332) -> FastAPI:
    if data_dir is None:
        data_dir = Path(os.environ.get("AUREUM_DATA_DIR", str(Path.home() / ".aureum_chain")))
    chain_config = ChainConfig()
    node_config = NodeConfig(data_dir=data_dir, host=host, port=port)
    storage = Storage(node_config)
    chain = Blockchain.load(node_config.chain_path, chain_config)
    chain.mempool = storage.load_mempool()
    peers = storage.load_peers()
    node = Node(chain=chain, peers=peers, storage=storage)

    app = FastAPI(title=chain_config.name)

    @app.on_event("shutdown")
    def _shutdown() -> None:
        node.save_state()

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/status")
    def status() -> dict[str, Any]:
        return {
            "height": node.chain.height(),
            "last_hash": node.chain.last_hash(),
            "mempool": len(node.chain.mempool.transactions),
            "peers": node.peers,
        }

    @app.get("/chain")
    def chain_state() -> dict[str, Any]:
        return node.chain.to_dict()

    @app.get("/block/{height}")
    def block_by_height(height: int) -> dict[str, Any]:
        if height < 0 or height > node.chain.height():
            raise HTTPException(status_code=404, detail="Block not found")
        return node.chain.state.blocks[height].to_dict()

    @app.get("/utxos/{address}")
    def utxos_by_address(address: str) -> dict[str, Any]:
        pubkey_hash = pubkey_hash_from_address(address).hex()
        utxos = {
            key: out.to_dict()
            for key, out in node.chain.state.utxos.items()
            if out.pubkey_hash == pubkey_hash
        }
        return {"utxos": utxos}

    @app.post("/transactions/new")
    def new_transaction(payload: dict[str, Any]) -> dict[str, Any]:
        tx = transaction_from_dict(payload)
        if not node.chain.add_transaction(tx):
            raise HTTPException(status_code=400, detail="Invalid transaction")
        return {"status": "accepted", "txid": tx.txid}

    @app.post("/mine")
    def mine(payload: dict[str, Any]) -> dict[str, Any]:
        address = payload.get("address")
        if not address:
            raise HTTPException(status_code=400, detail="Missing miner address")
        block = node.chain.mine_block(address)
        return {"status": "mined", "block": block.to_dict()}

    @app.get("/peers")
    def list_peers() -> dict[str, Any]:
        return {"peers": node.peers}

    @app.post("/peers/add")
    def add_peers(payload: dict[str, Any]) -> dict[str, Any]:
        peers = payload.get("peers", [])
        for peer in peers:
            node.add_peer(peer)
        return {"status": "ok", "peers": node.peers}

    @app.post("/sync")
    def sync_chain() -> dict[str, Any]:
        synced = node.sync()
        return {"synced": synced, "height": node.chain.height()}

    return app
