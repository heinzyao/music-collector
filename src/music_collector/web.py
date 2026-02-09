"""Streamlit Web 介面：瀏覽蒐集紀錄、來源統計、播放清單管理。

啟動方式：./run.sh --web 或 streamlit run src/music_collector/web.py
"""

import json
import sqlite3
from collections import Counter
from pathlib import Path

import streamlit as st

from .config import BACKUP_DIR, DATA_DIR, DB_PATH


def _get_connection() -> sqlite3.Connection:
    """取得 SQLite 連線。"""
    if not DB_PATH.exists():
        st.warning("資料庫尚未建立。請先執行 `./run.sh` 蒐集曲目。")
        st.stop()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def page_browse() -> None:
    """瀏覽蒐集紀錄。"""
    st.header("🎵 蒐集紀錄")

    conn = _get_connection()

    # 篩選條件
    col1, col2, col3 = st.columns(3)

    sources = [r[0] for r in conn.execute("SELECT DISTINCT source FROM tracks ORDER BY source").fetchall()]

    with col1:
        selected_source = st.selectbox("來源", ["全部"] + sources)
    with col2:
        spotify_filter = st.selectbox("Spotify 狀態", ["全部", "已配對", "未配對"])
    with col3:
        search_text = st.text_input("搜尋（藝人/曲名）")

    # 組合查詢
    conditions = []
    params: list = []

    if selected_source != "全部":
        conditions.append("source = ?")
        params.append(selected_source)

    if spotify_filter == "已配對":
        conditions.append("spotify_uri IS NOT NULL")
    elif spotify_filter == "未配對":
        conditions.append("spotify_uri IS NULL")

    if search_text:
        conditions.append("(LOWER(artist) LIKE ? OR LOWER(title) LIKE ?)")
        params.extend([f"%{search_text.lower()}%"] * 2)

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    total = conn.execute(f"SELECT COUNT(*) FROM tracks {where}", params).fetchone()[0]

    st.caption(f"共 {total} 首曲目")

    # 分頁
    page_size = 50
    total_pages = max(1, (total + page_size - 1) // page_size)
    page = st.number_input("頁碼", min_value=1, max_value=total_pages, value=1)
    offset = (page - 1) * page_size

    rows = conn.execute(
        f"SELECT artist, title, source, spotify_uri, added_at "
        f"FROM tracks {where} ORDER BY added_at DESC LIMIT ? OFFSET ?",
        params + [page_size, offset],
    ).fetchall()

    if rows:
        data = []
        for r in rows:
            data.append({
                "藝人": r["artist"],
                "曲名": r["title"],
                "來源": r["source"],
                "Spotify": "✅" if r["spotify_uri"] else "❌",
                "加入日期": r["added_at"][:10] if r["added_at"] else "",
            })
        st.dataframe(data, use_container_width=True)
    else:
        st.info("無符合條件的曲目。")

    conn.close()


def page_stats() -> None:
    """來源統計圖表。"""
    st.header("📊 來源統計")

    conn = _get_connection()

    # 各來源貢獻
    rows = conn.execute(
        "SELECT source, COUNT(*) as total, "
        "SUM(CASE WHEN spotify_uri IS NOT NULL THEN 1 ELSE 0 END) as matched "
        "FROM tracks GROUP BY source ORDER BY total DESC"
    ).fetchall()

    if rows:
        sources = [r["source"] for r in rows]
        totals = [r["total"] for r in rows]
        matched = [r["matched"] for r in rows]

        col1, col2 = st.columns(2)
        with col1:
            st.subheader("各來源曲目數")
            chart_data = {r["source"]: r["total"] for r in rows}
            st.bar_chart(chart_data)

        with col2:
            st.subheader("Spotify 配對率")
            rate_data = {
                r["source"]: round(r["matched"] / r["total"] * 100, 1) if r["total"] else 0
                for r in rows
            }
            st.bar_chart(rate_data)

        # 整體統計
        total_all = sum(totals)
        matched_all = sum(matched)
        rate = f"{matched_all / total_all * 100:.1f}%" if total_all else "N/A"

        st.metric("總曲目", total_all)
        col1, col2 = st.columns(2)
        col1.metric("Spotify 配對", matched_all)
        col2.metric("配對率", rate)

    # 每日趨勢
    daily = conn.execute(
        "SELECT DATE(added_at) as day, COUNT(*) as cnt "
        "FROM tracks "
        "WHERE added_at >= DATE('now', '-30 days') "
        "GROUP BY day ORDER BY day"
    ).fetchall()

    if daily:
        st.subheader("近 30 天趨勢")
        trend_data = {r["day"]: r["cnt"] for r in daily}
        st.line_chart(trend_data)

    conn.close()


def page_backups() -> None:
    """季度備份瀏覽。"""
    st.header("📦 季度備份")

    backups = sorted(BACKUP_DIR.glob("**/Q*.json"))

    if not backups:
        st.info("尚無備份資料。執行完整蒐集後會自動建立備份。")
        return

    # 選擇備份
    options = {f"{f.parent.name}/{f.stem}": f for f in backups}
    selected = st.selectbox("選擇季度", list(options.keys()))

    if selected:
        path = options[selected]
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            st.error("備份讀取失敗。")
            return

        st.caption(f"共 {len(data)} 首曲目")

        if data:
            display = []
            for t in data:
                display.append({
                    "藝人": t.get("artist", ""),
                    "曲名": t.get("title", ""),
                    "來源": t.get("source", ""),
                    "Spotify": "✅" if t.get("spotify_uri") else "❌",
                })
            st.dataframe(display, use_container_width=True)


def main() -> None:
    """Streamlit 應用程式主函式。"""
    st.set_page_config(
        page_title="Music Collector",
        page_icon="🎵",
        layout="wide",
    )

    st.title("🎵 Music Collector")
    st.caption("自動蒐集音樂評論網站推薦曲目")

    # 導覽
    page = st.sidebar.radio(
        "功能",
        ["蒐集紀錄", "來源統計", "季度備份"],
        index=0,
    )

    if page == "蒐集紀錄":
        page_browse()
    elif page == "來源統計":
        page_stats()
    elif page == "季度備份":
        page_backups()


if __name__ == "__main__":
    main()
