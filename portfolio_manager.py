# =============================================================================
# QuantPulse Pro V3 — Portfolio Manager
# =============================================================================
# Fitur:
#   1. Catat posisi aktif lintas market (Crypto/Forex/Gold/Oil/Saham)
#   2. PnL realtime per posisi dalam USD dan IDR
#   3. Total portofolio: modal, profit, drawdown
#   4. Alert: near SL, drawdown besar, alokasi berlebih
#   5. Riwayat trade yang sudah ditutup
# =============================================================================

from __future__ import annotations
import uuid, logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
import numpy as np
import pandas as pd

logger = logging.getLogger("QuantPulse.V3.Portfolio")
IDR_FALLBACK = 16200

def _now(): return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
def _uid(): return str(uuid.uuid4())[:8]

MARKET_CAPS = {
    "crypto": 0.40, "forex": 0.20, "commodity": 0.20,
    "stock_us": 0.30, "stock_id": 0.30,
}

@dataclass
class Position:
    pos_id:        str
    symbol:        str
    market:        str
    direction:     str
    entry_price:   float
    entry_usd:     float
    current_price: float
    units:         float
    stop_loss:     float
    take_profit:   float
    currency:      str
    idr_rate:      float
    confidence:    float
    regime:        str
    fee_pct:       float = 0.001
    opened_at:     str = field(default_factory=_now)
    updated_at:    str = field(default_factory=_now)

    @property
    def _idr(self):
        return self.idr_rate if self.idr_rate > 1 else max(1/self.idr_rate, 1)

    @property
    def cost_basis(self):
        return self.entry_price * self.units * (1 + self.fee_pct)

    @property
    def cost_basis_usd(self):
        return self.cost_basis if self.currency != "IDR" else self.cost_basis / self._idr

    @property
    def unrealized_pnl(self):
        if self.direction == "BUY":
            return (self.current_price - self.entry_price) * self.units
        return (self.entry_price - self.current_price) * self.units

    @property
    def unrealized_pnl_usd(self):
        return self.unrealized_pnl if self.currency != "IDR" else self.unrealized_pnl / self._idr

    @property
    def unrealized_pnl_idr(self):
        return self.unrealized_pnl_usd * self._idr

    @property
    def pnl_pct(self):
        return self.unrealized_pnl / self.cost_basis if self.cost_basis > 0 else 0

    @property
    def sl_distance_pct(self):
        if self.current_price <= 0 or self.stop_loss <= 0: return 1.0
        return abs(self.current_price - self.stop_loss) / self.current_price

    @property
    def near_sl(self):
        return 0 < self.sl_distance_pct < 0.10

    def update_price(self, p):
        self.current_price = p
        self.updated_at    = _now()

    def to_dict(self):
        return {
            "pos_id": self.pos_id, "symbol": self.symbol,
            "market": self.market, "direction": self.direction,
            "entry": round(self.entry_price, 4),
            "sekarang": round(self.current_price, 4),
            "units": round(self.units, 4),
            "SL": round(self.stop_loss, 4),
            "TP": round(self.take_profit, 4),
            "PnL_USD": round(self.unrealized_pnl_usd, 2),
            "PnL_IDR": round(self.unrealized_pnl_idr, 0),
            "PnL%": f"{self.pnl_pct:+.2%}",
            "Jarak_SL": f"{self.sl_distance_pct:.1%}",
            "Near_SL": "⚠️ YA" if self.near_sl else "✅",
            "Conf": f"{self.confidence:.0f}%",
            "Regime": self.regime,
            "dibuka": self.opened_at,
        }


@dataclass
class ClosedTrade:
    pos_id: str; symbol: str; market: str; direction: str
    entry_price: float; exit_price: float; units: float
    pnl_usd: float; pnl_idr: float; pnl_pct: float
    fee_usd: float; opened_at: str; closed_at: str
    exit_reason: str; currency: str; idr_rate: float

    def to_dict(self):
        return {
            "symbol": self.symbol, "market": self.market,
            "arah": self.direction,
            "entry": round(self.entry_price, 4),
            "exit": round(self.exit_price, 4),
            "units": round(self.units, 4),
            "PnL_USD": round(self.pnl_usd, 2),
            "PnL_IDR": round(self.pnl_idr, 0),
            "PnL%": f"{self.pnl_pct:+.2%}",
            "alasan": self.exit_reason,
            "dibuka": self.opened_at,
            "ditutup": self.closed_at,
        }


