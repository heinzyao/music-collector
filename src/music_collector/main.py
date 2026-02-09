"""主流程模組：調度擷取、去重、搜尋、備份、通知的完整流程。

使用方式：
    python -m music_collector              # 完整執行
    python -m music_collector --dry-run    # 僅擷取，不寫入 Spotify / 不備份 / 不通知
    python -m music_collector --recent 7   # 顯示最近 7 天蒐集的曲目
    python -m music_collector --backup     # 列出所有備份
    python -m music_collector --backup Q1  # 顯示指定季度備份內容
    python -m music_collector --export Q1  # 匯出 Q1 為 CSV（供 Apple Music 匯入）
    python -m music_collector --export Q1 --format txt  # 匯出為純文字
    python -m music_collector --import Q1  # 匯出並自動匯入 Apple Music（需瀏覽器）
    python -m music_collector --reset      # 清除歌單與資料庫，重新蒐集
"""

import argparse
import logging
from pathlib import Path

from .backup import list_backups, save_backup, show_backup
from .export import export_playlist, export_spotify_url
from .tunemymusic import import_to_apple_music
from .stats import show_stats
from .config import DB_PATH, PLAYLIST_NAME
from .db import init_db, save_track, track_exists, get_recent_tracks
from .notify import send_notification
from .scrapers import ALL_SCRAPERS
from .scrapers.base import Track
from .spotify import (
    add_tracks_to_playlist,
    archive_previous_quarters,
    clear_playlist,
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


def reset() -> None:
    """清除 Spotify 歌單與本地資料庫，重新蒐集。"""
    logger.info("重置模式：清除歌單與資料庫...")

    # 清除 Spotify 播放清單
    sp = get_spotify_client()
    playlist_id = get_or_create_playlist(sp)
    removed = clear_playlist(sp, playlist_id)
    logger.info(f"已從 Spotify 歌單移除 {removed} 首曲目")

    # 清除本地資料庫
    if DB_PATH.exists():
        DB_PATH.unlink()
        logger.info("已刪除本地資料庫")

    # 重新執行完整蒐集流程
    logger.info("開始重新蒐集...")
    run(dry_run=False)


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

    # 備份至季度 JSON
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
    parser.add_argument("--backup", nargs="?", const="", metavar="QUARTER",
                        help="檢視備份：不帶參數列出所有備份，帶季度（如 Q1、2026Q1）顯示詳情")
    parser.add_argument("--export", metavar="QUARTER",
                        help="匯出備份為 CSV 或 TXT，供 Apple Music 匯入工具使用")
    parser.add_argument("--format", choices=["csv", "txt"], default="csv",
                        help="匯出格式：csv（預設，適用 TuneMyMusic）或 txt（純文字）")
    parser.add_argument("--all", action="store_true", dest="include_all",
                        help="匯出時包含未在 Spotify 找到的曲目")
    parser.add_argument("--reset", action="store_true",
                        help="清除 Spotify 歌單與資料庫，重新蒐集")
    parser.add_argument("--import", metavar="QUARTER", dest="import_quarter",
                        help="匯出備份並自動透過 TuneMyMusic 匯入 Apple Music")
    parser.add_argument("--export-spotify-url", action="store_true",
                        help="輸出 Spotify 播放清單連結，供轉換至 YouTube Music / Tidal 等平台")
    parser.add_argument("--stats", nargs="?", const="", metavar="SUBCOMMAND",
                        help="資料分析：不帶參數顯示總覽，overlap 顯示重疊分析，sources 顯示來源比較")
    parser.add_argument("--web", action="store_true",
                        help="啟動 Streamlit Web 介面")
    args = parser.parse_args()

    if args.web:
        import subprocess
        import sys
        web_path = str(Path(__file__).parent / "web.py")
        subprocess.run([sys.executable, "-m", "streamlit", "run", web_path])
    elif args.stats is not None:
        show_stats(args.stats if args.stats else None)
    elif args.export_spotify_url:
        export_spotify_url()
    elif args.import_quarter:
        # 先匯出為 CSV（使用 Spotify 歌單名稱作為檔名，TuneMyMusic 會用檔名作為目標歌單名）
        csv_path = export_playlist(
            args.import_quarter,
            fmt="csv",
            include_all=args.include_all,
            playlist_name=PLAYLIST_NAME,
        )
        if csv_path:
            import_to_apple_music(str(csv_path))
    elif args.export:
        export_playlist(args.export, fmt=args.format, include_all=args.include_all)
    elif args.backup is not None:
        if args.backup:
            show_backup(args.backup)
        else:
            list_backups()
    elif args.recent is not None:
        show_recent(days=args.recent)
    elif args.reset:
        reset()
    else:
        run(dry_run=args.dry_run)

