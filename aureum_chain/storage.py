from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from aureum_chain.config import NodeConfig
from aureum_chain.mempool import Mempool
from aureum_chain.tx import Transaction, TxInput, TxOutput


@dataclass
class Storage:
    config: NodeConfig

    def ensure(self) -> None:
        self.config.data_dir.mkdir(parents=True, exist_ok=True)

    def load_peers(self) -> list[str]:
        if not self.config.peers_path.exists():
            return []
        return json.loads(self.config.peers_path.read_text())

    def save_peers(self, peers: list[str]) -> None:
        self.ensure()
        self.config.peers_path.write_text(json.dumps(sorted(set(peers)), indent=2))

    def load_mempool(self) -> Mempool:
        if not self.config.mempool_path.exists():
            return Mempool()
        data = json.loads(self.config.mempool_path.read_text())
        mempool = Mempool()
        for entry in data.get("transactions", []):
            tx_data = entry["tx"]
            inputs = [TxInput(**inp) for inp in tx_data["inputs"]]
            outputs = [TxOutput(**out) for out in tx_data["outputs"]]
            tx = Transaction(
                inputs=inputs,
                outputs=outputs,
                locktime=tx_data.get("locktime", 0),
                extra_data=tx_data.get("extra_data"),
            )
            mempool.transactions[tx.txid] = tx
            mempool.fees[tx.txid] = entry.get("fee", 0)
        return mempool

    def save_mempool(self, mempool: Mempool) -> None:
        self.ensure()
        data = {
            "transactions": [
                {"tx": tx.to_dict(), "fee": mempool.fees.get(tx.txid, 0)}
                for tx in mempool.transactions.values()
            ]
        }
        self.config.mempool_path.write_text(json.dumps(data, indent=2))
