# =============================================================================
# QuantPulse Pro V3 — Dashboard
# =============================================================================
# Rebuild dari nol — lebih stabil, lebih akurat, tidak ada cache error
# =============================================================================

import sys
import logging
from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).parent))
logging.basicConfig(level=logging.WARNING)

# Page config — harus paling pertama
st.set_page_config(
    page_title = "QuantPulse Pro",
    page_icon  = "⚡",
    layout     = "wide",
    initial_sidebar_state = "expanded",
)

# =============================================================================
# IMPORT MODULES
# =============================================================================

@st.cache_resource
def _import_modules():
    mods = {}
    try:
        from data_loader import (
            smart_load, smart_load_mtfa, get_symbol_info,
            AVAILABLE_SYMBOLS, TIMEFRAME_OPTIONS, MTFA_DEFAULTS,
        )
        mods.update({
            "smart_load": smart_load, "smart_load_mtfa": smart_load_mtfa,
            "get_symbol_info": get_symbol_info,
            "AVAILABLE_SYMBOLS": AVAILABLE_SYMBOLS,
            "TIMEFRAME_OPTIONS": TIMEFRAME_OPTIONS,
            "MTFA_DEFAULTS": MTFA_DEFAULTS,
        })
    except Exception as e:
        mods["loader_error"] = str(e)

    try:
        from signal_engine import SignalEngine
        mods["SignalEngine"] = SignalEngine
    except Exception as e:
        mods["signal_error"] = str(e)

    try:
        from risk_engine import RiskEngine
        mods["RiskEngine"] = RiskEngine
    except Exception as e:
        mods["risk_error"] = str(e)

    try:
        from predictive_trade import PredictiveTrade
        mods["PredictiveTrade"] = PredictiveTrade
    except Exception as e:
        mods["predict_error"] = str(e)

    try:
        from portfolio_manager import PortfolioManager, render_portfolio
        mods["get_portfolio"]    = PortfolioManager
        mods["render_portfolio"] = render_portfolio
    except Exception as e:
        mods["portfolio_error"] = str(e)

    try:
        from backtester import Backtester, render_backtest
        mods["Backtester"]     = Backtester
        mods["render_backtest"]= render_backtest
    except Exception as e:
        mods["backtester_error"] = str(e)

    try:
        from sr_detector import SRDetector, render_sr
        mods["SRDetector"] = SRDetector
        mods["render_sr"]  = render_sr
    except Exception as e:
        mods["sr_error"] = str(e)

    try:
        from candle_detector import CandleDetector, render_candle
        mods["CandleDetector"] = CandleDetector
        mods["render_candle"]  = render_candle
    except Exception as e:
        mods["candle_error"] = str(e)



    return mods

M = _import_modules()



# =============================================================================
# CANDLESTICK CHART
# =============================================================================
def render_candle_chart(df, title="", n_candles=100, show_vol=True, sr_result=None, height=420):
    """Candlestick chart dengan Plotly — EMA + Volume + S/R overlay."""
    try:
        import plotly.graph_objects as go
        from plotly.subplots import make_subplots
    except ImportError:
        st.line_chart(df[["close"]].tail(n_candles))
        st.caption("⚠️ Install plotly: pip install plotly")
        return

    df_p = df.tail(n_candles).copy()
    has_vol = show_vol and "volume" in df_p.columns and df_p["volume"].sum() > 1

    # Format x axis
    try:
        x = [t.strftime("%d/%m %H:%M") for t in df_p.index]
    except Exception:
        x = list(range(len(df_p)))

    if has_vol:
        fig = make_subplots(rows=2, cols=1, shared_xaxes=True,
                            vertical_spacing=0.03, row_heights=[0.75, 0.25])
    else:
        fig = make_subplots(rows=1, cols=1)

    # Candlestick
    fig.add_trace(go.Candlestick(
        x=x,
        open=df_p["open"], high=df_p["high"],
        low=df_p["low"],   close=df_p["close"],
        name="OHLC",
        increasing_line_color  = "#00C851",
        increasing_fillcolor   = "#00C851",
        decreasing_line_color  = "#FF4444",
        decreasing_fillcolor   = "#FF4444",
    ), row=1, col=1)

    # EMA lines
    if len(df_p) >= 21:
        ema9  = df_p["close"].ewm(span=9,  adjust=False).mean()
        ema21 = df_p["close"].ewm(span=21, adjust=False).mean()
        fig.add_trace(go.Scatter(x=x, y=ema9,  name="EMA9",
            line=dict(color="#FFD700", width=1.5), opacity=0.9), row=1, col=1)
        fig.add_trace(go.Scatter(x=x, y=ema21, name="EMA21",
            line=dict(color="#4FC3F7", width=1.5), opacity=0.9), row=1, col=1)

    # S/R levels
    if sr_result and hasattr(sr_result, "levels"):
        for lv in sorted(sr_result.levels, key=lambda x: x.strength, reverse=True)[:5]:
            color = "#00C851" if lv.label=="SUPPORT" else "#FF4444" if lv.label=="RESISTANCE" else "#FFD700"
            fig.add_hline(y=lv.price, line_dash="dash", line_color=color,
                          line_width=1, opacity=0.7,
                          annotation_text=f"{lv.label[:3]} {lv.price:,.0f}",
                          annotation_position="right", row=1, col=1)

    # Volume
    if has_vol:
        vol_colors = ["#00C851" if c >= o else "#FF4444"
                      for c, o in zip(df_p["close"], df_p["open"])]
        fig.add_trace(go.Bar(x=x, y=df_p["volume"], name="Vol",
            marker_color=vol_colors, opacity=0.5, showlegend=False), row=2, col=1)

    # Layout
    fig.update_layout(
        title=title, height=height,
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(14,17,23,1)",
        font=dict(color="#E0E0E0", size=11),
        xaxis_rangeslider_visible=False,
        legend=dict(orientation="h", y=1.02, x=1, xanchor="right",
                    bgcolor="rgba(0,0,0,0)"),
        margin=dict(l=0, r=0, t=40 if title else 10, b=0),
    )
    for r in [1, 2] if has_vol else [1]:
        fig.update_xaxes(gridcolor="rgba(255,255,255,0.06)", row=r, col=1)
        fig.update_yaxes(gridcolor="rgba(255,255,255,0.06)", row=r, col=1)

    st.plotly_chart(fig, use_container_width=True)

# =============================================================================
# CSS
# =============================================================================

st.markdown("""
<style>
[data-testid="metric-container"] {
    background: rgba(255,255,255,0.03);
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 10px;
    padding: 12px 16px;
}
.signal-buy  { color: #00C851; font-size: 2rem; font-weight: 900; }
.signal-sell { color: #FF4444; font-size: 2rem; font-weight: 900; }
.signal-hold { color: #FFD700; font-size: 2rem; font-weight: 900; }
.regime-badge {
    display: inline-block;
    padding: 3px 12px;
    border-radius: 12px;
    font-size: 0.8rem;
    font-weight: 600;
}
</style>
""", unsafe_allow_html=True)

# =============================================================================
# SESSION STATE
# =============================================================================

