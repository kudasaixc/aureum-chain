from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from aureum_chain.crypto import generate_keypair, load_private_key


@dataclass
class Wallet:
    private_key_pem: str
    public_key_pem: str
    address: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "private_key": self.private_key_pem,
            "public_key": self.public_key_pem,
            "address": self.address,
        }

    @staticmethod
    def create() -> "Wallet":
        keypair = generate_keypair()
        return Wallet(
            private_key_pem=keypair.serialize_private(),
            public_key_pem=keypair.serialize_public(),
            address=keypair.address(),
        )

    @staticmethod
    def load(path: Path) -> "Wallet":
        data = json.loads(path.read_text())
        return Wallet(
            private_key_pem=data["private_key"],
            public_key_pem=data["public_key"],
            address=data["address"],
        )

    def save(self, path: Path) -> None:
        path.write_text(json.dumps(self.to_dict(), indent=2))

    def keypair(self):
        return load_private_key(self.private_key_pem)
