"""季度 JSON 備份模組：將新曲目追加至 data/backups/YYYY/QN.json。

每次執行後呼叫 save_backup()，自動建立目錄、讀取既有檔案、合併去重後寫回。
亦提供 list_backups() / show_backup() 供 CLI 檢視備份內容。
"""

import json
import logging
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

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


def list_backups() -> None:
    """列出所有備份檔案及其曲目數量。"""
    if not BACKUP_DIR.exists():
        print("尚無備份資料。")
        return

    files = sorted(BACKUP_DIR.glob("**/Q*.json"))
    if not files:
        print("尚無備份資料。")
        return

    print("\n可用的備份檔案：\n")
    for f in files:
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            matched = sum(1 for t in data if t.get("spotify_uri"))
            label = f"{f.parent.name}/{f.stem}"
            print(f"  {label}  —  {len(data)} 首（Spotify 配對 {matched} 首）")
        except (json.JSONDecodeError, OSError):
            print(f"  {f.relative_to(BACKUP_DIR)}  —  讀取失敗")


def show_backup(query: str) -> None:
    """顯示指定季度備份的詳細內容。

    query 格式：'Q1'、'2026Q1'、'2026/Q1' 皆可。
    """
    # 解析查詢
    q = query.upper().replace("/", "").replace("-", "").strip()

    # 嘗試各種匹配
    candidates = sorted(BACKUP_DIR.glob("**/Q*.json"))
    target: Path | None = None
    for f in candidates:
        label = f"{f.parent.name}{f.stem}".upper()
        if q == label or q == f.stem.upper():
            target = f
            break

    if not target or not target.exists():
        print(f"找不到備份：{query}")
        print("可用備份：", ", ".join(f"{f.parent.name}/{f.stem}" for f in candidates) or "無")
        return

    try:
        data = json.loads(target.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        print(f"備份讀取失敗：{e}")
        return

    label = f"{target.parent.name}/{target.stem}"
    matched = sum(1 for t in data if t.get("spotify_uri"))
    sources = Counter(t["source"] for t in data)

    print(f"\n{label} 備份（共 {len(data)} 首，Spotify 配對 {matched} 首）")
    print(f"來源分布：{', '.join(f'{s} {c}' for s, c in sources.most_common())}\n")

    for i, t in enumerate(data, 1):
        status = "✓" if t.get("spotify_uri") else "✗"
        print(f"  {i:3d}. [{status}] [{t['source']}] {t['artist']} — {t['title']}")