for key, val in {
    "df": None, "mtfa": None,
    "signal": None, "risk": None,
    "errors": [],
}.items():
    if key not in st.session_state:
        st.session_state[key] = val

# =============================================================================
# DATA CACHE — DataFrame only, tidak ada object kompleks
# =============================================================================

@st.cache_data(ttl=900, show_spinner=False)
def cached_load(symbol: str, interval: str, limit: int, use_demo: bool, market: str = ""):
    """Cache hanya DataFrame — 100% serializable."""
    SL = M.get("smart_load")
    if SL is None:
        return None, True
    df, is_demo = SL(symbol, interval, limit, use_demo, market=market)
    return df, is_demo


@st.cache_data(ttl=1800, show_spinner=False)
def cached_mtfa(symbol: str, htf: str, mtf: str, ltf: str, limit: int, use_demo: bool, market: str = ""):
    """Cache MTFA sebagai dict DataFrame."""
    SML = M.get("smart_load_mtfa")
    if SML is None:
        return None, True
    dfs, is_demo = SML(symbol, htf, mtf, ltf, limit, use_demo, market=market)
    return dfs, is_demo

# =============================================================================
# SIDEBAR
# =============================================================================

with st.sidebar:
    st.markdown("## ⚡ QuantPulse Pro")
    st.caption("Predictive Wealth Engine V3")
    st.divider()

    AVAIL = M.get("AVAILABLE_SYMBOLS", {
        "crypto": ["BTCUSDT","ETHUSDT","SOLUSDT"],
        "forex":  ["EURUSD","GBPUSD"],
        "commodity": ["XAUUSD (Gold)","OIL"],
        "stock_us": ["AAPL","NVDA","TSLA"],
        "stock_id": ["BBCA","BBRI","TLKM","ASII","BMRI","BUMI","WBSA","ANTM","ADRO"],
    })
    TF_OPTS = M.get("TIMEFRAME_OPTIONS", {
        "crypto":    ["5m","15m","30m","1h","4h","1d"],
        "forex":     ["15m","30m","1h","4h","1d"],
        "commodity": ["15m","30m","1h","4h","1d"],
        "stock_us":  ["30m","1h","1d","1w"],
        "stock_id":  ["1d","1w"],
    })
    MTFA_DEF = M.get("MTFA_DEFAULTS", {
        "crypto":    ("4h","1h","15m"),
        "forex":     ("1d","4h","1h"),
        "commodity": ("1d","4h","1h"),
        "stock_us":  ("1w","1d","1h"),
        "stock_id":  ("1w","1d","1d"),
    })

    # Market selector
    st.markdown("**Market**")
    market = st.selectbox("", [
        "crypto", "forex", "commodity", "stock_us", "stock_id"
    ], format_func=lambda x: {
        "crypto":    "🪙 Crypto",
        "forex":     "💱 Forex",
        "commodity": "🏅 Commodity (Gold/Oil)",
        "stock_us":  "🇺🇸 Saham US",
        "stock_id":  "🇮🇩 Saham IDX",
    }[x], label_visibility="collapsed")

    # Simbol
    sym_opts = AVAIL.get(market, [])
    st.markdown("**Simbol**")

    # Mode input: pilih dari list atau ketik bebas
    input_mode = st.radio("", ["Pilih dari daftar", "Ketik simbol sendiri"],
                           horizontal=True, label_visibility="collapsed")

    if input_mode == "Pilih dari daftar":
        sym_select = st.selectbox("", sym_opts, label_visibility="collapsed")
        symbol = sym_select.split(" ")[0].upper()
    else:
        hints = {
            "crypto":    "Contoh: BTCUSDT, ETHUSDT, SOLUSDT",
            "forex":     "Contoh: EURUSD, GBPUSD, USDJPY",
            "commodity": "Contoh: XAUUSD, OIL, XAGUSD",
            "stock_us":  "Contoh: AAPL, NVDA, TSLA, MSFT",
            "stock_id":  "Contoh: BBCA, BUMI, WBSA, ANTM, GOTO",
        }
        custom_sym = st.text_input(
            "", placeholder=hints.get(market, "Ketik simbol"),
            label_visibility="collapsed"
        )
        if custom_sym.strip():
            symbol = custom_sym.strip().upper()
            # Auto-append .JK untuk saham IDX jika belum ada
            if market == "stock_id" and not symbol.endswith(".JK"):
                symbol = symbol  # biarkan data_loader yang handle
        else:
            symbol = sym_opts[0].split(" ")[0].upper() if sym_opts else "BTCUSDT"

    st.caption(f"Simbol aktif: **{symbol}**")

    st.divider()

    # MTFA Timeframes
    st.markdown("**Multi-Timeframe (MTFA)**")
    tf_opts = TF_OPTS.get(market, ["1h","4h","1d"])
    htf_def, mtf_def, ltf_def = MTFA_DEF.get(market, (tf_opts[-1], tf_opts[min(1,len(tf_opts)-1)], tf_opts[0]))

    # Tampilkan label timeframe dengan format jelas
    st.markdown(
        f"<div style='display:flex;gap:4px;margin-bottom:4px'>"
        f"<span style='flex:1;text-align:center;font-size:0.75rem;color:#aaa'>HTF (Tren)</span>"
        f"<span style='flex:1;text-align:center;font-size:0.75rem;color:#aaa'>MTF (Momentum)</span>"
        f"<span style='flex:1;text-align:center;font-size:0.75rem;color:#aaa'>LTF (Entry)</span>"
        f"</div>", unsafe_allow_html=True
    )
    col_h, col_m, col_l = st.columns(3)
    htf = col_h.selectbox(
        "HTF", tf_opts,
        index=tf_opts.index(htf_def) if htf_def in tf_opts else max(0, len(tf_opts)-1),
        help="Higher Timeframe — lihat tren besar",
        key=f"htf_{market}",
        label_visibility="collapsed",
    )
    mtf = col_m.selectbox(
        "MTF", tf_opts,
        index=tf_opts.index(mtf_def) if mtf_def in tf_opts else min(1, len(tf_opts)-1),
        help="Medium Timeframe — momentum",
        key=f"mtf_{market}",
        label_visibility="collapsed",
    )
    ltf = col_l.selectbox(
        "LTF", tf_opts,
        index=tf_opts.index(ltf_def) if ltf_def in tf_opts else 0,
        help="Lower Timeframe — sinyal entry",
        key=f"ltf_{market}",
        label_visibility="collapsed",
    )
    st.caption(f"HTF={htf} · MTF={mtf} · LTF={ltf}")

    st.divider()

    # Risk Settings
    st.markdown("**Risk Settings**")
    capital = st.number_input("Modal (USD)", 100, 1_000_000, 1000, step=100)
    risk_pct = st.slider("Risk per Trade (%)", 0.5, 5.0, 1.0, 0.5) / 100
    min_conf = st.slider("Min Confidence (%)", 10, 60, 25, 5)

    sl_mult = st.slider("SL Multiplier (ATR ×)", 1.0, 4.0, 2.0, 0.5)
    tp_mult = st.slider("TP Multiplier (ATR ×)", 1.5, 6.0, 3.0, 0.5)

    st.divider()

    # Auto Refresh
    st.markdown("**Auto Refresh**")
    ar_enabled  = st.toggle("Auto Refresh", value=False)
    ar_interval = st.selectbox(
        "Interval", ["1 menit","5 menit","15 menit","30 menit","1 jam"],
        index=2, disabled=not ar_enabled, label_visibility="collapsed"
    )
    if ar_enabled:
        ar_secs = {"1 menit":60,"5 menit":300,"15 menit":900,"30 menit":1800,"1 jam":3600}
        try:
            from streamlit_autorefresh import st_autorefresh
            st_autorefresh(interval=ar_secs[ar_interval]*1000, key="qp_ar")
            st.caption(f"🔄 Auto-refresh setiap {ar_interval}")
        except ImportError:
            st.caption("Install: pip install streamlit-autorefresh")

    st.divider()
    use_demo = st.toggle("Mode Demo (data simulasi)", value=False)

    if st.button("🔄 Refresh Data", use_container_width=True):
        st.cache_data.clear()
        for k in ["df","mtfa","signal","risk"]:
            st.session_state[k] = None
        st.rerun()


    st.caption(f"V3 · {market.upper()} · {symbol}")

