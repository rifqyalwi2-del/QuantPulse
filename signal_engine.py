# =============================================================================
# QuantPulse Pro V3 — Signal Engine
# =============================================================================
# Perubahan dari V2:
#   - Confidence adaptif: dihitung relatif terhadap kekuatan sinyal aktual
#   - Threshold dinamis per volatility regime (tidak lagi hardcode)
#   - MTFA menerima dict DataFrame (bukan MTFABundle object)
#   - Output selalu BUY/SELL/HOLD yang lebih bermakna
# =============================================================================

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

import numpy as np
import pandas as pd

logger = logging.getLogger("QuantPulse.V3.SignalEngine")


# =============================================================================
# 1. SIGNAL TYPES
# =============================================================================

class Signal(str, Enum):
    BUY  = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"

    def emoji(self) -> str:
        return {"BUY": "🟢", "SELL": "🔴", "HOLD": "🟡"}[self.value]

    def score(self) -> int:
        return {"BUY": 1, "SELL": -1, "HOLD": 0}[self.value]


@dataclass
class IndicatorResult:
    name:        str
    signal:      Signal
    value:       float
    weight:      float
    description: str
    strength:    float  # 0.0–1.0, seberapa kuat sinyal ini

    def weighted_score(self) -> float:
        return self.signal.score() * self.weight * self.strength


@dataclass
class SignalResult:
    symbol:      str
    market:      str
    interval:    str
    timestamp:   pd.Timestamp
    signal:      Signal
    confidence:  float          # 0–100%
    score:       float          # -1.0 sampai +1.0
    mtfa_score:  float          # alignment HTF+MTF+LTF
    veto:        bool           # True = sistem menahan
    veto_reason: str
    indicators:  list[IndicatorResult]
    close:       float
    close_usd:   float
    atr:         float
    regime:      str            # LOW / NORMAL / HIGH / CRISIS

    def to_dict(self) -> dict:
        return {
            "symbol":      self.symbol,
            "market":      self.market,
            "interval":    self.interval,
            "timestamp":   str(self.timestamp),
            "signal":      self.signal.value,
            "emoji":       self.signal.emoji(),
            "confidence":  round(self.confidence, 1),
            "score":       round(self.score, 4),
            "mtfa_score":  round(self.mtfa_score, 2),
            "veto":        self.veto,
            "veto_reason": self.veto_reason,
            "close":       round(self.close, 6),
            "close_usd":   round(self.close_usd, 6),
            "atr":         round(self.atr, 6),
            "regime":      self.regime,
            "indicators": [{
                "name":        i.name,
                "signal":      i.signal.value,
                "value":       round(i.value, 4),
                "weight":      i.weight,
                "strength":    round(i.strength, 3),
                "description": i.description,
            } for i in self.indicators],
        }


# =============================================================================
# 2. INDICATORS
# =============================================================================

class IndicatorBase:
    name   = "Base"
    weight = 0.0

    def compute(self, df: pd.DataFrame) -> IndicatorResult:
        raise NotImplementedError


class RSI(IndicatorBase):
    name   = "RSI"
    weight = 0.20

    def __init__(self, period=14, ob=70, os=30):
        self.period = period
        self.ob = ob  # overbought
        self.os = os  # oversold

    def compute(self, df: pd.DataFrame) -> IndicatorResult:
        delta = df["close"].diff()
        g = delta.clip(lower=0).ewm(alpha=1/self.period, adjust=False).mean()
        l = (-delta.clip(upper=0)).ewm(alpha=1/self.period, adjust=False).mean()
        rs  = g / l.replace(0, np.nan)
        rsi = float((100 - 100 / (1 + rs)).iloc[-1])

        if np.isnan(rsi):
            return IndicatorResult(self.name, Signal.HOLD, 0, self.weight, "Data tidak cukup", 0)

        # Strength: seberapa jauh dari zona netral (50)
        if rsi <= self.os:
            sig      = Signal.BUY
            strength = min((self.os - rsi) / self.os, 1.0)
            desc     = f"Oversold RSI={rsi:.1f} (< {self.os})"
        elif rsi >= self.ob:
            sig      = Signal.SELL
            strength = min((rsi - self.ob) / (100 - self.ob), 1.0)
            desc     = f"Overbought RSI={rsi:.1f} (> {self.ob})"
        else:
            sig      = Signal.HOLD
            strength = 0.3
            desc     = f"Netral RSI={rsi:.1f}"

        return IndicatorResult(self.name, sig, rsi, self.weight, desc, strength)


