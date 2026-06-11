"""清理模組：優化磁碟空間，清除快取、舊日誌、匯出檔案與過期的瀏覽器。

支援清理：
1. Python/工具快取：__pycache__、.pytest_cache、.ruff_cache、.sisyphus
2. 系統日誌與匯出：prod-run-*.log、舊的 apple_music_recovery.log、data/exports/*.csv、data/exports/*.txt
3. 資料庫優化：對 tracks.db 執行 VACUUM 壓縮
4. 瀏覽器快取：清理 Playwright 在系統中產生的舊版本 (obsolete) 瀏覽器複本
"""

import os
import shutil
import sqlite3
import sys
from pathlib import Path
from datetime import datetime, timedelta

from .config import PROJECT_ROOT, DATA_DIR, DB_PATH, ENABLE_PLAYWRIGHT

# 定義快取與暫存目錄
CACHE_DIRS = [
    PROJECT_ROOT / ".pytest_cache",
    PROJECT_ROOT / ".ruff_cache",
    PROJECT_ROOT / ".sisyphus",
]

def format_size(size_in_bytes: int) -> str:
    """將位元組轉換為易讀的格式。"""
    for unit in ["B", "KB", "MB", "GB"]:
        if size_in_bytes < 1024.0:
            return f"{size_in_bytes:.2f} {unit}"
        size_in_bytes /= 1024.0
    return f"{size_in_bytes:.2f} TB"

def get_dir_size(path: Path) -> int:
    """計算目錄總大小（以位元組為單位）。"""
    total = 0
    if not path.exists():
        return 0
    try:
        if path.is_file() or path.is_symlink():
            return path.stat().st_size
        for entry in os.scandir(path):
            entry_path = Path(entry.path)
            if entry.is_file(follow_symlinks=False):
                total += entry.stat().st_size
            elif entry.is_dir(follow_symlinks=False):
                total += get_dir_size(entry_path)
    except Exception:
        pass
    return total

def get_playwright_cache_dir() -> Path | None:
    """跨平台取得 Playwright 預設瀏覽器快取路徑。"""
    home = Path.home()
    if sys.platform == "darwin":
        return home / "Library/Caches/ms-playwright"
    elif sys.platform == "win32":
        local_app_data = os.environ.get("LOCALAPPDATA")
        if local_app_data:
            return Path(local_app_data) / "ms-playwright"
        return home / "AppData/Local/ms-playwright"
    else:  # linux or others
        xdg_cache = os.environ.get("XDG_CACHE_HOME")
        if xdg_cache:
            return Path(xdg_cache) / "ms-playwright"
        return home / ".cache/ms-playwright"

def clean_python_caches(dry_run: bool = False) -> tuple[int, int]:
    """清除 Python 快取與暫存檔。

    Returns:
        (清除的目錄數, 釋放的位元組)
    """
    freed_bytes = 0
    cleaned_count = 0

    print("🧹 [1/4] 開始清理 Python 與工具快取...")

    # 1. 清理 CACHE_DIRS
    for cache_dir in CACHE_DIRS:
        if cache_dir.exists():
            size = get_dir_size(cache_dir)
            freed_bytes += size
            cleaned_count += 1
            print(f"   - 快取目錄: {cache_dir.relative_to(PROJECT_ROOT)} ({format_size(size)})")
            if not dry_run:
                try:
                    shutil.rmtree(cache_dir)
                except Exception as e:
                    print(f"     ⚠️ 無法刪除 {cache_dir}: {e}")

    # 2. 遞迴清理 __pycache__
    for root, dirs, files in os.walk(PROJECT_ROOT):
        # 排除 .venv
        if ".venv" in root:
            continue
        for d in dirs:
            if d == "__pycache__":
                pycache_path = Path(root) / d
                size = get_dir_size(pycache_path)
                freed_bytes += size
                cleaned_count += 1
                try:
                    rel_path = pycache_path.relative_to(PROJECT_ROOT)
                except ValueError:
                    rel_path = pycache_path
                print(f"   - Python 快取: {rel_path} ({format_size(size)})")
                if not dry_run:
                    try:
                        shutil.rmtree(pycache_path)
                    except Exception as e:
                        print(f"     ⚠️ 無法刪除 {pycache_path}: {e}")

    return cleaned_count, freed_bytes

