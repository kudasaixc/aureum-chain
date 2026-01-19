from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import requests
from fastapi import BackgroundTasks, FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse

from aureum_chain.block import Block, BlockHeader
from aureum_chain.chain import Blockchain
from aureum_chain.config import ChainConfig, NodeConfig
from aureum_chain.storage import Storage
from aureum_chain.tx import Transaction, TxInput, TxOutput
from aureum_chain.crypto import pubkey_hash_from_address
from aureum_chain.ui import render_ui


@dataclass
class Node:
    chain: Blockchain
    peers: list[str]
    storage: Storage
    seen_txs: dict[str, float]
    seen_blocks: dict[str, float]
    orphan_blocks: dict[str, list[Block]]

    def self_urls(self) -> set[str]:
        host = self.storage.config.host
        port = self.storage.config.port
        if host in {"0.0.0.0", "127.0.0.1", "localhost"}:
            return {
                f"http://127.0.0.1:{port}",
                f"http://localhost:{port}",
                f"http://{host}:{port}",
            }
        return {f"http://{host}:{port}"}

    def save_state(self) -> None:
        self.chain.save(self.storage.config.chain_path)
        self.storage.save_mempool(self.chain.mempool)
        self.storage.save_peers(self.peers)

    def add_peer(self, peer: str) -> None:
        normalized = normalize_peer(peer)
        if not normalized:
            return
        if normalized in self.self_urls():
            return
        if normalized not in self.peers:
            self.peers.append(normalized)

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

    def remember_seen_tx(self, txid: str, ttl_seconds: int = 300, max_entries: int = 2000) -> None:
        self._remember_seen(self.seen_txs, txid, ttl_seconds, max_entries)

    def remember_seen_block(self, block_hash: str, ttl_seconds: int = 300, max_entries: int = 2000) -> None:
        self._remember_seen(self.seen_blocks, block_hash, ttl_seconds, max_entries)

    def has_seen_tx(self, txid: str) -> bool:
        return self._has_seen(self.seen_txs, txid)

    def has_seen_block(self, block_hash: str) -> bool:
        return self._has_seen(self.seen_blocks, block_hash)

    def _remember_seen(
        self, cache: dict[str, float], key: str, ttl_seconds: int, max_entries: int
    ) -> None:
        now = time.time()
        cache[key] = now
        self._purge_cache(cache, ttl_seconds)
        if len(cache) > max_entries:
            oldest = sorted(cache.items(), key=lambda item: item[1])[: len(cache) - max_entries]
            for old_key, _ in oldest:
                cache.pop(old_key, None)

    def _has_seen(self, cache: dict[str, float], key: str, ttl_seconds: int = 300) -> bool:
        self._purge_cache(cache, ttl_seconds)
        return key in cache

    @staticmethod
    def _purge_cache(cache: dict[str, float], ttl_seconds: int) -> None:
        now = time.time()
        expired = [key for key, timestamp in cache.items() if now - timestamp > ttl_seconds]
        for key in expired:
            cache.pop(key, None)

    def broadcast_tx(self, tx: Transaction, origin: str | None = None) -> None:
        payload = {"tx": tx.to_dict(), "origin": origin}
        self._broadcast("/transactions/relay", payload, origin=origin, item=tx.txid, label="tx")

    def broadcast_block(self, block: Block, origin: str | None = None) -> None:
        payload = {"block": block.to_dict(), "origin": origin}
        self._broadcast("/blocks/relay", payload, origin=origin, item=block.hash, label="block")

    def _broadcast(self, path: str, payload: dict[str, Any], origin: str | None, item: str, label: str) -> None:
        peers = [normalize_peer(peer) for peer in self.peers]
        peers = [peer for peer in peers if peer]
        skip = set(filter(None, {origin, *self.self_urls()}))
        targets = [peer for peer in peers if peer not in skip]
        if not targets:
            return
        failures = 0
        for peer in targets:
            try:
                requests.post(
                    f"{peer}{path}",
                    json=payload,
                    headers={"X-Aureum-Origin": origin or ""},
                    timeout=3,
                )
            except Exception:
                failures += 1
        print(f"relayed {label} {item} to {len(targets) - failures}/{len(targets)} peers")

    def is_block_known(self, block_hash: str) -> bool:
        return any(block.hash == block_hash for block in self.chain.state.blocks)

    def try_apply_orphans(self) -> list[str]:
        applied = []
        while True:
            candidates = self.orphan_blocks.get(self.chain.last_hash(), [])
            if not candidates:
                break
            candidates.sort(key=lambda blk: blk.height)
            progressed = False
            for block in list(candidates):
                if self.chain.apply_block(block):
                    applied.append(block.hash)
                    candidates.remove(block)
                    progressed = True
            if candidates:
                self.orphan_blocks[self.chain.last_hash()] = candidates
            else:
                self.orphan_blocks.pop(self.chain.last_hash(), None)
            if not progressed:
                break
        return applied


