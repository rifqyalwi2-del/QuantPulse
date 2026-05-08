# =============================================================================
# QuantPulse Pro V3 — Predictive Trade Table
# =============================================================================
# Perubahan dari V2:
#   - Timestamp selalu WIB (UTC+7), selalu di masa DEPAN
#   - Prediksi BUY/SELL berdasarkan EMA + momentum aktual
#   - Estimasi profit/loss dalam USD dan IDR per candle
#   - Confidence menurun secara realistis makin jauh ke depan
# =============================================================================

from __future__ import annotations

import logging
import math
from dataclasses import dataclass

import numpy as np
import pandas as pd

logger = logging.getLogger("QuantPulse.V3.Predictive")

WIB = "Asia/Jakarta"  # UTC+7


@dataclass
class PredictiveRow:
    candle_num:          int
    timestamp_wib:       pd.Timestamp
    position:            str           # BUY / SELL / HOLD
    close_pred:          float         # Prediksi harga close
    range_low:           float
    range_high:          float
    entry_price:         float
    stop_loss:           float
    take_profit:         float
    risk_reward:         float
    confidence:          float
    potential_profit_usd: float
    potential_profit_idr: float
    potential_loss_usd:   float
    potential_loss_idr:   float
    units:               float
    currency:            str
    idr_rate:            float
    note:                str

    @property
    def emoji(self) -> str:
        return {"BUY": "🟢", "SELL": "🔴", "HOLD": "🟡"}.get(self.position, "⚪")

    def to_dict(self) -> dict:
        return {
            "candle":            f"+{self.candle_num}",
            "waktu_wib":         self.timestamp_wib.strftime("%d %b %H:%M WIB"),
            "position":          f"{self.emoji} {self.position}",
            "close_pred":        round(self.close_pred, 4),
            "range":             f"{self.range_low:,.2f} – {self.range_high:,.2f}",
            "entry":             round(self.entry_price, 4),
            "stop_loss":         round(self.stop_loss, 4),
            "take_profit":       round(self.take_profit, 4),
            "risk_reward":       f"{self.risk_reward:.1f}x",
            "confidence":        f"{self.confidence:.0f}%",
            "profit_usd":        f"+${self.potential_profit_usd:,.2f}",
            "profit_idr":        f"+Rp {self.potential_profit_idr:,.0f}",
            "loss_usd":          f"-${self.potential_loss_usd:,.2f}",
            "loss_idr":          f"-Rp {self.potential_loss_idr:,.0f}",
            "units":             round(self.units, 4),
            "catatan":           self.note,
        }


