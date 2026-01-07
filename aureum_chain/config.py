from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ChainConfig:
    name: str = "Aureum Chain"
    symbol: str = "AUR"
    network: str = "testnet"
    genesis_message: str = "Aureum Chain Genesis Block"
    genesis_timestamp: int = 1_700_000_000
    block_time_seconds: int = 600
    target_leading_zeros: int = 4
    max_block_size: int = 1_000_000
    coinbase_maturity: int = 100
    initial_reward: int = 50
    halving_interval: int = 210_000
    max_supply: int = 21_000_000
    base_version: int = 1
    version_flags: tuple[str, ...] = ()


@dataclass(frozen=True)
class NodeConfig:
    data_dir: Path
    host: str = "0.0.0.0"
    port: int = 8332
    peers_file: str = "peers.json"
    chain_file: str = "chain.json"
    mempool_file: str = "mempool.json"

    @property
    def peers_path(self) -> Path:
        return self.data_dir / self.peers_file

    @property
    def chain_path(self) -> Path:
        return self.data_dir / self.chain_file

    @property
    def mempool_path(self) -> Path:
        return self.data_dir / self.mempool_file
