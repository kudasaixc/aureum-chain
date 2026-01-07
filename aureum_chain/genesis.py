from __future__ import annotations

from aureum_chain.block import Block, BlockHeader, encode_version
from aureum_chain.config import ChainConfig
from aureum_chain.crypto import merkle_root
from aureum_chain.tx import Transaction, TxInput, TxOutput, coinbase_extra_data

TESTNET_GENESIS_VERSION = 1
TESTNET_GENESIS_PREV_HASH = "0" * 64
TESTNET_GENESIS_BITS = 0
TESTNET_GENESIS_NONCE = 42
TESTNET_GENESIS_COINBASE_AMOUNT = 50
TESTNET_GENESIS_COINBASE_PUBKEY_HASH = "00" * 20


def _build_testnet_coinbase() -> Transaction:
    return Transaction(
        inputs=[
            TxInput(
                txid="",
                vout=-1,
                signature="",
                pubkey="",
            )
        ],
        outputs=[
            TxOutput(
                amount=TESTNET_GENESIS_COINBASE_AMOUNT,
                pubkey_hash=TESTNET_GENESIS_COINBASE_PUBKEY_HASH,
            )
        ],
        extra_data=coinbase_extra_data(0),
    )


def get_testnet_genesis_block(config: ChainConfig) -> Block:
    if config.network != "testnet":
        raise NotImplementedError(f"Genesis not configured for network '{config.network}'")
    coinbase = _build_testnet_coinbase()
    merkle = merkle_root([coinbase.txid])
    header = BlockHeader(
        version=encode_version(TESTNET_GENESIS_VERSION, list(config.version_flags)),
        prev_hash=TESTNET_GENESIS_PREV_HASH,
        merkle_root=merkle,
        timestamp=config.genesis_timestamp,
        bits=TESTNET_GENESIS_BITS,
        nonce=TESTNET_GENESIS_NONCE,
    )
    block = Block(header=header, transactions=[coinbase], height=0)
    block.hash = block.header.hash()
    return block


TESTNET_GENESIS_HASH = get_testnet_genesis_block(ChainConfig()).hash


def get_genesis_hash(config: ChainConfig) -> str:
    if config.network == "testnet":
        return TESTNET_GENESIS_HASH
    raise NotImplementedError(f"Genesis not configured for network '{config.network}'")
