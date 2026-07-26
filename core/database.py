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
