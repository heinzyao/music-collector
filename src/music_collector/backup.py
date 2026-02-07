"""季度 JSON 備份模組：將新曲目追加至 data/backups/YYYY/QN.json。

每次執行後呼叫 save_backup()，自動建立目錄、讀取既有檔案、合併去重後寫回。
"""

import json
import logging
from datetime import datetime, timezone

from .config import BACKUP_DIR
from .scrapers.base import Track

logger = logging.getLogger(__name__)


def _get_quarter(month: int) -> int:
    """回傳季度編號（1–4）。"""
    return (month - 1) // 3 + 1


def save_backup(
    tracks: list[Track],
    spotify_results: dict[tuple[str, str], str | None],
) -> None:
    """將本次蒐集的曲目追加至季度備份檔案。

    Args:
        tracks: 本次新發現的曲目清單。
        spotify_results: {(artist, title): spotify_uri or None} 對應表。
    """
    if not tracks:
        return

    now = datetime.now(timezone.utc)
    quarter = _get_quarter(now.month)
    year_dir = BACKUP_DIR / str(now.year)
    year_dir.mkdir(parents=True, exist_ok=True)
    backup_file = year_dir / f"Q{quarter}.json"

    # 讀取現有備份
    existing: list[dict] = []
    if backup_file.exists():
        try:
            existing = json.loads(backup_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as e:
            logger.warning(f"備份檔案讀取失敗，將覆寫：{e}")

    # 建立去重索引（以小寫 artist + title 為鍵）
    seen = {(e["artist"].lower(), e["title"].lower()) for e in existing}

    # 追加新曲目
    added = 0
    for track in tracks:
        key = (track.artist.lower(), track.title.lower())
        if key in seen:
            continue
        seen.add(key)

        uri = spotify_results.get((track.artist, track.title))
        existing.append({
            "artist": track.artist,
            "title": track.title,
            "source": track.source,
            "spotify_uri": uri,
            "added_at": now.isoformat(),
        })
        added += 1

    # 寫回檔案
    backup_file.write_text(
        json.dumps(existing, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    logger.info(f"備份完成：新增 {added} 首至 {backup_file}")
