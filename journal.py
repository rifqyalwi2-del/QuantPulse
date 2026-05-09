# =============================================================================
# QuantPulse Pro V3 — Trading Journal
# =============================================================================
from __future__ import annotations
import logging, uuid, io
from dataclasses import dataclass, field
from datetime import datetime, timezone
import pandas as pd

logger = logging.getLogger("QuantPulse.V3.Journal")

def _now(): return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
def _uid(): return str(uuid.uuid4())[:8]


@dataclass
class JournalEntry:
    entry_id:    str
    date:        str
    symbol:      str
    market:      str
    direction:   str   # BUY / SELL
    entry_price: float
    exit_price:  float
    stop_loss:   float
    take_profit: float
    units:       float
    pnl_usd:     float
    pnl_pct:     float
    outcome:     str   # WIN / LOSS / BREAKEVEN / OPEN
    confidence:  float
    regime:      str
    timeframe:   str
    setup:       str   # Deskripsi setup (EMA crossover, S/R bounce, dll)
    mistake:     str   # Kesalahan yang dibuat
    lesson:      str   # Pelajaran yang dipetik
    rating:      int   # 1-5 kualitas eksekusi
    created_at:  str = field(default_factory=_now)

    def to_dict(self):
        outcome_emoji = {"WIN":"✅","LOSS":"❌","BREAKEVEN":"➖","OPEN":"🔵"}.get(self.outcome,"⚪")
        dir_emoji = "🟢" if self.direction == "BUY" else "🔴"
        return {
            "ID":       self.entry_id,
            "Tanggal":  self.date,
            "Simbol":   self.symbol,
            "Arah":     f"{dir_emoji} {self.direction}",
            "TF":       self.timeframe,
            "Entry":    round(self.entry_price, 4),
            "Exit":     round(self.exit_price,  4) if self.exit_price else "-",
            "SL":       round(self.stop_loss,   4),
            "TP":       round(self.take_profit, 4),
            "PnL_USD":  round(self.pnl_usd, 2),
            "PnL%":     f"{self.pnl_pct:+.2%}",
            "Outcome":  f"{outcome_emoji} {self.outcome}",
            "Conf%":    f"{self.confidence:.0f}%",
            "Rating":   "⭐" * self.rating,
            "Setup":    self.setup[:40] if self.setup else "-",
        }


