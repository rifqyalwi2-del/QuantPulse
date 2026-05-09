# =============================================================================
# QuantPulse Pro V3 — Watchlist & Quick Scanner
# =============================================================================
from __future__ import annotations
import logging, time
from dataclasses import dataclass
import pandas as pd
import numpy as np

logger = logging.getLogger("QuantPulse.V3.Watchlist")

DEFAULT_WATCHLIST = {
    "crypto":    ["BTCUSDT","ETHUSDT","SOLUSDT","BNBUSDT","XRPUSDT"],
    "forex":     ["EURUSD","GBPUSD","USDJPY"],
    "commodity": ["XAUUSD"],
    "stock_id":  ["BBCA","BBRI","TLKM","BMRI"],
    "stock_us":  ["AAPL","NVDA","TSLA"],
}

@dataclass
class WatchItem:
    symbol:     str
    market:     str
    price:      float
    ret_pct:    float
    signal:     str
    confidence: float
    regime:     str
    atr:        float
    volume:     float
    status:     str  # OK / ERROR / LOADING

    @property
    def signal_emoji(self):
        return {"BUY":"🟢","SELL":"🔴","HOLD":"🟡"}.get(self.signal,"⚪")

    @property
    def regime_emoji(self):
        return {"LOW":"🔵","NORMAL":"🟢","HIGH":"🟠","CRISIS":"🔴"}.get(self.regime,"⚪")

    def to_dict(self):
        return {
            "Simbol":    self.symbol,
            "Market":    self.market.upper(),
            "Harga":     round(self.price, 4),
            "Return%":   f"{self.ret_pct:+.2%}",
            "Sinyal":    f"{self.signal_emoji} {self.signal}",
            "Conf%":     f"{self.confidence:.0f}%",
            "Regime":    f"{self.regime_emoji} {self.regime}",
            "ATR":       round(self.atr, 4),
            "Status":    self.status,
        }


def scan_symbol(symbol: str, market: str, interval: str = "1h") -> WatchItem:
    """Scan satu simbol — ambil data dan generate sinyal."""
    try:
        from data_loader  import smart_load
        from signal_engine import SignalEngine

        df, _ = smart_load(symbol, interval, 150, False, market)
        df.attrs.update({"symbol": symbol, "market": market, "interval": interval})

        se  = SignalEngine()
        sig = se.analyze(df)

        price  = float(df["close"].iloc[-1])
        ret    = float(df["returns"].iloc[-1]) if "returns" in df.columns else 0
        vol    = float(df["volume"].iloc[-1]) if "volume" in df.columns else 0

        return WatchItem(
            symbol     = symbol,
            market     = market,
            price      = price,
            ret_pct    = ret,
            signal     = sig.signal.value,
            confidence = sig.confidence,
            regime     = sig.regime,
            atr        = sig.atr,
            volume     = vol,
            status     = "OK",
        )
    except Exception as e:
        logger.warning(f"[Watchlist] {symbol} error: {e}")
        return WatchItem(
            symbol=symbol, market=market, price=0, ret_pct=0,
            signal="HOLD", confidence=0, regime="NORMAL", atr=0, volume=0,
            status=f"ERR: {str(e)[:40]}",
        )


