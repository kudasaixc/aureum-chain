from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

from aureum_chain.tx import Transaction, TxOutput


@dataclass
class Mempool:
    transactions: dict[str, Transaction] = field(default_factory=dict)
    fees: dict[str, int] = field(default_factory=dict)

    def add(self, tx: Transaction, utxos: dict[str, TxOutput]) -> None:
        fee = self.calculate_fee(tx, utxos)
        self.transactions[tx.txid] = tx
        self.fees[tx.txid] = fee

    def calculate_fee(self, tx: Transaction, utxos: dict[str, TxOutput]) -> int:
        if tx.is_coinbase():
            return 0
        total_in = sum(utxos[f"{i.txid}:{i.vout}"].amount for i in tx.inputs)
        total_out = sum(o.amount for o in tx.outputs)
        return max(total_in - total_out, 0)

    def fee_total(self) -> int:
        return sum(self.fees.values())

    def sorted_transactions(self) -> list[Transaction]:
        return sorted(self.transactions.values(), key=lambda tx: self.fees.get(tx.txid, 0), reverse=True)

    def remove_transactions(self, txids: Iterable[str]) -> None:
        for txid in txids:
            self.transactions.pop(txid, None)
            self.fees.pop(txid, None)