class MACD(IndicatorBase):
    name   = "MACD"
    weight = 0.20

    def __init__(self, fast=12, slow=26, signal=9):
        self.fast   = fast
        self.slow   = slow
        self.signal = signal

    def compute(self, df: pd.DataFrame) -> IndicatorResult:
        ema_f   = df["close"].ewm(span=self.fast,   adjust=False).mean()
        ema_s   = df["close"].ewm(span=self.slow,   adjust=False).mean()
        macd    = ema_f - ema_s
        sig_l   = macd.ewm(span=self.signal, adjust=False).mean()
        hist    = macd - sig_l

        m  = float(macd.iloc[-1])
        s  = float(sig_l.iloc[-1])
        h  = float(hist.iloc[-1])
        ph = float(hist.iloc[-2]) if len(hist) > 1 else h

        crossover_up   = (float(macd.iloc[-2]) <= float(sig_l.iloc[-2])) and (m > s) if len(macd) > 1 else False
        crossover_down = (float(macd.iloc[-2]) >= float(sig_l.iloc[-2])) and (m < s) if len(macd) > 1 else False

        # Strength dari besar histogram
        max_hist = float(hist.abs().rolling(50).max().iloc[-1]) or 1
        strength = min(abs(h) / max_hist, 1.0)

        if crossover_up:
            sig  = Signal.BUY
            desc = f"Bullish crossover MACD={m:.4f}"
            strength = min(strength + 0.3, 1.0)
        elif crossover_down:
            sig  = Signal.SELL
            desc = f"Bearish crossover MACD={m:.4f}"
            strength = min(strength + 0.3, 1.0)
        elif m > s and h > ph:
            sig  = Signal.BUY
            desc = f"Momentum bullish menguat (hist={h:.4f}↑)"
        elif m < s and h < ph:
            sig  = Signal.SELL
            desc = f"Momentum bearish menguat (hist={h:.4f}↓)"
        else:
            sig  = Signal.HOLD
            desc = f"MACD={m:.4f} Signal={s:.4f}"
            strength = 0.2

        return IndicatorResult(self.name, sig, m, self.weight, desc, strength)


class BollingerBands(IndicatorBase):
    name   = "BB"
    weight = 0.15

    def __init__(self, period=20, std=2.0):
        self.period = period
        self.std    = std

    def compute(self, df: pd.DataFrame) -> IndicatorResult:
        sma    = df["close"].rolling(self.period).mean()
        stddev = df["close"].rolling(self.period).std()
        upper  = sma + self.std * stddev
        lower  = sma - self.std * stddev
        pct    = (df["close"] - lower) / (upper - lower).replace(0, np.nan)

        p = float(pct.iloc[-1])
        c = float(df["close"].iloc[-1])
        u = float(upper.iloc[-1])
        l = float(lower.iloc[-1])

        if np.isnan(p):
            return IndicatorResult(self.name, Signal.HOLD, 0, self.weight, "Data tidak cukup", 0)

        if c < l or p < 0:
            strength = min(abs(p), 1.0) if p < 0 else 0.8
            return IndicatorResult(self.name, Signal.BUY, p, self.weight,
                                   f"Di bawah Lower Band (%B={p:.2f})", strength)
        elif c > u or p > 1:
            strength = min(p - 1, 1.0) if p > 1 else 0.8
            return IndicatorResult(self.name, Signal.SELL, p, self.weight,
                                   f"Di atas Upper Band (%B={p:.2f})", strength)
        elif p < 0.25:
            return IndicatorResult(self.name, Signal.BUY, p, self.weight,
                                   f"Mendekati Lower Band (%B={p:.2f})", 0.5)
        elif p > 0.75:
            return IndicatorResult(self.name, Signal.SELL, p, self.weight,
                                   f"Mendekati Upper Band (%B={p:.2f})", 0.5)
        else:
            return IndicatorResult(self.name, Signal.HOLD, p, self.weight,
                                   f"Di tengah band (%B={p:.2f})", 0.2)


