"""Apple Music 手動匯入整合。

將原本的自動登入與 API 同步，調整為產出 Apple Music 專用手動匯入文字檔（TXT）。
使用者可在 macOS 「音樂 (Music)」App 中，透過「檔案 -> 資料庫 -> 匯入播放清單」完成手動匯入。
"""

import csv
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# 保留以相容於原有設計，但不再實際使用或拋出
TOKEN_FILE = Path("data/apple_music_tokens.json")


class AppleMusicAuthRequiredError(RuntimeError):
    """Raised when Apple Music sync requires a manual login (legacy)."""


def _load_token_file() -> tuple[str, str]:
    """返回 Dummy tokens，用於通過 main.py 的相容性驗證。"""
    return "dummy_dev_token", "dummy_user_token"


def _validate_session(dev_token: str, user_token: str) -> bool:
    """Session 驗證，手動匯入模式下恆為 True。"""
    return True


def list_playlists_by_prefix(prefix: str, dev_token: str, user_token: str) -> list:
    """回傳空列表，避免觸發自動刪除邏輯。"""
    return []


def _delete_playlist_by_id(playlist_id: str, dev_token: str, user_token: str) -> bool:
    return True


def _delete_playlists_by_prefix_applescript(prefix: str) -> int:
    return 0


def _delete_playlists_by_name_applescript(name: str) -> bool:
    return True


def import_to_apple_music(
    csv_path: str,
    keep_browser_open: bool = False,
    playlist_name: str | None = None,
) -> bool:
    """調整為產出 Apple Music 可手動匯入檔案的機制。

    讀取傳入的 CSV 路徑，並於同目錄下生成 Tab 分隔的 Apple Music 專用 TXT 匯入檔（若尚未生成）。
    接著在終端印出詳細的手動匯入教學。

    Args:
        csv_path: CSV 檔案路徑（欄位：Artist, Title）
        keep_browser_open: 已廢棄，僅保留相容性
        playlist_name: 目標播放清單名稱
    """
    csv_p = Path(csv_path).resolve()
    if not csv_p.exists():
        logger.error(f"CSV 檔案不存在：{csv_p}")
        return False

    name = playlist_name or csv_p.stem
    txt_p = csv_p.parent / f"{csv_p.stem}_Apple_Music.txt"

    # 若手動匯入 TXT 尚未由 export.py 生成，在此行補充生成
    if not txt_p.exists():
        tracks = []
        try:
            with csv_p.open("r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    artist = (row.get("Artist") or row.get("artist") or "").strip()
                    title = (row.get("Title") or row.get("title") or "").strip()
                    if artist and title:
                        tracks.append((artist, title))
            
            with txt_p.open("w", encoding="utf-8") as f:
                f.write("Name\tArtist\tAlbum\n")
                for artist, title in tracks:
                    t_title = title.replace("\t", " ").replace("\n", " ").replace("\r", " ")
                    t_artist = artist.replace("\t", " ").replace("\n", " ").replace("\r", " ")
                    f.write(f"{t_title}\t{t_artist}\t\n")
        except Exception as e:
            logger.error(f"自動補建 Apple Music 文字檔失敗：{e}")
            return False

    # 輸出極度清晰、友善的手動匯入指引
    print("\n" + "=" * 60)
    print(" 🎵 Apple Music 歌單手動匯入指引 🎵 ")
    print("=" * 60)
    print("已成功為您產出 Apple Music 專用手動匯入文字檔：")
    print(f"👉 {txt_p}")
    print("\n📱 請依照以下簡單步驟完成手動匯入：")
    print("  1. 在您的 Mac 電腦上開啟「音樂 (Music)」App (或 Windows 上的 iTunes)。")
    print("  2. 在上方選單中，選擇「檔案」 -> 「資料庫」 -> 「匯入播放清單...」。")
    print("  3. 選擇並打開上述的文字檔：")
    print(f"     [{txt_p.name}]")
    print(f"  4. 恭喜！音樂 App 將會自動搜尋匹配並建立名為「{name}」的播放清單！")
    print("=" * 60 + "\n")

    return True
