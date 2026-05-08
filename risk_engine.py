# =============================================================================
# QuantPulse Pro V3 — Risk Engine
# =============================================================================
# Kompatibel dengan semua platform eksekusi:
#   - Crypto Exchange : Binance, OKX, Bybit, KuCoin, dll
#   - Forex Broker    : MT5, cTrader, TradingView, OANDA, IC Markets, dll
#   - Saham IDX       : Stockbit, IPOT, Mirae, BNI Sekuritas, dll
#   - Saham US        : Interactive Brokers, Webull, eToro, dll
#   - Komoditas       : Gold, Oil via broker CFD manapun
#
# Fitur:
#   - Estimasi profit/loss dalam USD dan IDR
#   - Position sizing per market (crypto unit, lot forex, lembar saham)
#   - Veto system transparan
#   - Toleransi spread/slippage otomatis per market
#   - Level entry BUY/SELL siap dipakai di platform apapun
# =============================================================================

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

import numpy as np
import pandas as pd

logger = logging.getLogger("QuantPulse.V3.RiskEngine")

IDR_PER_USD = 16200  # Default fallback, override dengan kurs live


@dataclass
class RiskResult:
    """Output lengkap Risk Engine — semua yang dibutuhkan untuk eksekusi trade."""

    # Status
    approved:       bool
    veto_reasons:   list[str]

    # Sinyal
    signal:         str    # BUY / SELL / HOLD
    confidence:     float

    # Harga eksekusi
    entry_price:    float
    stop_loss:      float
    take_profit:    float
    sl_distance:    float   # Jarak SL dari entry
    tp_distance:    float   # Jarak TP dari entry
    sl_pct:         float   # SL dalam %
    tp_pct:         float   # TP dalam %
    risk_reward:    float   # TP/SL ratio

    # Position sizing
    units:          float   # Jumlah unit/lembar/lot
    position_value_usd: float
    position_value_idr: float
    capital_at_risk_usd: float
    capital_at_risk_idr: float

    # Estimasi keuntungan
    potential_profit_usd: float   # Jika TP tercapai
    potential_profit_idr: float
    potential_loss_usd:   float   # Jika SL kena
    potential_loss_idr:   float
    profit_pct:           float   # % dari modal

    # Konteks
    atr:            float
    regime:         str
    regime_note:    str
    market:         str
    currency:       str
    idr_rate:       float   # Kurs USD/IDR yang dipakai

    # VaR
    var_95_usd:     float
    var_95_idr:     float

    # Toleransi Spread — level siap pakai di semua platform
    spread_pct:        float = 0.001  # Spread % per market
    entry_buy_broker:  float = 0.0    # Entry BUY (harga ASK) — pakai ini untuk open BUY
    entry_sell_broker: float = 0.0    # Entry SELL (harga BID) — pakai ini untuk open SELL
    sl_buy_broker:     float = 0.0    # Stop Loss untuk posisi BUY
    tp_buy_broker:     float = 0.0    # Take Profit untuk posisi BUY
    sl_sell_broker:    float = 0.0    # Stop Loss untuk posisi SELL
    tp_sell_broker:    float = 0.0    # Take Profit untuk posisi SELL

    def to_dict(self) -> dict:
        return {
            "approved":           self.approved,
            "veto_reasons":       self.veto_reasons,
            "signal":             self.signal,
            "confidence":         round(self.confidence, 1),
            "entry_price":        round(self.entry_price, 6),
            "stop_loss":          round(self.stop_loss, 6),
            "take_profit":        round(self.take_profit, 6),
            "sl_pct":             round(self.sl_pct, 4),
            "tp_pct":             round(self.tp_pct, 4),
            "risk_reward":        round(self.risk_reward, 2),
            "units":              round(self.units, 6),
            "position_value_usd": round(self.position_value_usd, 2),
            "position_value_idr": round(self.position_value_idr, 0),
            "capital_at_risk_usd":round(self.capital_at_risk_usd, 2),
            "capital_at_risk_idr":round(self.capital_at_risk_idr, 0),
            "potential_profit_usd":round(self.potential_profit_usd, 2),
            "potential_profit_idr":round(self.potential_profit_idr, 0),
            "potential_loss_usd": round(self.potential_loss_usd, 2),
            "potential_loss_idr": round(self.potential_loss_idr, 0),
            "profit_pct":         round(self.profit_pct, 4),
            "atr":                round(self.atr, 6),
            "regime":             self.regime,
            "var_95_usd":         round(self.var_95_usd, 2),
            "var_95_idr":         round(self.var_95_idr, 0),
            "spread_pct":         round(self.spread_pct, 4),
            "entry_buy_broker":   round(self.entry_buy_broker, 6),
            "entry_sell_broker":  round(self.entry_sell_broker, 6),
            "sl_buy_broker":      round(self.sl_buy_broker, 6),
            "tp_buy_broker":      round(self.tp_buy_broker, 6),
            "sl_sell_broker":     round(self.sl_sell_broker, 6),
            "tp_sell_broker":     round(self.tp_sell_broker, 6),
        }


