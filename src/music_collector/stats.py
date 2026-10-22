"""資料分析模組：曲目趨勢、來源貢獻、跨來源重疊分析。

全部基於 SQLite 查詢 + 終端表格輸出，無需額外依賴。
"""

import sqlite3
from collections import Counter

from .config import ALL_TIME_PLAYLIST_NAME, PLAYLIST_NAME
from .db import init_db


def show_overview() -> None:
    """顯示蒐集總覽：各來源貢獻數、Spotify 配對率、趨勢。"""
    conn = init_db()

    # 總計
    total = _scalar(conn, "SELECT COUNT(*) FROM tracks")
    matched = _scalar(conn, "SELECT COUNT(*) FROM tracks WHERE spotify_uri IS NOT NULL")
    not_matched = total - matched
    rate = f"{matched / total * 100:.1f}%" if total else "N/A"

    print("\n📊 Music Collector 蒐集總覽\n")
    print(f"  總曲目數：{total}")
    print(f"  Spotify 配對：{matched}（{rate}）")
    print(f"  未配對：{not_matched}\n")

    # 各來源統計
    rows = conn.execute(
        "SELECT source, COUNT(*) as cnt, "
        "SUM(CASE WHEN spotify_uri IS NOT NULL THEN 1 ELSE 0 END) as matched "
        "FROM tracks GROUP BY source ORDER BY cnt DESC"
    ).fetchall()

    if rows:
        print("  來源貢獻：")
        print(f"  {'來源':<25} {'曲目數':>6} {'配對':>6} {'配對率':>8}")
        print(f"  {'─' * 25} {'─' * 6} {'─' * 6} {'─' * 8}")
        for r in rows:
            source, cnt, matched = r["source"], r["cnt"], r["matched"]
            src_rate = f"{matched / cnt * 100:.0f}%" if cnt else "N/A"
            print(f"  {source:<25} {cnt:>6} {matched:>6} {src_rate:>8}")

    # 近 7 天趨勢
    recent = conn.execute(
        "SELECT DATE(added_at) as day, COUNT(*) as cnt "
        "FROM tracks "
        "WHERE added_at >= DATE('now', '-7 days') "
        "GROUP BY day ORDER BY day"
    ).fetchall()

    if recent:
        print("\n  近 7 天趨勢：")
        for r in recent:
            bar = "█" * min(r["cnt"], 50)
            print(f"  {r['day']}  {bar} {r['cnt']}")

    conn.close()


def show_overlap() -> None:
    """分析跨來源重疊：哪些曲目被多個來源同時推薦。"""
    conn = init_db()

    # 查找 (artist, title) 出現在多個 source 的曲目
    # 因為 UNIQUE(artist, title) 限制，同一曲目只有一筆記錄
    # 但我們可以分析不同 source 推薦了相同 artist 的曲目
    rows = conn.execute(
        "SELECT LOWER(artist) as a, LOWER(title) as t, source FROM tracks ORDER BY a, t"
    ).fetchall()

    conn.close()

    if not rows:
        print("尚無蒐集資料。")
        return

    # 統計各來源推薦的獨立藝人
    source_artists: dict[str, set[str]] = {}
    for r in rows:
        source_artists.setdefault(r["source"], set()).add(r["a"])

    # 來源之間的藝人重疊
    sources = list(source_artists.keys())

    print("\n🔗 跨來源重疊分析\n")
    print("  各來源獨立藝人數：")
    for src in sorted(sources):
        print(f"    {src}: {len(source_artists[src])} 位藝人")

    if len(sources) >= 2:
        print("\n  來源間共同藝人：")
        for i in range(len(sources)):
            for j in range(i + 1, len(sources)):
                s1, s2 = sources[i], sources[j]
                overlap = source_artists[s1] & source_artists[s2]
                if overlap:
                    print(f"    {s1} ∩ {s2}: {len(overlap)} 位")

    # 最常被推薦的藝人 (top 10)
    artist_counts = Counter(r["a"] for r in rows)
    top = artist_counts.most_common(10)
    if top:
        print("\n  最常被推薦的藝人（前 10）：")
        for artist, count in top:
            print(f"    {artist}: {count} 首")


