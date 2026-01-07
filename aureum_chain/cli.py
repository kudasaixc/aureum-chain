from __future__ import annotations

import argparse
import json
from pathlib import Path

import requests

from aureum_chain.chain import Blockchain
from aureum_chain.config import ChainConfig, NodeConfig
from aureum_chain.crypto import pubkey_hash_from_address
from aureum_chain.node import create_app
from aureum_chain.tx import Transaction, TxInput, TxOutput
from aureum_chain.wallet import Wallet


def default_data_dir() -> Path:
    return Path.home() / ".aureum_chain"


def init_chain(data_dir: Path) -> None:
    config = ChainConfig()
    chain = Blockchain(config)
    data_dir.mkdir(parents=True, exist_ok=True)
    chain.save(data_dir / "chain.json")
    (data_dir / "mempool.json").write_text(json.dumps({"transactions": []}, indent=2))
    (data_dir / "peers.json").write_text(json.dumps([], indent=2))
    print(f"Initialized {config.name} at {data_dir}")


def wallet_create(path: Path) -> None:
    wallet = Wallet.create()
    wallet.save(path)
    print(f"Wallet created: {wallet.address}")


def wallet_show(path: Path) -> None:
    wallet = Wallet.load(path)
    print(json.dumps(wallet.to_dict(), indent=2))


def start_node(data_dir: Path, host: str, port: int) -> None:
    import uvicorn

    app = create_app(data_dir, host, port)
    uvicorn.run(app, host=host, port=port)


def build_transaction(wallet_path: Path, to_address: str, amount: int, node_url: str) -> Transaction:
    wallet = Wallet.load(wallet_path)
    utxos_resp = requests.get(f"{node_url}/utxos/{wallet.address}", timeout=5)
    utxos_resp.raise_for_status()
    utxos = utxos_resp.json().get("utxos", {})
    selected = []
    total = 0
    for key, output in utxos.items():
        txid, vout = key.split(":")
        selected.append((txid, int(vout), output))
        total += output["amount"]
        if total >= amount:
            break
    if total < amount:
        raise RuntimeError("Insufficient funds")
    inputs = [TxInput(txid=txid, vout=vout) for txid, vout, _ in selected]
    outputs = [TxOutput(amount=amount, pubkey_hash=pubkey_hash_from_address(to_address).hex())]
    change = total - amount
    if change > 0:
        outputs.append(TxOutput(amount=change, pubkey_hash=pubkey_hash_from_address(wallet.address).hex()))
    tx = Transaction(inputs=inputs, outputs=outputs)
    tx.sign(wallet.keypair().private_key)
    return tx


def send_transaction(wallet_path: Path, to_address: str, amount: int, node_url: str) -> None:
    tx = build_transaction(wallet_path, to_address, amount, node_url)
    resp = requests.post(f"{node_url}/transactions/new", json=tx.to_dict(), timeout=5)
    resp.raise_for_status()
    print(json.dumps(resp.json(), indent=2))


def mine_block(node_url: str, address: str) -> None:
    resp = requests.post(f"{node_url}/mine", json={"address": address}, timeout=30)
    resp.raise_for_status()
    print(json.dumps(resp.json(), indent=2))


def add_peers(node_url: str, peers: list[str]) -> None:
    resp = requests.post(f"{node_url}/peers/add", json={"peers": peers}, timeout=5)
    resp.raise_for_status()
    print(json.dumps(resp.json(), indent=2))


def sync_chain(node_url: str) -> None:
    resp = requests.post(f"{node_url}/sync", json={}, timeout=10)
    resp.raise_for_status()
    print(json.dumps(resp.json(), indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description="Aureum Chain CLI")
    parser.add_argument("--data-dir", type=Path, default=default_data_dir())
    parser.add_argument("--node-url", default="http://127.0.0.1:8332")

    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("init")

    wallet_parser = subparsers.add_parser("wallet")
    wallet_sub = wallet_parser.add_subparsers(dest="wallet_command")
    wallet_sub.add_parser("create")
    wallet_sub.add_parser("show")
    wallet_parser.add_argument("--path", type=Path, default=default_data_dir() / "wallet.json")

    node_parser = subparsers.add_parser("node")
    node_parser.add_argument("--host", default="0.0.0.0")
    node_parser.add_argument("--port", type=int, default=8332)

    tx_parser = subparsers.add_parser("tx")
    tx_parser.add_argument("to")
    tx_parser.add_argument("amount", type=int)
    tx_parser.add_argument("--wallet", type=Path, default=default_data_dir() / "wallet.json")

    mine_parser = subparsers.add_parser("mine")
    mine_parser.add_argument("address")

    peers_parser = subparsers.add_parser("peers")
    peers_parser.add_argument("peers", nargs="+")

    subparsers.add_parser("sync")

    args = parser.parse_args()

    if args.command == "init":
        init_chain(args.data_dir)
    elif args.command == "wallet":
        if args.wallet_command == "create":
            wallet_create(args.path)
        elif args.wallet_command == "show":
            wallet_show(args.path)
        else:
            parser.error("wallet command required")
    elif args.command == "node":
        start_node(args.data_dir, args.host, args.port)
    elif args.command == "tx":
        send_transaction(args.wallet, args.to, args.amount, args.node_url)
    elif args.command == "mine":
        mine_block(args.node_url, args.address)
    elif args.command == "peers":
        add_peers(args.node_url, args.peers)
    elif args.command == "sync":
        sync_chain(args.node_url)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