class PredictiveTrade:
    """
    Generator tabel prediksi trade V3.
    - Timestamp selalu di masa depan dalam WIB
    - Sinyal BUY/SELL dari momentum aktual data real
    - Estimasi profit dalam USD dan IDR
    """

    def __init__(
        self,
        sl_mult:        float = 2.0,
        tp_mult:        float = 3.0,
        min_confidence: float = 15.0,
    ):
        self.sl_mult        = sl_mult
        self.tp_mult        = tp_mult
        self.min_confidence = min_confidence

    def generate(
        self,
        df:           pd.DataFrame,
        n_candles:    int   = 5,
        capital_usd:  float = 1000.0,
        risk_pct:     float = 0.01,
    ) -> list[PredictiveRow]:
        """
        Generate tabel prediksi N candle ke depan.

        Args:
            df          : DataFrame dari data_loader (sudah di-wrangle)
            n_candles   : Jumlah candle ke depan (maks 10)
            capital_usd : Modal dalam USD untuk estimasi profit
            risk_pct    : % modal yang dirisiko per trade
        """
        n_candles = min(n_candles, 10)
        if len(df) < 30:
            logger.warning("Data terlalu sedikit untuk prediksi")
            return []

        symbol   = df.attrs.get("symbol", "UNKNOWN")
        interval = df.attrs.get("interval", "1h")
        currency = df.attrs.get("currency", "USD")
        idr_rate = df.attrs.get("idr_rate", 1.0)
        idr_per_usd = 1 / idr_rate if 0 < idr_rate < 1 else idr_rate if idr_rate > 1 else 16200

        # Hitung indikator teknikal dari data aktual
        close   = df["close"].values
        atr     = float(df["atr"].iloc[-1]) if "atr" in df.columns else float(np.mean(df["high"] - df["low"]))
        ema9    = float(df["close"].ewm(span=9,  adjust=False).mean().iloc[-1])
        ema21   = float(df["close"].ewm(span=21, adjust=False).mean().iloc[-1])
        ema50   = float(df["close"].ewm(span=50, adjust=False).mean().iloc[-1])

        # Momentum aktual (rata-rata return 5 candle terakhir)
        returns    = df["close"].pct_change().dropna()
        avg_ret_5  = float(returns.tail(5).mean())
        vol_ret    = float(returns.tail(20).std())
        last_close = float(close[-1])

        # Tentukan arah tren dari EMA
        trend_up   = ema9 > ema21 > ema50
        trend_down = ema9 < ema21 < ema50
        trend_neutral = not trend_up and not trend_down

        # Momentum score: -1 sampai +1
        mom_score = float(np.clip(avg_ret_5 / (vol_ret + 1e-10), -1.5, 1.5))

        # Base timestamp — selalu mulai dari candle BERIKUTNYA setelah SEKARANG
        now_utc  = pd.Timestamp.now(tz="UTC")
        iv_mins  = self._interval_to_minutes(interval)
        epoch    = pd.Timestamp("1970-01-01", tz="UTC")
        mins_now = int((now_utc - epoch).total_seconds() / 60)
        # Candle saat ini dimulai di:
        current_candle_start = epoch + pd.Timedelta(
            minutes=math.floor(mins_now / iv_mins) * iv_mins
        )

        rows      = []
        cur_price = last_close

        for i in range(1, n_candles + 1):
            # Timestamp candle ke-i di masa depan
            ts_utc = current_candle_start + pd.Timedelta(minutes=iv_mins * i)
            ts_wib = ts_utc.tz_convert(WIB)

            # Proyeksi harga dengan decay
            decay      = 0.88 ** i
            momentum   = avg_ret_5 * decay
            # Mean reversion: tarik ke EMA21
            pull_ema   = (ema21 - cur_price) / cur_price * 0.08 * decay
            total_ret  = momentum + pull_ema

            close_pred = cur_price * (1 + total_ret)
            close_pred = max(close_pred, last_close * 0.5)  # Safety floor

            # Range ketidakpastian
            uncertainty = atr * (1.0 + (i - 1) * 0.25)
            range_low   = max(close_pred - uncertainty, 0)
            range_high  = close_pred + uncertainty

            # Tentukan posisi berdasarkan tren + momentum
            confidence = self._calc_confidence(
                trend_up, trend_down, mom_score, decay, i
            )

            position, note = self._determine_position(
                trend_up, trend_down, trend_neutral,
                mom_score, confidence, i
            )

            # SL & TP
            entry = close_pred
            atr_i = atr * (1.0 + (i - 1) * 0.1)  # ATR melebar makin jauh

            if position == "BUY":
                sl = max(entry - atr_i * self.sl_mult, 0)
                tp = entry + atr_i * self.tp_mult
            elif position == "SELL":
                sl = entry + atr_i * self.sl_mult
                tp = max(entry - atr_i * self.tp_mult, 0)
            else:
                sl = max(entry - atr_i * self.sl_mult, 0)
                tp = entry + atr_i * self.tp_mult

            sl_dist = abs(entry - sl)
            tp_dist = abs(tp - entry)
            rr = tp_dist / sl_dist if sl_dist > 0 else 0

            # Position sizing
            capital_risk_usd = capital_usd * risk_pct
            if currency == "IDR":
                capital_risk_idr = capital_risk_usd * idr_per_usd
                units = max(100, round(capital_risk_idr / max(sl_dist, 1) / 100) * 100)
            else:
                close_usd = float(df["close_usd"].iloc[-1]) if "close_usd" in df.columns else last_close
                price_usd = close_pred * (close_usd / last_close) if last_close > 0 else close_pred
                units = capital_risk_usd / max(sl_dist * price_usd / last_close, 1e-10) if sl_dist > 0 else 0

            units = max(units, 0)

            # Estimasi profit/loss
            if currency == "IDR":
                profit_idr = units * tp_dist
                profit_usd = profit_idr / idr_per_usd if idr_per_usd > 0 else 0
                loss_idr   = units * sl_dist
                loss_usd   = loss_idr / idr_per_usd if idr_per_usd > 0 else 0
            else:
                close_usd = float(df["close_usd"].iloc[-1]) if "close_usd" in df.columns else last_close
                ratio = close_usd / last_close if last_close > 0 else 1
                profit_usd = units * tp_dist * ratio
                profit_idr = profit_usd * idr_per_usd
                loss_usd   = units * sl_dist * ratio
                loss_idr   = loss_usd * idr_per_usd

            rows.append(PredictiveRow(
                candle_num           = i,
                timestamp_wib        = ts_wib,
                position             = position,
                close_pred           = close_pred,
                range_low            = range_low,
                range_high           = range_high,
                entry_price          = entry,
                stop_loss            = sl,
                take_profit          = tp,
                risk_reward          = rr,
                confidence           = confidence,
                potential_profit_usd = profit_usd,
                potential_profit_idr = profit_idr,
                potential_loss_usd   = loss_usd,
                potential_loss_idr   = loss_idr,
                units                = units,
                currency             = currency,
                idr_rate             = idr_per_usd,
                note                 = note,
            ))

            cur_price = close_pred

        return rows

    def _calc_confidence(
        self,
        trend_up:   bool,
        trend_down: bool,
        mom_score:  float,
        decay:      float,
        candle_num: int,
    ) -> float:
        """Confidence realistis — makin jauh makin rendah."""
        base = 0.0

        # Tren jelas → confidence lebih tinggi
        if trend_up or trend_down:
            base += 40
        else:
            base += 20

        # Momentum kuat → confidence lebih tinggi
        base += min(abs(mom_score) * 30, 35)

        # Decay per candle
        base *= decay

        # Candle pertama lebih confident
        bonus = max(0, (3 - candle_num) * 5)
        return round(min(base + bonus, 85), 1)

    def _determine_position(
        self,
        trend_up:      bool,
        trend_down:    bool,
        trend_neutral: bool,
        mom_score:     float,
        confidence:    float,
        candle_num:    int,
    ) -> tuple[str, str]:
        """Tentukan posisi berdasarkan tren aktual."""
        if confidence < self.min_confidence:
            return "HOLD", f"Confidence rendah ({confidence:.0f}%) — tunggu konfirmasi"

        threshold = 0.10  # Lebih sensitif dari V2

        if trend_up and mom_score > threshold:
            return "BUY",  f"Uptrend + momentum bullish ({mom_score:+.2f})"
        elif trend_down and mom_score < -threshold:
            return "SELL", f"Downtrend + momentum bearish ({mom_score:+.2f})"
        elif mom_score > threshold * 1.5:
            return "BUY",  f"Momentum bullish kuat ({mom_score:+.2f})"
        elif mom_score < -threshold * 1.5:
            return "SELL", f"Momentum bearish kuat ({mom_score:+.2f})"
        elif candle_num <= 2 and trend_up:
            return "BUY",  f"Uptrend ({mom_score:+.2f})"
        elif candle_num <= 2 and trend_down:
            return "SELL", f"Downtrend ({mom_score:+.2f})"
        else:
            return "HOLD", f"Momentum netral ({mom_score:+.2f})"

    def _interval_to_minutes(self, interval: str) -> int:
        mapping = {
            "1m": 1, "3m": 3, "5m": 5, "15m": 15, "30m": 30,
            "1h": 60, "2h": 120, "4h": 240, "6h": 360,
            "8h": 480, "12h": 720, "1d": 1440, "1w": 10080,
        }
        return mapping.get(interval, 60)

    def render(self, rows: list[PredictiveRow], symbol: str = "", capital_usd: float = 1000):
        """Render tabel di Streamlit."""
        try:
            import streamlit as st
        except ImportError:
            for r in rows:
                print(r.to_dict())
            return

        if not rows:
            st.warning("Tidak ada prediksi — data tidak cukup")
            return

        currency = rows[0].currency
        idr_rate = rows[0].idr_rate

        st.markdown(f"### 🔮 Prediksi Trade — {symbol}")

        now_wib = pd.Timestamp.now(tz="UTC").tz_convert(WIB)
        st.caption(f"⏰ Sekarang: **{now_wib.strftime('%d %b %Y %H:%M WIB')}** · "
                   f"Semua waktu dalam WIB · Kurs: Rp {idr_rate:,.0f}/USD")

        # Summary counts
        buy_c  = sum(1 for r in rows if r.position == "BUY")
        sell_c = sum(1 for r in rows if r.position == "SELL")
        hold_c = sum(1 for r in rows if r.position == "HOLD")
        max_profit_usd = max((r.potential_profit_usd for r in rows if r.position != "HOLD"), default=0)
        max_profit_idr = max_profit_usd * idr_rate

        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("🟢 BUY",  buy_c)
        c2.metric("🔴 SELL", sell_c)
        c3.metric("🟡 HOLD", hold_c)
        c4.metric("💰 Max Profit",  f"${max_profit_usd:,.2f}")
        c5.metric("💰 Max Profit IDR", f"Rp {max_profit_idr:,.0f}")

        st.divider()

        # Tabel utama
        tbl_rows = [r.to_dict() for r in rows]
        df_tbl   = pd.DataFrame(tbl_rows)

       # Rename kolom untuk tampilan
        df_tbl.columns = [
            "Candle", "Waktu (WIB)", "Posisi", "Close Prediksi",
            "Range Harga", "Entry", "Stop Loss", "Take Profit",
            "R/R", "Confidence", "Profit (USD)", "Profit (IDR)",
            "Loss (USD)", "Loss (IDR)", "Units", "Catatan",
        ]

        # Tampilkan kolom utama saja
        display_cols = [
            "Candle", "Waktu (WIB)", "Posisi", "Close Prediksi",
            "Entry", "Stop Loss", "Take Profit", "R/R", "Confidence",
            "Profit (USD)", "Profit (IDR)", "Catatan",
        ]
        st.dataframe(
            df_tbl[display_cols],
            use_container_width=True,
            hide_index=True,
        )

        st.divider()

        # Kartu detail per candle
        st.markdown("#### 📋 Detail Eksekusi per Candle")
        cols = st.columns(min(len(rows), 5))
        for row, col in zip(rows, cols):
            color = {"BUY": "#00C851", "SELL": "#FF4444", "HOLD": "#FFD700"}.get(row.position, "#888")
            with col:
                st.markdown(
                    f"<div style='border:1.5px solid {color};border-radius:10px;"
                    f"padding:10px;text-align:center;background:{color}18'>"
                    f"<div style='color:{color};font-weight:700'>"
                    f"{row.emoji} {row.position}</div>"
                    f"<div style='font-size:0.7rem;color:#888'>+{row.candle_num} candle</div>"
                    f"<div style='font-weight:700'>{row.close_pred:,.2f}</div>"
                    f"<div style='font-size:0.65rem;color:#aaa'>"
                    f"{row.timestamp_wib.strftime('%d %b %H:%M WIB')}</div>"
                    f"<hr style='margin:6px 0;border-color:#333'>"
                    f"<div style='font-size:0.68rem;text-align:left'>"
                    f"📍 Ref: {row.entry_price:,.2f}<br>"
                    f"🛑 SL: {row.stop_loss:,.2f}<br>"
                    f"🎯 TP: {row.take_profit:,.2f}<br>"
                    f"📊 R/R: {row.risk_reward:.1f}x<br>"
                    f"💡 {row.confidence:.0f}%<br>"
                    f"💰 +${row.potential_profit_usd:,.2f}<br>"
                    f"💰 +Rp{row.potential_profit_idr:,.0f}"
                    f"</div></div>",
                    unsafe_allow_html=True,
                )

        # Chart proyeksi
        st.divider()
        st.markdown("#### 📈 Proyeksi Harga ke Depan")
        chart = pd.DataFrame({
            "Prediksi":    [r.close_pred  for r in rows],
            "Batas Bawah": [r.range_low   for r in rows],
            "Batas Atas":  [r.range_high  for r in rows],
        }, index=[r.timestamp_wib.strftime("%H:%M") for r in rows])
        st.line_chart(chart)

        st.caption(
            "⚠️ Proyeksi berbasis momentum & EMA — BUKAN prediksi pasti. "
            "Akurasi tertinggi di +1 dan +2 candle. Selalu gunakan Stop Loss."
        )