class TradingJournal:
    def __init__(self):
        self.entries: list[JournalEntry] = []

    def add(self, entry: JournalEntry):
        self.entries.append(entry)

    def delete(self, entry_id: str):
        self.entries = [e for e in self.entries if e.entry_id != entry_id]

    def update_exit(self, entry_id: str, exit_price: float):
        for e in self.entries:
            if e.entry_id == entry_id:
                e.exit_price = exit_price
                diff = (exit_price - e.entry_price) if e.direction == "BUY" else (e.entry_price - exit_price)
                e.pnl_usd = diff * e.units
                e.pnl_pct = diff / e.entry_price if e.entry_price > 0 else 0
                e.outcome = "WIN" if e.pnl_usd > 0 else "LOSS" if e.pnl_usd < 0 else "BREAKEVEN"

    def stats(self) -> dict:
        closed = [e for e in self.entries if e.outcome != "OPEN"]
        if not closed:
            return {}
        wins   = [e for e in closed if e.outcome == "WIN"]
        losses = [e for e in closed if e.outcome == "LOSS"]
        total_pnl = sum(e.pnl_usd for e in closed)
        tw = sum(e.pnl_usd for e in wins)
        tl = abs(sum(e.pnl_usd for e in losses))
        by_market = {}
        for e in closed:
            if e.market not in by_market:
                by_market[e.market] = {"win":0,"loss":0,"pnl":0}
            by_market[e.market]["pnl"] += e.pnl_usd
            if e.outcome == "WIN":   by_market[e.market]["win"]  += 1
            if e.outcome == "LOSS":  by_market[e.market]["loss"] += 1
        avg_rating = sum(e.rating for e in self.entries) / len(self.entries) if self.entries else 0
        return {
            "total_trades":  len(closed),
            "open_trades":   len([e for e in self.entries if e.outcome == "OPEN"]),
            "win_rate":      len(wins) / len(closed),
            "total_pnl":     total_pnl,
            "profit_factor": tw / tl if tl > 0 else float("inf"),
            "avg_win":       sum(e.pnl_usd for e in wins)  / len(wins)   if wins   else 0,
            "avg_loss":      sum(e.pnl_usd for e in losses) / len(losses) if losses else 0,
            "best_trade":    max(closed, key=lambda e: e.pnl_usd),
            "worst_trade":   min(closed, key=lambda e: e.pnl_usd),
            "by_market":     by_market,
            "avg_rating":    avg_rating,
        }

    def to_df(self) -> pd.DataFrame:
        if not self.entries:
            return pd.DataFrame()
        return pd.DataFrame([e.to_dict() for e in reversed(self.entries)])

    def to_csv(self) -> bytes:
        if not self.entries:
            return b""
        rows = []
        for e in self.entries:
            rows.append({
                "entry_id": e.entry_id, "date": e.date,
                "symbol": e.symbol, "market": e.market,
                "direction": e.direction, "timeframe": e.timeframe,
                "entry_price": e.entry_price, "exit_price": e.exit_price,
                "stop_loss": e.stop_loss, "take_profit": e.take_profit,
                "units": e.units, "pnl_usd": e.pnl_usd, "pnl_pct": e.pnl_pct,
                "outcome": e.outcome, "confidence": e.confidence,
                "regime": e.regime, "setup": e.setup,
                "mistake": e.mistake, "lesson": e.lesson,
                "rating": e.rating,
            })
        df = pd.DataFrame(rows)
        buf = io.BytesIO()
        df.to_csv(buf, index=False)
        return buf.getvalue()

    def from_csv(self, data: bytes):
        try:
            df = pd.read_csv(io.BytesIO(data))
            for _, row in df.iterrows():
                self.entries.append(JournalEntry(
                    entry_id    = str(row.get("entry_id", _uid())),
                    date        = str(row.get("date","")),
                    symbol      = str(row.get("symbol","")),
                    market      = str(row.get("market","crypto")),
                    direction   = str(row.get("direction","BUY")),
                    entry_price = float(row.get("entry_price",0)),
                    exit_price  = float(row.get("exit_price",0)),
                    stop_loss   = float(row.get("stop_loss",0)),
                    take_profit = float(row.get("take_profit",0)),
                    units       = float(row.get("units",0)),
                    pnl_usd     = float(row.get("pnl_usd",0)),
                    pnl_pct     = float(row.get("pnl_pct",0)),
                    outcome     = str(row.get("outcome","OPEN")),
                    confidence  = float(row.get("confidence",0)),
                    regime      = str(row.get("regime","NORMAL")),
                    timeframe   = str(row.get("timeframe","1h")),
                    setup       = str(row.get("setup","")),
                    mistake     = str(row.get("mistake","")),
                    lesson      = str(row.get("lesson","")),
                    rating      = int(row.get("rating",3)),
                ))
        except Exception as e:
            logger.error(f"[Journal] Import error: {e}")


def get_journal() -> TradingJournal:
    try:
        import streamlit as st
        if "trading_journal" not in st.session_state:
            st.session_state["trading_journal"] = TradingJournal()
        return st.session_state["trading_journal"]
    except ImportError:
        return TradingJournal()