def show_sources() -> None:
    """各來源效能比較：擷取數、配對率、最近活動。"""
    conn = init_db()

    rows = conn.execute(
        "SELECT source, "
        "COUNT(*) as total, "
        "SUM(CASE WHEN spotify_uri IS NOT NULL THEN 1 ELSE 0 END) as matched, "
        "MAX(added_at) as last_activity "
        "FROM tracks GROUP BY source ORDER BY total DESC"
    ).fetchall()

    conn.close()

    if not rows:
        print("尚無蒐集資料。")
        return

    print("\n📈 各來源效能比較\n")
    print(f"  {'來源':<25} {'總數':>6} {'配對':>6} {'配對率':>8} {'最後活動':<20}")
    print(f"  {'─' * 25} {'─' * 6} {'─' * 6} {'─' * 8} {'─' * 20}")
    for r in rows:
        rate = f"{r['matched'] / r['total'] * 100:.0f}%" if r["total"] else "N/A"
        last = r["last_activity"][:10] if r["last_activity"] else "N/A"
        print(
            f"  {r['source']:<25} {r['total']:>6} {r['matched']:>6} {rate:>8} {last:<20}"
        )


def own_playlist_track_ids(sp) -> set[str]:
    """收集使用者自己擁有的歌單中所有曲目 ID（唯讀）。

    排除本工具產生的歌單（名稱以 Critics' Picks 開頭、Fresh Tracks，
    以及環境變數覆寫後的主歌單／All Time 名稱），否則採用率會被自己灌水。
    """
    from .spotify import _own_playlists, _playlist_items

    ids: set[str] = set()
    for p in _own_playlists(sp):
        if p["name"].startswith("Critics' Picks") or p["name"] in (
            "Fresh Tracks", PLAYLIST_NAME, ALL_TIME_PLAYLIST_NAME
        ):
            continue
        ids.update(t["id"] for t in _playlist_items(sp, p["id"]) if t["id"])
    return ids


def compute_adoption(conn: sqlite3.Connection, own_ids: set[str]) -> list[tuple[str, int, int]]:
    """回傳 [(來源, 配對到 Spotify 數, 被收進自己歌單數)]，依採用率、再依配對數降序。"""
    total: Counter[str] = Counter()
    kept: Counter[str] = Counter()
    for r in conn.execute("SELECT source, spotify_uri FROM tracks WHERE spotify_uri IS NOT NULL"):
        total[r["source"]] += 1
        if r["spotify_uri"].split(":")[-1] in own_ids:
            kept[r["source"]] += 1
    rows = [(src, n, kept[src]) for src, n in total.items()]
    return sorted(rows, key=lambda x: (-x[2] / x[1], -x[1]))


def show_adoption() -> None:
    """採用率：每個來源推薦的曲目有多少被收進使用者自己的歌單。只讀，不寫入 Spotify。"""
    from .spotify import get_spotify_client

    own_ids = own_playlist_track_ids(get_spotify_client())
    conn = init_db()
    rows = compute_adoption(conn, own_ids)
    conn.close()

    if not rows:
        print("尚無配對到 Spotify 的曲目。")
        return

    print(f"\n💚 各來源採用率（自己的歌單共 {len(own_ids)} 首不重複曲目）\n")
    print(f"  {'來源':<25} {'配對':>6} {'採用':>6} {'採用率':>8}")
    print(f"  {'─' * 25} {'─' * 6} {'─' * 6} {'─' * 8}")
    for src, n, k in rows:
        print(f"  {src:<25} {n:>6} {k:>6} {k / n:>8.1%}")
    n_sum, k_sum = sum(r[1] for r in rows), sum(r[2] for r in rows)
    print(f"  {'合計':<25} {n_sum:>6} {k_sum:>6} {k_sum / n_sum:>8.1%}")
    print("\n  註：已在自己歌單裡的舊歌也會計入，會略為高估。")


def show_stats(subcommand: str | None = None) -> None:
    """CLI 進入點：依子命令顯示對應統計。"""
    if subcommand == "overlap":
        show_overlap()
    elif subcommand == "sources":
        show_sources()
    elif subcommand == "adoption":
        show_adoption()
    else:
        show_overview()


def _scalar(conn: sqlite3.Connection, sql: str) -> int:
    """執行查詢，回傳單一整數值。"""
    row = conn.execute(sql).fetchone()
    return row[0] if row else 0
