# =============================================================================
# QuantPulse Pro V3 — Position Calculator
# =============================================================================
from __future__ import annotations

def render_calculator(
    default_capital: float = 1000.0,
    default_price:   float = 0.0,
    default_sl:      float = 0.0,
    market:          str   = "crypto",
):
    try:
        import streamlit as st
    except ImportError:
        return

    st.markdown("#### 🧮 Kalkulator Posisi Trading")
    st.caption(
        "Hitung ukuran posisi, margin, dan estimasi profit/loss "
        "sebelum membuka trade. Tidak perlu data live."
    )

    # Spread default per market
    spread_map = {
        "crypto":    0.001, "forex":     0.0002,
        "commodity": 0.0005,"stock_us":  0.0005,
        "stock_id":  0.0025,
    }
    idr_rate = 16200

    col1, col2 = st.columns(2)
    mode = col1.radio("Mode", ["Hitung dari Risk %", "Hitung dari Lot Manual"],
                       horizontal=True, key="calc_mode")
    calc_mkt = col2.selectbox(
        "Market", ["crypto","forex","commodity","stock_id","stock_us"],
        index=["crypto","forex","commodity","stock_id","stock_us"].index(market)
        if market in ["crypto","forex","commodity","stock_id","stock_us"] else 0,
        key="calc_mkt"
    )

    spread = spread_map.get(calc_mkt, 0.001)
    col_m1, col_m2, col_m3 = st.columns(3)
    capital  = col_m1.number_input("Modal ($)", 10.0, 1_000_000.0,
                                    float(default_capital), step=100.0, key="calc_cap")
    risk_pct = col_m2.slider("Risk per Trade (%)", 0.5, 10.0, 1.0, 0.5, key="calc_risk") / 100
    leverage = col_m3.number_input("Leverage (1=spot)", 1, 100, 1, key="calc_lev")

    col_p1, col_p2, col_p3 = st.columns(3)
    entry_price = col_p1.number_input("Entry Price", 0.0001, 10_000_000.0,
                                       float(default_price) if default_price > 0 else 100.0,
                                       format="%.4f", key="calc_entry")
    sl_price = col_p2.number_input("Stop Loss", 0.0001, 10_000_000.0,
                                    float(default_sl) if default_sl > 0 else entry_price * 0.98,
                                    format="%.4f", key="calc_sl")
    direction = col_p3.radio("Arah", ["BUY","SELL"], horizontal=True, key="calc_dir")

    # TP dari R/R ratio
    rr_ratio = st.slider("Risk/Reward Ratio", 1.0, 5.0, 2.0, 0.5, key="calc_rr")

    # Kalkulasi
    sl_dist = abs(entry_price - sl_price)
    sl_pct  = sl_dist / entry_price if entry_price > 0 else 0

    if direction == "BUY":
        tp_price = entry_price + sl_dist * rr_ratio
        entry_broker = entry_price * (1 + spread)
    else:
        tp_price = entry_price - sl_dist * rr_ratio
        entry_broker = entry_price * (1 - spread)

    tp_dist = abs(tp_price - entry_price)
    tp_pct  = tp_dist / entry_price if entry_price > 0 else 0

    # Position sizing
    capital_at_risk = capital * risk_pct
    if sl_dist > 0:
        units = capital_at_risk / sl_dist
    else:
        units = 0

    if mode == "Hitung dari Lot Manual":
        units = st.number_input("Lot / Units", 0.001, 100_000.0, max(units, 0.01),
                                 format="%.4f", key="calc_units_manual")

    # Batasi max position
    pos_value   = units * entry_price
    max_pos     = capital * leverage * 0.5
    if pos_value > max_pos and max_pos > 0:
        units = max_pos / entry_price

    pos_value   = units * entry_price
    margin_req  = pos_value / leverage
    pot_profit  = units * tp_dist
    pot_loss    = units * sl_dist
    pot_prof_idr= pot_profit * idr_rate
    pot_loss_idr= pot_loss   * idr_rate
    pot_prof_pct= pot_profit / capital if capital > 0 else 0
    pot_loss_pct= pot_loss   / capital if capital > 0 else 0

    st.divider()
    st.markdown("#### 📊 Hasil Kalkulasi")

    # Level harga
    c1,c2,c3,c4 = st.columns(4)
    c1.metric("Entry (Exchange)", f"{entry_price:,.4f}")
    c2.metric("Entry (Broker)", f"{entry_broker:,.4f}", f"+{spread:.2%} spread")
    c3.metric("Stop Loss", f"{sl_price:,.4f}", f"-{sl_pct:.2%}")
    c4.metric("Take Profit", f"{tp_price:,.4f}", f"+{tp_pct:.2%}")

    # Position info
    c5,c6,c7,c8 = st.columns(4)
    c5.metric("Lot / Units", f"{units:,.4f}")
    c6.metric("Nilai Posisi", f"${pos_value:,.2f}")
    c7.metric("Margin Required", f"${margin_req:,.2f}")
    c8.metric("R/R Ratio", f"{rr_ratio:.1f}x")

    st.divider()

    # Profit / Loss estimate — kotak besar
    col_prof, col_loss = st.columns(2)
    with col_prof:
        st.markdown(
            f"<div style='background:#00C85118;border:2px solid #00C851;"
            f"border-radius:12px;padding:16px;text-align:center'>"
            f"<div style='color:#00C851;font-size:0.85rem'>🎯 Jika TP Tercapai</div>"
            f"<div style='color:#00C851;font-size:1.8rem;font-weight:900'>+${pot_profit:,.2f}</div>"
            f"<div style='color:#00C851;font-size:0.85rem'>+Rp {pot_prof_idr:,.0f}</div>"
            f"<div style='font-size:0.8rem;color:#aaa;margin-top:4px'>"
            f"+{pot_prof_pct:.2%} dari modal</div>"
            f"</div>",
            unsafe_allow_html=True
        )
    with col_loss:
        st.markdown(
            f"<div style='background:#FF444418;border:2px solid #FF4444;"
            f"border-radius:12px;padding:16px;text-align:center'>"
            f"<div style='color:#FF4444;font-size:0.85rem'>🛑 Jika SL Kena</div>"
            f"<div style='color:#FF4444;font-size:1.8rem;font-weight:900'>-${pot_loss:,.2f}</div>"
            f"<div style='color:#FF4444;font-size:0.85rem'>-Rp {pot_loss_idr:,.0f}</div>"
            f"<div style='font-size:0.8rem;color:#aaa;margin-top:4px'>"
            f"-{pot_loss_pct:.2%} dari modal</div>"
            f"</div>",
            unsafe_allow_html=True
        )

    # Summary tabel siap copy ke broker
    st.divider()
    st.markdown("#### 📋 Ringkasan — Siap Dipakai di Broker")
    import pandas as pd
    summary = pd.DataFrame({
        "Parameter": ["Entry (broker)","Stop Loss","Take Profit","Lot/Units",
                       "Nilai Posisi","Margin","Max Profit","Max Loss"],
        "Nilai":     [f"{entry_broker:,.4f}", f"{sl_price:,.4f}",
                      f"{tp_price:,.4f}",    f"{units:,.4f}",
                      f"${pos_value:,.2f}",  f"${margin_req:,.2f}",
                      f"+${pot_profit:,.2f} (+Rp {pot_prof_idr:,.0f})",
                      f"-${pot_loss:,.2f} (-Rp {pot_loss_idr:,.0f})"],
    })
    st.dataframe(summary, use_container_width=True, hide_index=True)
    st.caption(
        f"💡 Spread {spread:.2%} sudah ditambahkan ke entry. "
        f"Kurs IDR: Rp {idr_rate:,}"
    )