def render_watchlist(interval: str = "1h"):
    """Render tab Watchlist di Streamlit."""
    try:
        import streamlit as st
    except ImportError:
        return

    st.markdown("#### 👁️ Watchlist & Quick Scanner")
    st.caption(
        "Pantau banyak simbol sekaligus. Klik **Scan** untuk update sinyal semua simbol. "
        "Tambah/hapus simbol sesuai kebutuhan."
    )

    # Session state untuk watchlist
    if "watchlist_symbols" not in st.session_state:
        st.session_state["watchlist_symbols"] = DEFAULT_WATCHLIST.copy()
    if "watchlist_results" not in st.session_state:
        st.session_state["watchlist_results"] = []

    wl = st.session_state["watchlist_symbols"]

    # UI tambah simbol
    with st.expander("➕ Kelola Watchlist"):
        col_add1, col_add2, col_add3 = st.columns([2,2,1])
        new_sym = col_add1.text_input("Simbol baru", placeholder="BTCUSDT / BBCA / EURUSD")
        new_mkt = col_add2.selectbox("Market", ["crypto","forex","commodity","stock_id","stock_us"])
        if col_add3.button("Tambah", use_container_width=True):
            if new_sym.strip():
                sym = new_sym.strip().upper()
                if new_mkt not in wl:
                    wl[new_mkt] = []
                if sym not in wl[new_mkt]:
                    wl[new_mkt].append(sym)
                    st.success(f"✅ {sym} ditambahkan ke {new_mkt}")
                    st.rerun()

        # List per market dengan opsi hapus
        for mkt, syms in wl.items():
            if syms:
                st.markdown(f"**{mkt.upper()}**: {', '.join(syms)}")
        if st.button("🔄 Reset ke Default", use_container_width=True):
            st.session_state["watchlist_symbols"] = DEFAULT_WATCHLIST.copy()
            st.rerun()

    # Pilih interval
    col_iv, col_scan = st.columns([2, 1])
    scan_interval = col_iv.selectbox(
        "Timeframe", ["15m","30m","1h","4h","1d"],
        index=2, key="wl_interval"
    )
    scan_clicked = col_scan.button(
        "🔍 Scan Semua", use_container_width=True, type="primary"
    )

    if scan_clicked:
        all_symbols = [(s, m) for m, syms in wl.items() for s in syms]
        results = []
        prog = st.progress(0)
        status_txt = st.empty()

        for idx, (sym, mkt) in enumerate(all_symbols):
            status_txt.caption(f"Scanning {sym} ({idx+1}/{len(all_symbols)})...")
            item = scan_symbol(sym, mkt, scan_interval)
            results.append(item)
            prog.progress((idx + 1) / len(all_symbols))
            time.sleep(0.3)  # Hindari rate limit

        prog.empty()
        status_txt.empty()
        st.session_state["watchlist_results"] = results
        st.success(f"✅ Scan selesai — {len(results)} simbol")

    # Tampilkan hasil
    results = st.session_state.get("watchlist_results", [])
    if results:
        # Summary cards
        buy_ct  = sum(1 for r in results if r.signal == "BUY")
        sell_ct = sum(1 for r in results if r.signal == "SELL")
        hold_ct = sum(1 for r in results if r.signal == "HOLD")
        err_ct  = sum(1 for r in results if r.status.startswith("ERR"))

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("🟢 BUY",  buy_ct)
        c2.metric("🔴 SELL", sell_ct)
        c3.metric("🟡 HOLD", hold_ct)
        c4.metric("⚠️ Error", err_ct)

        st.divider()

        # Filter
        col_f1, col_f2 = st.columns(2)
        filter_sig = col_f1.multiselect(
            "Filter sinyal", ["BUY","SELL","HOLD"],
            default=["BUY","SELL","HOLD"], key="wl_filter_sig"
        )
        filter_mkt = col_f2.multiselect(
            "Filter market", list(wl.keys()),
            default=list(wl.keys()), key="wl_filter_mkt"
        )

        filtered = [r for r in results
                    if r.signal in filter_sig and r.market in filter_mkt]

        if filtered:
            # Sort: BUY dan SELL dulu, confidence tertinggi
            filtered.sort(key=lambda x: (
                0 if x.signal != "HOLD" else 1,
                -x.confidence
            ))
            df_wl = pd.DataFrame([r.to_dict() for r in filtered])
            st.dataframe(df_wl, use_container_width=True, hide_index=True)

            # Highlight BUY/SELL terkuat
            top_signals = [r for r in filtered if r.signal != "HOLD"][:3]
            if top_signals:
                st.divider()
                st.markdown("#### 🎯 Sinyal Terkuat")
                cols = st.columns(len(top_signals))
                for col, item in zip(cols, top_signals):
                    color = "#00C851" if item.signal == "BUY" else "#FF4444"
                    col.markdown(
                        f"<div style='border:1.5px solid {color};border-radius:10px;"
                        f"padding:12px;background:{color}11'>"
                        f"<div style='color:{color};font-weight:700;font-size:1.1rem'>"
                        f"{item.signal_emoji} {item.symbol}</div>"
                        f"<div style='font-size:0.8rem;color:#aaa'>{item.market.upper()}</div>"
                        f"<div style='margin-top:6px'>{item.price:,.4f}</div>"
                        f"<div style='font-size:0.8rem'>Conf: {item.confidence:.0f}% | "
                        f"{item.ret_pct:+.2%}</div>"
                        f"</div>",
                        unsafe_allow_html=True
                    )
        else:
            st.info("Tidak ada hasil setelah filter.")
    else:
        # Tampilkan daftar watchlist saat ini
        st.info(
            f"Watchlist: {sum(len(v) for v in wl.values())} simbol di "
            f"{len(wl)} market. Klik **Scan Semua** untuk mulai."
        )
        rows = []
        for mkt, syms in wl.items():
            for s in syms:
                rows.append({"Market": mkt.upper(), "Simbol": s, "Status": "Belum di-scan"})
        if rows:
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
