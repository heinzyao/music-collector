"""主流程模組：調度擷取、去重、搜尋、備份、通知的完整流程。

使用方式：
    python -m music_collector              # 完整執行
    python -m music_collector --dry-run    # 僅擷取，不寫入 Spotify / 不備份 / 不通知
    python -m music_collector --recent 7   # 顯示最近 7 天蒐集的曲目
    python -m music_collector --backup     # 列出所有備份
    python -m music_collector --backup Q1  # 顯示指定季度備份內容
    python -m music_collector --export Q1  # 匯出 Q1 為 CSV
    python -m music_collector --export Q1 --format txt  # 匯出為純文字
    python -m music_collector --backfill-all-time  # 回填 All Time 累積歌單
    python -m music_collector --reset      # 清除歌單與資料庫，重新蒐集
"""

import argparse
import asyncio
import logging
from pathlib import Path

from .backup import list_backups, save_backup, show_backup
from .export import (
    export_playlist,
    export_spotify_url,
)
from .stats import show_stats
from .config import DB_PATH
from .db import init_db, save_track, track_exists, get_recent_tracks
from .health import (
    get_health_report,
    get_unhealthy_sources,
    prune_old_checks,
    record_scrape_result,
)
from .notify import (
    send_error_notification,
    send_no_new_tracks_notification,
    send_notification,
    send_source_health_notification,
)
from .scrapers import ALL_SCRAPERS
from .scrapers.base import Track
from .spotify import (
    add_tracks_to_playlist,
    archive_previous_quarters,
    backfill_all_time,
    clear_playlist,
    get_or_create_playlist,
    get_spotify_client,
    migrate_old_playlist,
    mirror_to_all_time,
    search_track,
)

# 設定日誌格式
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def _fetch_from_scraper(scraper) -> tuple[str, list[Track], str | None]:
    """執行單一擷取器，回傳 (scraper name, tracks, error)。錯誤時回傳空列表與錯誤訊息。"""
    try:
        return scraper.name, scraper.fetch_tracks(), None
    except Exception as e:
        logger.warning(f"{scraper.name} 擷取失敗：{e}")
        return scraper.name, [], str(e)


def collect_tracks() -> list[Track]:
    """平行執行所有擷取器，回傳尚未紀錄的新曲目。

    使用 asyncio.to_thread 將各擷取器的同步 fetch_tracks() 發送至
    執行緒池平行執行，避免 I/O 等待時間疊加。15 個來源原本依序約需
    30-60 秒，平行化後約 5-10 秒。
    同時記錄各來源健康狀態到 source_checks 資料表。
    """

    async def _collect_all() -> list[tuple[str, list[Track], str | None]]:
        tasks = [
            asyncio.to_thread(_fetch_from_scraper, scraper) for scraper in ALL_SCRAPERS
        ]
        return await asyncio.gather(*tasks)

    results = asyncio.run(_collect_all())

    conn = init_db()
    new_tracks: list[Track] = []
    seen_in_run: set[tuple[str, str]] = set()

    for scraper_name, tracks, error in results:
        record_scrape_result(conn, scraper_name, len(tracks), error)
        for track in tracks:
            key = (track.artist.strip().lower(), track.title.strip().lower())
            if key in seen_in_run:
                continue
            if not track_exists(conn, track.artist, track.title):
                new_tracks.append(track)
                seen_in_run.add(key)

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
    """主流程：擷取 → Spotify 搜尋 → All Time 鏡射 → 備份 → 季度歸檔 → 通知。"""
    logger.info("開始音樂蒐集...")

    new_tracks = collect_tracks()
    logger.info(f"發現 {len(new_tracks)} 首新曲目")

    if not new_tracks:
        logger.info("今日無新曲目。")
        if not dry_run:
            try:
                send_no_new_tracks_notification()
            except Exception as e:
                logger.warning(f"通知失敗：{e}")
            return

    # 乾跑模式：僅列出擷取結果，不操作 Spotify / 不備份 / 不通知
    if dry_run:
        if new_tracks:
            logger.info("乾跑模式 — 僅列出擷取結果：")
            for t in new_tracks:
                print(f"  [{t.source}] {t.artist} — {t.title}")
        return

    # Spotify 更新（僅有新曲目時執行）
    spotify_uris: list[str] = []
    not_found: list[Track] = []

    if new_tracks:
        # 連接 Spotify 並取得或建立播放清單。
        # 授權失效（refresh token 被撤銷）會讓整個排程靜默失敗，所以在此攔截並通知。
        try:
            sp = get_spotify_client()
            playlist_id = get_or_create_playlist(sp)
        except Exception as e:
            logger.error(f"Spotify 認證或連線失敗：{e}")
            try:
                send_error_notification(
                    "Spotify 連線失敗",
                    str(e),
                    "請刪除 .spotify_cache 後執行 ./run.sh 重新完成瀏覽器授權。",
                )
            except Exception as notify_error:
                logger.warning(f"通知失敗：{notify_error}")
            return

        # 一次性合併舊播放清單（找不到則自動跳過）
        try:
            migrate_old_playlist(sp, playlist_id)
        except Exception as e:
            logger.warning(f"舊播放清單合併失敗：{e}")

        conn = init_db()
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
            # 實際加入數由 add_tracks_to_playlist() 自行記錄（去重後可能少於送入數）
            add_tracks_to_playlist(sp, playlist_id, spotify_uris)

            # 同步鏡射至 All Time 累積歌單。
            # 失敗不影響主流程：下次執行或 --backfill-all-time 都會補回。
            try:
                mirror_to_all_time(sp, spotify_uris)
            except Exception as e:
                logger.warning(f"All Time 累積歌單鏡射失敗：{e}")

        if not_found:
            logger.info(f"{len(not_found)} 首曲目在 Spotify 上未找到")

        # 備份至季度 JSON
        try:
            save_backup(new_tracks, spotify_results)
        except Exception as e:
            logger.warning(f"備份失敗：{e}")

    # 季度歸檔：將前季曲目從 Spotify 主歌單移至歸檔清單。
    # All Time 累積歌單不受影響，仍保有完整歷史。
    try:
        sp_archive = get_spotify_client()
        pid_archive = get_or_create_playlist(sp_archive)
        archive_previous_quarters(sp_archive, pid_archive)
    except Exception as e:
        logger.warning(f"季度歸檔失敗：{e}")

    unhealthy_sources = []
    try:
        conn_health = init_db()
        source_names = [s.name for s in ALL_SCRAPERS]
        unhealthy_sources = get_unhealthy_sources(conn_health, source_names)
        prune_old_checks(conn_health)
        conn_health.close()
    except Exception as e:
        logger.warning(f"來源健康檢查失敗：{e}")

    if unhealthy_sources:
        try:
            send_source_health_notification(unhealthy_sources)
        except Exception as e:
            logger.warning(f"來源健康通知失敗：{e}")

    # 通知（LINE / Telegram / Slack）
    try:
        send_notification(new_tracks, spotify_uris, not_found, unhealthy_sources)
    except Exception as e:
        logger.warning(f"通知失敗：{e}")

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