# =============================================================================
# HEADER
# =============================================================================

st.markdown(f"# ⚡ QuantPulse Pro")
st.markdown(f"**{symbol}** · {market.upper()} · MTFA {htf}/{mtf}/{ltf}")
st.divider()

# =============================================================================
# LOAD DATA
# =============================================================================

with st.spinner(f"Memuat data {symbol} ({ltf})..."):
    try:
        df, is_demo = cached_load(symbol, ltf, 500, use_demo, market)
        if df is not None:
            st.session_state["df"] = df
        if is_demo:
            st.info("🎮 Data simulasi — aktifkan Mode Demo OFF untuk data real dari exchange")
    except Exception as e:
        st.error(f"Gagal load data: {e}")
        df = None
        is_demo = True

# Load MTFA
with st.spinner(f"Memuat MTFA {htf}/{mtf}/{ltf}..."):
    try:
        mtfa_dfs, mtfa_demo = cached_mtfa(symbol, htf, mtf, ltf, 300, use_demo, market)
        st.session_state["mtfa"] = mtfa_dfs
    except Exception as e:
        mtfa_dfs = None

# =============================================================================
# RUN ENGINES
# =============================================================================

signal_result = None
risk_result   = None

SE = M.get("SignalEngine")
RE = M.get("RiskEngine")

if SE and df is not None and len(df) >= 30:
    try:
        engine = SE()
        signal_result = engine.analyze(df, mtfa_dfs)
        st.session_state["signal"] = signal_result


    except Exception as e:
        st.session_state["errors"].append(f"Signal: {e}")

if RE and signal_result and df is not None:
    try:
        idr_rate = df.attrs.get("idr_rate", 1/16200)
        re = RE(
            capital_usd    = capital,
            risk_per_trade = risk_pct,
            sl_atr_mult    = sl_mult,
            tp_atr_mult    = tp_mult,
            min_confidence = min_conf,
        )
        risk_result = re.evaluate(signal_result, df)
        st.session_state["risk"] = risk_result
    except Exception as e:
        st.session_state["errors"].append(f"Risk: {e}")

# =============================================================================
# TABS
# =============================================================================

tab_signal, tab_risk, tab_portfolio, tab_backtest, tab_sr, tab_candle, tab_predict, tab_guide, tab_debug = st.tabs([
    "📡 Sinyal", "🛡️ Risk & Eksekusi", "📁 Portfolio", "📊 Backtest", "📐 S&R", "🕯️ Candle", "🔮 Prediksi", "📖 Panduan", "🔧 Debug"
])

# ─────────────────────────────────────────────────────────────────────────────
# TAB 1 — SINYAL
# ─────────────────────────────────────────────────────────────────────────────
with tab_signal:
    if df is not None:
        last_close     = float(df["close"].iloc[-1])
        last_close_usd = float(df["close_usd"].iloc[-1]) if "close_usd" in df.columns else last_close
        last_ret       = float(df["returns"].iloc[-1]) if "returns" in df.columns else 0
        currency       = df.attrs.get("currency", "USD")

        # Harga terkini
        c1, c2, c3, c4 = st.columns(4)
        if currency == "IDR":
            c1.metric("Harga (IDR)", f"Rp {last_close:,.0f}")
            c2.metric("Harga (USD)", f"${last_close_usd:,.2f}")
        elif last_close > 100:
            # Harga besar (saham US, Gold) — tampilkan 2 desimal
            c1.metric("Harga Terkini", f"{last_close:,.2f} {currency}")
            c2.metric("Harga USD", f"${last_close_usd:,.2f}")
        else:
            # Harga kecil (Forex) — tampilkan 4 desimal
            c1.metric("Harga Terkini", f"{last_close:,.4f} {currency}")
            c2.metric("Harga USD", f"${last_close_usd:,.4f}")
        c3.metric("Return Candle",  f"{last_ret:+.3%}")
        c4.metric("Candle Dianalisis", f"{len(df)}")

        st.divider()

    if signal_result:
        sig   = signal_result.signal.value
        conf  = signal_result.confidence
        score = signal_result.score
        mtfa  = signal_result.mtfa_score

        # Signal badge
        color_map = {"BUY": "#00C851", "SELL": "#FF4444", "HOLD": "#FFD700"}
        color = color_map.get(sig, "#888")
        st.markdown(
            f"<div style='text-align:center;margin:16px 0'>"
            f"<span style='font-size:2.5rem;font-weight:900;color:{color}'>"
            f"{signal_result.signal.emoji()} {sig}</span></div>",
            unsafe_allow_html=True
        )

        # Veto
        if signal_result.veto:
            st.error(f"🔴 VETO: {signal_result.veto_reason}")

        # Regime badge
        regime_colors = {
            "LOW": "#4FC3F7", "NORMAL": "#00C851",
            "HIGH": "#FFD700", "CRISIS": "#FF4444"
        }
        rc = regime_colors.get(signal_result.regime, "#888")
        st.markdown(
            f"<div style='margin:8px 0'>"
            f"<span style='background:{rc}22;color:{rc};padding:4px 14px;"
            f"border-radius:12px;border:1px solid {rc};font-size:0.85rem;font-weight:600'>"
            f"Regime: {signal_result.regime}</span></div>",
            unsafe_allow_html=True
        )

        # Metrics
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Confidence",    f"{conf:.1f}%")
        c2.metric("Final Score",   f"{score:+.3f}")
        c3.metric("MTFA Alignment",f"{mtfa:+.2f}/3.0")
        c4.metric("ATR",           f"{signal_result.atr:,.4f}")

        st.divider()

        # Breakdown indikator
        st.markdown("#### 📊 Breakdown Indikator")
        rows = []
        for ind in signal_result.indicators:
            rows.append({
                "Indikator":   ind.name,
                "Sinyal":      f"{ind.signal.emoji()} {ind.signal.value}",
                "Nilai":       f"{ind.value:.4f}",
                "Bobot":       f"{ind.weight:.0%}",
                "Strength":    f"{ind.strength:.2f}",
                "Kontribusi":  f"{ind.weighted_score():+.4f}",
                "Keterangan":  ind.description,
            })
        if rows:
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

        st.divider()

        # Candle quick summary di tab sinyal
        CD2 = M.get("CandleDetector")
        if CD2 and df is not None and len(df) >= 3:
            try:
                cd_quick = CD2().detect(df)
                sig_val  = signal_result.signal.value if signal_result else "HOLD"
                cd_quick.confirm_signal = CD2().check_confirmation(cd_quick, sig_val)
                c_color  = {"BULLISH":"#00C851","BEARISH":"#FF4444","MIXED":"#FFD700","NEUTRAL":"#888"}.get(cd_quick.overall,"#888")
                c_emoji  = {"BULLISH":"🟢","BEARISH":"🔴","MIXED":"🟡","NEUTRAL":"⚪"}.get(cd_quick.overall,"⚪")
                conf_txt = {"CONFIRM":"✅ Konfirmasi sinyal","CONTRADICT":"⚠️ Kontradiksi sinyal","NEUTRAL":"➖ Netral"}.get(cd_quick.confirm_signal,"")
                if cd_quick.patterns:
                    pola_txt = ", ".join([p.name for p in cd_quick.patterns])
                    st.markdown(
                        f"<div style='background:{c_color}15;border:1px solid {c_color}33;"
                        f"border-radius:8px;padding:8px 14px;margin:8px 0'>"
                        f"<span style='color:{c_color};font-weight:600'>{c_emoji} Candle: {cd_quick.overall}</span>"
                        f" · <span style='font-size:0.85rem'>{pola_txt}</span>"
                        f" · <span style='color:{c_color};font-size:0.85rem'>{conf_txt}</span>"
                        f"</div>",
                        unsafe_allow_html=True
                    )
            except Exception:
                pass

        # Candlestick chart
        if df is not None:
            st.markdown("#### 📈 Chart Harga (LTF)")

            # Ambil S/R
            _sr_chart = None
            try:
                _SRD = M.get("SRDetector")
                if _SRD and len(df) >= 30:
                    _sr_chart = _SRD(pivot_window=8, max_levels=5).detect(df)
            except Exception:
                pass

            col_cn, col_cv = st.columns([3, 1])
            n_candles_show = col_cn.slider("Candle", 30, 300, 100, 10, key="cn")
            show_volume    = col_cv.toggle("Volume", value=True, key="sv")

            render_candle_chart(
                df, title=f"{symbol} · {ltf}",
                n_candles=n_candles_show, show_vol=show_volume,
                sr_result=_sr_chart, height=460,
            )

            # MTFA mini charts
            if mtfa_dfs:
                col_h, col_m = st.columns(2)
                with col_h:
                    st.caption(f"HTF ({htf}) — Trend")
                    render_candle_chart(mtfa_dfs["htf"], n_candles=60,
                                        show_vol=False, height=260)
                with col_m:
                    st.caption(f"MTF ({mtf}) — Momentum")
                    render_candle_chart(mtfa_dfs["mtf"], n_candles=80,
                                        show_vol=False, height=260)
    else:
        st.warning("Signal engine tidak berjalan. Cek tab Debug.")