class EMACross(IndicatorBase):
    name   = "EMA Cross"
    weight = 0.20

    def __init__(self, fast=9, slow=21):
        self.fast = fast
        self.slow = slow

    def compute(self, df: pd.DataFrame) -> IndicatorResult:
        ef   = df["close"].ewm(span=self.fast, adjust=False).mean()
        es   = df["close"].ewm(span=self.slow, adjust=False).mean()
        diff = ef - es

        d    = float(diff.iloc[-1])
        pd_  = float(diff.iloc[-2]) if len(diff) > 1 else d

        golden = (pd_ <= 0) and (d > 0)
        death  = (pd_ >= 0) and (d < 0)

        # Strength dari jarak EMA
        close = float(df["close"].iloc[-1])
        strength = min(abs(d) / close * 100, 1.0) if close > 0 else 0.5

        if golden:
            return IndicatorResult(self.name, Signal.BUY, d, self.weight,
                                   f"Golden Cross EMA{self.fast}/EMA{self.slow}", min(strength + 0.4, 1.0))
        elif death:
            return IndicatorResult(self.name, Signal.SELL, d, self.weight,
                                   f"Death Cross EMA{self.fast}/EMA{self.slow}", min(strength + 0.4, 1.0))
        elif d > 0:
            return IndicatorResult(self.name, Signal.BUY, d, self.weight,
                                   f"Uptrend EMA{self.fast} > EMA{self.slow}", strength)
        else:
            return IndicatorResult(self.name, Signal.SELL, d, self.weight,
                                   f"Downtrend EMA{self.fast} < EMA{self.slow}", strength)


class Stochastic(IndicatorBase):
    name   = "Stochastic"
    weight = 0.15

    def __init__(self, k=14, d=3, ob=80, os=20):
        self.k  = k
        self.d  = d
        self.ob = ob
        self.os = os

    def compute(self, df: pd.DataFrame) -> IndicatorResult:
        lo  = df["low"].rolling(self.k).min()
        hi  = df["high"].rolling(self.k).max()
        k_  = 100 * (df["close"] - lo) / (hi - lo).replace(0, np.nan)
        d_  = k_.rolling(self.d).mean()

        k = float(k_.iloc[-1])
        d = float(d_.iloc[-1])
        pk = float(k_.iloc[-2]) if len(k_) > 1 else k
        pd = float(d_.iloc[-2]) if len(d_) > 1 else d

        if np.isnan(k) or np.isnan(d):
            return IndicatorResult(self.name, Signal.HOLD, 0, self.weight, "Data tidak cukup", 0)

        k_up   = (pk <= pd) and (k > d)
        k_down = (pk >= pd) and (k < d)
        strength = abs(k - d) / 100

        if k < self.os and k_up:
            return IndicatorResult(self.name, Signal.BUY, k, self.weight,
                                   f"Oversold + K cross up ({k:.1f})", min(strength + 0.4, 1.0))
        elif k > self.ob and k_down:
            return IndicatorResult(self.name, Signal.SELL, k, self.weight,
                                   f"Overbought + K cross down ({k:.1f})", min(strength + 0.4, 1.0))
        elif k < self.os:
            return IndicatorResult(self.name, Signal.BUY, k, self.weight,
                                   f"Oversold zone ({k:.1f})", 0.5)
        elif k > self.ob:
            return IndicatorResult(self.name, Signal.SELL, k, self.weight,
                                   f"Overbought zone ({k:.1f})", 0.5)
        else:
            return IndicatorResult(self.name, Signal.HOLD, k, self.weight,
                                   f"Netral %K={k:.1f}", 0.2)


