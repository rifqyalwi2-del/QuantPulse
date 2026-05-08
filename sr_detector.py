# =============================================================================
# QuantPulse Pro V3 — Support & Resistance Auto-Detection
# =============================================================================
# Metode:
#   1. Pivot Points (High/Low lokal) — paling reliable
#   2. Volume Profile — level dengan volume tertinggi = S/R kuat
#   3. Round Numbers — harga bulat psikologis (10000, 50000, dll)
#   4. Fibonacci Retracement — level 23.6%, 38.2%, 50%, 61.8%, 78.6%
#
# Output:
#   - List level S/R dengan strength score
#   - Label: SUPPORT / RESISTANCE / BOTH
#   - Jarak ke harga saat ini dalam %
#   - Visual chart di Streamlit
# =============================================================================

from __future__ import annotations
import logging
from dataclasses import dataclass
import numpy as np
import pandas as pd

logger = logging.getLogger("QuantPulse.V3.SR")


# =============================================================================
# 1. DATA CONTRACT
# =============================================================================

@dataclass
class SRLevel:
    price:      float
    label:      str         # SUPPORT / RESISTANCE / BOTH
    strength:   float       # 0.0 - 1.0
    touches:    int         # Berapa kali harga menyentuh level ini
    method:     str         # pivot / volume / round / fib
    fib_label:  str = ""    # "38.2%" dll jika dari Fibonacci
    dist_pct:   float = 0.0 # Jarak dari harga saat ini dalam %

    @property
    def emoji(self) -> str:
        return {"SUPPORT":"🟢","RESISTANCE":"🔴","BOTH":"🟡"}.get(self.label,"⚪")

    @property
    def strength_bar(self) -> str:
        filled = int(self.strength * 5)
        return "█" * filled + "░" * (5 - filled)

    def to_dict(self) -> dict:
        return {
            "Level":     f"{self.emoji} {self.label}",
            "Harga":     round(self.price, 4),
            "Strength":  self.strength_bar,
            "Touches":   self.touches,
            "Metode":    self.method,
            "Jarak":     f"{self.dist_pct:+.2%}",
            "Fib":       self.fib_label,
        }


@dataclass
class SRResult:
    levels:      list[SRLevel]
    current:     float
    swing_high:  float
    swing_low:   float
    nearest_sup: SRLevel | None
    nearest_res: SRLevel | None
    zone_signal: str   # "NEAR_SUPPORT" / "NEAR_RESISTANCE" / "IN_RANGE"
    zone_note:   str

    def supports(self) -> list[SRLevel]:
        return [l for l in self.levels if l.label in ("SUPPORT","BOTH")]

    def resistances(self) -> list[SRLevel]:
        return [l for l in self.levels if l.label in ("RESISTANCE","BOTH")]


# =============================================================================
# 2. DETECTOR ENGINE
# =============================================================================