class PortfolioManager:
    def __init__(self, initial_capital_usd: float = 1000.0):
        self.initial_capital  = initial_capital_usd
        self.cash_usd         = initial_capital_usd
        self.realized_pnl_usd = 0.0
        self.positions: dict[str, Position] = {}
        self.closed_trades: list[ClosedTrade] = []
        self._peak            = initial_capital_usd
        self._max_dd          = 0.0
        self._daily_start     = initial_capital_usd
        self._idr_rate        = IDR_FALLBACK

    def open_position(self, symbol, market, direction, entry_price, units,
                      stop_loss, take_profit, currency="USD",
                      idr_rate=IDR_FALLBACK, confidence=0.0,
                      regime="NORMAL", fee_pct=0.001, entry_usd=0.0):
        idr      = idr_rate if idr_rate > 1 else max(1/idr_rate, 1)
        cost     = entry_price * units * (1 + fee_pct)
        cost_usd = cost if currency != "IDR" else cost / idr

        if cost_usd > self.cash_usd:
            return False, f"Kas tidak cukup: butuh ${cost_usd:,.2f}, ada ${self.cash_usd:,.2f}", ""

        pos_id = f"pos_{_uid()}"
        self.positions[pos_id] = Position(
            pos_id=pos_id, symbol=symbol, market=market,
            direction=direction, entry_price=entry_price,
            entry_usd=entry_usd or (entry_price if currency!="IDR" else entry_price/idr),
            current_price=entry_price, units=units,
            stop_loss=stop_loss, take_profit=take_profit,
            currency=currency, idr_rate=idr,
            confidence=confidence, regime=regime, fee_pct=fee_pct,
        )
        self.cash_usd -= cost_usd
        return True, f"Posisi dibuka: {pos_id}", pos_id

    def close_position(self, pos_id, exit_price, exit_reason="MANUAL"):
        if pos_id not in self.positions:
            return False, "Posisi tidak ditemukan", 0, 0
        pos = self.positions[pos_id]
        idr = pos._idr
        fee = exit_price * pos.units * pos.fee_pct
        pnl_native = ((exit_price - pos.entry_price) if pos.direction=="BUY"
                      else (pos.entry_price - exit_price)) * pos.units - fee
        pnl_usd = pnl_native if pos.currency!="IDR" else pnl_native/idr
        pnl_idr = pnl_usd * idr
        pnl_pct = pnl_native / pos.cost_basis if pos.cost_basis > 0 else 0
        proceeds = (exit_price*pos.units - fee) if pos.currency!="IDR" else (exit_price*pos.units-fee)/idr
        self.cash_usd         += max(0, proceeds)
        self.realized_pnl_usd += pnl_usd
        self.closed_trades.append(ClosedTrade(
            pos_id=pos_id, symbol=pos.symbol, market=pos.market,
            direction=pos.direction, entry_price=pos.entry_price,
            exit_price=exit_price, units=pos.units,
            pnl_usd=pnl_usd, pnl_idr=pnl_idr, pnl_pct=pnl_pct,
            fee_usd=fee/idr if pos.currency=="IDR" else fee,
            opened_at=pos.opened_at, closed_at=_now(),
            exit_reason=exit_reason, currency=pos.currency, idr_rate=idr,
        ))
        del self.positions[pos_id]
        return True, f"PnL: ${pnl_usd:+,.2f} / Rp {pnl_idr:+,.0f}", pnl_usd, pnl_idr

    def update_prices(self, price_map: dict):
        for pos in self.positions.values():
            if pos.symbol in price_map:
                pos.update_price(price_map[pos.symbol])

    def snapshot(self, idr_rate=IDR_FALLBACK):
        self._idr_rate = idr_rate if idr_rate > 1 else IDR_FALLBACK
        idr = self._idr_rate
        unreal_usd = sum(p.unrealized_pnl_usd for p in self.positions.values())
        total_usd  = self.cash_usd + sum(p.cost_basis_usd + p.unrealized_pnl_usd for p in self.positions.values())
        if total_usd > self._peak: self._peak = total_usd
        dd = (self._peak - total_usd)/self._peak if self._peak > 0 else 0
        self._max_dd = max(self._max_dd, dd)
        daily_usd  = total_usd - self._daily_start
        total_pnl  = total_usd - self.initial_capital
        wins = sum(1 for t in self.closed_trades if t.pnl_usd > 0)
        wr   = wins / len(self.closed_trades) if self.closed_trades else 0

        by_market = {}
        for mkt in MARKET_CAPS:
            mpos = [p for p in self.positions.values() if p.market==mkt]
            val  = sum(p.cost_basis_usd + p.unrealized_pnl_usd for p in mpos)
            by_market[mkt] = {
                "value_usd": val, "value_idr": val*idr,
                "pct": val/total_usd if total_usd>0 else 0,
                "cap": MARKET_CAPS[mkt], "n_pos": len(mpos),
                "over": val/total_usd > MARKET_CAPS[mkt] if total_usd>0 else False,
            }

        alerts = []
        if dd > 0.10:
            alerts.append({"level":"CRISIS" if dd>0.15 else "DANGER",
                           "msg":f"Drawdown {dd:.1%}!"})
        for pos in self.positions.values():
            if pos.near_sl:
                alerts.append({"level":"WARNING",
                               "msg":f"{pos.symbol} mendekati SL! Jarak {pos.sl_distance_pct:.1%}"})
        for mkt,info in by_market.items():
            if info["over"]:
                alerts.append({"level":"WARNING",
                               "msg":f"Alokasi {mkt} ({info['pct']:.1%}) > batas {info['cap']:.0%}"})

        return {
            "timestamp": _now(),
            "total_usd": round(total_usd,2), "total_idr": round(total_usd*idr,0),
            "cash_usd": round(self.cash_usd,2), "cash_idr": round(self.cash_usd*idr,0),
            "unreal_usd": round(unreal_usd,2), "unreal_idr": round(unreal_usd*idr,0),
            "real_usd": round(self.realized_pnl_usd,2), "real_idr": round(self.realized_pnl_usd*idr,0),
            "total_pnl_usd": round(total_pnl,2), "total_pnl_idr": round(total_pnl*idr,0),
            "total_pnl_pct": round(total_pnl/self.initial_capital if self.initial_capital>0 else 0,4),
            "daily_usd": round(daily_usd,2), "daily_idr": round(daily_usd*idr,0),
            "daily_pct": round(daily_usd/self._daily_start if self._daily_start>0 else 0,4),
            "drawdown": round(dd,4), "max_drawdown": round(self._max_dd,4),
            "n_open": len(self.positions), "n_closed": len(self.closed_trades),
            "win_rate": round(wr,4),
            "open_positions": list(self.positions.values()),
            "alerts": alerts, "by_market": by_market,
        }

    def get_risk_context(self):
        snap = self.snapshot(self._idr_rate)
        return {
            "current_drawdown": snap["drawdown"],
            "daily_pnl_pct":   snap["daily_pct"],
            "cash_usd":        self.cash_usd,
            "n_open":          len(self.positions),
        }

    def reset_daily(self):
        snap = self.snapshot(self._idr_rate)
        self._daily_start = snap["total_usd"]