# ─────────────────────────────────────────────────────────────────────────────
# TAB 2 — RISK & EKSEKUSI
# ─────────────────────────────────────────────────────────────────────────────
with tab_risk:
    if risk_result:
        # Status
        if risk_result.approved:
            st.success(f"✅ TRADE DIIZINKAN — {risk_result.signal}")
        elif risk_result.signal == "HOLD":
            st.info("🟡 HOLD — Tidak ada trade saat ini")
        else:
            st.error(f"🔴 TRADE DITAHAN")
            for msg in risk_result.veto_reasons:
                st.warning(msg)

        # Regime
        rc = {"LOW":"#4FC3F7","NORMAL":"#00C851","HIGH":"#FFD700","CRISIS":"#FF4444"}.get(risk_result.regime,"#888")
        st.markdown(
            f"<span style='background:{rc}22;color:{rc};padding:4px 14px;"
            f"border-radius:12px;border:1px solid {rc};font-size:0.85rem'>"
            f"Regime: {risk_result.regime} — {risk_result.regime_note}</span>",
            unsafe_allow_html=True
        )
        st.markdown("")

        # Level harga eksekusi
        st.markdown("#### 📍 Level Eksekusi — Referensi")
        currency = risk_result.currency

        ca, cb, cc, cd = st.columns(4)
        ca.metric("📍 Entry Referensi",
                  f"{risk_result.entry_price:,.4f}",
                  currency)
        cb.metric("🛑 Stop Loss",
                  f"{risk_result.stop_loss:,.4f}",
                  f"-{risk_result.sl_pct:.2%}")
        cc.metric("🎯 Take Profit",
                  f"{risk_result.take_profit:,.4f}",
                  f"+{risk_result.tp_pct:.2%}")
        cd.metric("📊 Risk/Reward",  f"{risk_result.risk_reward:.2f}x")

        st.divider()

        # ─── MT5 ENTRY WITH SPREAD TOLERANCE ────────────────────────────────
        st.markdown("#### 🖥️ Level Eksekusi di Broker / Platform (dengan Spread Toleransi)")
        st.caption(
            f"Spread otomatis ditambahkan: **{risk_result.spread_pct:.2%}** "
            f"sesuai karakteristik market **{risk_result.market.upper()}**. "
            f"Gunakan angka ini saat input order di platform manapun (MT5, Binance, OKX, Bybit, TradingView, dll)."
        )

        signal_active = risk_result.signal

        # Tab BUY vs SELL
        if signal_active == "BUY":
            # Tampilkan BUY entry prominently
            st.markdown(
                f"<div style='background:#00C85118;border:2px solid #00C851;"
                f"border-radius:12px;padding:16px;margin:8px 0'>"
                f"<div style='color:#00C851;font-weight:700;font-size:1rem;margin-bottom:12px'>"
                f"🟢 ORDER BUY — Masukkan angka ini ke platform kamu</div>"
                f"<div style='display:flex;gap:20px;flex-wrap:wrap'>"
                f"<div><div style='font-size:0.75rem;color:#aaa'>Entry (ASK)</div>"
                f"<div style='font-size:1.4rem;font-weight:900;color:#00C851'>"
                f"{risk_result.entry_buy_broker:,.4f}</div></div>"
                f"<div><div style='font-size:0.75rem;color:#aaa'>Stop Loss</div>"
                f"<div style='font-size:1.4rem;font-weight:900;color:#FF4444'>"
                f"{risk_result.sl_buy_broker:,.4f}</div></div>"
                f"<div><div style='font-size:0.75rem;color:#aaa'>Take Profit</div>"
                f"<div style='font-size:1.4rem;font-weight:900;color:#00C851'>"
                f"{risk_result.tp_buy_broker:,.4f}</div></div>"
                f"<div><div style='font-size:0.75rem;color:#aaa'>Volume (Lot)</div>"
                f"<div style='font-size:1.4rem;font-weight:900;color:#fff'>"
                f"{risk_result.units:,.4f}</div></div>"
                f"</div></div>",
                unsafe_allow_html=True
            )
        elif signal_active == "SELL":
            # Tampilkan SELL entry prominently
            st.markdown(
                f"<div style='background:#FF444418;border:2px solid #FF4444;"
                f"border-radius:12px;padding:16px;margin:8px 0'>"
                f"<div style='color:#FF4444;font-weight:700;font-size:1rem;margin-bottom:12px'>"
                f"🔴 ORDER SELL — Masukkan angka ini ke platform kamu</div>"
                f"<div style='display:flex;gap:20px;flex-wrap:wrap'>"
                f"<div><div style='font-size:0.75rem;color:#aaa'>Entry (BID)</div>"
                f"<div style='font-size:1.4rem;font-weight:900;color:#FF4444'>"
                f"{risk_result.entry_sell_broker:,.4f}</div></div>"
                f"<div><div style='font-size:0.75rem;color:#aaa'>Stop Loss</div>"
                f"<div style='font-size:1.4rem;font-weight:900;color:#FF4444'>"
                f"{risk_result.sl_sell_broker:,.4f}</div></div>"
                f"<div><div style='font-size:0.75rem;color:#aaa'>Take Profit</div>"
                f"<div style='font-size:1.4rem;font-weight:900;color:#00C851'>"
                f"{risk_result.tp_sell_broker:,.4f}</div></div>"
                f"<div><div style='font-size:0.75rem;color:#aaa'>Volume (Lot)</div>"
                f"<div style='font-size:1.4rem;font-weight:900;color:#fff'>"
                f"{risk_result.units:,.4f}</div></div>"
                f"</div></div>",
                unsafe_allow_html=True
            )
        else:
            st.info("Tidak ada sinyal aktif — level MT5 tidak ditampilkan.")

        # Tabel perbandingan lengkap
        with st.expander("📋 Perbandingan Harga Exchange vs MT5"):
            import pandas as pd
            comp_data = {
                "Level":      ["Entry", "Stop Loss", "Take Profit"],
                "Exchange (Referensi)": [
                    f"{risk_result.entry_price:,.4f}",
                    f"{risk_result.stop_loss:,.4f}",
                    f"{risk_result.take_profit:,.4f}",
                ],
                "MT5 BUY (ASK)": [
                    f"{risk_result.entry_buy_broker:,.4f}",
                    f"{risk_result.sl_buy_broker:,.4f}",
                    f"{risk_result.tp_buy_broker:,.4f}",
                ],
                "MT5 SELL (BID)": [
                    f"{risk_result.entry_sell_broker:,.4f}",
                    f"{risk_result.sl_sell_broker:,.4f}",
                    f"{risk_result.tp_sell_broker:,.4f}",
                ],
                "Selisih Spread": [
                    f"{risk_result.entry_price * risk_result.spread_pct:,.4f}",
                    "-", "-",
                ],
            }
            st.dataframe(pd.DataFrame(comp_data), use_container_width=True, hide_index=True)
            st.caption(
                f"Spread {risk_result.spread_pct:.2%} = "
                f"selisih {risk_result.entry_price * risk_result.spread_pct:,.4f} "
                f"antara harga exchange dan broker MT5."
            )

        st.divider()
        # ──────────────────────────────────────────────────────────────────────

        # Position sizing
        st.markdown("#### 💰 Position Sizing & Estimasi Profit")

        ce, cf, cg = st.columns(3)
        ce.metric("Ukuran Posisi", f"{risk_result.units:,.4f} unit")
        cf.metric("Nilai Posisi (USD)", f"${risk_result.position_value_usd:,.2f}")
        cg.metric("Nilai Posisi (IDR)", f"Rp {risk_result.position_value_idr:,.0f}")

        # Estimasi profit/loss — ini yang utama
        st.markdown("#### 📈 Estimasi Hasil Trade")

        col_profit, col_loss = st.columns(2)

        with col_profit:
            st.markdown(
                f"<div style='background:#00C85118;border:1.5px solid #00C851;"
                f"border-radius:10px;padding:16px;text-align:center'>"
                f"<div style='color:#00C851;font-weight:700;font-size:1rem'>🎯 JIKA TAKE PROFIT TERCAPAI</div>"
                f"<div style='font-size:1.8rem;font-weight:900;color:#00C851'>"
                f"+${risk_result.potential_profit_usd:,.2f}</div>"
                f"<div style='font-size:1.2rem;color:#00C851'>"
                f"+Rp {risk_result.potential_profit_idr:,.0f}</div>"
                f"<div style='font-size:0.8rem;color:#888;margin-top:4px'>"
                f"+{risk_result.profit_pct:.2%} dari modal</div>"
                f"</div>",
                unsafe_allow_html=True
            )

        with col_loss:
            st.markdown(
                f"<div style='background:#FF444418;border:1.5px solid #FF4444;"
                f"border-radius:10px;padding:16px;text-align:center'>"
                f"<div style='color:#FF4444;font-weight:700;font-size:1rem'>🛑 JIKA STOP LOSS KENA</div>"
                f"<div style='font-size:1.8rem;font-weight:900;color:#FF4444'>"
                f"-${risk_result.potential_loss_usd:,.2f}</div>"
                f"<div style='font-size:1.2rem;color:#FF4444'>"
                f"-Rp {risk_result.potential_loss_idr:,.0f}</div>"
                f"<div style='font-size:0.8rem;color:#888;margin-top:4px'>"
                f"-{risk_result.sl_pct:.2%} dari posisi</div>"
                f"</div>",
                unsafe_allow_html=True
            )

        st.divider()

        # VaR
        st.markdown("#### 📉 Value at Risk")
        cv1, cv2 = st.columns(2)
        cv1.metric("VaR 95% (USD)", f"${risk_result.var_95_usd:,.2f}",
                   "Max loss 95% skenario")
        cv2.metric("VaR 95% (IDR)", f"Rp {risk_result.var_95_idr:,.0f}")

        st.caption(f"Kurs digunakan: 1 USD = Rp {risk_result.idr_rate:,.0f}")

    else:
        st.info("Jalankan analisis sinyal terlebih dahulu di tab Sinyal.")


