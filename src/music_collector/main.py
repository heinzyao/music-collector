"""主流程模組：調度擷取、去重、搜尋、備份、通知的完整流程。

使用方式：
    python -m music_collector              # 完整執行
    python -m music_collector --dry-run    # 僅擷取，不寫入 Spotify / 不備份 / 不通知
    python -m music_collector --recent 7   # 顯示最近 7 天蒐集的曲目
"""

import argparse
import logging
import sys

from .backup import save_backup
from .db import init_db, save_track, track_exists, get_recent_tracks
from .notify import send_notification
from .scrapers import ALL_SCRAPERS
from .scrapers.base import Track
from .spotify import (
    add_tracks_to_playlist,
    archive_previous_quarters,
    get_or_create_playlist,
    get_spotify_client,
    migrate_old_playlist,
    search_track,
)

# 設定日誌格式
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def collect_tracks() -> list[Track]:
    """執行所有擷取器，回傳尚未紀錄的新曲目。"""
    conn = init_db()
    new_tracks: list[Track] = []

    for scraper in ALL_SCRAPERS:
        try:
            tracks = scraper.fetch_tracks()
            for track in tracks:
                # 比對資料庫，過濾已存在的曲目
                if not track_exists(conn, track.artist, track.title):
                    new_tracks.append(track)
        except Exception as e:
            # 單一擷取器失敗不影響其他來源
            logger.warning(f"{scraper.name} 擷取失敗：{e}")

    conn.close()
    return new_tracks


def run(dry_run: bool = False) -> None:
    """主流程：擷取 → Spotify 搜尋 → 備份 → 通知。"""
    logger.info("開始音樂蒐集...")

    new_tracks = collect_tracks()
    logger.info(f"發現 {len(new_tracks)} 首新曲目")

    if not new_tracks:
        logger.info("今日無新曲目。")
        return

    # 乾跑模式：僅列出擷取結果，不操作 Spotify / 不備份 / 不通知
    if dry_run:
        logger.info("乾跑模式 — 僅列出擷取結果：")
        for t in new_tracks:
            print(f"  [{t.source}] {t.artist} — {t.title}")
        return

    # 連接 Spotify 並取得或建立播放清單
    sp = get_spotify_client()
    playlist_id = get_or_create_playlist(sp)

    # 一次性合併舊播放清單（找不到則自動跳過）
    try:
        migrate_old_playlist(sp, playlist_id)
    except Exception as e:
        logger.warning(f"舊播放清單合併失敗：{e}")

    # 季度歸檔：將前季曲目移至歸檔清單
    try:
        archive_previous_quarters(sp, playlist_id)
    except Exception as e:
        logger.warning(f"季度歸檔失敗：{e}")

    conn = init_db()
    spotify_uris: list[str] = []
    not_found: list[Track] = []
    spotify_results: dict[tuple[str, str], str | None] = {}

    # 逐首搜尋 Spotify 並儲存結果
    for track in new_tracks:
        try:
            uri = search_track(sp, track.artist, track.title)
            if uri:
                spotify_uris.append(uri)
                spotify_results[(track.artist, track.title)] = uri
                save_track(conn, track.artist, track.title, track.source, uri)
                logger.info(f"  找到：{track.artist} — {track.title}")
            else:
                not_found.append(track)
                spotify_results[(track.artist, track.title)] = None
                save_track(conn, track.artist, track.title, track.source, None)
                logger.warning(f"  Spotify 未找到：{track.artist} — {track.title}")
        except Exception as e:
            logger.warning(f"  搜尋失敗：{track.artist} — {track.title}: {e}")

    conn.close()

    # 批次加入播放清單
    if spotify_uris:
        add_tracks_to_playlist(sp, playlist_id, spotify_uris)
        logger.info(f"已加入 {len(spotify_uris)} 首曲目至播放清單")

    if not_found:
        logger.info(f"{len(not_found)} 首曲目在 Spotify 上未找到")

    # 備份至月度 JSON
    try:
        save_backup(new_tracks, spotify_results)
    except Exception as e:
        logger.warning(f"備份失敗：{e}")

    # LINE 通知
    try:
        send_notification(new_tracks, spotify_uris, not_found)
    except Exception as e:
        logger.warning(f"LINE 通知失敗：{e}")

    logger.info("完成。")


def show_recent(days: int = 7) -> None:
    """顯示最近 N 天蒐集的曲目紀錄。"""
    conn = init_db()
    tracks = get_recent_tracks(conn, days=days)
    conn.close()

    if not tracks:
        print(f"最近 {days} 天內無蒐集紀錄。")
        return

    print(f"\n最近 {days} 天蒐集的曲目（共 {len(tracks)} 首）：\n")
    for t in tracks:
        status = "已加入 Spotify" if t["spotify_uri"] else "未找到"
        print(f"  [{t['source']}] {t['artist']} — {t['title']} ({status})")


def main() -> None:
    """CLI 進入點：解析命令列參數並執行對應功能。"""
    parser = argparse.ArgumentParser(description="從音樂評論網站蒐集推薦曲目")
    parser.add_argument("--dry-run", action="store_true", help="僅擷取，不寫入 Spotify")
    parser.add_argument("--recent", type=int, metavar="DAYS", help="顯示最近 N 天蒐集的曲目")
    args = parser.parse_args()

    if args.recent is not None:
        show_recent(days=args.recent)
    else:
        run(dry_run=args.dry_run)