class VolumeConfirm(IndicatorBase):
    name   = "Volume"
    weight = 0.10

    def __init__(self, period=20, threshold=1.5):
        self.period    = period
        self.threshold = threshold

    def compute(self, df: pd.DataFrame) -> IndicatorResult:
        # Forex/Futures tidak punya volume real
        if df["volume"].sum() < 1:
            return IndicatorResult(self.name, Signal.HOLD, 0, 0.0,
                                   "Volume tidak tersedia (Forex/Futures)", 0)

        avg_vol = df["volume"].rolling(self.period).mean()
        ratio   = float(df["volume"].iloc[-1] / avg_vol.iloc[-1]) if float(avg_vol.iloc[-1]) > 0 else 1.0
        ret     = float(df["returns"].iloc[-1]) if "returns" in df.columns else 0

        strength = min((ratio - 1) / self.threshold, 1.0) if ratio > 1 else 0.1

        if ratio > self.threshold and ret > 0:
            return IndicatorResult(self.name, Signal.BUY, ratio, self.weight,
                                   f"Volume {ratio:.1f}x avg + harga naik", strength)
        elif ratio > self.threshold and ret < 0:
            return IndicatorResult(self.name, Signal.SELL, ratio, self.weight,
                                   f"Volume {ratio:.1f}x avg + harga turun", strength)
        else:
            return IndicatorResult(self.name, Signal.HOLD, ratio, self.weight,
                                   f"Volume rendah ({ratio:.1f}x avg)", 0.1)


# =============================================================================
# 3. SIGNAL ENGINE
# =============================================================================

