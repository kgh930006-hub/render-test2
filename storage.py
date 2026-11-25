"""SQLite storage layer for the memory bot.

This module has no Telegram dependency, so it can be tested on its own.
Every memory belongs to one ``user_id`` and is stored in one row:

    id, user_id, chat_id, type, file_id, text, tags, created_at

* ``type`` is one of: text, photo, video, document, voice, audio,
  animation, sticker.
* ``file_id`` is the Telegram file id for media memories (``None`` for text).
* ``text`` holds the message text or the media caption.
* ``tags`` is stored as a comma-separated string, e.g. ``"work,idea"``.
* ``created_at`` is a UTC ISO-8601 timestamp.
"""

from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

MEMORY_TYPES = (
    "text",
    "photo",
    "video",
    "document",
    "voice",
    "audio",
    "animation",
    "sticker",
)

_TAG_RE = re.compile(r"#([\w\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF]+)", re.UNICODE)


@dataclass
class Memory:
    """One saved memory."""

    id: int
    user_id: int
    chat_id: int
    type: str
    file_id: Optional[str]
    text: str
    tags: list[str]
    created_at: str


def extract_tags(text: Optional[str]) -> list[str]:
    """Extract ``#tag`` words from text/caption, without the ``#``.

    Arabic tags are supported. Duplicates are removed, order preserved.
    """
    if not text:
        return []
    seen: set[str] = set()
    tags: list[str] = []
    for tag in _TAG_RE.findall(text):
        tag = tag.strip()
        if tag and tag not in seen:
            seen.add(tag)
            tags.append(tag)
    return tags


def _connect(db_path: str | Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: str | Path) -> None:
    """Create the ``memories`` table if it does not exist."""
    with _connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS memories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                chat_id INTEGER NOT NULL,
                type TEXT NOT NULL,
                file_id TEXT,
                text TEXT NOT NULL DEFAULT '',
                tags TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_memories_user ON memories(user_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_memories_type ON memories(user_id, type)")
        conn.commit()


def _row_to_memory(row: sqlite3.Row) -> Memory:
    tags = [t for t in (row["tags"] or "").split(",") if t]
    return Memory(
        id=int(row["id"]),
        user_id=int(row["user_id"]),
        chat_id=int(row["chat_id"]),
        type=str(row["type"]),
        file_id=row["file_id"],
        text=str(row["text"] or ""),
        tags=tags,
        created_at=str(row["created_at"]),
    )


def add_memory(
    db_path: str | Path,
    *,
    user_id: int,
    chat_id: int,
    type: str,
    file_id: Optional[str] = None,
    text: str = "",
) -> Memory:
    """Save a memory and return it with its new id."""
    if type not in MEMORY_TYPES:
        raise ValueError(f"Unknown memory type: {type!r}")
    tags = extract_tags(text)
    created_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with _connect(db_path) as conn:
        cursor = conn.execute(
            """
            INSERT INTO memories (user_id, chat_id, type, file_id, text, tags, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (user_id, chat_id, type, file_id, text, ",".join(tags), created_at),
        )
        memory_id = int(cursor.lastrowid)
        conn.commit()
    memory = get_memory(db_path, memory_id, user_id)
    assert memory is not None  # just inserted
    return memory


def get_memory(db_path: str | Path, memory_id: int, user_id: int) -> Optional[Memory]:
    """Return one memory of this user, or ``None`` if it does not exist."""
    with _connect(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM memories WHERE id = ? AND user_id = ?",
            (memory_id, user_id),
        ).fetchone()
    return _row_to_memory(row) if row else None


def list_memories(
    db_path: str | Path,
    user_id: int,
    type: Optional[str] = None,
    limit: int = 5,
    offset: int = 0,
) -> list[Memory]:
    """List a user's memories, newest first, with optional type filter."""
    if type is not None and type not in MEMORY_TYPES:
        raise ValueError(f"Unknown memory type: {type!r}")
    with _connect(db_path) as conn:
        if type:
            rows = conn.execute(
                """
                SELECT * FROM memories WHERE user_id = ? AND type = ?
                ORDER BY id DESC LIMIT ? OFFSET ?
                """,
                (user_id, type, limit, offset),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT * FROM memories WHERE user_id = ?
                ORDER BY id DESC LIMIT ? OFFSET ?
                """,
                (user_id, limit, offset),
            ).fetchall()
    return [_row_to_memory(row) for row in rows]


def count_memories(
    db_path: str | Path, user_id: int, type: Optional[str] = None
) -> int:
    """Count a user's memories, optionally filtered by type."""
    with _connect(db_path) as conn:
        if type:
            row = conn.execute(
                "SELECT COUNT(*) AS n FROM memories WHERE user_id = ? AND type = ?",
                (user_id, type),
            ).fetchone()
        else:
            row = conn.execute(
                "SELECT COUNT(*) AS n FROM memories WHERE user_id = ?",
                (user_id,),
            ).fetchone()
    return int(row["n"])


def search_memories(
    db_path: str | Path, user_id: int, keyword: str, limit: int = 10
) -> list[Memory]:
    """Search text, caption and tags (case-insensitive, partial match)."""
    keyword = keyword.strip()
    if not keyword:
        return []
    pattern = f"%{keyword}%"
    with _connect(db_path) as conn:
        rows = conn.execute(
            """
            SELECT * FROM memories
            WHERE user_id = ? AND (text LIKE ? OR tags LIKE ?)
            ORDER BY id DESC LIMIT ?
            """,
            (user_id, pattern, pattern, limit),
        ).fetchall()
    return [_row_to_memory(row) for row in rows]


def delete_memory(db_path: str | Path, memory_id: int, user_id: int) -> bool:
    """Delete one memory. Returns ``True`` if a row was deleted."""
    with _connect(db_path) as conn:
        cursor = conn.execute(
            "DELETE FROM memories WHERE id = ? AND user_id = ?",
            (memory_id, user_id),
        )
        conn.commit()
        return cursor.rowcount > 0


def delete_all(db_path: str | Path, user_id: int) -> int:
    """Delete all of a user's memories. Returns how many were deleted."""
    with _connect(db_path) as conn:
        cursor = conn.execute(
            "DELETE FROM memories WHERE user_id = ?", (user_id,)
        )
        conn.commit()
        return int(cursor.rowcount)


def get_stats(db_path: str | Path, user_id: int) -> dict[str, int]:
    """Return ``{"total": N, "text": N, "photo": N, ...}`` for a user."""
    stats: dict[str, int] = {"total": 0}
    with _connect(db_path) as conn:
        rows = conn.execute(
            """
            SELECT type, COUNT(*) AS n FROM memories
            WHERE user_id = ? GROUP BY type
            """,
            (user_id,),
        ).fetchall()
    for row in rows:
        stats[str(row["type"])] = int(row["n"])
    stats["total"] = sum(v for k, v in stats.items() if k != "total")
    for memory_type in MEMORY_TYPES:
        stats.setdefault(memory_type, 0)
    return stats
