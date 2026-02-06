"""資料庫模組：SQLite 曲目紀錄與去重。

資料表 tracks 以 (artist, title) 為唯一鍵，確保同一首曲目不會重複寫入。
"""

import sqlite3
from datetime import datetime, timedelta

from .config import DATA_DIR, DB_PATH


def init_db() -> sqlite3.Connection:
    """初始化資料庫連線，自動建立 tracks 資料表（若不存在）。"""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("""
        CREATE TABLE IF NOT EXISTS tracks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            artist TEXT NOT NULL,       -- 藝人名稱
            title TEXT NOT NULL,        -- 曲目名稱
            source TEXT NOT NULL,       -- 來源媒體（如 Stereogum、SPIN 等）
            spotify_uri TEXT,           -- Spotify 曲目 URI（未找到為 NULL）
            added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(artist, title)       -- 去重：同一藝人+曲名只存一筆
        )
    """)
    conn.commit()
    return conn


def track_exists(conn: sqlite3.Connection, artist: str, title: str) -> bool:
    """檢查曲目是否已存在於資料庫中（大小寫不敏感比對）。"""
    row = conn.execute(
        "SELECT 1 FROM tracks WHERE LOWER(artist) = LOWER(?) AND LOWER(title) = LOWER(?)",
        (artist.strip(), title.strip()),
    ).fetchone()
    return row is not None


def save_track(
    conn: sqlite3.Connection,
    artist: str,
    title: str,
    source: str,
    spotify_uri: str | None,
) -> None:
    """儲存曲目至資料庫。若已存在（UNIQUE 衝突）則忽略。"""
    conn.execute(
        "INSERT OR IGNORE INTO tracks (artist, title, source, spotify_uri) VALUES (?, ?, ?, ?)",
        (artist.strip(), title.strip(), source, spotify_uri),
    )
    conn.commit()


def get_recent_tracks(conn: sqlite3.Connection, days: int = 7) -> list[dict]:
    """查詢最近 N 天內蒐集的曲目，依加入時間降序排列。"""
    cutoff = (datetime.now() - timedelta(days=days)).isoformat()
    rows = conn.execute(
        "SELECT artist, title, source, spotify_uri, added_at FROM tracks WHERE added_at >= ? ORDER BY added_at DESC",
        (cutoff,),
    ).fetchall()
    return [dict(r) for r in rows]
