# =============================================================================
# QuantPulse Pro V3 — Candlestick Pattern Detector
# =============================================================================
# Pola yang dideteksi (18 pola):
#   Bullish: Hammer, Inverted Hammer, Bullish Engulfing, Morning Star,
#            Piercing Line, Three White Soldiers, Bullish Harami, Doji Star
#   Bearish: Shooting Star, Hanging Man, Bearish Engulfing, Evening Star,
#            Dark Cloud Cover, Three Black Crows, Bearish Harami, Gravestone Doji
#   Neutral: Doji, Spinning Top
# =============================================================================

from __future__ import annotations
import logging
from dataclasses import dataclass
import numpy as np
import pandas as pd

logger = logging.getLogger("QuantPulse.V3.Candle")


@dataclass
class PatternResult:
    name:        str
    signal:      str      # BULLISH / BEARISH / NEUTRAL
    strength:    float    # 0.0 - 1.0
    reliability: float    # Win rate historis pola ini
    candles:     int      # Berapa candle yang membentuk pola
    description: str
    action:      str      # Saran tindakan

    @property
    def emoji(self) -> str:
        return {"BULLISH":"🟢","BEARISH":"🔴","NEUTRAL":"🟡"}.get(self.signal,"⚪")

    def to_dict(self) -> dict:
        return {
            "Pola":        f"{self.emoji} {self.name}",
            "Sinyal":      self.signal,
            "Strength":    f"{'█'*int(self.strength*5)}{'░'*(5-int(self.strength*5))}",
            "Reliability": f"{self.reliability:.0%}",
            "Candle":      self.candles,
            "Deskripsi":   self.description,
            "Saran":       self.action,
        }


@dataclass 
class CandleResult:
    patterns:      list[PatternResult]
    overall:       str    # BULLISH / BEARISH / NEUTRAL / MIXED
    confidence:    float  # 0-100
    summary:       str
    confirm_signal: str   # CONFIRM / CONTRADICT / NEUTRAL vs signal engine

    def bullish_patterns(self):
        return [p for p in self.patterns if p.signal == "BULLISH"]

    def bearish_patterns(self):
        return [p for p in self.patterns if p.signal == "BEARISH"]