# ─────────────────────────────────────────────────────────────────────────────
# TAB PORTFOLIO
# ─────────────────────────────────────────────────────────────────────────────
with tab_portfolio:
    gp = M.get("get_portfolio")
    rp = M.get("render_portfolio")

    if gp is None or rp is None:
        # Kita tampilkan error aslinya biar ketahuan kalau ada salah
        err_msg = M.get("portfolio_error", "Modul gagal dimuat.")
        st.error(f"Error memuat Portfolio Manager: {err_msg}")
    else:
        pm = gp(initial_capital_usd=capital)

        # Update harga terkini ke portfolio
        if df is not None and signal_result:
            pm.update_prices({symbol: float(df["close"].iloc[-1])})

        # Gunakan get_snapshot() (Update nama fungsi dari versi sebelumnya)
        snap = pm.snapshot()

        # Tombol buka posisi dari risk result
        if risk_result and risk_result.approved:
            # FIX 1: Ganti final_signal menjadi signal
            st.success(f"✅ Sinyal {risk_result.signal} siap dieksekusi")
            
            if st.button("📥 Tambah ke Portfolio", use_container_width=True, type="primary"):
                # FIX 2: Sesuaikan semua parameter dengan struktur V3 yang baru
                ok, msg, pid = pm.open_position(
                    symbol       = symbol,
                    market       = signal_result.market, 
                    direction    = risk_result.signal,
                    entry_price  = risk_result.entry_price,
                    units        = risk_result.units,
                    stop_loss    = risk_result.stop_loss,
                    take_profit  = risk_result.take_profit,
                    confidence   = signal_result.confidence,
                    regime       = risk_result.regime,
                )
                if ok:
                    st.success(f"✅ {msg}")
                    st.rerun()
                else:
                    st.error(f"❌ {msg}")
            st.divider()

        # FIX 3: Pastikan fungsi render memanggil 2 parameter (snap dan pm)
        rp(snap, pm)


