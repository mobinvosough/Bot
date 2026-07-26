import aiosqlite
from loguru import logger
from config import settings

SCHEMA = """
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS source_channels (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username_or_id TEXT NOT NULL UNIQUE,
    added_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS admins (
    user_id INTEGER PRIMARY KEY,
    username TEXT,
    added_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS pending_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_channel TEXT NOT NULL,
    message_id INTEGER NOT NULL,
    content_type TEXT NOT NULL,
    text_or_caption TEXT,
    media_file_id TEXT,
    status TEXT NOT NULL DEFAULT 'pending',
    acted_by INTEGER,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS queue (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pending_id INTEGER NOT NULL,
    scheduled_time TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    added_by INTEGER,
    FOREIGN KEY (pending_id) REFERENCES pending_messages(id)
);

CREATE TABLE IF NOT EXISTS actions_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    message_id INTEGER,
    admin_id INTEGER NOT NULL,
    action TEXT NOT NULL,
    timestamp TEXT NOT NULL DEFAULT (datetime('now'))
);
"""

_db: aiosqlite.Connection | None = None


async def get_db() -> aiosqlite.Connection:
    global _db
    if _db is None:
        _db = await aiosqlite.connect(settings.DATABASE_PATH)
        _db.row_factory = aiosqlite.Row
        await _db.executescript(SCHEMA)
        await _db.commit()
        logger.info("Database connected: {}", settings.DATABASE_PATH)
    return _db


async def close_db():
    global _db
    if _db:
        await _db.close()
        _db = None
        logger.info("Database closed")


async def get_setting(key: str) -> str | None:
    db = await get_db()
    cursor = await db.execute("SELECT value FROM settings WHERE key = ?", (key,))
    row = await cursor.fetchone()
    return row["value"] if row else None


async def set_setting(key: str, value: str):
    db = await get_db()
    await db.execute(
        "INSERT INTO settings (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = ?",
        (key, value, value),
    )
    await db.commit()


async def add_source_channel(username_or_id: str):
    db = await get_db()
    await db.execute(
        "INSERT OR IGNORE INTO source_channels (username_or_id) VALUES (?)",
        (username_or_id,),
    )
    await db.commit()


async def remove_source_channel(username_or_id: str) -> bool:
    db = await get_db()
    cursor = await db.execute(
        "DELETE FROM source_channels WHERE username_or_id = ?", (username_or_id,)
    )
    await db.commit()
    return cursor.rowcount > 0


async def get_source_channels() -> list[str]:
    db = await get_db()
    cursor = await db.execute("SELECT username_or_id FROM source_channels")
    rows = await cursor.fetchall()
    return [row["username_or_id"] for row in rows]


async def add_admin(user_id: int, username: str | None = None):
    db = await get_db()
    await db.execute(
        "INSERT OR REPLACE INTO admins (user_id, username) VALUES (?, ?)",
        (user_id, username),
    )
    await db.commit()


async def remove_admin(user_id: int) -> bool:
    db = await get_db()
    cursor = await db.execute("DELETE FROM admins WHERE user_id = ?", (user_id,))
    await db.commit()
    return cursor.rowcount > 0


async def get_admins() -> list[dict]:
    db = await get_db()
    cursor = await db.execute("SELECT user_id, username FROM admins")
    rows = await cursor.fetchall()
    return [{"user_id": row["user_id"], "username": row["username"]} for row in rows]


async def is_setup_complete() -> bool:
    val = await get_setting("setup_complete")
    return val == "true"


async def log_action(admin_id: int, action: str, message_id: int | None = None):
    db = await get_db()
    await db.execute(
        "INSERT INTO actions_log (message_id, admin_id, action) VALUES (?, ?, ?)",
        (message_id, admin_id, action),
    )
    await db.commit()


async def get_recent_actions(limit: int = 5) -> list[dict]:
    db = await get_db()
    cursor = await db.execute(
        "SELECT action, admin_id, timestamp FROM actions_log ORDER BY id DESC LIMIT ?",
        (limit,),
    )
    rows = await cursor.fetchall()
    return [{"action": r["action"], "admin_id": r["admin_id"], "timestamp": r["timestamp"]} for r in rows]


