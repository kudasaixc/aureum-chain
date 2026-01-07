from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from aureum_chain.block import Block, encode_version
from aureum_chain.config import ChainConfig
from aureum_chain.crypto import merkle_root, pubkey_hash_from_address
from aureum_chain.genesis import get_genesis_hash, get_testnet_genesis_block
from aureum_chain.mempool import Mempool
from aureum_chain.tx import Transaction, TxInput, TxOutput, coinbase_extra_data


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
        genesis = get_testnet_genesis_block(self.config)
        utxos = {f"{genesis.transactions[0].txid}:0": genesis.transactions[0].outputs[0]}
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

    def current_supply(self) -> int:
        total = 0
        for block in self.state.blocks:
            if not block.transactions:
                continue
            coinbase_tx = block.transactions[0]
            if not coinbase_tx.is_coinbase():
                continue
            total += sum(output.amount for output in coinbase_tx.outputs)
        return total

    def add_transaction(self, tx: Transaction) -> bool:
        if not tx.validate(self.state.utxos):
            return False
        self.mempool.add(tx, self.state.utxos)
        return True

    def mine_block(self, miner_address: str) -> Block:
        height = self.height() + 1
        txs = self.mempool.sorted_transactions()
        fee_total = self.mempool.fee_total()
        remaining_supply = max(self.config.max_supply - self.current_supply(), 0)
        reward = min(self.block_reward(height) + fee_total, remaining_supply)
        miner_pubkey_hash = pubkey_hash_from_address(miner_address).hex()
        coinbase = Transaction(
            inputs=[TxInput(txid="", vout=-1, signature="", pubkey="")],
            outputs=[TxOutput(amount=reward, pubkey_hash=miner_pubkey_hash)],
            extra_data=coinbase_extra_data(height),
        )
        block_txs = [coinbase] + txs
        block = Block.create(
            prev_hash=self.last_hash(),
            height=height,
            transactions=block_txs,
            bits=self.difficulty_bits(),
            version=encode_version(self.config.base_version, list(self.config.version_flags)),
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
        if not block.transactions:
            return False
        coinbase_tx = block.transactions[0]
        if not coinbase_tx.is_coinbase():
            return False
        if any(tx.is_coinbase() for tx in block.transactions[1:]):
            return False
        if coinbase_tx.extra_data != coinbase_extra_data(block.height):
            return False
        temp_utxos = dict(self.state.utxos)
        total_fees = 0
        for tx in block.transactions:
            if not tx.validate(temp_utxos):
                return False
            if not tx.is_coinbase():
                total_in = sum(temp_utxos[f"{i.txid}:{i.vout}"].amount for i in tx.inputs)
                total_out = sum(output.amount for output in tx.outputs)
                total_fees += total_in - total_out
                for tx_input in tx.inputs:
                    temp_utxos.pop(f"{tx_input.txid}:{tx_input.vout}", None)
            for index, output in enumerate(tx.outputs):
                temp_utxos[f"{tx.txid}:{index}"] = output
        current_supply = self.current_supply()
        remaining_supply = max(self.config.max_supply - current_supply, 0)
        expected_reward = min(self.block_reward(block.height), remaining_supply)
        coinbase_total = sum(output.amount for output in coinbase_tx.outputs)
        max_coinbase = min(expected_reward + total_fees, remaining_supply)
        if coinbase_total > max_coinbase:
            return False
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
        blocks_data = data.get("blocks", [])
        if not blocks_data:
            return Blockchain(config)
        first_block_data = blocks_data[0]
        transactions = []
        for tx_data in first_block_data["transactions"]:
            inputs = [TxInput(**inp) for inp in tx_data["inputs"]]
            outputs = [TxOutput(**out) for out in tx_data["outputs"]]
            tx = Transaction(
                inputs=inputs,
                outputs=outputs,
                locktime=tx_data.get("locktime", 0),
                extra_data=tx_data.get("extra_data"),
            )
            transactions.append(tx)
        genesis_block = Block.create(
            prev_hash=first_block_data["header"]["prev_hash"],
            height=first_block_data["height"],
            transactions=transactions,
            bits=first_block_data["header"]["bits"],
            version=first_block_data["header"]["version"],
        )
        genesis_block.header.nonce = first_block_data["header"]["nonce"]
        genesis_block.header.timestamp = first_block_data["header"]["timestamp"]
        computed_genesis_hash = genesis_block.header.hash()
        stored_genesis_hash = first_block_data.get("hash")
        if stored_genesis_hash and stored_genesis_hash != computed_genesis_hash:
            raise ValueError("Genesis block hash mismatch in chain data.")
        expected_genesis_hash = get_genesis_hash(config)
        if computed_genesis_hash != expected_genesis_hash:
            raise ValueError(
                "Genesis mismatch: this data dir belongs to a different network. "
                "Delete data dir or use the correct network config."
            )
        chain = Blockchain(config)
        for block_data in blocks_data:
            transactions = []
            for tx_data in block_data["transactions"]:
                inputs = [TxInput(**inp) for inp in tx_data["inputs"]]
                outputs = [TxOutput(**out) for out in tx_data["outputs"]]
                tx = Transaction(
                    inputs=inputs,
                    outputs=outputs,
                    locktime=tx_data.get("locktime", 0),
                    extra_data=tx_data.get("extra_data"),
                )
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
            if block.height == 0:
                block.hash = block.header.hash()
            else:
                block.hash = block_data["hash"]
            if block.height == 0:
                chain.state.blocks = [block]
                chain.state.utxos = {f"{transactions[0].txid}:0": transactions[0].outputs[0]}
                continue
            chain.apply_block(block)
        return chain
