"""全域測試 fixtures。"""

from pathlib import Path

import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "html"


@pytest.fixture
def fixture_dir() -> Path:
    """回傳 HTML fixture 目錄路徑。"""
    return FIXTURES_DIR


def load_fixture(name: str) -> str:
    """讀取 HTML fixture 檔案。"""
    return (FIXTURES_DIR / name).read_text(encoding="utf-8")


@pytest.fixture(autouse=True)
def _isolated_playlist_cache(tmp_path, monkeypatch):
    """歌單快取寫到暫存目錄，不碰真的 data/playlist_cache.json。"""
    from music_collector import spotify

    monkeypatch.setattr(spotify, "PLAYLIST_CACHE_PATH", tmp_path / "playlist_cache.json")
