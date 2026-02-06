import sqlite3
from datetime import datetime, timedelta

from .config import DATA_DIR, DB_PATH


def init_db() -> sqlite3.Connection:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("""
        CREATE TABLE IF NOT EXISTS tracks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            artist TEXT NOT NULL,
            title TEXT NOT NULL,
            source TEXT NOT NULL,
            spotify_uri TEXT,
            added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(artist, title)
        )
    """)
    conn.commit()
    return conn


def track_exists(conn: sqlite3.Connection, artist: str, title: str) -> bool:
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
    conn.execute(
        "INSERT OR IGNORE INTO tracks (artist, title, source, spotify_uri) VALUES (?, ?, ?, ?)",
        (artist.strip(), title.strip(), source, spotify_uri),
    )
    conn.commit()


def get_recent_tracks(conn: sqlite3.Connection, days: int = 7) -> list[dict]:
    cutoff = (datetime.now() - timedelta(days=days)).isoformat()
    rows = conn.execute(
        "SELECT artist, title, source, spotify_uri, added_at FROM tracks WHERE added_at >= ? ORDER BY added_at DESC",
        (cutoff,),
    ).fetchall()
    return [dict(r) for r in rows]
