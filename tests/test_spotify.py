from unittest.mock import Mock

from music_collector.config import ALL_TIME_PLAYLIST_NAME, PLAYLIST_NAME
from music_collector.spotify import (
    _playlist_items,
    _remove_items,
    add_tracks_to_playlist,
    backfill_all_time,
    get_or_create_playlist,
    mirror_to_all_time,
    search_track,
)


def _mock_sp(playlists: list[dict], items_by_id: dict[str, list[str]]) -> Mock:
    """建立回傳固定歌單與曲目的 Spotify 客戶端 mock。"""
    sp = Mock()
    sp.current_user.return_value = {"id": "henry"}
    for pl in playlists:
        pl.setdefault("owner", {"id": "henry"})  # 未指定 owner 即視為自己的歌單
    sp.current_user_playlists.return_value = {"items": playlists, "next": None}
    sp._get.side_effect = lambda path, **kw: {
        "items": [
            {"item": {"uri": uri}, "added_at": "2026-08-01T00:00:00Z"}
            for uri in items_by_id[path.split("/")[1]]
        ],
        "next": None,
    }
    sp._post.return_value = {"id": "mine"}
    return sp


def _added(sp: Mock) -> list[tuple[str, list[str]]]:
    """回傳所有 POST /items 呼叫的 (playlist_id, uris)。"""
    return [
        (c.args[0].split("/")[1], c.kwargs["payload"]["uris"])
        for c in sp._post.call_args_list
        if c.args[0].endswith("/items")
    ]


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


def test_get_or_create_playlist_ignores_followed_playlist_of_same_name():
    """追蹤中的同名歌單是別人擁有的，不可被當成自己的歌單接手寫入。"""
    sp = _mock_sp(
        playlists=[
            {"id": "theirs", "name": PLAYLIST_NAME, "owner": {"id": "someone_else"}},
        ],
        items_by_id={},
    )
    assert get_or_create_playlist(sp) == "mine"
    sp._post.assert_called_once()
    assert sp._post.call_args.args[0] == "me/playlists"  # /users/{id}/playlists 新 app 被封
    sp.playlist_change_details.assert_not_called()


def test_mirror_to_all_time_skips_existing_uris():
    """已在 All Time 歌單中的曲目不應重複加入。"""
    sp = _mock_sp(
        playlists=[{"id": "all", "name": ALL_TIME_PLAYLIST_NAME}],
        items_by_id={"all": ["spotify:track:a"]},
    )

    added = mirror_to_all_time(sp, ["spotify:track:a", "spotify:track:b"])

    assert added == 1
    assert _added(sp) == [("all", ["spotify:track:b"])]


def test_add_tracks_to_playlist_skips_duplicates():
    """同一首歌被兩個來源以不同 (artist, title) 收錄時，歌單裡只能有一份。

    DB 去重的鍵是 (artist, title)，不同來源對同一首歌的字串寫法可能不同，
    因此兩筆不同的 DB 紀錄可能指向同一個 Spotify URI。
    """
    sp = _mock_sp(
        playlists=[{"id": "main", "name": PLAYLIST_NAME}],
        items_by_id={"main": ["spotify:track:a"]},
    )

    add_tracks_to_playlist(
        sp, "main", ["spotify:track:a", "spotify:track:b", "spotify:track:b"]
    )

    assert _added(sp) == [("main", ["spotify:track:b"])]


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
    assert _added(sp) == [("all", ["spotify:track:a", "spotify:track:b"])]


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
    assert _added(sp) == [("all", ["spotify:track:a", "spotify:track:b"])]


def _search_results(*rounds: list[dict]) -> Mock:
    """建立依序回傳各輪搜尋結果的 mock。"""
    sp = Mock()
    sp.search.side_effect = [{"tracks": {"items": r}} for r in rounds]
    return sp


def test_search_track_retries_without_band_possessive_prefix():
    """Stereogum 寫成「樂團’s 團員」，Spotify 上的藝人是後半段那個人。"""
    item = {
        "name": "Radio Station",
        "artists": [{"name": "Elena Tonra"}],
        "uri": "spotify:track:abc",
    }
    sp = _search_results([], [], [item])

    assert search_track(sp, "Daughter’s Elena Tonra", "Radio Station") == item["uri"]
    assert sp.search.call_args.kwargs["q"] == "Elena Tonra Radio Station"


def test_search_track_leaves_apostrophe_artist_names_alone():
    """真名就帶撇號的藝人第一輪就命中，不該走到剝離所有格那步。"""
    item = {
        "name": "Unclouded",
        "artists": [{"name": "Melody’s Echo Chamber"}],
        "uri": "spotify:track:def",
    }
    sp = _search_results([item])

    assert search_track(sp, "Melody’s Echo Chamber", "Unclouded") == item["uri"]
    assert sp.search.call_count == 1


def test_search_track_skips_possessive_retry_when_remainder_is_one_word():
    """剝完只剩一個字（sachi’s mirror → mirror）太容易誤配，不重試。"""
    sp = _search_results([], [])

    assert search_track(sp, "sachi’s mirror", "Talking in a Different Way") is None
    assert sp.search.call_count == 2


def test_playlist_items_paginates_and_accepts_item_or_track_key():
    """新 app 只回 item 鍵、舊 app 兩者都有；分頁走 next，略過已下架的 null 項目。"""
    sp = Mock()
    sp._get.return_value = {
        "items": [
            {"item": {"uri": "u:a", "id": "a"}, "added_at": "t1"},
            {"item": None, "track": None},
        ],
        "next": "page2",
    }
    sp.next.side_effect = lambda r: {
        "items": [{"track": {"uri": "u:b", "id": "b"}, "added_at": "t2"}],
        "next": None,
    }

    assert list(_playlist_items(sp, "pl")) == [
        {"uri": "u:a", "id": "a", "added_at": "t1"},
        {"uri": "u:b", "id": "b", "added_at": "t2"},
    ]
    assert sp._get.call_args.args[0] == "playlists/pl/items"
    assert sp._get.call_args.kwargs["limit"] == 50


def test_add_and_remove_items_batch_by_100():
    uris = [f"spotify:track:{i}" for i in range(250)]
    sp = _mock_sp(playlists=[], items_by_id={"main": []})

    add_tracks_to_playlist(sp, "main", uris)
    assert [len(u) for _, u in _added(sp)] == [100, 100, 50]
    assert sum((u for _, u in _added(sp)), []) == uris

    _remove_items(sp, "main", uris)
    sizes = [len(c.kwargs["payload"]["items"]) for c in sp._delete.call_args_list]
    assert sizes == [100, 100, 50]
    assert sp._delete.call_args.args[0] == "playlists/main/items"


def test_429_raises_immediately_with_retry_after():
    """不能照 Retry-After 睡：新 app 曾被封 14.5 小時，排程會卡死。"""
    from unittest.mock import patch

    import pytest
    from spotipy.exceptions import SpotifyException

    from music_collector.spotify import RateLimited, _Spotify

    sp = _Spotify(auth="token")
    assert sp.retries == 0 and sp.status_forcelist == ()
    err = SpotifyException(429, -1, "too many", headers={"Retry-After": "52000"})
    with patch("spotipy.Spotify._internal_call", side_effect=err), pytest.raises(RateLimited) as ei:
        sp.search(q="x")
    assert ei.value.retry_after == 52000 and "14.4 小時" in str(ei.value)