# ─────────────────────────────────────────────────────────────────────────────
# TAB BACKTEST
# ─────────────────────────────────────────────────────────────────────────────
with tab_backtest:
    st.markdown("#### 📊 Backtester — Validasi Strategi di Data Historis")
    st.caption(
        "Simulasi trading menggunakan Signal Engine + Risk Engine V3 "
        "di data historis. Wajib lakukan ini sebelum pakai uang real."
    )

    BT  = M.get("Backtester")
    RBT = M.get("render_backtest")

    if BT is None:
        st.error("backtester.py tidak ditemukan")
    else:
        col_b1, col_b2, col_b3 = st.columns(3)
        bt_candles  = col_b1.number_input("Jumlah Candle", 100, 2000, 500, step=100)
        bt_capital  = col_b2.number_input("Modal Backtest ($)", 100, 100_000, int(capital), step=100)
        bt_fee      = col_b3.number_input("Fee (%)", 0.0, 1.0, 0.1, step=0.05) / 100

        col_b4, col_b5, col_b6 = st.columns(3)
        bt_risk     = col_b4.slider("Risk per Trade (%)", 0.5, 5.0, float(risk_pct*100), 0.5, key="bt_risk_slider") / 100
        bt_sl       = col_b5.slider("SL Mult (ATR)", 1.0, 4.0, sl_mult, 0.5, key="bt_sl_slider")
        bt_tp       = col_b6.slider("TP Mult (ATR)", 1.5, 6.0, tp_mult, 0.5, key="bt_tp_slider")

        use_wfa     = st.toggle("Walk-Forward Analysis", value=False,
                                help="Split data train/test untuk validasi anti-overfitting")
        if use_wfa:
            n_folds = st.slider("Jumlah Fold", 3, 8, 4)

        if st.button("🚀 Jalankan Backtest", use_container_width=True, type="primary"):
            with st.spinner(f"Menjalankan backtest {symbol} ({bt_candles} candle)..."):
                try:
                    from data_loader import smart_load
                    bt_df, bt_demo = smart_load(symbol, ltf, bt_candles, use_demo)
                    bt_df.attrs.update({
                        "symbol": symbol, "market": market, "interval": ltf,
                        "currency": df.attrs.get("currency","USD") if df is not None else "USD",
                    })

                    if bt_demo:
                        st.info("🎮 Menggunakan data simulasi untuk backtest")

                    bt_engine = BT(
                        capital  = bt_capital,
                        fee      = bt_fee,
                        slippage = 0.0005,
                        risk_pct = bt_risk,
                        sl_mult  = bt_sl,
                        tp_mult  = bt_tp,
                        min_conf = min_conf,
                    )

                    if use_wfa:
                        result = bt_engine.walk_forward(
                            bt_df, symbol, market, ltf,
                            n_folds=n_folds, train_ratio=0.70
                        )
                    else:
                        result = bt_engine.run(bt_df, symbol, market, ltf)

                    st.success("✅ Backtest selesai!")
                    if RBT:
                        RBT(result, symbol=symbol)
                    else:
                        st.json(result.metrics.to_dict())

                except Exception as e:
                    st.error(f"❌ Backtest gagal: {e}")
                    import traceback
                    st.code(traceback.format_exc())
        else:
            st.info(
                f"Klik **Jalankan Backtest** untuk simulasi strategi "
                f"di {bt_candles} candle historis {symbol} ({ltf}). "
                f"Modal simulasi: ${bt_capital:,}"
            )


# ─────────────────────────────────────────────────────────────────────────────
# TAB S&R — Support & Resistance
# ─────────────────────────────────────────────────────────────────────────────
with tab_sr:
    st.markdown("#### 📐 Support & Resistance Auto-Detection")
    st.caption(
        "Deteksi level Support dan Resistance secara otomatis dari data historis "
        "menggunakan 4 metode: Pivot Points, Volume Profile, Round Numbers, dan Fibonacci."
    )

    SRD = M.get("SRDetector")
    RSR = M.get("render_sr")

    if SRD is None:
        st.error("sr_detector.py tidak ditemukan.")
    elif df is None or len(df) < 30:
        st.warning("Data belum tersedia. Klik Refresh Data terlebih dahulu.")
    else:
        col_sr1, col_sr2, col_sr3 = st.columns(3)
        sr_window = col_sr1.slider("Pivot Window", 5, 20, 10,
                                   help="Candle kiri/kanan untuk deteksi pivot")
        sr_max    = col_sr2.slider("Maks Level", 5, 20, 12,
                                   help="Jumlah maksimal level yang ditampilkan")
        sr_fib    = col_sr3.slider("Fibonacci Lookback", 50, 300, 100,
                                   help="Jumlah candle untuk hitung swing high/low Fibonacci")

        if st.button("🔍 Deteksi S/R", use_container_width=True, type="primary"):
            with st.spinner("Mendeteksi level Support & Resistance..."):
                try:
                    detector = SRD(
                        pivot_window    = sr_window,
                        max_levels      = sr_max,
                        fib_lookback    = sr_fib,
                        merge_threshold = 0.003,
                    )
                    sr_result = detector.detect(df)

                    st.success(
                        f"✅ Ditemukan {len(sr_result.levels)} level S/R | "
                        f"Support: {len(sr_result.supports())} | "
                        f"Resistance: {len(sr_result.resistances())}"
                    )

                    if RSR:
                        RSR(sr_result, df, symbol=symbol)
                    else:
                        st.json([lv.to_dict() for lv in sr_result.levels])

                    # Integrasi dengan sinyal
                    if signal_result:
                        st.divider()
                        st.markdown("#### 🔗 Kaitkan dengan Sinyal")
                        sig = signal_result.signal.value
                        close = signal_result.close

                        if sr_result.nearest_sup and sr_result.nearest_res:
                            sup_dist = abs(close - sr_result.nearest_sup.price) / close
                            res_dist = abs(close - sr_result.nearest_res.price) / close

                            if sig == "BUY":
                                if sup_dist < 0.02:
                                    st.success("✅ Sinyal BUY dikonfirmasi — harga dekat Support kuat")
                                elif res_dist < 0.02:
                                    st.warning("⚠️ Sinyal BUY tapi harga dekat Resistance — risiko rejection")
                                else:
                                    st.info(f"ℹ️ Sinyal BUY | Support {sup_dist:.1%} di bawah | Resistance {res_dist:.1%} di atas")
                            elif sig == "SELL":
                                if res_dist < 0.02:
                                    st.success("✅ Sinyal SELL dikonfirmasi — harga dekat Resistance kuat")
                                elif sup_dist < 0.02:
                                    st.warning("⚠️ Sinyal SELL tapi harga dekat Support — risiko bounce")
                                else:
                                    st.info(f"ℹ️ Sinyal SELL | Support {sup_dist:.1%} di bawah | Resistance {res_dist:.1%} di atas")

                except Exception as e:
                    st.error(f"Error: {e}")
                    import traceback
                    st.code(traceback.format_exc())
        else:
            col_info1, col_info2 = st.columns(2)
            col_info1.info(
                "**4 Metode Deteksi:**\n"
                "- 🔵 Pivot Points (High/Low lokal)\n"
                "- 🟣 Volume Profile (level volume tinggi)\n"
                "- 🟤 Round Numbers (harga psikologis)\n"
                "- 📐 Fibonacci Retracement"
            )
            col_info2.info(
                "**Cara Pakai:**\n"
                "- Klik Deteksi S/R\n"
                "- Lihat level terdekat dari harga saat ini\n"
                "- JANGAN beli dekat Resistance\n"
                "- JANGAN jual dekat Support"
            )


