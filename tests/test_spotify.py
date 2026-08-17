from unittest.mock import Mock

from music_collector.config import ALL_TIME_PLAYLIST_NAME, PLAYLIST_NAME
from music_collector.spotify import backfill_all_time, mirror_to_all_time, search_track


def _mock_sp(playlists: list[dict], items_by_id: dict[str, list[str]]) -> Mock:
    """建立回傳固定歌單與曲目的 Spotify 客戶端 mock。"""
    sp = Mock()
    sp.current_user.return_value = {"id": "henry"}
    sp.current_user_playlists.return_value = {"items": playlists, "next": None}
    sp.playlist_items.side_effect = lambda pid, **kw: {
        "items": [
            {"track": {"uri": uri}, "added_at": "2026-08-01T00:00:00Z"}
            for uri in items_by_id.get(pid, [])
        ],
        "next": None,
    }
    return sp


def test_search_track_uses_primary_artist_for_feature():
    item = {
        "name": "La Monda",
        "artists": [{"name": "De La Rose"}, {"name": "Ryan Castro"}],
        "uri": "spotify:track:7cIyY45Uw7NIWkVt3QkbsH",
    }
    sp = Mock()
    sp.search.return_value = {"tracks": {"items": [item]}}

    assert search_track(sp, "De La Rose feat. Ryan Castro", "La Monda") == item["uri"]
    sp.search.assert_called_once_with(
        q="track:La Monda artist:De La Rose", type="track", limit=5,
    )


def test_mirror_to_all_time_skips_existing_uris():
    """已在 All Time 歌單中的曲目不應重複加入。"""
    sp = _mock_sp(
        playlists=[{"id": "all", "name": ALL_TIME_PLAYLIST_NAME}],
        items_by_id={"all": ["spotify:track:a"]},
    )

    added = mirror_to_all_time(sp, ["spotify:track:a", "spotify:track:b"])

    assert added == 1
    sp.playlist_add_items.assert_called_once_with("all", ["spotify:track:b"])


def test_mirror_to_all_time_dedupes_within_incoming_batch():
    """傳入清單自身若有重複也只能加一次。

    backfill_all_time() 會把主歌單與各季歸檔串接後一次送入，同一首歌若同時
    存在於多個來源歌單就會重複出現，只比對「歌單既有內容」擋不住。
    """
    sp = _mock_sp(
        playlists=[{"id": "all", "name": ALL_TIME_PLAYLIST_NAME}],
        items_by_id={"all": []},
    )

    added = mirror_to_all_time(
        sp, ["spotify:track:a", "spotify:track:b", "spotify:track:a"]
    )

    assert added == 2
    sp.playlist_add_items.assert_called_once_with(
        "all", ["spotify:track:a", "spotify:track:b"]
    )


def test_backfill_all_time_collects_main_and_archives_only():
    """回填應涵蓋主歌單與季度歸檔，但不得把 All Time 自己當成來源。"""
    sp = _mock_sp(
        playlists=[
            {"id": "main", "name": PLAYLIST_NAME},
            {"id": "q1", "name": "Critics' Picks — 2026 Q1"},
            {"id": "all", "name": ALL_TIME_PLAYLIST_NAME},
            {"id": "other", "name": "Road Trip"},
        ],
        items_by_id={
            "main": ["spotify:track:a"],
            "q1": ["spotify:track:b"],
            "all": [],
            "other": ["spotify:track:z"],
        },
    )

    added = backfill_all_time(sp)

    assert added == 2
    sp.playlist_add_items.assert_called_once_with(
        "all", ["spotify:track:a", "spotify:track:b"]
    )