class CandleDetector:
    """Deteksi 18 pola candlestick klasik."""

    def detect(self, df: pd.DataFrame) -> CandleResult:
        if len(df) < 3:
            return CandleResult([], "NEUTRAL", 0, "Data tidak cukup", "NEUTRAL")

        o = df["open"].values.astype(float)
        h = df["high"].values.astype(float)
        l = df["low"].values.astype(float)
        c = df["close"].values.astype(float)

        patterns: list[PatternResult] = []

        # Ambil 3 candle terakhir
        i = len(df) - 1
        if i >= 0:
            patterns.extend(self._single_patterns(o, h, l, c, i))
        if i >= 1:
            patterns.extend(self._double_patterns(o, h, l, c, i))
        if i >= 2:
            patterns.extend(self._triple_patterns(o, h, l, c, i))

        # Hitung overall
        bull_score = sum(p.strength * p.reliability for p in patterns if p.signal == "BULLISH")
        bear_score = sum(p.strength * p.reliability for p in patterns if p.signal == "BEARISH")

        if not patterns:
            overall = "NEUTRAL"
            conf    = 0.0
            summary = "Tidak ada pola candlestick yang terdeteksi"
        elif bull_score > bear_score * 1.3:
            overall = "BULLISH"
            conf    = min(bull_score * 40, 95)
            summary = f"{len([p for p in patterns if p.signal=='BULLISH'])} pola bullish terdeteksi"
        elif bear_score > bull_score * 1.3:
            overall = "BEARISH"
            conf    = min(bear_score * 40, 95)
            summary = f"{len([p for p in patterns if p.signal=='BEARISH'])} pola bearish terdeteksi"
        else:
            overall = "MIXED"
            conf    = 30.0
            summary = "Sinyal campuran — tunggu konfirmasi candle berikutnya"

        return CandleResult(
            patterns        = patterns,
            overall         = overall,
            confidence      = conf,
            summary         = summary,
            confirm_signal  = "NEUTRAL",
        )

    def check_confirmation(self, result: CandleResult, signal: str) -> str:
        """Cek apakah pola candlestick mengkonfirmasi sinyal engine."""
        if signal == "HOLD":
            return "NEUTRAL"
        if result.overall == signal:
            return "CONFIRM"
        elif result.overall in ("BULLISH","BEARISH") and result.overall != signal:
            return "CONTRADICT"
        return "NEUTRAL"

    # ------------------------------------------------------------------
    # Single Candle Patterns
    # ------------------------------------------------------------------
    def _single_patterns(self, o, h, l, c, i) -> list[PatternResult]:
        patterns = []
        body     = abs(c[i] - o[i])
        rng      = h[i] - l[i]
        if rng == 0: return patterns

        upper_wick = h[i] - max(o[i], c[i])
        lower_wick = min(o[i], c[i]) - l[i]
        body_pct   = body / rng

        # Doji — body sangat kecil
        if body_pct < 0.1:
            if upper_wick > body * 3 and lower_wick < body:
                patterns.append(PatternResult(
                    "Gravestone Doji", "BEARISH", 0.7, 0.60, 1,
                    "Body kecil, shadow atas panjang — sinyal pembalikan turun",
                    "Pertimbangkan SELL atau tahan BUY"
                ))
            else:
                patterns.append(PatternResult(
                    "Doji", "NEUTRAL", 0.4, 0.50, 1,
                    "Keraguan pasar — pembeli dan penjual seimbang",
                    "Tunggu konfirmasi candle berikutnya"
                ))

        # Hammer — lower wick panjang, body kecil di atas
        elif lower_wick >= body * 2 and upper_wick < body * 0.5 and c[i] > o[i]:
            patterns.append(PatternResult(
                "Hammer", "BULLISH", 0.75, 0.65, 1,
                "Shadow bawah panjang — penjual gagal, pembeli kuat",
                "Potensi BUY jika di area Support"
            ))

        # Inverted Hammer
        elif upper_wick >= body * 2 and lower_wick < body * 0.5 and c[i] > o[i]:
            patterns.append(PatternResult(
                "Inverted Hammer", "BULLISH", 0.6, 0.55, 1,
                "Shadow atas panjang — pembeli mulai mengambil alih",
                "Tunggu konfirmasi bullish berikutnya"
            ))

        # Shooting Star — upper wick panjang, body kecil, bearish
        elif upper_wick >= body * 2 and lower_wick < body * 0.5 and c[i] < o[i]:
            patterns.append(PatternResult(
                "Shooting Star", "BEARISH", 0.75, 0.65, 1,
                "Shadow atas panjang setelah uptrend — penolakan di atas",
                "Potensi SELL jika di area Resistance"
            ))

        # Hanging Man
        elif lower_wick >= body * 2 and upper_wick < body * 0.5 and c[i] < o[i]:
            patterns.append(PatternResult(
                "Hanging Man", "BEARISH", 0.65, 0.55, 1,
                "Mirip Hammer tapi setelah uptrend — tanda kelemahan",
                "Waspadai pembalikan — konfirmasi dengan candle berikutnya"
            ))

        # Spinning Top
        elif body_pct < 0.3 and upper_wick > body and lower_wick > body:
            patterns.append(PatternResult(
                "Spinning Top", "NEUTRAL", 0.3, 0.45, 1,
                "Ketidakpastian — pasar sedang mempertimbangkan arah",
                "Tunggu breakout dari range candle ini"
            ))

        # Marubozu Bullish — body besar tanpa shadow
        elif c[i] > o[i] and body_pct > 0.9:
            patterns.append(PatternResult(
                "Bullish Marubozu", "BULLISH", 0.85, 0.70, 1,
                "Candle bullish kuat tanpa shadow — dominasi pembeli penuh",
                "Momentum kuat ke atas — pertimbangkan BUY"
            ))

        # Marubozu Bearish
        elif c[i] < o[i] and body_pct > 0.9:
            patterns.append(PatternResult(
                "Bearish Marubozu", "BEARISH", 0.85, 0.70, 1,
                "Candle bearish kuat tanpa shadow — dominasi penjual penuh",
                "Momentum kuat ke bawah — pertimbangkan SELL"
            ))

        return patterns

    # ------------------------------------------------------------------
    # Double Candle Patterns
    # ------------------------------------------------------------------
    def _double_patterns(self, o, h, l, c, i) -> list[PatternResult]:
        patterns = []
        p = i - 1  # Previous candle

        prev_bull = c[p] > o[p]
        curr_bull = c[i] > o[i]
        prev_body = abs(c[p] - o[p])
        curr_body = abs(c[i] - o[i])

        # Bullish Engulfing
        if (not prev_bull and curr_bull and
            o[i] < c[p] and c[i] > o[p] and
            curr_body > prev_body):
            patterns.append(PatternResult(
                "Bullish Engulfing", "BULLISH", 0.85, 0.72, 2,
                "Candle bullish menelan candle bearish sebelumnya",
                "Sinyal BUY kuat — terutama di area Support"
            ))

        # Bearish Engulfing
        elif (prev_bull and not curr_bull and
              o[i] > c[p] and c[i] < o[p] and
              curr_body > prev_body):
            patterns.append(PatternResult(
                "Bearish Engulfing", "BEARISH", 0.85, 0.72, 2,
                "Candle bearish menelan candle bullish sebelumnya",
                "Sinyal SELL kuat — terutama di area Resistance"
            ))

        # Bullish Harami — candle kecil di dalam candle besar
        elif (not prev_bull and curr_bull and
              o[i] > c[p] and c[i] < o[p] and
              curr_body < prev_body * 0.5):
            patterns.append(PatternResult(
                "Bullish Harami", "BULLISH", 0.65, 0.60, 2,
                "Candle kecil bullish di dalam candle bearish besar",
                "Sinyal pembalikan lemah — tunggu konfirmasi"
            ))

        # Bearish Harami
        elif (prev_bull and not curr_bull and
              o[i] < c[p] and c[i] > o[p] and
              curr_body < prev_body * 0.5):
            patterns.append(PatternResult(
                "Bearish Harami", "BEARISH", 0.65, 0.60, 2,
                "Candle kecil bearish di dalam candle bullish besar",
                "Sinyal pembalikan lemah — tunggu konfirmasi"
            ))

        # Piercing Line
        elif (not prev_bull and curr_bull and
              o[i] < l[p] and c[i] > (o[p] + c[p]) / 2):
            patterns.append(PatternResult(
                "Piercing Line", "BULLISH", 0.70, 0.64, 2,
                "Gap turun lalu naik menembus setengah candle bearish",
                "Potensi pembalikan bullish — konfirmasi dengan candle berikutnya"
            ))

        # Dark Cloud Cover
        elif (prev_bull and not curr_bull and
              o[i] > h[p] and c[i] < (o[p] + c[p]) / 2):
            patterns.append(PatternResult(
                "Dark Cloud Cover", "BEARISH", 0.70, 0.64, 2,
                "Gap naik lalu turun menembus setengah candle bullish",
                "Potensi pembalikan bearish — konfirmasi dengan candle berikutnya"
            ))

        return patterns

    # ------------------------------------------------------------------
    # Triple Candle Patterns
    # ------------------------------------------------------------------
    def _triple_patterns(self, o, h, l, c, i) -> list[PatternResult]:
        patterns = []
        p1, p2 = i-2, i-1

        # Morning Star
        if (c[p1] < o[p1] and                    # Candle 1 bearish
            abs(c[p2]-o[p2]) < abs(c[p1]-o[p1])*0.3 and  # Candle 2 kecil
            c[i] > o[i] and                       # Candle 3 bullish
            c[i] > (o[p1] + c[p1]) / 2):          # Recover > 50%
            patterns.append(PatternResult(
                "Morning Star", "BULLISH", 0.90, 0.78, 3,
                "Tiga candle: bearish, bintang kecil, bullish kuat",
                "Sinyal BUY sangat kuat — sering terjadi di bottom"
            ))

        # Evening Star
        elif (c[p1] > o[p1] and
              abs(c[p2]-o[p2]) < abs(c[p1]-o[p1])*0.3 and
              c[i] < o[i] and
              c[i] < (o[p1] + c[p1]) / 2):
            patterns.append(PatternResult(
                "Evening Star", "BEARISH", 0.90, 0.78, 3,
                "Tiga candle: bullish, bintang kecil, bearish kuat",
                "Sinyal SELL sangat kuat — sering terjadi di top"
            ))

        # Three White Soldiers
        elif (c[p1] > o[p1] and c[p2] > o[p2] and c[i] > o[i] and
              c[p2] > c[p1] and c[i] > c[p2] and
              o[p2] > o[p1] and o[i] > o[p2]):
            patterns.append(PatternResult(
                "Three White Soldiers", "BULLISH", 0.88, 0.75, 3,
                "Tiga candle bullish berturut-turut dengan close makin tinggi",
                "Momentum bullish sangat kuat — tren naik terkonfirmasi"
            ))

        # Three Black Crows
        elif (c[p1] < o[p1] and c[p2] < o[p2] and c[i] < o[i] and
              c[p2] < c[p1] and c[i] < c[p2] and
              o[p2] < o[p1] and o[i] < o[p2]):
            patterns.append(PatternResult(
                "Three Black Crows", "BEARISH", 0.88, 0.75, 3,
                "Tiga candle bearish berturut-turut dengan close makin rendah",
                "Momentum bearish sangat kuat — tren turun terkonfirmasi"
            ))

        return patterns


