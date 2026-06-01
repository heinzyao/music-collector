"""Apple Music手動匯入機制測試。"""

import csv
from pathlib import Path
import pytest

from music_collector.apple_music import api


def test_load_token_file_returns_dummy_values() -> None:
    """測試相容性的 Token 載入函式回傳 Dummy 值。"""
    dev, user = api._load_token_file()
    assert dev == "dummy_dev_token"
    assert user == "dummy_user_token"


def test_validate_session_always_returns_true() -> None:
    """測試 Session 驗證在手動匯入模式下恆為 True。"""
    assert api._validate_session("dev", "user") is True


def test_import_to_apple_music_creates_tab_separated_txt_file(tmp_path: Path) -> None:
    """測試 import_to_apple_music 能從 CSV 正確生成適合 Apple Music 匯入的 TXT 檔案。"""
    csv_file = tmp_path / "Critics_Picks.csv"
    
    # 建立測試 CSV 資料
    with csv_file.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Artist", "Title"])
        writer.writerow(["Radiohead", "Creep"])
        writer.writerow(["Massive Attack", "Teardrop"])

    # 執行轉換匯入流程
    result = api.import_to_apple_music(str(csv_file), playlist_name="Test Playlist")
    assert result is True

    # 驗證是否產生了對應的 TXT 檔案
    txt_file = tmp_path / "Critics_Picks_Apple_Music.txt"
    assert txt_file.exists()

    # 讀取並驗證 TXT 檔案格式
    lines = txt_file.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 3
    assert lines[0] == "Name\tArtist\tAlbum"
    assert lines[1] == "Creep\tRadiohead\t"
    assert lines[2] == "Teardrop\tMassive Attack\t"


def test_import_to_apple_music_returns_false_when_csv_missing() -> None:
    """測試當 CSV 檔案不存在時應回傳 False。"""
    result = api.import_to_apple_music("nonexistent.csv")
    assert result is False