class SRDetector:
    """
    Support & Resistance Auto-Detector V3.

    Cara pakai:
        detector = SRDetector()
        result   = detector.detect(df)
        render_sr(result, df)
    """

    def __init__(
        self,
        pivot_window:    int   = 10,    # Candle kiri/kanan untuk pivot
        merge_threshold: float = 0.003, # Level dalam 0.3% digabung jadi 1
        max_levels:      int   = 12,    # Maks level yang ditampilkan
        fib_lookback:    int   = 100,   # Candle untuk hitung Fibonacci
    ):
        self.pivot_window    = pivot_window
        self.merge_threshold = merge_threshold
        self.max_levels      = max_levels
        self.fib_lookback    = fib_lookback

    def detect(self, df: pd.DataFrame) -> SRResult:
        """
        Detect semua S/R level dari DataFrame OHLCV.

        Returns:
            SRResult dengan level terurut dari yang paling dekat ke harga
        """
        if len(df) < self.pivot_window * 3:
            logger.warning("[SR] Data terlalu sedikit")
            return self._empty(df)

        current = float(df["close"].iloc[-1])
        all_levels: list[SRLevel] = []

        # Method 1: Pivot Points
        all_levels.extend(self._pivot_levels(df))

        # Method 2: Volume Profile (jika volume tersedia)
        if "volume" in df.columns and df["volume"].sum() > 0:
            all_levels.extend(self._volume_levels(df))

        # Method 3: Round Numbers
        all_levels.extend(self._round_levels(current, df))

        # Method 4: Fibonacci Retracement
        all_levels.extend(self._fib_levels(df))

        # Merge level yang terlalu dekat
        merged = self._merge_levels(all_levels, current)

        # Hitung jarak ke harga saat ini
        for lv in merged:
            lv.dist_pct = (lv.price - current) / current if current > 0 else 0

        # Label SUPPORT vs RESISTANCE berdasarkan posisi relatif ke harga
        for lv in merged:
            if lv.label == "BOTH":
                pass  # Tetap BOTH
            elif lv.price < current:
                lv.label = "SUPPORT"
            else:
                lv.label = "RESISTANCE"

        # Sort berdasarkan strength
        merged.sort(key=lambda x: x.strength, reverse=True)
        merged = merged[:self.max_levels]

        # Sort final berdasarkan harga
        merged.sort(key=lambda x: x.price)

        # Swing high/low
        swing_high = float(df["high"].tail(self.fib_lookback).max())
        swing_low  = float(df["low"].tail(self.fib_lookback).min())

        # Nearest support dan resistance
        supports    = [l for l in merged if l.price < current]
        resistances = [l for l in merged if l.price >= current]
        nearest_sup = max(supports,    key=lambda x: x.price) if supports    else None
        nearest_res = min(resistances, key=lambda x: x.price) if resistances else None

        # Zone signal
        zone_signal, zone_note = self._zone_signal(
            current, nearest_sup, nearest_res
        )

        return SRResult(
            levels      = merged,
            current     = current,
            swing_high  = swing_high,
            swing_low   = swing_low,
            nearest_sup = nearest_sup,
            nearest_res = nearest_res,
            zone_signal = zone_signal,
            zone_note   = zone_note,
        )

    # ------------------------------------------------------------------
    # Method 1: Pivot Points
    # ------------------------------------------------------------------

    def _pivot_levels(self, df: pd.DataFrame) -> list[SRLevel]:
        levels = []
        w      = self.pivot_window
        high   = df["high"].values
        low    = df["low"].values
        close  = df["close"].values
        n      = len(df)

        for i in range(w, n - w):
            # Pivot High
            if high[i] == max(high[i-w:i+w+1]):
                strength = self._pivot_strength(df, i, "high")
                levels.append(SRLevel(
                    price=float(high[i]), label="RESISTANCE",
                    strength=strength, touches=1, method="pivot"
                ))
            # Pivot Low
            if low[i] == min(low[i-w:i+w+1]):
                strength = self._pivot_strength(df, i, "low")
                levels.append(SRLevel(
                    price=float(low[i]), label="SUPPORT",
                    strength=strength, touches=1, method="pivot"
                ))

        return levels

    def _pivot_strength(self, df: pd.DataFrame, idx: int, ptype: str) -> float:
        """Strength pivot: makin dominan makin kuat."""
        w     = self.pivot_window
        price = float(df["high"].iloc[idx] if ptype=="high" else df["low"].iloc[idx])
        close = df["close"].values

        # Hitung berapa kali harga balik dari level ini
        tolerance = price * 0.003
        touches   = sum(
            1 for i in range(len(close))
            if abs(close[i] - price) <= tolerance
        )

        # Recency bonus: pivot lebih baru lebih relevan
        recency = 1 - (len(df) - idx) / len(df)
        return float(np.clip(0.3 + touches * 0.1 + recency * 0.3, 0, 1))

    # ------------------------------------------------------------------
    # Method 2: Volume Profile
    # ------------------------------------------------------------------

    def _volume_levels(self, df: pd.DataFrame) -> list[SRLevel]:
        """Harga dengan volume tertinggi = S/R kuat."""
        levels = []
        tail   = df.tail(min(200, len(df)))

        price_min = float(tail["low"].min())
        price_max = float(tail["high"].max())
        n_bins    = 20
        bins      = np.linspace(price_min, price_max, n_bins + 1)

        vol_by_bin = np.zeros(n_bins)
        for _, row in tail.iterrows():
            midprice = (row["high"] + row["low"]) / 2
            bin_idx  = min(int((midprice - price_min) / (price_max - price_min) * n_bins), n_bins-1)
            vol_by_bin[bin_idx] += row["volume"]

        max_vol = vol_by_bin.max()
        if max_vol == 0:
            return levels

        # Ambil bin dengan volume tertinggi (top 3)
        top_bins = np.argsort(vol_by_bin)[-3:]
        for b in top_bins:
            if vol_by_bin[b] / max_vol > 0.6:
                price    = (bins[b] + bins[b+1]) / 2
                strength = float(vol_by_bin[b] / max_vol) * 0.8
                levels.append(SRLevel(
                    price=float(price), label="BOTH",
                    strength=strength, touches=2, method="volume"
                ))

        return levels

    # ------------------------------------------------------------------
    # Method 3: Round Numbers (Psychological Levels)
    # ------------------------------------------------------------------

    def _round_levels(self, current: float, df: pd.DataFrame) -> list[SRLevel]:
        """Level harga bulat psikologis."""
        levels = []

        # Tentukan granularitas berdasarkan magnitude harga
        if current >= 10000:
            rounds = [1000, 5000, 10000]
        elif current >= 1000:
            rounds = [100, 500, 1000]
        elif current >= 100:
            rounds = [10, 50, 100]
        elif current >= 10:
            rounds = [1, 5, 10]
        elif current >= 1:
            rounds = [0.1, 0.5, 1]
        else:
            rounds = [0.001, 0.005, 0.01]

        price_range = df["close"].tail(100)
        for r in rounds:
            # Level bulat di sekitar harga saat ini
            base = round(current / r) * r
            for multiplier in range(-3, 4):
                lv_price = base + multiplier * r
                if lv_price <= 0:
                    continue
                # Cek apakah harga pernah bounce dari level ini
                tolerance = lv_price * 0.005
                bounces   = sum(
                    1 for p in price_range
                    if abs(p - lv_price) <= tolerance
                )
                if bounces >= 1 or abs(lv_price - current) / current < 0.05:
                    strength = min(0.3 + bounces * 0.1, 0.7)
                    # Angka paling bulat lebih kuat
                    if lv_price % (r * 5) == 0:
                        strength = min(strength + 0.2, 0.9)
                    levels.append(SRLevel(
                        price=float(lv_price), label="BOTH",
                        strength=strength, touches=bounces, method="round"
                    ))

        return levels

    # ------------------------------------------------------------------
    # Method 4: Fibonacci Retracement
    # ------------------------------------------------------------------

    def _fib_levels(self, df: pd.DataFrame) -> list[SRLevel]:
        """Fibonacci retracement dari swing high ke swing low."""
        tail      = df.tail(min(self.fib_lookback, len(df)))
        swing_hi  = float(tail["high"].max())
        swing_lo  = float(tail["low"].min())
        diff      = swing_hi - swing_lo

        if diff <= 0:
            return []

        fib_ratios = {
            "23.6%": 0.236, "38.2%": 0.382,
            "50.0%": 0.500, "61.8%": 0.618, "78.6%": 0.786,
        }
        fib_strengths = {
            "23.6%": 0.5, "38.2%": 0.7,
            "50.0%": 0.6, "61.8%": 0.85, "78.6%": 0.65,
        }

        levels = []
        for name, ratio in fib_ratios.items():
            # Retracement dari high ke low
            price = swing_hi - diff * ratio
            levels.append(SRLevel(
                price=float(price), label="BOTH",
                strength=fib_strengths[name], touches=0,
                method="fib", fib_label=name
            ))

        return levels

    # ------------------------------------------------------------------
    # Merge & Zone
    # ------------------------------------------------------------------

    def _merge_levels(
        self,
        levels: list[SRLevel],
        current: float,
    ) -> list[SRLevel]:
        """Gabungkan level yang terlalu berdekatan."""
        if not levels:
            return []

        levels.sort(key=lambda x: x.price)
        merged = []
        i      = 0

        while i < len(levels):
            group = [levels[i]]
            j     = i + 1
            while j < len(levels):
                diff = abs(levels[j].price - levels[i].price) / levels[i].price
                if diff <= self.merge_threshold:
                    group.append(levels[j])
                    j += 1
                else:
                    break

            # Gabungkan: ambil harga rata-rata, strength max, touches sum
            avg_price = float(np.mean([l.price    for l in group]))
            max_str   = float(max(l.strength      for l in group))
            tot_touch = sum(l.touches              for l in group)
            methods   = list(set(l.method         for l in group))
            fib_label = next((l.fib_label for l in group if l.fib_label), "")

            # Lebih banyak metode yang agree = lebih kuat
            method_bonus = min((len(methods) - 1) * 0.1, 0.3)
            final_str    = min(max_str + method_bonus, 1.0)

            merged.append(SRLevel(
                price     = avg_price,
                label     = "BOTH",
                strength  = final_str,
                touches   = tot_touch,
                method    = "+".join(methods),
                fib_label = fib_label,
            ))
            i = j

        return merged

    def _zone_signal(
        self,
        current:     float,
        nearest_sup: SRLevel | None,
        nearest_res: SRLevel | None,
    ) -> tuple[str, str]:
        """Tentukan apakah harga dekat S/R."""
        if nearest_sup and abs(current - nearest_sup.price) / current < 0.015:
            return "NEAR_SUPPORT", (
                f"Harga mendekati Support kuat di {nearest_sup.price:,.4f} "
                f"(jarak {abs(current-nearest_sup.price)/current:.2%}) — "
                f"potensi bounce BUY"
            )
        if nearest_res and abs(current - nearest_res.price) / current < 0.015:
            return "NEAR_RESISTANCE", (
                f"Harga mendekati Resistance kuat di {nearest_res.price:,.4f} "
                f"(jarak {abs(current-nearest_res.price)/current:.2%}) — "
                f"waspadai rejection SELL"
            )
        return "IN_RANGE", "Harga berada di tengah zona S/R — tunggu konfirmasi arah"

    def _empty(self, df: pd.DataFrame) -> SRResult:
        current = float(df["close"].iloc[-1]) if len(df) > 0 else 0
        return SRResult(
            levels=[], current=current,
            swing_high=current, swing_low=current,
            nearest_sup=None, nearest_res=None,
            zone_signal="IN_RANGE", zone_note="Data tidak cukup",
        )


