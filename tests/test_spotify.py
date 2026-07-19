from unittest.mock import Mock

from music_collector.spotify import search_track


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
