from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

import base58
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature, encode_dss_signature
from cryptography.hazmat.primitives.serialization import Encoding, PrivateFormat, PublicFormat, NoEncryption


def sha256(data: bytes) -> bytes:
    return hashlib.sha256(data).digest()


def double_sha256(data: bytes) -> bytes:
    return sha256(sha256(data))


def hash_hex(data: bytes) -> str:
    return double_sha256(data).hex()


def json_dumps(obj: Any) -> str:
    return json.dumps(obj, separators=(",", ":"), sort_keys=True)


def merkle_root(hashes: list[str]) -> str:
    if not hashes:
        return hash_hex(b"")
    level = [bytes.fromhex(h) for h in hashes]
    while len(level) > 1:
        if len(level) % 2 == 1:
            level.append(level[-1])
        next_level = []
        for i in range(0, len(level), 2):
            next_level.append(double_sha256(level[i] + level[i + 1]))
        level = next_level
    return level[0].hex()


def base58_check_encode(payload: bytes) -> str:
    checksum = double_sha256(payload)[:4]
    return base58.b58encode(payload + checksum).decode()


def base58_check_decode(address: str) -> bytes:
    data = base58.b58decode(address)
    payload, checksum = data[:-4], data[-4:]
    if double_sha256(payload)[:4] != checksum:
        raise ValueError("Invalid address checksum")
    return payload


def address_from_pubkey(pubkey_bytes: bytes) -> str:
    pubkey_hash = hashlib.new("ripemd160", sha256(pubkey_bytes)).digest()
    prefix = b"\x00"
    return base58_check_encode(prefix + pubkey_hash)


def pubkey_hash_from_address(address: str) -> bytes:
    payload = base58_check_decode(address)
    if len(payload) != 21:
        raise ValueError("Invalid address payload length")
    return payload[1:]


@dataclass
class KeyPair:
    private_key: ec.EllipticCurvePrivateKey

    @property
    def public_key(self) -> ec.EllipticCurvePublicKey:
        return self.private_key.public_key()

    def serialize_private(self) -> str:
        data = self.private_key.private_bytes(Encoding.PEM, PrivateFormat.PKCS8, NoEncryption())
        return data.decode()

    def serialize_public(self) -> str:
        data = self.public_key.public_bytes(Encoding.PEM, PublicFormat.SubjectPublicKeyInfo)
        return data.decode()

    def address(self) -> str:
        pubkey_bytes = self.public_key.public_bytes(Encoding.X962, PublicFormat.UncompressedPoint)
        return address_from_pubkey(pubkey_bytes)


def generate_keypair() -> KeyPair:
    return KeyPair(ec.generate_private_key(ec.SECP256K1()))


def load_private_key(pem: str) -> KeyPair:
    private_key = serialization.load_pem_private_key(pem.encode(), password=None)
    if not isinstance(private_key, ec.EllipticCurvePrivateKey):
        raise ValueError("Invalid private key type")
    return KeyPair(private_key)


def sign(private_key: ec.EllipticCurvePrivateKey, message: bytes) -> str:
    signature = private_key.sign(message, ec.ECDSA(hashes.SHA256()))
    r, s = decode_dss_signature(signature)
    return f"{r:x}:{s:x}"


def verify(public_key: ec.EllipticCurvePublicKey, message: bytes, signature: str) -> bool:
    try:
        r_str, s_str = signature.split(":", 1)
        signature_bytes = encode_dss_signature(int(r_str, 16), int(s_str, 16))
        public_key.verify(signature_bytes, message, ec.ECDSA(hashes.SHA256()))
        return True
    except Exception:
        return False