# =============================================================================
# 3. STREAMLIT RENDERER
# =============================================================================

def render_sr(result: SRResult, df: pd.DataFrame, symbol: str = ""):
    """Render S/R analysis di Streamlit."""
    try:
        import streamlit as st
    except ImportError:
        for lv in result.levels:
            print(lv.to_dict())
        return

    if not result.levels:
        st.warning("Tidak cukup data untuk deteksi S/R")
        return

    # Zone signal banner
    zone_colors = {
        "NEAR_SUPPORT":    ("#00C851", "🟢"),
        "NEAR_RESISTANCE": ("#FF4444", "🔴"),
        "IN_RANGE":        ("#FFD700", "🟡"),
    }
    zc, ze = zone_colors.get(result.zone_signal, ("#888","⚪"))
    st.markdown(
        f"<div style='background:{zc}18;border:1.5px solid {zc};"
        f"border-radius:10px;padding:12px 16px;margin:8px 0'>"
        f"<span style='color:{zc};font-weight:700'>{ze} {result.zone_signal.replace('_',' ')}</span><br>"
        f"<span style='font-size:0.85rem'>{result.zone_note}</span></div>",
        unsafe_allow_html=True
    )

    # Nearest S/R
    c1, c2, c3 = st.columns(3)
    c1.metric("💰 Harga Saat Ini", f"{result.current:,.4f}")
    if result.nearest_sup:
        c2.metric(
            "🟢 Support Terdekat",
            f"{result.nearest_sup.price:,.4f}",
            f"{result.nearest_sup.dist_pct:.2%}",
            delta_color="normal",
        )
    if result.nearest_res:
        c3.metric(
            "🔴 Resistance Terdekat",
            f"{result.nearest_res.price:,.4f}",
            f"{result.nearest_res.dist_pct:+.2%}",
            delta_color="inverse",
        )

    st.divider()

    # Tabel semua level
    st.markdown("#### 📋 Semua Level S/R")
    rows = [lv.to_dict() for lv in sorted(result.levels, key=lambda x: x.price, reverse=True)]
    df_tbl = pd.DataFrame(rows)
    st.dataframe(df_tbl, use_container_width=True, hide_index=True)

    st.divider()

    # Chart dengan S/R overlay
    st.markdown("#### 📈 Chart dengan Level S/R")
    _render_sr_chart(df, result)

    # Fibonacci levels
    fib_levels = [lv for lv in result.levels if "fib" in lv.method]
    if fib_levels:
        st.divider()
        st.markdown("#### 📐 Fibonacci Retracement")
        st.caption(
            f"Swing High: {result.swing_high:,.4f} → "
            f"Swing Low: {result.swing_low:,.4f}"
        )
        fib_rows = [
            {"Level": lv.fib_label, "Harga": round(lv.price,4),
             "Label": f"{lv.emoji} {lv.label}", "Jarak": f"{lv.dist_pct:+.2%}"}
            for lv in sorted(fib_levels, key=lambda x: x.price, reverse=True)
            if lv.fib_label
        ]
        if fib_rows:
            st.dataframe(pd.DataFrame(fib_rows), use_container_width=True, hide_index=True)

    # Cara membaca
    st.divider()
    with st.expander("📖 Cara Membaca Level S/R"):
        st.markdown("""
**Support (🟢)** — Level di bawah harga saat ini.
Harga cenderung *bounce* naik saat menyentuh support.
→ Potensi entry BUY jika ada konfirmasi sinyal bullish.

**Resistance (🔴)** — Level di atas harga saat ini.
Harga cenderung *reject* turun saat menyentuh resistance.
→ Pertimbangkan exit atau entry SELL jika ada konfirmasi bearish.

**Strength (█)** — Semakin penuh semakin kuat levelnya.
Level kuat = terbentuk dari banyak metode + sering di-touch.

**Catatan penting:**
- Jangan beli tepat di resistance — tunggu *breakout* atau *pullback*
- Jangan jual tepat di support — tunggu *breakdown* atau *bounce*
- Level S/R bukan garis pasti, tapi *zona* ±0.3%
        """)


def _render_sr_chart(df: pd.DataFrame, result: SRResult):
    """Render chart sederhana dengan S/R levels."""
    try:
        import streamlit as st
        # Siapkan data chart
        chart_df = df[["close"]].tail(100).copy()

        # Tambahkan kolom S/R sebagai garis horizontal
        for lv in result.levels:
            if lv.strength >= 0.5:  # Hanya tampilkan level kuat
                col_name = f"{'S' if lv.label=='SUPPORT' else 'R' if lv.label=='RESISTANCE' else 'SR'} {lv.price:.2f}"
                chart_df[col_name] = lv.price

        st.line_chart(chart_df)

    except Exception as e:
        logger.debug(f"[SR Chart] {e}")