def render_journal(
    symbol: str = "",
    market: str = "crypto",
    signal_result = None,
    risk_result   = None,
    interval: str = "1h",
):
    try:
        import streamlit as st
    except ImportError:
        return

    j = get_journal()

    tab_list, tab_add, tab_stats = st.tabs(["📋 Riwayat", "➕ Catat Trade", "📊 Statistik"])

    # ── Tab Riwayat ──────────────────────────────────────────────────────────
    with tab_list:
        df_j = j.to_df()
        if df_j.empty:
            st.info("Belum ada trade yang dicatat. Mulai dari tab **Catat Trade**.")
        else:
            st.markdown(f"**{len(j.entries)} trade tercatat**")

            # Filter
            col_f1, col_f2, col_f3 = st.columns(3)
            f_outcome = col_f1.multiselect("Outcome", ["WIN","LOSS","BREAKEVEN","OPEN"],
                                            default=["WIN","LOSS","BREAKEVEN","OPEN"], key="jf1")
            f_market  = col_f2.multiselect("Market",
                                            list(set(e.market for e in j.entries)),
                                            default=list(set(e.market for e in j.entries)), key="jf2")
            f_dir     = col_f3.multiselect("Arah", ["BUY","SELL"],
                                            default=["BUY","SELL"], key="jf3")

            filtered = [e for e in j.entries
                        if e.outcome in f_outcome and e.market in f_market and e.direction in f_dir]

            if filtered:
                df_show = pd.DataFrame([e.to_dict() for e in reversed(filtered)])
                st.dataframe(df_show, use_container_width=True, hide_index=True)

                # Update exit
                st.divider()
                st.markdown("**Update Exit Harga (untuk trade OPEN):**")
                open_trades = [e for e in j.entries if e.outcome == "OPEN"]
                if open_trades:
                    opts = {f"{e.symbol} ({e.direction}) @ {e.entry_price}": e.entry_id
                            for e in open_trades}
                    sel_label = st.selectbox("Pilih trade:", list(opts.keys()), key="jsel")
                    sel_id    = opts[sel_label]
                    sel_entry = next(e for e in j.entries if e.entry_id == sel_id)
                    col_ex, col_upd = st.columns([3,1])
                    exit_p = col_ex.number_input("Exit Price", value=float(sel_entry.entry_price), format="%.4f")
                    if col_upd.button("✅ Update", use_container_width=True):
                        j.update_exit(sel_id, exit_p)
                        st.success("Exit diupdate!")
                        st.rerun()

                # Hapus
                with st.expander("🗑️ Hapus trade"):
                    del_opts = {f"{e.entry_id} — {e.symbol} {e.direction} ({e.date})": e.entry_id
                                for e in filtered}
                    del_sel = st.selectbox("Pilih untuk hapus:", list(del_opts.keys()), key="jdel")
                    if st.button("Hapus trade ini", type="secondary"):
                        j.delete(del_opts[del_sel])
                        st.success("Trade dihapus")
                        st.rerun()

            # Export/Import
            st.divider()
            col_exp, col_imp = st.columns(2)
            csv_data = j.to_csv()
            col_exp.download_button(
                "⬇️ Export CSV", data=csv_data,
                file_name="quantpulse_journal.csv", mime="text/csv",
                use_container_width=True
            )
            uploaded = col_imp.file_uploader("⬆️ Import CSV", type="csv", key="jimp")
            if uploaded:
                j.from_csv(uploaded.read())
                st.success("Import berhasil!")
                st.rerun()

    # ── Tab Catat Trade ───────────────────────────────────────────────────────
    with tab_add:
        st.markdown("**Catat trade baru**")

        # Auto-fill dari sinyal aktif
        if signal_result and risk_result:
            st.info(
                f"✨ Auto-fill dari sinyal aktif: **{signal_result.signal.value}** "
                f"{symbol} @ {signal_result.close:,.4f}"
            )

        col1, col2 = st.columns(2)
        j_sym = col1.text_input("Simbol", value=symbol or "", key="jadd_sym")
        j_mkt = col2.selectbox("Market", ["crypto","forex","commodity","stock_id","stock_us"],
                               index=["crypto","forex","commodity","stock_id","stock_us"].index(market)
                               if market in ["crypto","forex","commodity","stock_id","stock_us"] else 0,
                               key="jadd_mkt")

        col3, col4, col5 = st.columns(3)
        j_dir = col3.selectbox("Arah", ["BUY","SELL"], key="jadd_dir")
        j_tf  = col4.selectbox("Timeframe", ["1m","5m","15m","30m","1h","4h","1d"],
                               index=4, key="jadd_tf")
        j_date = col5.text_input("Tanggal", value=_now()[:10], key="jadd_date")

        default_entry = risk_result.entry_price if risk_result else 0.0
        default_sl    = risk_result.stop_loss   if risk_result else 0.0
        default_tp    = risk_result.take_profit  if risk_result else 0.0

        col6, col7, col8, col9 = st.columns(4)
        j_entry = col6.number_input("Entry Price", value=float(default_entry), format="%.4f", key="jadd_en")
        j_exit  = col7.number_input("Exit Price (0=OPEN)", value=0.0, format="%.4f", key="jadd_ex")
        j_sl    = col8.number_input("Stop Loss",  value=float(default_sl),    format="%.4f", key="jadd_sl")
        j_tp    = col9.number_input("Take Profit",value=float(default_tp),    format="%.4f", key="jadd_tp")

        col10, col11, col12 = st.columns(3)
        j_units = col10.number_input("Units/Lot", value=risk_result.units if risk_result else 0.0, format="%.4f", key="jadd_u")
        j_conf  = col11.number_input("Confidence%", value=signal_result.confidence if signal_result else 0.0, format="%.1f", key="jadd_c")
        j_rat   = col12.slider("Rating Eksekusi (1-5)", 1, 5, 3, key="jadd_rat")

        j_setup   = st.text_area("Setup / Alasan Masuk", placeholder="EMA crossover + bounce di support kuat...", key="jadd_setup", height=80)
        j_mistake = st.text_area("Kesalahan (jika ada)", placeholder="Entry terlambat, tidak tunggu konfirmasi...", key="jadd_mis", height=68)
        j_lesson  = st.text_area("Pelajaran", placeholder="Selalu tunggu close candle sebelum entry...", key="jadd_les", height=68)

        if st.button("💾 Simpan ke Jurnal", use_container_width=True, type="primary"):

         if st.button("💾 Simpan ke Jurnal", use_container_width=True, type="primary"):
            if not j_sym.strip():
                st.error("Masukkan simbol terlebih dahulu")
            else:
                # Hitung PnL jika exit sudah diisi
                pnl_usd = 0.0
                pnl_pct = 0.0
                outcome = "OPEN"
                if j_exit > 0 and j_entry > 0:
                    diff = (j_exit - j_entry) if j_dir == "BUY" else (j_entry - j_exit)
                    pnl_usd = diff * j_units
                    pnl_pct = diff / j_entry
                    outcome = "WIN" if pnl_usd > 0 else "LOSS" if pnl_usd < 0 else "BREAKEVEN"

                entry = JournalEntry(
                    entry_id    = _uid(),
                    date        = j_date,
                    symbol      = j_sym.strip().upper(),
                    market      = j_mkt,
                    direction   = j_dir,
                    entry_price = j_entry,
                    exit_price  = j_exit,
                    stop_loss   = j_sl,
                    take_profit = j_tp,
                    units       = j_units,
                    pnl_usd     = pnl_usd,
                    pnl_pct     = pnl_pct,
                    outcome     = outcome,
                    confidence  = j_conf,
                    regime      = signal_result.regime if signal_result else "NORMAL",
                    timeframe   = j_tf,
                    setup       = j_setup,
                    mistake     = j_mistake,
                    lesson      = j_lesson,
                    rating      = j_rat,
                )
                j.add(entry)
                st.success(f"✅ Trade {j_sym.upper()} {j_dir} berhasil dicatat!")
                st.rerun()

    # ── Tab Statistik ─────────────────────────────────────────────────────────
    with tab_stats:
        stats = j.stats()
        if not stats:
            st.info("Belum cukup data. Catat minimal 1 trade yang sudah close.")
        else:
            c1,c2,c3,c4,c5 = st.columns(5)
            c1.metric("Total Trade",    stats["total_trades"])
            c2.metric("Win Rate",       f"{stats['win_rate']:.1%}")
            c3.metric("Total PnL",      f"${stats['total_pnl']:+,.2f}")
            c4.metric("Profit Factor",  f"{stats['profit_factor']:.2f}x" if stats['profit_factor'] < 999 else "∞")
            c5.metric("Avg Rating",     f"{stats['avg_rating']:.1f}⭐")

            st.divider()
            col_best, col_worst = st.columns(2)
            b = stats["best_trade"]
            w = stats["worst_trade"]
            col_best.success(f"✅ **Best Trade**: {b.symbol} {b.direction} +${b.pnl_usd:,.2f} ({b.pnl_pct:+.2%})")
            col_worst.error(f"❌ **Worst Trade**: {w.symbol} {w.direction} ${w.pnl_usd:,.2f} ({w.pnl_pct:+.2%})")

            st.divider()
            st.markdown("#### Performa per Market")
            mkt_rows = []
            for mkt, d in stats["by_market"].items():
                total_m = d["win"] + d["loss"]
                wr_m    = d["win"] / total_m if total_m > 0 else 0
                mkt_rows.append({
                    "Market": mkt.upper(), "Trades": total_m,
                    "Win": d["win"], "Loss": d["loss"],
                    "Win Rate": f"{wr_m:.1%}",
                    "Total PnL": f"${d['pnl']:+,.2f}",
                })
            st.dataframe(pd.DataFrame(mkt_rows), use_container_width=True, hide_index=True)

            st.divider()
            st.markdown("#### 📚 Pelajaran yang Dicatat")
            lessons = [e for e in j.entries if e.lesson and e.lesson.strip()]
            if lessons:
                for e in lessons[-5:]:
                    st.markdown(
                        f"**{e.symbol} {e.direction}** ({e.date}) — "
                        f"{'✅' if e.outcome=='WIN' else '❌'} {e.outcome}"
                    )
                    st.markdown(f"> {e.lesson}")
            else:
                st.info("Belum ada pelajaran yang dicatat.")
