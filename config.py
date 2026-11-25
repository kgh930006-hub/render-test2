"""Configuration for the memory bot.

Loads settings from environment variables, with optional support for a
local ``.env`` file (same format as ``.env.example``). The bot token is
never stored in code — it must come from the environment.
"""

from __future__ import annotations

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent


def _load_dotenv(path: Path) -> None:
    """Load KEY=VALUE lines from a .env file without overwriting real env vars."""
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


_load_dotenv(BASE_DIR / ".env")

TELEGRAM_BOT_TOKEN: str = os.environ.get("TELEGRAM_BOT_TOKEN", "")
DB_PATH: str = os.environ.get("MEMORY_DB_PATH", str(BASE_DIR / "memories.db"))
PAGE_SIZE: int = int(os.environ.get("MEMORY_PAGE_SIZE", "5"))
LOG_LEVEL: str = os.environ.get("LOG_LEVEL", "INFO")