class SignalEngine:
    """
    Signal Engine V3 — adaptive confidence, proper MTFA integration.
    """

    INDICATOR_CONFIGS = {
        "crypto":    {"rsi_ob": 70, "rsi_os": 30, "ema_fast": 9,  "ema_slow": 21},
        "forex":     {"rsi_ob": 70, "rsi_os": 30, "ema_fast": 9,  "ema_slow": 21},
        "commodity": {"rsi_ob": 70, "rsi_os": 30, "ema_fast": 9,  "ema_slow": 21},
        "stock_us":  {"rsi_ob": 70, "rsi_os": 30, "ema_fast": 10, "ema_slow": 20},
        "stock_id":  {"rsi_ob": 70, "rsi_os": 30, "ema_fast": 10, "ema_slow": 20},
    }

    def analyze(
        self,
        df:         pd.DataFrame,
        mtfa_dfs:   Optional[dict] = None,  # {"htf": df, "mtf": df, "ltf": df}
    ) -> SignalResult:
        """
        Analisis sinyal dari DataFrame OHLCV.

        Args:
            df        : DataFrame dari data_loader.smart_load()
            mtfa_dfs  : Dict 3 timeframe dari data_loader.smart_load_mtfa()
        """
        if len(df) < 30:
            raise ValueError(f"Minimal 30 candle, dapat {len(df)}")

        symbol   = df.attrs.get("symbol", "UNKNOWN")
        market   = df.attrs.get("market", "crypto")
        interval = df.attrs.get("interval", "1h")
        cfg      = self.INDICATOR_CONFIGS.get(market, self.INDICATOR_CONFIGS["crypto"])

        # Deteksi volatility regime
        regime, atr_ratio = self._detect_regime(df)

        # Hitung semua indikator
        indicators_list = [
            RSI(period=14, ob=cfg["rsi_ob"], os=cfg["rsi_os"]),
            MACD(fast=12, slow=26, signal=9),
            BollingerBands(period=20, std=2.0),
            EMACross(fast=cfg["ema_fast"], slow=cfg["ema_slow"]),
            Stochastic(k=14, d=3, ob=80, os=20),
            VolumeConfirm(period=20, threshold=1.5),
        ]

        results = []
        for ind in indicators_list:
            try:
                results.append(ind.compute(df.copy()))
            except Exception as e:
                logger.debug(f"Indikator {ind.name} error: {e}")

        # Ensemble voting dengan strength
        score = self._ensemble_score(results)

        # MTFA alignment
        mtfa_score = self._mtfa_alignment(mtfa_dfs) if mtfa_dfs else 0.0

        # Final score: gabungkan sinyal + MTFA
        # MTFA weight dikurangi agar sinyal LTF lebih independen
        mtfa_weight  = 0.25
        final_score  = (1 - mtfa_weight) * score + mtfa_weight * (mtfa_score / 3.0)

        # Confidence: seberapa kuat dan konsisten sinyal
        confidence = self._calc_confidence(results, final_score, regime)

        # Tentukan sinyal final
        # Threshold adaptif berdasarkan regime
        # Threshold adaptif — lebih sensitif agar BUY/SELL lebih sering muncul
        # di kondisi yang memang trending
        thresholds = {
            "LOW":    0.10,   # Volatilitas rendah → lebih mudah trigger
            "NORMAL": 0.15,   # Diturunkan dari 0.20 → lebih responsif
            "HIGH":   0.22,   # Diturunkan dari 0.30
            "CRISIS": 0.45,   # Tetap ketat saat crisis
        }
        threshold = thresholds.get(regime, 0.15)

        if final_score > threshold:
            signal = Signal.BUY
        elif final_score < -threshold:
            signal = Signal.SELL
        else:
            signal = Signal.HOLD

        # Veto check
        veto        = False
        veto_reason = ""
        if regime == "CRISIS" and signal == Signal.BUY:
            veto        = True
            veto_reason = f"CRISIS regime — volatilitas ekstrem ({atr_ratio:.1f}× normal)"
            signal      = Signal.HOLD
        elif mtfa_score <= -1.5 and signal == Signal.BUY:
            veto        = True
            veto_reason = f"MTFA bearish kuat (score={mtfa_score:.1f}) — jangan melawan tren"
            signal      = Signal.HOLD

        close     = float(df["close"].iloc[-1])
        close_usd = float(df.get("close_usd", df["close"]).iloc[-1]) if "close_usd" in df.columns else close
        atr       = float(df["atr"].iloc[-1]) if "atr" in df.columns else 0

        return SignalResult(
            symbol      = symbol,
            market      = market,
            interval    = interval,
            timestamp   = df.index[-1],
            signal      = signal,
            confidence  = confidence,
            score       = final_score,
            mtfa_score  = mtfa_score,
            veto        = veto,
            veto_reason = veto_reason,
            indicators  = results,
            close       = close,
            close_usd   = close_usd,
            atr         = atr,
            regime      = regime,
        )

    def _ensemble_score(self, results: list[IndicatorResult]) -> float:
        """Weighted ensemble score dengan strength."""
        total_w = sum(r.weight for r in results if r.weight > 0)
        if total_w == 0:
            return 0.0
        weighted_sum = sum(r.weighted_score() for r in results)
        return np.clip(weighted_sum / total_w, -1.0, 1.0)

    def _calc_confidence(
        self,
        results:     list[IndicatorResult],
        final_score: float,
        regime:      str,
    ) -> float:
        """
        Confidence V3 (kalibrasi ulang):
        - Konsistensi indikator (40%)
        - Rata-rata strength (35%)  
        - Absolute score (25%)
        Target range: 25-85% untuk sinyal yang valid
        """
        if not results:
            return 0.0

        active = [r for r in results if r.weight > 0]
        if not active:
            return 0.0

        # Konsistensi: % indikator yang searah dengan final score
        direction  = 1 if final_score > 0 else -1 if final_score < 0 else 0
        agree      = sum(1 for r in active if r.signal.score() == direction)
        consistency= agree / len(active)

        # Strength rata-rata (sudah 0-1)
        avg_str = float(np.mean([r.strength for r in active]))

        # Score absolut — normalize ke 0-1
        score_norm = min(abs(final_score) * 2, 1.0)

        # Baseline confidence — mulai dari 20% agar tidak pernah 0%
        baseline = 20.0

        # Komponen tambahan
        comp = (consistency * 40) + (avg_str * 35) + (score_norm * 25)

        # Total sebelum penalti regime
        raw = baseline + comp * 0.80  # Scale agar maks ~100

        # Penalti regime — jangan terlalu agresif
        regime_mult = {
            "LOW":    0.95,
            "NORMAL": 1.00,
            "HIGH":   0.80,
            "CRISIS": 0.45,
        }.get(regime, 1.0)

        return round(min(raw * regime_mult, 95.0), 1)

    def _detect_regime(self, df: pd.DataFrame) -> tuple[str, float]:
        """Deteksi volatility regime dari ATR ratio."""
        if "atr" not in df.columns or len(df) < 20:
            return "NORMAL", 1.0

        atr_current = float(df["atr"].iloc[-1])
        atr_median  = float(df["atr"].tail(50).median())
        ratio       = atr_current / atr_median if atr_median > 0 else 1.0

        if ratio >= 3.5:   return "CRISIS", ratio
        elif ratio >= 2.0: return "HIGH",   ratio
        elif ratio < 0.5:  return "LOW",    ratio
        else:              return "NORMAL", ratio

    def _mtfa_alignment(self, mtfa_dfs: dict) -> float:
        """
        Hitung alignment score dari 3 timeframe.
        Score -3 sampai +3.
        """
        score = 0.0
        weights = {"htf": 1.2, "mtf": 1.0, "ltf": 0.8}

        for tf_name, df in mtfa_dfs.items():
            if df is None or len(df) < 10:
                continue
            w = weights.get(tf_name, 1.0)
            try:
                # EMA trend direction
                ema9  = df["close"].ewm(span=9,  adjust=False).mean()
                ema21 = df["close"].ewm(span=21, adjust=False).mean()
                trend = 1 if float(ema9.iloc[-1]) > float(ema21.iloc[-1]) else -1

                # Momentum
                ret = float(df["returns"].iloc[-1]) if "returns" in df.columns else 0
                mom = 1 if ret > 0 else -1

                score += (trend * 0.6 + mom * 0.4) * w
            except Exception:
                continue

        return float(np.clip(score, -3, 3))


# =============================================================================
# DEMO
# =============================================================================

if __name__ == "__main__":
    import sys
    sys.path.insert(0, ".")
    from data_loader import smart_load, smart_load_mtfa

    engine = SignalEngine()

    print("QuantPulse Pro V3 — Signal Engine Test")
    print("="*60)

    for sym in ["BTCUSDT", "XAUUSD", "EURUSD"]:
        df, is_demo = smart_load(sym, "1h", 200)
        mtfa, _ = smart_load_mtfa(sym, "4h", "1h", "15m", 200)

        result = engine.analyze(df, mtfa)
        print(f"\n{result.signal.emoji()} {sym} | {result.signal.value} | "
              f"Confidence: {result.confidence:.1f}% | "
              f"Score: {result.score:+.3f} | "
              f"Regime: {result.regime}")
        for ind in result.indicators[:3]:
            print(f"   {ind.signal.emoji()} {ind.name:<12}: {ind.description}")

    print("="*60)
