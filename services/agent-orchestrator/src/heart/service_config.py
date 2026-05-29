"""P4-A: HTTP service configuration with env-var overrides.

All fields have safe defaults. Real writes are disabled by default.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class HeartServiceConfig:
    """Configuration for the Heart API HTTP adapter.

    Env vars:
        HEART_STORE: "sqlite" or "memory" (default: "sqlite")
        HEART_DB_PATH: path to SQLite file (default: ".heart/heart.sqlite3")
        HEART_GITHUB_PROVIDER: git provider type (default: "fake")
        HEART_GITHUB_WRITE_ENABLED: "1" to enable real writes (default: "0")

    Real GitHub writes are OFF by default (P3-D safety gate).
    """

    store_type: str = "sqlite"
    db_path: Path = field(default_factory=lambda: Path(".heart/heart.sqlite3"))
    github_provider: str = "fake"
    github_write_enabled: bool = False

    @classmethod
    def from_env(cls) -> HeartServiceConfig:
        """Create config from environment variables with safe defaults."""
        return cls(
            store_type=os.getenv("HEART_STORE", "sqlite"),
            db_path=Path(os.getenv("HEART_DB_PATH", ".heart/heart.sqlite3")),
            github_provider=os.getenv("HEART_GITHUB_PROVIDER", "fake"),
            github_write_enabled=os.getenv("HEART_GITHUB_WRITE_ENABLED", "0") == "1",
        )
