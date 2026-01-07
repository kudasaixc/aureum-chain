from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec

from aureum_chain.crypto import json_dumps, hash_hex, pubkey_hash_from_address, verify


@dataclass
class TxInput:
    txid: str
    vout: int
    signature: str = ""
    pubkey: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "txid": self.txid,
            "vout": self.vout,
            "signature": self.signature,
            "pubkey": self.pubkey,
        }


@dataclass
class TxOutput:
    amount: int
    pubkey_hash: str

    def to_dict(self) -> dict[str, Any]:
        return {"amount": self.amount, "pubkey_hash": self.pubkey_hash}


@dataclass
class Transaction:
    inputs: list[TxInput]
    outputs: list[TxOutput]
    locktime: int = 0
    extra_data: str | None = None
    txid: str = field(init=False)

    def __post_init__(self) -> None:
        self.txid = self.compute_txid()

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "txid": self.txid,
            "inputs": [i.to_dict() for i in self.inputs],
            "outputs": [o.to_dict() for o in self.outputs],
            "locktime": self.locktime,
        }
        if self.extra_data not in (None, ""):
            data["extra_data"] = self.extra_data
        return data

    def to_dict_unsigned(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "inputs": [
                {"txid": i.txid, "vout": i.vout, "signature": "", "pubkey": ""}
                for i in self.inputs
            ],
            "outputs": [o.to_dict() for o in self.outputs],
            "locktime": self.locktime,
        }
        if self.extra_data not in (None, ""):
            data["extra_data"] = self.extra_data
        return data

    def serialize_unsigned(self) -> bytes:
        return json_dumps(self.to_dict_unsigned()).encode()

    def compute_txid(self) -> str:
        return hash_hex(json_dumps(self.to_dict_unsigned()).encode())

    def sign(self, private_key: ec.EllipticCurvePrivateKey) -> None:
        from aureum_chain.crypto import sign

        signature = sign(private_key, self.serialize_unsigned())
        pubkey = private_key.public_key().public_bytes(
            serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint
        ).hex()
        for tx_input in self.inputs:
            tx_input.signature = signature
            tx_input.pubkey = pubkey
        self.txid = self.compute_txid()

    def is_coinbase(self) -> bool:
        return len(self.inputs) == 1 and self.inputs[0].txid == ""

    def validate(self, utxos: dict[str, TxOutput]) -> bool:
        if self.is_coinbase():
            return True
        if self.extra_data not in (None, ""):
            return False
        message = self.serialize_unsigned()
        for tx_input in self.inputs:
            key = f"{tx_input.txid}:{tx_input.vout}"
            utxo = utxos.get(key)
            if not utxo:
                return False
            try:
                pubkey_bytes = bytes.fromhex(tx_input.pubkey)
                public_key = ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256K1(), pubkey_bytes)
            except Exception:
                return False
            if not verify(public_key, message, tx_input.signature):
                return False
            if utxo.pubkey_hash != pubkey_hash_from_address(self.address_from_pubkey(pubkey_bytes)).hex():
                return False
        total_in = sum(utxos[f"{i.txid}:{i.vout}"].amount for i in self.inputs)
        total_out = sum(o.amount for o in self.outputs)
        return total_in >= total_out

    @staticmethod
    def address_from_pubkey(pubkey_bytes: bytes) -> str:
        from aureum_chain.crypto import address_from_pubkey

        return address_from_pubkey(pubkey_bytes)


@dataclass
class MempoolEntry:
    tx: Transaction
    fee: int

    def to_dict(self) -> dict[str, Any]:
        return {"tx": self.tx.to_dict(), "fee": self.fee}