# ─────────────────────────────────────────────────────────────────────────────
# TAB CANDLE — Candlestick Pattern Detector
# ─────────────────────────────────────────────────────────────────────────────
with tab_candle:
    st.markdown("#### 🕯️ Candlestick Pattern Detector")
    st.caption(
        "Deteksi 18 pola candlestick klasik dari 3 candle terakhir. "
        "Gunakan sebagai konfirmasi tambahan sebelum eksekusi sinyal."
    )

    CD  = M.get("CandleDetector")
    RCD = M.get("render_candle")

    if CD is None:
        st.error("candle_detector.py tidak ditemukan.")
    elif df is None or len(df) < 5:
        st.warning("Data belum tersedia.")
    else:
        try:
            detector     = CD()
            candle_res   = detector.detect(df)
            sig_val      = signal_result.signal.value if signal_result else "HOLD"
            candle_res.confirm_signal = detector.check_confirmation(candle_res, sig_val)

            if RCD:
                RCD(candle_res, signal_from_engine=sig_val)
            else:
                st.json([p.to_dict() for p in candle_res.patterns])

        except Exception as e:
            st.error(f"Error: {e}")

# ─────────────────────────────────────────────────────────────────────────────
# TAB 3 — PREDIKSI TRADE
# ─────────────────────────────────────────────────────────────────────────────
with tab_predict:
    st.markdown("#### 🔮 Prediksi Trade — Candle ke Depan")
    st.caption(
        "Proyeksi posisi BUY/SELL/HOLD untuk candle berikutnya "
        "berdasarkan tren EMA dan momentum aktual. "
        "Estimasi profit/loss dihitung dari modal yang kamu masukkan."
    )

    col_n, col_s, col_t = st.columns(3)
    n_pred    = col_n.slider("Jumlah Candle Proyeksi", 1, 10, 5)
    sl_pred   = col_s.slider("SL Multiplier", 1.0, 4.0, 2.0, 0.5)
    tp_pred   = col_t.slider("TP Multiplier", 1.5, 6.0, 3.0, 0.5)

    if is_demo:
        st.warning("⚠️ Mode Demo aktif — matikan di sidebar untuk prediksi berbasis data pasar real.")

    if st.button("🔮 Generate Prediksi", use_container_width=True, type="primary"):
        PT = M.get("PredictiveTrade")
        if PT is None:
            st.error("Module predictive_trade.py tidak ditemukan.")
        elif df is None or len(df) < 30:
            st.warning("Data tidak cukup untuk prediksi.")
        else:
            with st.spinner("Memproyeksi candle ke depan..."):
                try:
                    pt = PT(sl_mult=sl_pred, tp_mult=tp_pred, min_confidence=15.0)
                    rows = pt.generate(
                        df          = df,
                        n_candles   = n_pred,
                        capital_usd = capital,
                        risk_pct    = risk_pct,
                    )
                    if rows:
                        pt.render(rows, symbol=symbol, capital_usd=capital)
                    else:
                        st.warning("Tidak ada prediksi — coba dengan data lebih banyak")
                except Exception as e:
                    st.error(f"Error: {e}")
                    import traceback
                    st.code(traceback.format_exc())
    else:
        now_wib = pd.Timestamp.now(tz="UTC").tz_convert("Asia/Jakarta")
        st.info(
            f"⏰ Sekarang: **{now_wib.strftime('%d %b %Y %H:%M WIB')}**\n\n"
            f"Klik Generate Prediksi untuk melihat proyeksi {n_pred} candle {ltf} "
            f"berikutnya beserta estimasi profit/loss berdasarkan modal **${capital:,}**."
        )