def clean_logs_and_exports(dry_run: bool = False, keep_days: int = 3) -> tuple[int, int]:
    """清除舊日誌、歷史執行紀錄與匯出的 CSV/TXT 檔案。

    Returns:
        (清除的檔案數, 釋放的位元組)
    """
    freed_bytes = 0
    cleaned_count = 0
    print("🧹 [2/4] 開始清理日誌與歷史匯出檔案...")

    now = datetime.now()
    cutoff_date = now - timedelta(days=keep_days)

    # 1. 清理 data/ 下的日誌檔
    if DATA_DIR.exists():
        for file in DATA_DIR.glob("*.log"):
            # 排除 collector.log (我們之後做截斷)
            if file.name == "collector.log":
                continue
            
            # 檢查檔案時間，保留 keep_days 內的新檔案
            file_mtime = datetime.fromtimestamp(file.stat().st_mtime)
            if file_mtime < cutoff_date:
                size = file.stat().st_size
                freed_bytes += size
                cleaned_count += 1
                print(f"   - 歷史日誌: data/{file.name} ({format_size(size)}) [建立於 {file_mtime.strftime('%Y-%m-%d')}]")
                if not dry_run:
                    try:
                        file.unlink()
                    except Exception as e:
                        print(f"     ⚠️ 無法刪除 {file.name}: {e}")

        # 截斷 collector.log
        collector_log = DATA_DIR / "collector.log"
        if collector_log.exists() and collector_log.stat().st_size > 0:
            size = collector_log.stat().st_size
            freed_bytes += size
            print(f"   - 系統日誌截斷: data/collector.log (原大小 {format_size(size)})")
            if not dry_run:
                try:
                    with open(collector_log, "w") as f:
                        f.truncate(0)
                except Exception as e:
                    print(f"     ⚠️ 無法截斷 collector.log: {e}")

    # 2. 清理 data/exports/ 下的 CSV/TXT 檔
    export_dir = DATA_DIR / "exports"
    if export_dir.exists():
        for file in export_dir.glob("*"):
            if file.is_file() and file.name != ".gitkeep":
                file_mtime = datetime.fromtimestamp(file.stat().st_mtime)
                if file_mtime < cutoff_date:
                    size = file.stat().st_size
                    freed_bytes += size
                    cleaned_count += 1
                    print(f"   - 歷史匯出: data/exports/{file.name} ({format_size(size)}) [建立於 {file_mtime.strftime('%Y-%m-%d')}]")
                    if not dry_run:
                        try:
                            file.unlink()
                        except Exception as e:
                            print(f"     ⚠️ 無法刪除 {file.name}: {e}")

    return cleaned_count, freed_bytes

def optimize_database(dry_run: bool = False) -> tuple[int, int]:
    """執行 SQLite 資料庫的 VACUUM，釋放未使用的空間並進行優化。

    Returns:
        (壓縮次數, 釋放的位元組)
    """
    print("🧹 [3/4] 開始優化 SQLite 資料庫...")
    if not DB_PATH.exists():
        print("   - 資料庫檔案不存在，略過優化。")
        return 0, 0

    original_size = DB_PATH.stat().st_size
    if dry_run:
        print(f"   - 預計對 tracks.db 進行壓縮優化 (目前大小 {format_size(original_size)})")
        return 1, 0

    try:
        conn = sqlite3.connect(DB_PATH)
        conn.execute("VACUUM")
        conn.close()
        
        new_size = DB_PATH.stat().st_size
        freed = original_size - new_size
        if freed > 0:
            print(f"   ✨ tracks.db 壓縮成功！ {format_size(original_size)} ➡️ {format_size(new_size)} (釋放了 {format_size(freed)})")
            return 1, freed
        else:
            print(f"   - tracks.db 已處於最優狀態 ({format_size(original_size)})")
            return 1, 0
    except Exception as e:
        print(f"   ⚠️ 資料庫優化失敗: {e}")
        return 0, 0

