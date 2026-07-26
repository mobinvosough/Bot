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
    target = await get_setting("target_channel")
    return target is not None and target != ""


async def log_action(admin_id: int, action: str, message_id: int | None = None):
    db = await get_db()
    await db.execute(
        "INSERT INTO actions_log (message_id, admin_id, action) VALUES (?, ?, ?)",
        (message_id, admin_id, action),
    )
    await db.commit()


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


async def update_pending_status(pending_id: int, status: str):
    db = await get_db()
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