def normalize_peer(peer: str | None) -> str | None:
    if not peer:
        return None
    return peer.rstrip("/")


def transaction_from_dict(data: dict[str, Any]) -> Transaction:
    inputs = [TxInput(**inp) for inp in data.get("inputs", [])]
    outputs = [TxOutput(**out) for out in data.get("outputs", [])]
    tx = Transaction(
        inputs=inputs,
        outputs=outputs,
        locktime=data.get("locktime", 0),
        extra_data=data.get("extra_data"),
    )
    if "txid" in data and data["txid"] != tx.txid:
        raise ValueError("Transaction txid mismatch")
    return tx


def block_from_dict(data: dict[str, Any]) -> Block:
    header_data = data.get("header", {})
    transactions = [transaction_from_dict(tx) for tx in data.get("transactions", [])]
    computed_merkle = Block.create(
        prev_hash=header_data.get("prev_hash", ""),
        height=data.get("height", 0),
        transactions=transactions,
        bits=header_data.get("bits", 0),
        timestamp=header_data.get("timestamp", 0),
        version=header_data.get("version", 1),
    ).header.merkle_root
    provided_merkle = header_data.get("merkle_root")
    if provided_merkle and provided_merkle != computed_merkle:
        raise ValueError("Block merkle root mismatch")
    header = BlockHeader(
        version=header_data.get("version", 1),
        prev_hash=header_data.get("prev_hash", ""),
        merkle_root=computed_merkle,
        timestamp=header_data.get("timestamp", 0),
        bits=header_data.get("bits", 0),
        nonce=header_data.get("nonce", 0),
    )
    block = Block(header=header, transactions=transactions, height=data.get("height", 0))
    if "hash" in data and data["hash"] != block.hash:
        raise ValueError("Block hash mismatch")
    return block


