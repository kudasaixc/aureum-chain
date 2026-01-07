from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from aureum_chain.crypto import hash_hex, merkle_root, json_dumps
from aureum_chain.tx import Transaction

VERSION_BITS_MASK = 0b11100000_00000000_00000000_00000000
VERSION_SIGNALING_BITS = 0b00100000_00000000_00000000_00000000
FEATURE_FLAGS = {
    "future_softfork_1": 1 << 0,
    "future_softfork_2": 1 << 1,
}


def encode_version(base_version: int, flags: list[str]) -> int:
    flag_bits = 0
    for flag in flags:
        bit = FEATURE_FLAGS.get(flag)
        if bit is not None:
            flag_bits |= bit
    base_clean = base_version & ~VERSION_BITS_MASK
    return base_clean | VERSION_SIGNALING_BITS | flag_bits


def decode_version(version: int) -> dict[str, Any]:
    enabled_flags: list[str] = []
    known_bits = 0
    for name, bit in FEATURE_FLAGS.items():
        if version & bit:
            enabled_flags.append(name)
            known_bits |= bit
    base_version = version & ~VERSION_BITS_MASK & ~known_bits
    return {
        "signaling_bits": version & VERSION_BITS_MASK,
        "base_version": base_version,
        "flags": enabled_flags,
        "unknown_bits": version & ~VERSION_BITS_MASK & ~known_bits,
    }


@dataclass
class BlockHeader:
    version: int
    prev_hash: str
    merkle_root: str
    timestamp: int
    bits: int
    nonce: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "prev_hash": self.prev_hash,
            "merkle_root": self.merkle_root,
            "timestamp": self.timestamp,
            "bits": self.bits,
            "nonce": self.nonce,
        }

    def hash(self) -> str:
        return hash_hex(json_dumps(self.to_dict()).encode())


@dataclass
class Block:
    header: BlockHeader
    transactions: list[Transaction]
    height: int
    hash: str = field(init=False)

    def __post_init__(self) -> None:
        self.hash = self.header.hash()

    def to_dict(self) -> dict[str, Any]:
        return {
            "hash": self.hash,
            "height": self.height,
            "header": self.header.to_dict(),
            "transactions": [tx.to_dict() for tx in self.transactions],
        }

    @staticmethod
    def create(
        prev_hash: str,
        height: int,
        transactions: list[Transaction],
        bits: int,
        version: int = 1,
    ) -> "Block":
        merkle = merkle_root([tx.txid for tx in transactions])
        header = BlockHeader(
            version=version,
            prev_hash=prev_hash,
            merkle_root=merkle,
            timestamp=int(time.time()),
            bits=bits,
            nonce=0,
        )
        block = Block(header=header, transactions=transactions, height=height)
        return block

    def mine(self, target_prefix: str) -> None:
        while True:
            self.hash = self.header.hash()
            if self.hash.startswith(target_prefix):
                break
            self.header.nonce += 1