class RiskEngine:
    """
    Risk Engine V3.

    Cara pakai:
        engine = RiskEngine(
            capital_usd    = 1000,   # Modal dalam USD
            risk_per_trade = 0.01,   # 1% per trade
        )
        result = engine.evaluate(signal_result, df)
        print(f"Entry: {result.entry_price}")
        print(f"Potensi profit: ${result.potential_profit_usd:,.2f} (Rp {result.potential_profit_idr:,.0f})")
    """

    def __init__(
        self,
        capital_usd:    float = 1000.0,
        risk_per_trade: float = 0.01,     # 1%
        max_position:   float = 0.10,     # Maks 10% modal per posisi
        sl_atr_mult:    float = 2.0,      # SL = ATR × 2
        tp_atr_mult:    float = 3.0,      # TP = ATR × 3
        min_rr:         float = 1.5,      # Min Risk/Reward
        kelly_fraction: float = 0.25,     # 25% Kelly (konservatif)
        min_confidence: float = 25.0,     # Min confidence untuk approve
    ):
        self.capital_usd    = capital_usd
        self.risk_per_trade = risk_per_trade
        self.max_position   = max_position
        self.sl_atr_mult    = sl_atr_mult
        self.tp_atr_mult    = tp_atr_mult
        self.min_rr         = min_rr
        self.kelly_fraction = kelly_fraction
        self.min_confidence = min_confidence

    def evaluate(
        self,
        signal_result,           # SignalResult dari SignalEngine
        df:         pd.DataFrame,
        idr_rate:   float = None,  # Kurs IDR/USD (None = ambil dari df.attrs)
        win_rate:   float = 0.55,
        avg_win:    float = 0.03,
        avg_loss:   float = 0.015,
    ) -> RiskResult:
        """
        Evaluasi risk dan hitung semua level eksekusi + estimasi profit.

        Args:
            signal_result : SignalResult dari SignalEngine
            df            : DataFrame OHLCV yang sama
            idr_rate      : Kurs 1 USD = X IDR (default 16200)
        """
        # Ekstrak info
        signal     = signal_result.signal.value if hasattr(signal_result.signal, 'value') else str(signal_result.signal)
        confidence = signal_result.confidence
        regime     = signal_result.regime
        atr        = signal_result.atr
        close      = signal_result.close
        close_usd  = signal_result.close_usd
        market     = signal_result.market
        currency   = df.attrs.get("currency", "USD")

        # Kurs IDR
        if idr_rate is None:
            idr_rate = df.attrs.get("idr_rate", 1.0)
            if idr_rate <= 0 or idr_rate > 1:
                idr_rate = 1.0
        # Konversi: jika idr_rate = 0.0000617 (1 IDR = X USD), balik jadi IDR per USD
        usd_per_idr = idr_rate if idr_rate < 1 else 1 / idr_rate
        idr_per_usd = 1 / usd_per_idr if usd_per_idr > 0 else IDR_PER_USD

        # Veto checks
        veto_reasons = []
        if signal == "HOLD":
            pass  # HOLD tidak perlu veto
        elif regime == "CRISIS":
            veto_reasons.append(f"⛔ CRISIS regime — volatilitas ekstrem, jangan beli")
        if confidence < self.min_confidence and signal != "HOLD":
            veto_reasons.append(f"⚠️ Confidence {confidence:.1f}% terlalu rendah (min {self.min_confidence:.0f}%)")

        # Hitung ATR (gunakan dari df jika tersedia)
        if atr <= 0 and "atr" in df.columns:
            atr = float(df["atr"].iloc[-1])
        if atr <= 0:
            atr = close * 0.01  # Fallback: 1% dari harga

        # SL & TP berdasarkan arah sinyal
        entry = close_usd if currency == "IDR" else close

        # Untuk saham IDX, hitung dalam IDR
        entry_native = close  # Dalam mata uang asal

        regime_mult = {"LOW": 0.8, "NORMAL": 1.0, "HIGH": 1.5, "CRISIS": 2.0}.get(regime, 1.0)
        atr_adj = atr * regime_mult

        if signal == "BUY":
            sl = entry_native - atr_adj * self.sl_atr_mult
            tp = entry_native + atr_adj * self.tp_atr_mult
        elif signal == "SELL":
            sl = entry_native + atr_adj * self.sl_atr_mult
            tp = entry_native - atr_adj * self.tp_atr_mult
        else:
            sl = entry_native - atr_adj * self.sl_atr_mult
            tp = entry_native + atr_adj * self.tp_atr_mult

        sl = max(sl, 0)
        sl_dist = abs(entry_native - sl)
        tp_dist = abs(tp - entry_native)
        sl_pct  = sl_dist / entry_native if entry_native > 0 else 0
        tp_pct  = tp_dist / entry_native if entry_native > 0 else 0
        rr      = tp_dist / sl_dist if sl_dist > 0 else 0

        # Veto: RR terlalu rendah
        if rr < self.min_rr and signal != "HOLD":
            veto_reasons.append(f"⚠️ Risk/Reward {rr:.2f}x terlalu rendah (min {self.min_rr:.1f}x)")

        approved = len(veto_reasons) == 0 and signal != "HOLD"

        # Position sizing
        capital_risk_usd = self.capital_usd * self.risk_per_trade

        # Hitung units berdasarkan market
        lot_size = df.attrs.get("lot_size", 1.0)

        if currency == "IDR":
            # Saham IDX: hitung dalam IDR
            capital_idr = self.capital_usd * idr_per_usd
            capital_risk_idr = capital_idr * self.risk_per_trade
            sl_dist_idr = sl_dist  # Sudah dalam IDR
            units_by_risk = capital_risk_idr / sl_dist_idr if sl_dist_idr > 0 else 0
            # Snap ke lot size (kelipatan 100 lembar)
            units = max(lot_size, round(units_by_risk / lot_size) * lot_size)
            # Cap max position
            max_units = (capital_idr * self.max_position) / close if close > 0 else 0
            units = min(units, max_units)
        else:
            # USD-based markets
            units_by_risk = capital_risk_usd / (sl_dist * close_usd / close) if sl_dist > 0 and close > 0 else 0
            # Kelly
            if avg_loss > 0:
                b         = avg_win / avg_loss
                kelly_raw = max(0, win_rate - (1 - win_rate) / b)
                kelly_cap = self.capital_usd * kelly_raw * self.kelly_fraction / (close_usd if close_usd > 0 else 1)
                units_by_risk = min(units_by_risk, kelly_cap) if kelly_cap > 0 else units_by_risk

            # Cap max position
            max_units = (self.capital_usd * self.max_position) / (close_usd if close_usd > 0 else 1)
            units     = min(units_by_risk, max_units)

        units = max(units, 0)

        # Nilai posisi
        if currency == "IDR":
            pos_idr = units * close
            pos_usd = pos_idr / idr_per_usd if idr_per_usd > 0 else 0
        else:
            pos_usd = units * close_usd
            pos_idr = pos_usd * idr_per_usd

        # Modal berisiko
        risk_usd = units * sl_dist * (close_usd / close if close > 0 else 1) if currency != "IDR" else (units * sl_dist) / idr_per_usd
        risk_idr = risk_usd * idr_per_usd

        # Estimasi profit/loss
        if signal == "BUY":
            profit_native = units * tp_dist
            loss_native   = units * sl_dist
        elif signal == "SELL":
            profit_native = units * tp_dist
            loss_native   = units * sl_dist
        else:
            profit_native = 0
            loss_native   = 0

        if currency == "IDR":
            profit_idr = profit_native
            profit_usd = profit_idr / idr_per_usd if idr_per_usd > 0 else 0
            loss_idr   = loss_native
            loss_usd   = loss_idr / idr_per_usd if idr_per_usd > 0 else 0
        else:
            profit_usd = profit_native * (close_usd / close if close > 0 else 1)
            profit_idr = profit_usd * idr_per_usd
            loss_usd   = loss_native * (close_usd / close if close > 0 else 1)
            loss_idr   = loss_usd * idr_per_usd

        profit_pct = profit_usd / self.capital_usd if self.capital_usd > 0 else 0

        # VaR historis sederhana
        if "returns" in df.columns and len(df) >= 30:
            rets     = df["returns"].dropna().tail(252)
            var_95   = float(abs(np.percentile(rets, 5))) * pos_usd
        else:
            var_95   = pos_usd * 0.02
        var_95_idr = var_95 * idr_per_usd

        # ─── Spread & Broker Entry Tolerance ─────────────────────────────────────
        # Spread default per market — mencerminkan selisih antara harga exchange
        # dan harga eksekusi di broker/platform (BID-ASK spread + komisi)
        # Kompatibel: MT5, cTrader, Binance, OKX, Bybit, Stockbit, IPOT, dll
        spread_defaults = {
            "crypto":    0.0010,  # 0.10% — exchange spot (OKX, Bybit, Binance)
            "forex":     0.0002,  # 0.02% — ECN broker (IC Markets, Pepperstone)
            "commodity": 0.0005,  # 0.05% — Gold/Oil CFD
            "stock_us":  0.0005,  # 0.05% — US equity (IBKR, Webull)
            "stock_id":  0.0025,  # 0.25% — Saham IDX (Stockbit, IPOT, Mirae)
        }
        spread_pct = spread_defaults.get(market, 0.001)

        # Entry BUY = harga ASK (lebih tinggi dari mid price)
        # Entry SELL = harga BID (lebih rendah dari mid price)
        entry_buy_broker  = entry_native * (1 + spread_pct)
        entry_sell_broker = entry_native * (1 - spread_pct)

        # SL & TP disesuaikan dari entry broker
        if signal == "BUY":
            sl_buy_broker  = max(entry_buy_broker - sl_dist, 0)
            tp_buy_broker  = entry_buy_broker + tp_dist
            sl_sell_broker = entry_sell_broker + sl_dist   # referensi SELL
            tp_sell_broker = max(entry_sell_broker - tp_dist, 0)
        elif signal == "SELL":
            sl_sell_broker = entry_sell_broker + sl_dist
            tp_sell_broker = max(entry_sell_broker - tp_dist, 0)
            sl_buy_broker  = max(entry_buy_broker - sl_dist, 0)  # referensi BUY
            tp_buy_broker  = entry_buy_broker + tp_dist
        else:
            sl_buy_broker  = max(entry_buy_broker - sl_dist, 0)
            tp_buy_broker  = entry_buy_broker + tp_dist
            sl_sell_broker = entry_sell_broker + sl_dist
            tp_sell_broker = max(entry_sell_broker - tp_dist, 0)
        # ──────────────────────────────────────────────────────────────────────

        # Regime note
        regime_notes = {
            "LOW":    "Volatilitas rendah — sinyal mungkin lemah",
            "NORMAL": "Kondisi pasar normal",
            "HIGH":   "Volatilitas tinggi — SL lebih lebar dari biasa",
            "CRISIS": "CRISIS — hindari membuka posisi baru",
        }

        return RiskResult(
            approved            = approved,
            veto_reasons        = veto_reasons,
            signal              = signal,
            confidence          = confidence,
            entry_price         = entry_native,
            stop_loss           = sl,
            take_profit         = tp,
            sl_distance         = sl_dist,
            tp_distance         = tp_dist,
            sl_pct              = sl_pct,
            tp_pct              = tp_pct,
            risk_reward         = rr,
            units               = units,
            position_value_usd  = pos_usd,
            position_value_idr  = pos_idr,
            capital_at_risk_usd = risk_usd,
            capital_at_risk_idr = risk_idr,
            potential_profit_usd= profit_usd,
            potential_profit_idr= profit_idr,
            potential_loss_usd  = loss_usd,
            potential_loss_idr  = loss_idr,
            profit_pct          = profit_pct,
            atr                 = atr,
            regime              = regime,
            regime_note         = regime_notes.get(regime, ""),
            market              = market,
            currency            = currency,
            idr_rate            = idr_per_usd,
            var_95_usd          = var_95,
            var_95_idr          = var_95_idr,
            spread_pct          = spread_pct,
            entry_buy_broker    = entry_buy_broker,
            entry_sell_broker   = entry_sell_broker,
            sl_buy_broker       = sl_buy_broker,
            tp_buy_broker       = tp_buy_broker,
            sl_sell_broker      = sl_sell_broker,
            tp_sell_broker      = tp_sell_broker,
        )