def get_portfolio(initial_capital=1000.0):
    try:
        import streamlit as st
        if "portfolio_v3" not in st.session_state:
            st.session_state["portfolio_v3"] = PortfolioManager(initial_capital)
        return st.session_state["portfolio_v3"]
    except ImportError:
        return PortfolioManager(initial_capital)


def render_portfolio(snap: dict, pm: PortfolioManager):
    try:
        import streamlit as st
    except ImportError:
        print(f"Capital: ${snap['total_usd']:,.2f}")
        return

    for al in snap["alerts"]:
        fn = st.error if al["level"] in ("CRISIS","DANGER") else st.warning if al["level"]=="WARNING" else st.info
        fn(al["msg"])

    c1,c2,c3,c4,c5 = st.columns(5)
    c1.metric("Total Capital", f"${snap['total_usd']:,.2f}", f"Rp {snap['total_idr']:,.0f}")
    c2.metric("Total PnL",     f"${snap['total_pnl_usd']:+,.2f}", f"{snap['total_pnl_pct']:+.2%}")
    c3.metric("PnL Hari Ini",  f"${snap['daily_usd']:+,.2f}", f"{snap['daily_pct']:+.2%}")
    c4.metric("Drawdown",      f"{snap['drawdown']:.2%}", f"max {snap['max_drawdown']:.2%}")
    c5.metric("Kas",           f"${snap['cash_usd']:,.2f}", f"Rp {snap['cash_idr']:,.0f}")

    st.divider()
    col_r, col_u = st.columns(2)
    col_r.metric("Realized PnL",   f"${snap['real_usd']:+,.2f}", f"Rp {snap['real_idr']:+,.0f}")
    col_u.metric("Unrealized PnL", f"${snap['unreal_usd']:+,.2f}", f"Rp {snap['unreal_idr']:+,.0f}")

    st.divider()
    st.markdown(f"#### Posisi Aktif ({snap['n_open']})")
    if snap["open_positions"]:
        df_pos = pd.DataFrame([p.to_dict() for p in snap["open_positions"]])
        st.dataframe(df_pos, use_container_width=True, hide_index=True)

        pos_opts = {f"{p.symbol} ({p.direction}) PnL:${p.unrealized_pnl_usd:+,.2f}": p.pos_id
                    for p in snap["open_positions"]}
        sel = st.selectbox("Tutup posisi:", list(pos_opts.keys()))
        sel_id  = pos_opts[sel]
        sel_pos = pm.positions[sel_id]
        col_ep, col_btn = st.columns([3,1])
        ep = col_ep.number_input("Exit Price", value=float(sel_pos.current_price), format="%.4f")
        if col_btn.button("❌ Tutup", use_container_width=True):
            ok, msg, _, _ = pm.close_position(sel_id, ep, "MANUAL")
            if ok: st.success(msg); st.rerun()
            else:  st.error(msg)
    else:
        st.info("Belum ada posisi aktif.")

    st.divider()
    st.markdown("#### Alokasi per Market")
    alloc = [{"Market":m, "Nilai_USD":f"${i['value_usd']:,.2f}",
               "Nilai_IDR":f"Rp {i['value_idr']:,.0f}",
               "Alokasi":f"{i['pct']:.1%}", "Batas":f"{i['cap']:.0%}",
               "Posisi":i["n_pos"], "Status":"⚠️" if i["over"] else "✅"}
              for m,i in snap["by_market"].items()]
    st.dataframe(pd.DataFrame(alloc), use_container_width=True, hide_index=True)

    if pm.closed_trades:
        st.divider()
        st.markdown(f"#### Riwayat Trade ({snap['n_closed']})")
        df_hist = pd.DataFrame([t.to_dict() for t in reversed(pm.closed_trades[-20:])])
        st.dataframe(df_hist, use_container_width=True, hide_index=True)
        wins   = sum(1 for t in pm.closed_trades if t.pnl_usd > 0)
        tw     = sum(t.pnl_usd for t in pm.closed_trades if t.pnl_usd > 0)
        tl     = abs(sum(t.pnl_usd for t in pm.closed_trades if t.pnl_usd <= 0))
        pf     = f"{tw/tl:.2f}x" if tl > 0 else "∞"
        st.caption(f"Win Rate: {snap['win_rate']:.1%} ({wins}/{snap['n_closed']}) | "
                   f"Total Profit: ${tw:,.2f} | Total Loss: ${tl:,.2f} | Profit Factor: {pf}")