def show_health() -> None:
    """顯示所有擷取器來源的健康狀態報告。"""
    conn = init_db()
    source_names = [s.name for s in ALL_SCRAPERS]
    report = get_health_report(conn, source_names)
    conn.close()
    print("\n" + report)


def backfill_all_time_playlist() -> bool:
    """把主歌單與所有季度歸檔歌單回填進 All Time 累積歌單。"""
    from .config import ALL_TIME_PLAYLIST_NAME

    try:
        sp = get_spotify_client()
    except Exception as e:
        print(f"錯誤：無法連線 Spotify — {e}")
        return False

    added = backfill_all_time(sp)
    print(f"\n✅ 「{ALL_TIME_PLAYLIST_NAME}」新增 {added} 首曲目")
    return True


def main() -> None:
    """CLI 進入點：解析命令列參數並執行對應功能。"""
    parser = argparse.ArgumentParser(description="從音樂評論網站蒐集推薦曲目")
    parser.add_argument("--dry-run", action="store_true", help="僅擷取，不寫入 Spotify")
    parser.add_argument(
        "--recent", type=int, metavar="DAYS", help="顯示最近 N 天蒐集的曲目"
    )
    parser.add_argument(
        "--backup",
        nargs="?",
        const="",
        metavar="QUARTER",
        help="檢視備份：不帶參數列出所有備份，帶季度（如 Q1、2026Q1）顯示詳情",
    )
    parser.add_argument(
        "--export",
        metavar="QUARTER",
        help="匯出季度備份為 CSV 或 TXT",
    )
    parser.add_argument(
        "--format",
        choices=["csv", "txt"],
        default="csv",
        help="匯出格式：csv（預設）或 txt（純文字）",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        dest="include_all",
        help="匯出時包含未在 Spotify 找到的曲目",
    )
    parser.add_argument(
        "--reset", action="store_true", help="清除 Spotify 歌單與資料庫，重新蒐集"
    )
    parser.add_argument(
        "--export-spotify-url",
        action="store_true",
        help="輸出主歌單與 All Time 累積歌單的 Spotify 連結與曲目數",
    )
    parser.add_argument(
        "--stats",
        nargs="?",
        const="",
        metavar="SUBCOMMAND",
        help="資料分析：不帶參數顯示總覽，overlap 顯示重疊分析，sources 顯示來源比較",
    )
    parser.add_argument("--web", action="store_true", help="啟動 Streamlit Web 介面")
    parser.add_argument(
        "--backfill-all-time",
        action="store_true",
        dest="backfill_all_time",
        help="將主歌單與所有季度歸檔歌單回填至「All Time」累積歌單",
    )
    parser.add_argument(
        "--health",
        action="store_true",
        help="顯示各擷取器來源的健康狀態報告",
    )
    parser.add_argument(
        "--clean",
        action="store_true",
        help="清理快取、暫存、舊日誌、匯出檔案，優化資料庫與 Playwright 瀏覽器快取",
    )
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
    elif args.backfill_all_time:
        raise SystemExit(0 if backfill_all_time_playlist() else 1)
    elif args.health:
        show_health()
    elif args.clean:
        from .clean import clean_all
        clean_all(dry_run=args.dry_run)
    else:
        run(dry_run=args.dry_run)
