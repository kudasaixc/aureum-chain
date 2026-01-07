from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from aureum_chain.block import Block
from aureum_chain.config import ChainConfig
from aureum_chain.crypto import merkle_root, pubkey_hash_from_address
from aureum_chain.mempool import Mempool
from aureum_chain.tx import Transaction, TxInput, TxOutput


@dataclass
class ChainState:
    blocks: list[Block]
    utxos: dict[str, TxOutput]


class Blockchain:
    def __init__(self, config: ChainConfig) -> None:
        self.config = config
        self.mempool = Mempool()
        self.state = self._create_genesis()

    def _create_genesis(self) -> ChainState:
        coinbase = Transaction(
            inputs=[TxInput(txid="", vout=-1, signature="", pubkey="")],
            outputs=[TxOutput(amount=self.config.initial_reward, pubkey_hash="genesis")],
        )
        genesis = Block.create(prev_hash="0" * 64, height=0, transactions=[coinbase], bits=0)
        genesis.hash = genesis.header.hash()
        utxos = {f"{coinbase.txid}:0": coinbase.outputs[0]}
        return ChainState(blocks=[genesis], utxos=utxos)

    def height(self) -> int:
        return self.state.blocks[-1].height

    def last_hash(self) -> str:
        return self.state.blocks[-1].hash

    def target_prefix(self) -> str:
        return "0" * self.config.target_leading_zeros

    def difficulty_bits(self) -> int:
        return self.config.target_leading_zeros

    def block_reward(self, height: int) -> int:
        halvings = height // self.config.halving_interval
        reward = self.config.initial_reward >> halvings
        return max(reward, 1)

    def add_transaction(self, tx: Transaction) -> bool:
        if not tx.validate(self.state.utxos):
            return False
        self.mempool.add(tx, self.state.utxos)
        return True

    def mine_block(self, miner_address: str) -> Block:
        txs = self.mempool.sorted_transactions()
        fee_total = self.mempool.fee_total()
        reward = self.block_reward(self.height() + 1) + fee_total
        miner_pubkey_hash = pubkey_hash_from_address(miner_address).hex()
        coinbase = Transaction(
            inputs=[TxInput(txid="", vout=-1, signature="", pubkey="")],
            outputs=[TxOutput(amount=reward, pubkey_hash=miner_pubkey_hash)],
        )
        block_txs = [coinbase] + txs
        block = Block.create(
            prev_hash=self.last_hash(),
            height=self.height() + 1,
            transactions=block_txs,
            bits=self.difficulty_bits(),
        )
        block.mine(self.target_prefix())
        self.apply_block(block)
        self.mempool.remove_transactions([tx.txid for tx in txs])
        return block

    def apply_block(self, block: Block) -> bool:
        if not self.validate_block(block):
            return False
        for tx in block.transactions:
            if not tx.is_coinbase():
                for tx_input in tx.inputs:
                    self.state.utxos.pop(f"{tx_input.txid}:{tx_input.vout}", None)
            for index, output in enumerate(tx.outputs):
                self.state.utxos[f"{tx.txid}:{index}"] = output
        self.state.blocks.append(block)
        return True

    def validate_block(self, block: Block) -> bool:
        if block.header.prev_hash != self.last_hash():
            return False
        if block.height != self.height() + 1:
            return False
        if block.hash != block.header.hash():
            return False
        if not block.hash.startswith(self.target_prefix()):
            return False
        merkle = merkle_root([tx.txid for tx in block.transactions])
        if merkle != block.header.merkle_root:
            return False
        temp_utxos = dict(self.state.utxos)
        for tx in block.transactions:
            if not tx.validate(temp_utxos):
                return False
            if not tx.is_coinbase():
                for tx_input in tx.inputs:
                    temp_utxos.pop(f"{tx_input.txid}:{tx_input.vout}", None)
            for index, output in enumerate(tx.outputs):
                temp_utxos[f"{tx.txid}:{index}"] = output
        return True

    def to_dict(self) -> dict[str, Any]:
        return {
            "config": self.config.__dict__,
            "blocks": [block.to_dict() for block in self.state.blocks],
        }

    def save(self, path: Path) -> None:
        path.write_text(json.dumps(self.to_dict(), indent=2))

    @staticmethod
    def load(path: Path, config: ChainConfig) -> "Blockchain":
        if not path.exists():
            return Blockchain(config)
        data = json.loads(path.read_text())
        chain = Blockchain(config)
        for block_data in data.get("blocks", []):
            transactions = []
            for tx_data in block_data["transactions"]:
                inputs = [TxInput(**inp) for inp in tx_data["inputs"]]
                outputs = [TxOutput(**out) for out in tx_data["outputs"]]
                tx = Transaction(inputs=inputs, outputs=outputs, locktime=tx_data.get("locktime", 0))
                transactions.append(tx)
            block = Block.create(
                prev_hash=block_data["header"]["prev_hash"],
                height=block_data["height"],
                transactions=transactions,
                bits=block_data["header"]["bits"],
                version=block_data["header"]["version"],
            )
            block.header.nonce = block_data["header"]["nonce"]
            block.header.timestamp = block_data["header"]["timestamp"]
            block.hash = block_data["hash"]
            if block.height == 0:
                chain.state.blocks = [block]
                chain.state.utxos = {f"{transactions[0].txid}:0": transactions[0].outputs[0]}
                continue
            chain.apply_block(block)
        return chain