def clean_playwright_browsers(dry_run: bool = False) -> tuple[int, int]:
    """清理 Playwright 舊版本或多餘的瀏覽器快取。

    若未啟用 Playwright，可選擇一併提示完全清除或只保留最新版本。

    Returns:
        (清除的版本目錄數, 釋放的位元組)
    """
    print("🧹 [4/4] 開始檢測 Playwright 瀏覽器快取...")
    pw_cache = get_playwright_cache_dir()
    if not pw_cache or not pw_cache.exists():
        print("   - 未檢測到 Playwright 快取目錄，略過。")
        return 0, 0

    total_size = get_dir_size(pw_cache)
    print(f"   - 檢測到快取目錄: {pw_cache} (總大小 {format_size(total_size)})")

    # 找出各個瀏覽器類型（如 chromium, ffmpeg 等）的版本目錄
    # 例如：chromium-1208, chromium-1217 等
    categories: dict[str, list[tuple[int, Path]]] = {}
    
    try:
        for p in pw_cache.iterdir():
            if p.is_dir():
                # 匹配如 chromium-1217 或 ffmpeg-1011 等格式
                name = p.name
                if "-" in name:
                    parts = name.rsplit("-", 1)
                    prefix = parts[0]
                    suffix = parts[1]
                    try:
                        version = int(suffix)
                        categories.setdefault(prefix, []).append((version, p))
                    except ValueError:
                        pass
    except Exception as e:
        print(f"   ⚠️ 讀取 Playwright 快取目錄失敗: {e}")
        return 0, 0

    cleaned_count = 0
    freed_bytes = 0

    # 依類別整理並保留最新版，刪除舊版
    for prefix, versions in categories.items():
        if not versions:
            continue
        # 依版本號排序，找出最新的一個
        versions.sort(key=lambda x: x[0])
        latest_version, latest_path = versions[-1]
        
        # 舊版本需要被刪除
        obsolete_versions = versions[:-1]
        if obsolete_versions:
            print(f"   - 發現 {prefix} 有多個版本複本。將保留最新版 {latest_version}，清理以下舊版本：")
            for ver, path in obsolete_versions:
                size = get_dir_size(path)
                freed_bytes += size
                cleaned_count += 1
                print(f"     🗑️ 舊版本: {path.name} ({format_size(size)})")
                if not dry_run:
                    try:
                        shutil.rmtree(path)
                    except Exception as e:
                        print(f"       ⚠️ 無法刪除 {path.name}: {e}")
        else:
            print(f"   - {prefix} 僅有單一版本 {latest_version}，無舊版本需清理。")

    # 如果根本沒有開啟 Playwright 功能 (ENABLE_PLAYWRIGHT=False)，
    # 提醒使用者可以考慮完全移除 ms-playwright 快取以節省大量空間。
    if not ENABLE_PLAYWRIGHT and total_size > freed_bytes:
        remaining_size = total_size - freed_bytes
        print("\n   💡 溫馨提示：目前設定檔中並未啟用 Playwright 瀏覽器渲染 (ENABLE_PLAYWRIGHT=false)。")
        print(f"      Playwright 目前仍佔用 {format_size(remaining_size)} 的空間。")
        print("      若您平時不需要使用 Playwright，可手動執行以下命令完全清空它來釋放空間：")
        print(f"      rm -rf \"{pw_cache}\"")

    return cleaned_count, freed_bytes

def clean_all(dry_run: bool = False, keep_days: int = 3) -> None:
    """執行完整專案清理流程。"""
    action_str = " (預演模式，不實際刪除檔案)" if dry_run else ""
    print("============================================================")
    print(f"⚡ 開始執行 Music Collector 磁碟優化與清理程序{action_str} ⚡")
    print("============================================================")

    # 執行各步驟
    cleaned_caches, freed_caches = clean_python_caches(dry_run)
    print()
    cleaned_logs, freed_logs = clean_logs_and_exports(dry_run, keep_days)
    print()
    db_optimized, freed_db = optimize_database(dry_run)
    print()
    cleaned_pw, freed_pw = clean_playwright_browsers(dry_run)
    print()

    total_freed = freed_caches + freed_logs + freed_db + freed_pw
    
    print("============================================================")
    print("🏁 清理完成！報告總結：")
    print("============================================================")
    print(f"   - Python 與工具快取：清理了 {cleaned_caches} 個目錄/檔案，釋放 {format_size(freed_caches)}")
    print(f"   - 系統日誌與歷史匯出：清理了 {cleaned_logs} 個檔案，釋放 {format_size(freed_logs)}")
    print(f"   - SQLite 資料庫優化 ：完成對 tracks.db 的優化與壓縮，釋放 {format_size(freed_db)}")
    print(f"   - Playwright 瀏覽器 ：清理了 {cleaned_pw} 個舊版瀏覽器複本，釋放 {format_size(freed_pw)}")
    print("------------------------------------------------------------")
    if dry_run:
        print(f"   💡 預計總共可釋放空間：{format_size(total_freed)}")
    else:
        print(f"   🎉 實際總共釋放空間：{format_size(total_freed)}")
        final_size = get_dir_size(PROJECT_ROOT)
        print(f"   📦 專案目前占用空間：{format_size(final_size)}")
    print("============================================================")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="清理並優化 music-collector 專案磁碟空間")
    parser.add_argument("--dry-run", action="store_true", help="僅預演，不實際刪除檔案")
    parser.add_argument("--keep-days", type=int, default=3, help="保留最近 N 天內的日誌與歷史匯出檔案（預設: 3）")
    args = parser.parse_args()
    
    clean_all(dry_run=args.dry_run, keep_days=args.keep_days)