# ─────────────────────────────────────────────────────────────────────────────
# TAB PANDUAN — Step-by-step cara eksekusi
# ─────────────────────────────────────────────────────────────────────────────
with tab_guide:
    st.markdown("## 📖 Panduan Eksekusi QuantPulse Pro")
    st.caption("Cara membaca sinyal dan mengeksekusi trade di broker")

    st.markdown("### 🔄 Alur Kerja Harian")
    st.markdown("""
1. **Buka QuantPulse Pro** pagi dan sore hari (short-term trading)
2. **Pilih market dan simbol** yang ingin dianalisis di sidebar
3. **Klik Refresh Data** untuk ambil data terbaru
4. **Cek tab Sinyal** → lihat BUY / SELL / HOLD
5. **Jika BUY atau SELL** → lanjut ke tab Risk & Eksekusi
6. **Konfirmasi dengan tab S&R dan Candle** → pastikan sinyal valid
7. **Eksekusi di broker** dengan level yang diberikan
8. **Tambah ke Portfolio** untuk monitoring posisi
    """)

    st.divider()

    col_g1, col_g2 = st.columns(2)

    with col_g1:
        st.markdown("### 🟢 Cara Eksekusi Sinyal BUY")
        st.markdown("""
**Langkah di broker (MetaTrader / Binance / dll):**

1. Buka order baru → pilih **BUY / Long**
2. **Entry Price** → gunakan harga dari tab Risk
   - Di Forex/Crypto: gunakan **Market Order** (harga saat ini)
   - Atau **Limit Order** di harga entry yang disarankan
3. **Stop Loss** → masukkan angka SL dari tab Risk
   - WAJIB dipasang — lindungi modal dari kerugian besar
4. **Take Profit** → masukkan angka TP dari tab Risk
   - Otomatis close saat target profit tercapai
5. **Lot/Volume** → sesuaikan dengan "Units" di tab Risk
6. Klik **BUY / Open Long**

⚠️ **Jangan buka posisi jika:**
- Confidence < 30%
- Ada tanda ⚠️ VETO di tab Risk
- Harga dekat Resistance kuat (cek tab S&R)
- Pola candle berlawanan (cek tab Candle)
        """)

    with col_g2:
        st.markdown("### 🔴 Cara Eksekusi Sinyal SELL")
        st.markdown("""
**Langkah di broker:**

1. Buka order baru → pilih **SELL / Short**
   - Di Crypto spot: berarti **jual aset yang dipegang**
   - Di Forex/CFD: berarti **open short position**
2. **Entry Price** → gunakan harga dari tab Risk
3. **Stop Loss** → dipasang di ATAS harga entry (untuk SELL)
4. **Take Profit** → dipasang di BAWAH harga entry
5. **Lot/Volume** → sesuaikan dengan "Units" di tab Risk
6. Klik **SELL / Open Short**

⚠️ **Jangan open SELL jika:**
- Harga dekat Support kuat (cek tab S&R)
- Pola candle bullish kuat (Hammer, Engulfing)
- MTFA Alignment positif (semua timeframe bullish)
        """)

    st.divider()

    st.markdown("### 🟡 Kapan HOLD Berarti?")
    col_h1, col_h2 = st.columns(2)
    col_h1.info("""
**Jika belum punya posisi:**
→ Jangan buka posisi baru
→ Tunggu sinyal BUY atau SELL yang jelas
→ Kondisi pasar tidak mendukung
    """)
    col_h2.info("""
**Jika sudah punya posisi:**
→ Pertahankan posisi yang ada
→ Jangan close terlalu cepat
→ Biarkan TP atau SL yang bekerja
    """)

    st.divider()

    st.markdown("### 📊 Cara Membaca Metrik Sinyal")
    metrik_data = {
        "Metrik":       ["Confidence","Final Score","MTFA Alignment","Regime","ATR"],
        "Artinya":      [
            "Keyakinan sistem (25-85%). >40% = valid, <25% = lemah",
            "Kekuatan sinyal (-1 sampai +1). >0.2 = BUY, <-0.2 = SELL",
            "Keselarasan 3 timeframe (-3 sampai +3). >1 = bullish kuat",
            "LOW/NORMAL/HIGH/CRISIS — volatilitas pasar saat ini",
            "Average True Range — ukuran pergerakan harga per candle",
        ],
        "Ideal untuk BUY": [">40%", ">+0.20", ">+1.0", "NORMAL/LOW", "Tidak terlalu besar"],
    }
    import pandas as pd
    st.dataframe(pd.DataFrame(metrik_data), use_container_width=True, hide_index=True)

    st.divider()

    st.markdown("### ⚠️ Rules Wajib (Jangan Dilanggar)")
    st.error("""
1. **Selalu pasang Stop Loss** — tidak ada alasan untuk tidak memasang SL
2. **Jangan averaging down** — jika posisi rugi, jangan tambah lot
3. **Maksimal 3 posisi aktif** — fokus lebih baik dari diversifikasi berlebihan
4. **Berhenti jika drawdown >10%** — evaluasi strategi, jangan revenge trading
5. **Pakai modal yang siap hilang** — jangan gunakan uang kebutuhan pokok
    """)

    st.markdown("### 💡 Tips Short-Term Trading")
    st.success("""
- **Masuk di +1 atau +2 candle prediksi** — akurasi tertinggi, jangan tunggu +4 atau +5
- **Cek S&R dulu sebelum masuk** — jangan beli dekat resistance
- **Konfirmasi dengan candlestick** — Morning Star + BUY signal = entry kuat
- **Gunakan timeframe konsisten** — jika pakai 1h untuk entry, monitoring juga di 1h
- **Catat setiap trade** — gunakan tab Portfolio untuk tracking PnL
    """)

    st.divider()
    st.markdown("### 🏦 Rekomendasi Broker")
    broker_data = {
        "Market":   ["Crypto", "Crypto", "Forex/Gold", "Forex/Gold", "Saham IDX"],
        "Broker":   ["Binance", "OKX", "IC Markets", "XM", "Stockbit / IPOT"],
        "Biaya":    ["0.1%/trade", "0.1%/trade", "0.0 pip + komisi", "~1.6 pip spread", "~0.2%/trade"],
        "Leverage": ["Hingga 10x", "Hingga 10x", "Hingga 500x", "Hingga 888x", "Tidak ada"],
        "Min Deposit": ["$10", "$10", "$200", "$5", "Rp 100rb"],
    }
    st.dataframe(pd.DataFrame(broker_data), use_container_width=True, hide_index=True)
    st.caption("⚠️ Leverage tinggi = risiko tinggi. Mulai dengan leverage rendah atau tanpa leverage.")

# ─────────────────────────────────────────────────────────────────────────────
# TAB DEBUG
# ─────────────────────────────────────────────────────────────────────────────
with tab_debug:
    st.markdown("#### 🔧 Status & Debug")

    # Module status
    st.markdown("**Status Modul:**")
    for mod, err_key in [
        ("DataLoader", "loader_error"),
        ("SignalEngine", "signal_error"),
        ("RiskEngine", "risk_error"),
        ("PredictiveTrade", "predict_error"),
        ("PortfolioManager", "portfolio_error"),
        ("Backtester", "backtester_error"),
    ]:
        if err_key in M:
            st.error(f"❌ {mod}: {M[err_key]}")
        else:
            st.success(f"✅ {mod} — OK")

    # Error log
    errors = st.session_state.get("errors", [])
    if errors:
        st.markdown(f"**Error Log ({len(errors)}):**")
        for e in errors[-5:]:
            st.code(e)
    else:
        st.success("✅ Tidak ada error")

    # Data info
    if df is not None:
        st.divider()
        st.markdown("**Data Info:**")
        ci1, ci2, ci3, ci4, ci5 = st.columns(5)
        ci1.metric("Simbol",   df.attrs.get("symbol", "-"))
        ci2.metric("Market",   df.attrs.get("market", "-"))
        ci3.metric("Candle",   len(df))
        ci4.metric("Sumber",   df.attrs.get("data_source", "demo").upper())
        ci5.metric("Tipe",     df.attrs.get("data_source_type", "-").upper())

        st.markdown("**10 Candle Terakhir:**")
        st.dataframe(df.tail(10), use_container_width=True)

    # Signal JSON
    if signal_result:
        st.divider()
        st.markdown("**Signal Result (JSON):**")
        st.json(signal_result.to_dict())

    # Risk JSON
    if risk_result:
        st.divider()
        st.markdown("**Risk Result (JSON):**")
        st.json(risk_result.to_dict())

    st.divider()
    col_c1, col_c2 = st.columns(2)
    if col_c1.button("🗑️ Clear Cache"):
        st.cache_data.clear()
        st.cache_resource.clear()
        st.success("Cache dikosongkan")
    if col_c2.button("🔄 Reset State"):
        for k in ["df","mtfa","signal","risk","errors"]:
            st.session_state[k] = [] if k == "errors" else None
        st.rerun()

# =============================================================================
# FOOTER
# =============================================================================
st.divider()
st.caption(
    "⚡ QuantPulse Pro V3 · "
    "Data: ccxt (Crypto) + yfinance (Saham/Forex/Gold/Oil) · "
    "Bukan saran investasi — gunakan dengan bijak"
)
