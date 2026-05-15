"""來源健康檢查模組：追蹤各擷取器執行狀態與失效檢測。

當來源連續失敗或連續多日回傳零首曲目時，標記為不健康並觸發通知。
"""

import logging
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta

from .config import (
    SOURCE_EMPTY_DAYS_THRESHOLD,
    SOURCE_FAILURE_THRESHOLD,
)

logger = logging.getLogger(__name__)


@dataclass
class SourceHealth:
    """單一來源健康狀態。"""

    source: str
    status: str  # 'healthy', 'unhealthy', 'warning'
    last_checked: str | None
    last_track_count: int
    consecutive_failures: int
    consecutive_empty_days: int
    last_error: str | None


def init_health_table(conn: sqlite3.Connection) -> None:
    """建立 source_checks 資料表（若不存在）。"""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS source_checks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source TEXT NOT NULL,
            status TEXT NOT NULL,
            track_count INTEGER DEFAULT 0,
            error_message TEXT,
            checked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_source_checks_source_at
        ON source_checks(source, checked_at DESC)
    """)
    conn.commit()


def record_scrape_result(
    conn: sqlite3.Connection,
    source: str,
    track_count: int,
    error: str | None = None,
) -> None:
    """記錄單次擷取結果到資料庫。"""
    if error:
        status = "failure"
    elif track_count == 0:
        status = "empty"
    else:
        status = "success"

    conn.execute(
        "INSERT INTO source_checks (source, status, track_count, error_message) VALUES (?, ?, ?, ?)",
        (source, status, track_count, error),
    )
    conn.commit()


def _count_consecutive_failures(conn: sqlite3.Connection, source: str) -> int:
    """計算來源最近的連續失敗次數。"""
    rows = conn.execute(
        """
        SELECT status FROM source_checks
        WHERE source = ?
        ORDER BY checked_at DESC
        LIMIT ?
        """,
        (source, SOURCE_FAILURE_THRESHOLD + 1),
    ).fetchall()

    count = 0
    for row in rows:
        if row["status"] == "failure":
            count += 1
        else:
            break
    return count


def _count_consecutive_empty_days(conn: sqlite3.Connection, source: str) -> int:
    """計算來源最近連續空結果的天數（只計算有執行紀錄的不同日期）。"""
    rows = conn.execute(
        """
        SELECT DISTINCT date(checked_at) as check_date, track_count
        FROM source_checks
        WHERE source = ? AND status IN ('success', 'empty')
        ORDER BY check_date DESC
        LIMIT ?
        """,
        (source, SOURCE_EMPTY_DAYS_THRESHOLD + 1),
    ).fetchall()

    count = 0
    for row in rows:
        if row["track_count"] == 0:
            count += 1
        else:
            break
    return count


def get_source_health(conn: sqlite3.Connection, source: str) -> SourceHealth:
    """取得單一來源的健康狀態。"""
    consecutive_failures = _count_consecutive_failures(conn, source)
    consecutive_empty_days = _count_consecutive_empty_days(conn, source)

    last = conn.execute(
        "SELECT * FROM source_checks WHERE source = ? ORDER BY checked_at DESC LIMIT 1",
        (source,),
    ).fetchone()

    if not last:
        return SourceHealth(
            source=source,
            status="healthy",
            last_checked=None,
            last_track_count=0,
            consecutive_failures=0,
            consecutive_empty_days=0,
            last_error=None,
        )

    if consecutive_failures >= SOURCE_FAILURE_THRESHOLD:
        status = "unhealthy"
    elif consecutive_empty_days >= SOURCE_EMPTY_DAYS_THRESHOLD:
        status = "warning"
    else:
        status = "healthy"

    return SourceHealth(
        source=source,
        status=status,
        last_checked=last["checked_at"],
        last_track_count=last["track_count"],
        consecutive_failures=consecutive_failures,
        consecutive_empty_days=consecutive_empty_days,
        last_error=last["error_message"],
    )


def get_all_source_health(
    conn: sqlite3.Connection, sources: list[str]
) -> list[SourceHealth]:
    """取得所有來源的健康狀態。"""
    return [get_source_health(conn, s) for s in sources]


def get_unhealthy_sources(
    conn: sqlite3.Connection, sources: list[str]
) -> list[SourceHealth]:
    """取得所有不健康或有警告的來源。"""
    return [h for h in get_all_source_health(conn, sources) if h.status != "healthy"]


def get_health_report(conn: sqlite3.Connection, sources: list[str]) -> str:
    """產生文字格式的健康報告。"""
    health_list = get_all_source_health(conn, sources)

    lines = ["📊 來源健康狀態報告", ""]

    for h in health_list:
        if h.status == "healthy":
            icon = "🟢"
        elif h.status == "unhealthy":
            icon = "🔴"
        else:
            icon = "🟡"

        lines.append(f"{icon} {h.source}")
        lines.append(f"   狀態：{h.status}")
        if h.last_checked:
            lines.append(f"   最後檢查：{h.last_checked}")
            lines.append(f"   最後曲目數：{h.last_track_count}")
        if h.consecutive_failures > 0:
            lines.append(f"   連續失敗：{h.consecutive_failures} 次")
        if h.consecutive_empty_days > 0:
            lines.append(f"   連續空結果：{h.consecutive_empty_days} 天")
        if h.last_error:
            lines.append(f"   最後錯誤：{h.last_error}")
        lines.append("")

    return "\n".join(lines)


def prune_old_checks(conn: sqlite3.Connection, days: int = 30) -> int:
    """清理超過 N 天的歷史檢查紀錄，回傳刪除筆數。"""
    cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
    cursor = conn.execute(
        "DELETE FROM source_checks WHERE checked_at < ?",
        (cutoff,),
    )
    conn.commit()
    deleted = cursor.rowcount
    if deleted > 0:
        logger.info(f"已清理 {deleted} 筆超過 {days} 天的來源健康紀錄")
    return deleted
