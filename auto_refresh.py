# =============================================================================
# QuantPulse Pro V3 — Auto Refresh
# =============================================================================
# Streamlit auto-refresh menggunakan streamlit-autorefresh atau st.rerun loop
# Interval: 1m, 5m, 15m, 30m, 1h
# =============================================================================

def setup_auto_refresh(interval_seconds: int = 300) -> int:
    """
    Setup auto refresh di Streamlit.
    Returns countdown dalam detik.
    """
    try:
        from streamlit_autorefresh import st_autorefresh
        count = st_autorefresh(interval=interval_seconds * 1000, key="autorefresh")
        return count
    except ImportError:
        # Fallback: manual refresh button
        return -1


def render_refresh_status(interval_seconds: int, count: int):
    """Tampilkan status refresh di sidebar."""
    try:
        import streamlit as st
        import time
        from datetime import datetime, timezone

        now_wib = datetime.now(timezone.utc)
        now_str = now_wib.strftime("%H:%M:%S")

        if count >= 0:
            st.caption(f"🔄 Auto-refresh aktif | Interval: {interval_seconds//60}m | Terakhir: {now_str} WIB")
        else:
            st.caption(f"⏰ Data terakhir: {now_str} WIB")
    except Exception:
        pass