def create_app(data_dir: Path | None = None, host: str = "0.0.0.0", port: int = 8332) -> FastAPI:
    if data_dir is None:
        data_dir = Path(os.environ.get("AUREUM_DATA_DIR", str(Path.home() / ".aureum_chain")))
    chain_config = ChainConfig()
    node_config = NodeConfig(data_dir=data_dir, host=host, port=port)
    storage = Storage(node_config)
    try:
        chain = Blockchain.load(node_config.chain_path, chain_config)
    except ValueError as exc:
        raise RuntimeError(str(exc)) from exc
    chain.mempool = storage.load_mempool()
    peers = storage.load_peers()
    node = Node(
        chain=chain,
        peers=[normalize_peer(peer) for peer in peers if normalize_peer(peer)],
        storage=storage,
        seen_txs={},
        seen_blocks={},
        orphan_blocks={},
    )

    app = FastAPI(title=chain_config.name)

    @app.on_event("shutdown")
    def _shutdown() -> None:
        node.save_state()

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/", response_class=HTMLResponse)
    def ui_home() -> str:
        return render_ui()

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
    def new_transaction(payload: dict[str, Any], background_tasks: BackgroundTasks, request: Request) -> dict[str, Any]:
        try:
            tx = transaction_from_dict(payload)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        if tx.txid in node.chain.mempool.transactions:
            return {"status": "ok", "txid": tx.txid}
        if not node.chain.add_transaction(tx):
            raise HTTPException(status_code=400, detail="Invalid transaction")
        node.remember_seen_tx(tx.txid)
        origin = normalize_peer(str(request.base_url).rstrip("/"))
        background_tasks.add_task(node.broadcast_tx, tx, origin)
        return {"status": "accepted", "txid": tx.txid}

    @app.post("/transactions/relay")
    def relay_transaction(
        payload: dict[str, Any],
        background_tasks: BackgroundTasks,
        request: Request,
    ) -> dict[str, Any]:
        origin = payload.get("origin") or request.headers.get("X-Aureum-Origin")
        origin = normalize_peer(origin)
        tx_data = payload.get("tx") or payload
        try:
            tx = transaction_from_dict(tx_data)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        if tx.txid in node.chain.mempool.transactions or node.has_seen_tx(tx.txid):
            return {"status": "ok", "txid": tx.txid}
        if not node.chain.add_transaction(tx):
            raise HTTPException(status_code=400, detail="Invalid transaction")
        node.remember_seen_tx(tx.txid)
        print(f"received tx {tx.txid} from {origin or 'local'}")
        background_tasks.add_task(node.broadcast_tx, tx, origin)
        return {"status": "accepted", "txid": tx.txid}

    @app.post("/mine")
    def mine(payload: dict[str, Any], background_tasks: BackgroundTasks, request: Request) -> dict[str, Any]:
        address = payload.get("address")
        if not address:
            raise HTTPException(status_code=400, detail="Missing miner address")
        block = node.chain.mine_block(address)
        node.remember_seen_block(block.hash)
        node.try_apply_orphans()
        origin = normalize_peer(str(request.base_url).rstrip("/"))
        background_tasks.add_task(node.broadcast_block, block, origin)
        return {"status": "mined", "block": block.to_dict()}

    @app.post("/blocks/relay")
    def relay_block(
        payload: dict[str, Any],
        background_tasks: BackgroundTasks,
        request: Request,
    ) -> dict[str, Any]:
        origin = payload.get("origin") or request.headers.get("X-Aureum-Origin")
        origin = normalize_peer(origin)
        block_data = payload.get("block") or payload
        try:
            block = block_from_dict(block_data)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        if node.is_block_known(block.hash) or node.has_seen_block(block.hash):
            return {"status": "ok", "hash": block.hash}
        node.remember_seen_block(block.hash)
        if block.header.prev_hash == node.chain.last_hash():
            if not node.chain.apply_block(block):
                raise HTTPException(status_code=400, detail="Invalid block")
            print(f"received block {block.hash} from {origin or 'local'}")
            unlocked = node.try_apply_orphans()
            if unlocked:
                print(f"applied {len(unlocked)} orphan blocks")
            background_tasks.add_task(node.broadcast_block, block, origin)
            return {"status": "applied", "hash": block.hash}
        node.orphan_blocks.setdefault(block.header.prev_hash, []).append(block)
        print(f"stored orphan block {block.hash} waiting on {block.header.prev_hash}")
        background_tasks.add_task(node.sync)
        return {"status": "orphaned", "hash": block.hash}

    @app.get("/peers")
    def list_peers() -> dict[str, Any]:
        return {"peers": node.peers}

    @app.post("/peers/add")
    def add_peers(payload: dict[str, Any]) -> dict[str, Any]:
        peers = payload.get("peers", [])
        for peer in peers:
            node.add_peer(peer)
        node.storage.save_peers(node.peers)
        return {"status": "ok", "peers": node.peers}

    @app.get("/block/byhash/{block_hash}")
    def block_by_hash(block_hash: str) -> dict[str, Any]:
        for block in node.chain.state.blocks:
            if block.hash == block_hash:
                return block.to_dict()
        raise HTTPException(status_code=404, detail="Block not found")

    @app.post("/sync")
    def sync_chain() -> dict[str, Any]:
        synced = node.sync()
        return {"synced": synced, "height": node.chain.height()}

    return app
