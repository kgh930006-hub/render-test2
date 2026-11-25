"""Per-chat short memory + bot state in SQLite (stdlib)."""
import os
import sqlite3
import time

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "clawbot.db")


def _conn():
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "CREATE TABLE IF NOT EXISTS chats "
        "(chat_id INTEGER PRIMARY KEY, provider TEXT, updated_at REAL)"
    )
    conn.execute(
        "CREATE TABLE IF NOT EXISTS messages "
        "(id INTEGER PRIMARY KEY AUTOINCREMENT, chat_id INTEGER, "
        "role TEXT, content TEXT, ts REAL)"
    )
    conn.execute(
        "CREATE TABLE IF NOT EXISTS state (key TEXT PRIMARY KEY, value TEXT)"
    )
    return conn


def get_offset():
    conn = _conn()
    try:
        row = conn.execute("SELECT value FROM state WHERE key='offset'").fetchone()
        return int(row[0]) if row else 0
    finally:
        conn.close()


def set_offset(value):
    conn = _conn()
    try:
        conn.execute(
            "INSERT INTO state(key, value) VALUES('offset', ?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (str(value),),
        )
        conn.commit()
    finally:
        conn.close()


def get_provider(chat_id):
    conn = _conn()
    try:
        row = conn.execute(
            "SELECT provider FROM chats WHERE chat_id=?", (chat_id,)
        ).fetchone()
        return row[0] if row and row[0] else None
    finally:
        conn.close()


def set_provider(chat_id, provider_id):
    conn = _conn()
    try:
        conn.execute(
            "INSERT INTO chats(chat_id, provider, updated_at) VALUES(?,?,?) "
            "ON CONFLICT(chat_id) DO UPDATE SET provider=excluded.provider, "
            "updated_at=excluded.updated_at",
            (chat_id, provider_id, time.time()),
        )
        conn.commit()
    finally:
        conn.close()


def add_message(chat_id, role, content):
    conn = _conn()
    try:
        conn.execute(
            "INSERT INTO messages(chat_id, role, content, ts) VALUES(?,?,?,?)",
            (chat_id, role, content[:4000], time.time()),
        )
        conn.commit()
    finally:
        conn.close()


def history(chat_id, limit=12):
    conn = _conn()
    try:
        rows = conn.execute(
            "SELECT role, content FROM messages WHERE chat_id=? "
            "ORDER BY id DESC LIMIT ?",
            (chat_id, limit),
        ).fetchall()
        rows.reverse()
        return [{"role": r, "content": c} for r, c in rows]
    finally:
        conn.close()


def reset_chat(chat_id):
    conn = _conn()
    try:
        conn.execute("DELETE FROM messages WHERE chat_id=?", (chat_id,))
        conn.commit()
    finally:
        conn.close()