async def is_message_processed(source_channel: str, message_id: int) -> bool:
    db = await get_db()
    cursor = await db.execute(
        "SELECT 1 FROM pending_messages WHERE source_channel = ? AND message_id = ?",
        (source_channel, message_id),
    )
    return await cursor.fetchone() is not None


async def save_pending_message(
    source_channel: str,
    message_id: int,
    content_type: str,
    text_or_caption: str | None = None,
    media_file_id: str | None = None,
) -> int:
    db = await get_db()
    cursor = await db.execute(
        "INSERT INTO pending_messages (source_channel, message_id, content_type, text_or_caption, media_file_id) "
        "VALUES (?, ?, ?, ?, ?)",
        (source_channel, message_id, content_type, text_or_caption, media_file_id),
    )
    await db.commit()
    return cursor.lastrowid


async def update_pending_status(pending_id: int, status: str, acted_by: int | None = None):
    db = await get_db()
    if acted_by is not None:
        await db.execute(
            "UPDATE pending_messages SET status = ?, acted_by = ? WHERE id = ?",
            (status, acted_by, pending_id),
        )
    else:
        await db.execute(
            "UPDATE pending_messages SET status = ? WHERE id = ?",
            (status, pending_id),
        )
    await db.commit()


async def get_pending_by_id(pending_id: int) -> dict | None:
    db = await get_db()
    cursor = await db.execute(
        "SELECT * FROM pending_messages WHERE id = ?", (pending_id,)
    )
    row = await cursor.fetchone()
    return dict(row) if row else None


async def count_pending() -> int:
    db = await get_db()
    cursor = await db.execute(
        "SELECT COUNT(*) AS cnt FROM pending_messages WHERE status = 'pending'"
    )
    row = await cursor.fetchone()
    return row["cnt"] if row else 0


async def get_last_queue_time() -> str | None:
    db = await get_db()
    cursor = await db.execute(
        "SELECT scheduled_time FROM queue ORDER BY id DESC LIMIT 1"
    )
    row = await cursor.fetchone()
    return row["scheduled_time"] if row else None


async def add_to_queue(pending_id: int, scheduled_time: str, added_by: int) -> int:
    db = await get_db()
    cursor = await db.execute(
        "INSERT INTO queue (pending_id, scheduled_time, added_by) VALUES (?, ?, ?)",
        (pending_id, scheduled_time, added_by),
    )
    await db.commit()
    return cursor.lastrowid


async def get_admin_username(user_id: int) -> str:
    db = await get_db()
    cursor = await db.execute(
        "SELECT username FROM admins WHERE user_id = ?", (user_id,)
    )
    row = await cursor.fetchone()
    if row and row["username"]:
        return f"@{row['username']}"
    return str(user_id)


async def get_active_queue_items() -> list[dict]:
    db = await get_db()
    cursor = await db.execute(
        "SELECT q.id AS queue_id, q.pending_id, q.scheduled_time, q.status, "
        "q.added_by, p.source_channel, p.message_id, p.content_type, "
        "p.text_or_caption, p.media_file_id "
        "FROM queue q JOIN pending_messages p ON q.pending_id = p.id "
        "WHERE q.status = 'pending' ORDER BY q.id ASC"
    )
    rows = await cursor.fetchall()
    return [dict(r) for r in rows]


async def get_due_queue_items() -> list[dict]:
    from datetime import datetime
    now = datetime.utcnow().isoformat()
    db = await get_db()
    cursor = await db.execute(
        "SELECT q.id AS queue_id, q.pending_id, q.scheduled_time, q.status, "
        "q.added_by, p.source_channel, p.message_id, p.content_type, "
        "p.text_or_caption, p.media_file_id "
        "FROM queue q JOIN pending_messages p ON q.pending_id = p.id "
        "WHERE q.status = 'pending' AND q.scheduled_time <= ? ORDER BY q.id ASC",
        (now,),
    )
    rows = await cursor.fetchall()
    return [dict(r) for r in rows]


async def update_queue_status(queue_id: int, status: str):
    db = await get_db()
    await db.execute(
        "UPDATE queue SET status = ? WHERE id = ?", (status, queue_id)
    )
    await db.commit()


async def cancel_queue_item(queue_id: int) -> bool:
    db = await get_db()
    cursor = await db.execute(
        "UPDATE queue SET status = 'cancelled' WHERE id = ? AND status = 'pending'",
        (queue_id,),
    )
    await db.commit()
    return cursor.rowcount > 0
