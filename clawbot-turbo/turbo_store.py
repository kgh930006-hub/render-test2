"""TURBO persistent store: chat history, memories, answer cache (SQLite)."""
import hashlib
import pathlib
import sqlite3
import threading
import time

DB = pathlib.Path(__file__).with_name("turbo.db")
_lock = threading.Lock()
CACHE_TTL = 3600


def _conn():
    c = sqlite3.connect(DB)
    c.execute("CREATE TABLE IF NOT EXISTS messages(id INTEGER PRIMARY KEY, chat_id INTEGER, role TEXT, content TEXT, ts REAL)")
    c.execute("CREATE TABLE IF NOT EXISTS memories(id INTEGER PRIMARY KEY, chat_id INTEGER, text TEXT, ts REAL)")
    c.execute("CREATE TABLE IF NOT EXISTS cache(hash TEXT PRIMARY KEY, answer TEXT, ts REAL)")
    return c


def add_message(chat_id, role, content):
    try:
        with _lock, _conn() as c:
            c.execute("INSERT INTO messages(chat_id,role,content,ts) VALUES(?,?,?,?)",
                      (int(chat_id), role, str(content)[:4000], time.time()))
    except Exception:
        pass


def get_history(chat_id, limit=30):
    try:
        with _lock, _conn() as c:
            rows = c.execute("SELECT role,content FROM messages WHERE chat_id=? ORDER BY id DESC LIMIT ?",
                             (int(chat_id), limit)).fetchall()
        return [f"{r}: {t}" for r, t in reversed(rows)]
    except Exception:
        return []


def remember(chat_id, text):
    with _lock, _conn() as c:
        c.execute("INSERT INTO memories(chat_id,text,ts) VALUES(?,?,?)", (int(chat_id), str(text)[:1000], time.time()))


def list_memories(chat_id, limit=30):
    try:
        with _lock, _conn() as c:
            rows = c.execute("SELECT text FROM memories WHERE chat_id=? ORDER BY id DESC LIMIT ?",
                             (int(chat_id), limit)).fetchall()
        return [r[0] for r in reversed(rows)]
    except Exception:
        return []


def forget_all(chat_id):
    with _lock, _conn() as c:
        n = c.execute("DELETE FROM memories WHERE chat_id=?", (int(chat_id),)).rowcount
        c.execute("DELETE FROM messages WHERE chat_id=?", (int(chat_id),))
    return n


def _h(text):
    return hashlib.sha256(" ".join(str(text).strip().lower().split()).encode("utf-8")).hexdigest()


def cache_get(text):
    try:
        with _lock, _conn() as c:
            row = c.execute("SELECT answer,ts FROM cache WHERE hash=?", (_h(text),)).fetchone()
        if row and time.time() - row[1] < CACHE_TTL:
            return row[0]
    except Exception:
        pass
    return None


def cache_set(text, answer):
    try:
        with _lock, _conn() as c:
            c.execute("INSERT OR REPLACE INTO cache(hash,answer,ts) VALUES(?,?,?)",
                      (_h(text), str(answer)[:4000], time.time()))
    except Exception:
        pass


def stats(chat_id=None):
    try:
        with _lock, _conn() as c:
            m = c.execute("SELECT COUNT(*) FROM messages").fetchone()[0]
            mem = c.execute("SELECT COUNT(*) FROM memories").fetchone()[0]
            ca = c.execute("SELECT COUNT(*) FROM cache WHERE ts > ?", (time.time() - CACHE_TTL,)).fetchone()[0]
        return {"messages": m, "memories": mem, "cache_live": ca,
                "db_kb": round(DB.stat().st_size / 1024, 1) if DB.exists() else 0}
    except Exception:
        return {"messages": 0, "memories": 0, "cache_live": 0, "db_kb": 0}