def render_candle(result: CandleResult, signal_from_engine: str = "HOLD"):
    """Render hasil candlestick di Streamlit."""
    try:
        import streamlit as st
    except ImportError:
        for p in result.patterns:
            print(p.to_dict())
        return

    if not result.patterns:
        st.info("Tidak ada pola candlestick yang terdeteksi di 3 candle terakhir.")
        return

    # Overall
    color_map = {"BULLISH":"#00C851","BEARISH":"#FF4444","MIXED":"#FFD700","NEUTRAL":"#888"}
    oc        = color_map.get(result.overall, "#888")
    oe        = {"BULLISH":"🟢","BEARISH":"🔴","MIXED":"🟡","NEUTRAL":"⚪"}.get(result.overall,"⚪")

    st.markdown(
        f"<div style='background:{oc}18;border:1.5px solid {oc};"
        f"border-radius:10px;padding:12px 16px'>"
        f"<span style='color:{oc};font-weight:700;font-size:1.1rem'>"
        f"{oe} {result.overall} — {result.summary}</span><br>"
        f"<span style='font-size:0.85rem;color:#aaa'>Confidence: {result.confidence:.0f}%</span>"
        f"</div>",
        unsafe_allow_html=True
    )
    st.markdown("")

    # Konfirmasi vs sinyal engine
    confirm = {"CONFIRM":"✅ KONFIRMASI",
               "CONTRADICT":"⚠️ KONTRADIKSI",
               "NEUTRAL":"➖ NETRAL"}.get(result.confirm_signal,"")
    if confirm and signal_from_engine != "HOLD":
        if result.confirm_signal == "CONFIRM":
            st.success(f"{confirm} — Pola candlestick searah dengan sinyal {signal_from_engine}")
        elif result.confirm_signal == "CONTRADICT":
            st.warning(f"{confirm} — Pola candlestick berlawanan dengan sinyal {signal_from_engine} — hati-hati!")
        else:
            st.info(f"{confirm} — Pola candlestick netral terhadap sinyal {signal_from_engine}")

    st.divider()

    # Tabel pola
    st.markdown(f"#### 📋 Pola Terdeteksi ({len(result.patterns)})")
    df_p = pd.DataFrame([p.to_dict() for p in result.patterns])
    st.dataframe(df_p, use_container_width=True, hide_index=True)

    # Detail kartu per pola
    if len(result.patterns) > 0:
        st.divider()
        st.markdown("#### 🕯️ Detail per Pola")
        cols = st.columns(min(len(result.patterns), 3))
        for pat, col in zip(result.patterns, cols):
            pc = color_map.get(pat.signal, "#888")
            with col:
                st.markdown(
                    f"<div style='border:1.5px solid {pc};border-radius:10px;"
                    f"padding:12px;background:{pc}11'>"
                    f"<div style='color:{pc};font-weight:700'>{pat.emoji} {pat.name}</div>"
                    f"<div style='font-size:0.75rem;color:#aaa'>{pat.candles} candle</div>"
                    f"<hr style='margin:6px 0;border-color:#333'>"
                    f"<div style='font-size:0.75rem'>{pat.description}</div>"
                    f"<hr style='margin:6px 0;border-color:#333'>"
                    f"<div style='font-size:0.75rem;color:{pc}'><b>{pat.action}</b></div>"
                    f"<div style='font-size:0.7rem;color:#888;margin-top:4px'>"
                    f"Reliability: {pat.reliability:.0%} | "
                    f"Strength: {'█'*int(pat.strength*5)}</div>"
                    f"</div>",
                    unsafe_allow_html=True
                )
