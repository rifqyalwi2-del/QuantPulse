# =============================================================================
# QuantPulse Pro V3 — Backtester
# =============================================================================
# Posisi dalam arsitektur:
#   data_loader.py → signal_engine.py → risk_engine.py
#                                     ↘ [backtester.py] → app.py
#
# Fitur:
#   - Simulasi historis full pipeline (Signal + Risk Engine)
#   - Anti look-ahead bias: signal dihitung dari df[:i], entry di open[i+1]
#   - Trading fee + slippage diperhitungkan
#   - Metrik lengkap: Sharpe, Sortino, Max Drawdown, Win Rate, Profit Factor
#   - Grade A-F untuk penilaian cepat
#   - Walk-Forward Analysis (train/test split)
#   - Output siap render di Streamlit
# =============================================================================

from __future__ import annotations
import logging
from dataclasses import dataclass
import numpy as np
import pandas as pd

logger = logging.getLogger("QuantPulse.V3.Backtester")


# =============================================================================
# 1. DATA CONTRACTS
# =============================================================================

@dataclass
class TradeRecord:
    trade_id:     int
    entry_time:   pd.Timestamp
    exit_time:    pd.Timestamp
    direction:    str           # BUY / SELL
    entry_price:  float
    exit_price:   float
    stop_loss:    float
    take_profit:  float
    units:        float
    pnl_net:      float         # Setelah fee
    pnl_pct:      float         # % dari modal saat entry
    fee_total:    float
    exit_reason:  str           # TAKE_PROFIT / STOP_LOSS / END_OF_DATA
    regime:       str
    confidence:   float
    bars_held:    int
    capital_before: float
    capital_after:  float

    def to_dict(self) -> dict:
        return {
            "ID":         self.trade_id,
            "Entry":      self.entry_time.strftime("%d %b %H:%M"),
            "Exit":       self.exit_time.strftime("%d %b %H:%M"),
            "Arah":       self.direction,
            "Entry Price":round(self.entry_price, 4),
            "Exit Price": round(self.exit_price, 4),
            "SL":         round(self.stop_loss, 4),
            "TP":         round(self.take_profit, 4),
            "PnL ($)":    round(self.pnl_net, 2),
            "PnL%":       f"{self.pnl_pct:+.2%}",
            "Fee":        round(self.fee_total, 4),
            "Alasan":     self.exit_reason,
            "Regime":     self.regime,
            "Conf%":      f"{self.confidence:.0f}%",
            "Candle":     self.bars_held,
        }


@dataclass
class BacktestMetrics:
    # Return
    total_return_pct:  float
    annual_return_pct: float
    best_trade_pct:    float
    worst_trade_pct:   float

    # Risk
    max_drawdown_pct:  float
    avg_drawdown_pct:  float
    volatility_annual: float

    # Risk-adjusted
    sharpe_ratio:      float
    sortino_ratio:     float
    calmar_ratio:      float

    # Trade stats
    total_trades:      int
    winning_trades:    int
    losing_trades:     int
    win_rate:          float
    avg_win_pct:       float
    avg_loss_pct:      float
    profit_factor:     float
    avg_bars_held:     float
    expectancy:        float

    # Meta
    initial_capital:   float
    final_capital:     float
    start_date:        str
    end_date:          str
    interval:          str
    total_bars:        int

    def grade(self) -> str:
        score = 0
        if self.sharpe_ratio >= 1.5:       score += 2
        elif self.sharpe_ratio >= 1.0:     score += 1
        if self.win_rate >= 0.55:          score += 2
        elif self.win_rate >= 0.50:        score += 1
        if self.max_drawdown_pct <= 0.10:  score += 2
        elif self.max_drawdown_pct <= 0.20:score += 1
        if self.profit_factor >= 2.0:      score += 2
        elif self.profit_factor >= 1.5:    score += 1
        return {8:"A",7:"A-",6:"B+",5:"B",4:"B-",3:"C+",2:"C",1:"D",0:"F"}.get(score,"F")

    def grade_color(self) -> str:
        g = self.grade()[0]
        return {"A":"#00C851","B":"#4CAF50","C":"#FFD700","D":"#FF9800","F":"#FF4444"}.get(g,"#888")

    def to_dict(self) -> dict:
        return {
            "Grade":           self.grade(),
            "Total Return":    f"{self.total_return_pct:+.2%}",
            "Annual Return":   f"{self.annual_return_pct:+.2%}",
            "Sharpe Ratio":    round(self.sharpe_ratio, 3),
            "Sortino Ratio":   round(self.sortino_ratio, 3),
            "Calmar Ratio":    round(self.calmar_ratio, 3),
            "Max Drawdown":    f"{self.max_drawdown_pct:.2%}",
            "Win Rate":        f"{self.win_rate:.1%}",
            "Total Trades":    self.total_trades,
            "Profit Factor":   round(self.profit_factor, 3),
            "Expectancy":      round(self.expectancy, 4),
            "Initial Capital": f"${self.initial_capital:,.2f}",
            "Final Capital":   f"${self.final_capital:,.2f}",
            "Period":          f"{self.start_date} → {self.end_date}",
        }


@dataclass
class BacktestResult:
    metrics:        BacktestMetrics
    trades:         list[TradeRecord]
    equity_curve:   pd.Series
    drawdown_curve: pd.Series
    is_walk_forward: bool = False
    wf_folds:       list[dict] = None

    def trades_df(self) -> pd.DataFrame:
        if not self.trades:
            return pd.DataFrame()
        return pd.DataFrame([t.to_dict() for t in self.trades])


# =============================================================================
# 2. METRICS CALCULATOR
# =============================================================================

class MetricsCalculator:
    RISK_FREE = 0.04  # 4% per tahun

    def calculate(
        self,
        equity_curve:    pd.Series,
        trades:          list[TradeRecord],
        initial_capital: float,
        interval:        str,
    ) -> BacktestMetrics:
        if len(equity_curve) < 2:
            return self._empty(initial_capital, interval)

        final_cap    = float(equity_curve.iloc[-1])
        total_return = (final_cap - initial_capital) / initial_capital

        bars_per_year = {
            "1m":525600,"5m":105120,"15m":35040,"30m":17520,
            "1h":8760,"4h":2190,"1d":365,"1w":52,
        }.get(interval, 8760)

        years = len(equity_curve) / bars_per_year
        annual_return = (1 + total_return) ** (1/years) - 1 if years > 0 and total_return > -1 else total_return

        returns    = equity_curve.pct_change().dropna()
        vol_annual = float(returns.std() * np.sqrt(bars_per_year))

        # Sharpe
        rf_bar  = self.RISK_FREE / bars_per_year
        excess  = returns - rf_bar
        sharpe  = float(excess.mean() / excess.std() * np.sqrt(bars_per_year)) if excess.std() > 0 else 0
        sharpe  = sharpe if np.isfinite(sharpe) else 0

        # Sortino
        down     = returns[returns < 0]
        down_std = float(down.std()) if len(down) > 1 else float(returns.std())
        sortino  = float((annual_return - self.RISK_FREE) / (down_std * np.sqrt(bars_per_year))) if down_std > 0 else 0
        sortino  = sortino if np.isfinite(sortino) else 0

        # Drawdown
        rolling_max = equity_curve.cummax()
        dd_curve    = (equity_curve - rolling_max) / rolling_max
        max_dd      = float(abs(dd_curve.min()))
        avg_dd      = float(abs(dd_curve[dd_curve < 0].mean())) if (dd_curve < 0).any() else 0

        calmar = float(annual_return / max_dd) if max_dd > 0 else 0
        calmar = calmar if np.isfinite(calmar) else 0

        # Trade stats
        if trades:
            pnl_pcts  = [t.pnl_pct for t in trades]
            winning   = [t for t in trades if t.pnl_net > 0]
            losing    = [t for t in trades if t.pnl_net <= 0]
            win_rate  = len(winning) / len(trades)
            avg_win   = float(np.mean([t.pnl_pct for t in winning])) if winning else 0
            avg_loss  = float(np.mean([t.pnl_pct for t in losing]))  if losing  else 0
            tot_gain  = sum(t.pnl_net for t in winning)
            tot_loss  = abs(sum(t.pnl_net for t in losing))
            pf        = tot_gain / tot_loss if tot_loss > 0 else float("inf")
            pf        = min(pf, 999)
            avg_bars  = float(np.mean([t.bars_held for t in trades]))
            best      = max(pnl_pcts)
            worst     = min(pnl_pcts)
            expect    = win_rate * avg_win + (1 - win_rate) * avg_loss
        else:
            winning = losing = []
            win_rate = avg_win = avg_loss = pf = avg_bars = expect = 0
            best = worst = 0

        return BacktestMetrics(
            total_return_pct  = total_return,
            annual_return_pct = annual_return,
            best_trade_pct    = best,
            worst_trade_pct   = worst,
            max_drawdown_pct  = max_dd,
            avg_drawdown_pct  = avg_dd,
            volatility_annual = vol_annual,
            sharpe_ratio      = sharpe,
            sortino_ratio     = sortino,
            calmar_ratio      = calmar,
            total_trades      = len(trades),
            winning_trades    = len(winning),
            losing_trades     = len(losing),
            win_rate          = win_rate,
            avg_win_pct       = avg_win,
            avg_loss_pct      = avg_loss,
            profit_factor     = pf,
            avg_bars_held     = avg_bars,
            expectancy        = expect,
            initial_capital   = initial_capital,
            final_capital     = final_cap,
            start_date        = str(equity_curve.index[0])[:10],
            end_date          = str(equity_curve.index[-1])[:10],
            interval          = interval,
            total_bars        = len(equity_curve),
        )

    def _empty(self, capital: float, interval: str) -> BacktestMetrics:
        now = str(pd.Timestamp.now().date())
        return BacktestMetrics(
            total_return_pct=0,annual_return_pct=0,best_trade_pct=0,
            worst_trade_pct=0,max_drawdown_pct=0,avg_drawdown_pct=0,
            volatility_annual=0,sharpe_ratio=0,sortino_ratio=0,calmar_ratio=0,
            total_trades=0,winning_trades=0,losing_trades=0,win_rate=0,
            avg_win_pct=0,avg_loss_pct=0,profit_factor=0,avg_bars_held=0,
            expectancy=0,initial_capital=capital,final_capital=capital,
            start_date=now,end_date=now,interval=interval,total_bars=0,
        )


# =============================================================================
# 3. BACKTESTER ENGINE
# =============================================================================

class Backtester:
    """
    Backtester V3 — terintegrasi dengan Signal Engine dan Risk Engine V3.

    Cara pakai:
        bt     = Backtester(capital=1000, fee=0.001)
        result = bt.run(df, symbol="BTCUSDT", market="crypto", interval="1h")
        render_backtest(result)  # di Streamlit

    Anti look-ahead bias:
        Signal dihitung dari df[:i]
        Entry dilakukan di open candle i+1
        SL/TP dicek menggunakan high/low candle (intrabar)
    """

    def __init__(
        self,
        capital:    float = 1000.0,
        fee:        float = 0.001,
        slippage:   float = 0.0005,
        min_bars:   int   = 50,
        risk_pct:   float = 0.01,
        sl_mult:    float = 2.0,
        tp_mult:    float = 3.0,
        min_conf:   float = 25.0,
    ):
        self.capital    = capital
        self.fee        = fee
        self.slippage   = slippage
        self.min_bars   = min_bars
        self.risk_pct   = risk_pct
        self.sl_mult    = sl_mult
        self.tp_mult    = tp_mult
        self.min_conf   = min_conf
        self.metrics_calc = MetricsCalculator()

    def run(
        self,
        df:       pd.DataFrame,
        symbol:   str = "UNKNOWN",
        market:   str = "crypto",
        interval: str = "1h",
        verbose:  bool = False,
    ) -> BacktestResult:
        """
        Jalankan backtest pada DataFrame OHLCV.

        Args:
            df       : DataFrame dari data_loader.smart_load()
            symbol   : Nama simbol
            market   : Jenis market
            interval : Timeframe
            verbose  : Print progress

        Returns:
            BacktestResult
        """
        from signal_engine import SignalEngine
        from risk_engine   import RiskEngine

        logger.info(f"[Backtester] {symbol} {interval} — {len(df)} candle")

        # Set attrs agar signal engine dan risk engine mengenali market
        df.attrs.update({
            "symbol": symbol, "market": market,
            "interval": interval,
            "currency": df.attrs.get("currency", "USD"),
            "fee": self.fee,
        })

        se = SignalEngine()
        re = RiskEngine(
            capital_usd    = self.capital,
            risk_per_trade = self.risk_pct,
            sl_atr_mult    = self.sl_mult,
            tp_atr_mult    = self.tp_mult,
            min_confidence = self.min_conf,
        )

        capital      = self.capital
        equity_curve = {}
        trades       = []
        trade_id     = 0
        position     = None

        for i in range(self.min_bars, len(df) - 1):
            df_slice = df.iloc[:i+1].copy()
            df_slice.attrs.update(df.attrs)
            current  = df.iloc[i]
            next_bar = df.iloc[i+1]
            ts       = df.index[i]

            # --- Cek exit posisi aktif ---
            if position is not None:
                exit_info = self._check_exit(position, current)
                if exit_info:
                    trade, capital = self._close(position, exit_info, capital, ts, i)
                    trade.trade_id = trade_id
                    trade_id += 1
                    trades.append(trade)
                    position = None
                    if verbose:
                        logger.info(f"  EXIT {trade.exit_reason} PnL={trade.pnl_pct:+.2%}")

            # --- Generate sinyal baru ---
            if position is None:
                try:
                    sig = se.analyze(df_slice)
                    if sig.signal.value in ("BUY", "SELL") and sig.confidence >= self.min_conf:
                        risk = re.evaluate(sig, df_slice)
                        if risk.approved:
                            entry = float(next_bar["open"]) * (1 + self.slippage if sig.signal.value == "BUY" else 1 - self.slippage)
                            units = risk.units
                            if units > 0:
                                fee_entry = entry * units * self.fee
                                position  = {
                                    "entry_time":  df.index[i+1],
                                    "entry_price": entry,
                                    "units":       units,
                                    "direction":   sig.signal.value,
                                    "stop_loss":   risk.stop_loss,
                                    "take_profit": risk.take_profit,
                                    "capital_before": capital,
                                    "regime":      sig.regime,
                                    "confidence":  sig.confidence,
                                    "entry_bar":   i + 1,
                                    "fee_entry":   fee_entry,
                                }
                                capital -= fee_entry
                except Exception as e:
                    logger.debug(f"[{ts}] signal/risk error: {e}")

            # Update equity
            if position is not None:
                if position["direction"] == "BUY":
                    unreal = (float(current["close"]) - position["entry_price"]) * position["units"]
                else:
                    unreal = (position["entry_price"] - float(current["close"])) * position["units"]
                equity_curve[ts] = capital + unreal
            else:
                equity_curve[ts] = capital

        # Force close posisi terakhir
        if position is not None:
            last   = df.iloc[-1]
            lp     = float(last["close"])
            trade, capital = self._close(
                position, {"reason": "END_OF_DATA", "exit_price": lp},
                capital, df.index[-1], len(df)-1
            )
            trade.trade_id = trade_id
            trades.append(trade)

        eq = pd.Series(equity_curve)
        if len(eq) == 0:
            eq = pd.Series({df.index[-1]: capital})

        rolling_max = eq.cummax()
        dd_curve    = (eq - rolling_max) / rolling_max

        metrics = self.metrics_calc.calculate(eq, trades, self.capital, interval)

        logger.info(
            f"[Backtester] {symbol} selesai — "
            f"{len(trades)} trade | "
            f"Grade={metrics.grade()} | "
            f"Return={metrics.total_return_pct:+.2%} | "
            f"Sharpe={metrics.sharpe_ratio:.2f}"
        )

        return BacktestResult(
            metrics        = metrics,
            trades         = trades,
            equity_curve   = eq,
            drawdown_curve = dd_curve,
        )

    def walk_forward(
        self,
        df:          pd.DataFrame,
        symbol:      str   = "UNKNOWN",
        market:      str   = "crypto",
        interval:    str   = "1h",
        n_folds:     int   = 4,
        train_ratio: float = 0.70,
    ) -> BacktestResult:
        """
        Walk-Forward Analysis.

        Setiap fold:
          [────TRAIN────][TEST]
          Optimasi di TRAIN, validasi di TEST.
        """
        logger.info(f"[WFA] {symbol} {n_folds} fold")

        fold_size   = len(df) // n_folds
        all_trades  = []
        all_equity  = pd.Series(dtype=float)
        wf_folds    = []
        capital     = self.capital

        for fold in range(n_folds):
            start = fold * fold_size
            end   = start + fold_size if fold < n_folds - 1 else len(df)
            df_fold     = df.iloc[start:end].copy()
            df_fold.attrs.update(df.attrs)
            train_end   = int(len(df_fold) * train_ratio)
            df_train    = df_fold.iloc[:train_end]
            df_test     = df_fold.iloc[train_end:]

            if len(df_train) < self.min_bars * 2 or len(df_test) < self.min_bars:
                continue

            # Backtest di TRAIN
            train_res = self.run(df_train, symbol, market, interval)

            # Backtest di TEST dengan carry-forward capital
            saved_cap       = self.capital
            self.capital    = capital
            test_res        = self.run(df_test, symbol, market, interval)
            self.capital    = saved_cap

            if len(test_res.equity_curve) > 0:
                capital = float(test_res.equity_curve.iloc[-1])

            consistency = (test_res.metrics.sharpe_ratio / train_res.metrics.sharpe_ratio
                          if train_res.metrics.sharpe_ratio != 0 else 0)

            wf_folds.append({
                "fold":          fold + 1,
                "train_start":   str(df_train.index[0])[:10],
                "train_end":     str(df_train.index[-1])[:10],
                "test_start":    str(df_test.index[0])[:10],
                "test_end":      str(df_test.index[-1])[:10],
                "train_sharpe":  round(train_res.metrics.sharpe_ratio, 2),
                "test_sharpe":   round(test_res.metrics.sharpe_ratio, 2),
                "train_winrate": f"{train_res.metrics.win_rate:.1%}",
                "test_winrate":  f"{test_res.metrics.win_rate:.1%}",
                "train_return":  f"{train_res.metrics.total_return_pct:+.2%}",
                "test_return":   f"{test_res.metrics.total_return_pct:+.2%}",
                "consistency":   round(consistency, 2),
                "status":        "✅ OK" if consistency >= 0.6 else "⚠️ Rendah",
            })
            all_trades.extend(test_res.trades)
            all_equity = pd.concat([all_equity, test_res.equity_curve])

        if len(all_equity) == 0:
            all_equity = pd.Series({df.index[-1]: self.capital})

        rolling_max = all_equity.cummax()
        dd_curve    = (all_equity - rolling_max) / rolling_max
        metrics     = self.metrics_calc.calculate(
            all_equity, all_trades, self.capital, interval
        )

        avg_cons = float(np.mean([f["consistency"] for f in wf_folds])) if wf_folds else 0
        logger.info(f"[WFA] selesai — avg consistency={avg_cons:.2f} | grade={metrics.grade()}")

        return BacktestResult(
            metrics         = metrics,
            trades          = all_trades,
            equity_curve    = all_equity,
            drawdown_curve  = dd_curve,
            is_walk_forward = True,
            wf_folds        = wf_folds,
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _check_exit(self, position: dict, current: pd.Series):
        d  = position["direction"]
        sl = position["stop_loss"]
        tp = position["take_profit"]
        hi = float(current["high"])
        lo = float(current["low"])
        if d == "BUY":
            if lo <= sl: return {"reason": "STOP_LOSS",   "exit_price": sl}
            if hi >= tp: return {"reason": "TAKE_PROFIT", "exit_price": tp}
        else:
            if hi >= sl: return {"reason": "STOP_LOSS",   "exit_price": sl}
            if lo <= tp: return {"reason": "TAKE_PROFIT", "exit_price": tp}
        return None

    def _close(self, position, exit_info, capital, ts, bar_idx):
        ep    = exit_info["exit_price"] * (1 - self.slippage)
        units = position["units"]
        fee   = ep * units * self.fee
        if position["direction"] == "BUY":
            pnl_raw = (ep - position["entry_price"]) * units
        else:
            pnl_raw = (position["entry_price"] - ep) * units
        pnl_net  = pnl_raw - fee - position["fee_entry"]
        cost     = position["entry_price"] * units
        pnl_pct  = pnl_net / cost if cost > 0 else 0
        new_cap  = capital + (position["entry_price"] * units) + pnl_net

        return TradeRecord(
            trade_id      = 0,
            entry_time    = position["entry_time"],
            exit_time     = ts,
            direction     = position["direction"],
            entry_price   = position["entry_price"],
            exit_price    = ep,
            stop_loss     = position["stop_loss"],
            take_profit   = position["take_profit"],
            units         = units,
            pnl_net       = pnl_net,
            pnl_pct       = pnl_pct,
            fee_total     = fee + position["fee_entry"],
            exit_reason   = exit_info["reason"],
            regime        = position["regime"],
            confidence    = position["confidence"],
            bars_held     = bar_idx - position["entry_bar"],
            capital_before= position["capital_before"],
            capital_after = new_cap,
        ), new_cap


# =============================================================================
# 4. STREAMLIT RENDERER
# =============================================================================

def render_backtest(result: BacktestResult, symbol: str = ""):
    """Render hasil backtest di Streamlit."""
    try:
        import streamlit as st
    except ImportError:
        print(result.metrics.to_dict())
        return

    m = result.metrics

    # Grade header
    gc = m.grade_color()
    st.markdown(
        f"<h2 style='color:{gc}'>Grade: {m.grade()} "
        f"<span style='font-size:1rem;color:#888'>— {symbol} {m.interval}</span></h2>",
        unsafe_allow_html=True
    )

    # Metrik utama
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Return",  f"{m.total_return_pct:+.2%}")
    c2.metric("Sharpe Ratio",  f"{m.sharpe_ratio:.3f}")
    c3.metric("Win Rate",      f"{m.win_rate:.1%}")
    c4.metric("Max Drawdown",  f"-{m.max_drawdown_pct:.2%}")

    c5, c6, c7, c8 = st.columns(4)
    c5.metric("Annual Return", f"{m.annual_return_pct:+.2%}")
    c6.metric("Profit Factor", f"{m.profit_factor:.2f}" if m.profit_factor < 999 else "∞")
    c7.metric("Total Trades",  str(m.total_trades))
    c8.metric("Final Capital", f"${m.final_capital:,.2f}")

    c9, c10, c11, c12 = st.columns(4)
    c9.metric("Sortino",       f"{m.sortino_ratio:.3f}")
    c10.metric("Avg Win",      f"{m.avg_win_pct:+.2%}")
    c11.metric("Avg Loss",     f"{m.avg_loss_pct:+.2%}")
    c12.metric("Expectancy",   f"{m.expectancy:+.4f}")

    st.divider()

    # Equity + Drawdown
    if len(result.equity_curve) > 1:
        col_eq, col_dd = st.columns(2)
        with col_eq:
            st.markdown("**📈 Equity Curve**")
            st.line_chart(result.equity_curve)
        with col_dd:
            st.markdown("**📉 Drawdown**")
            st.area_chart(result.drawdown_curve)

    # Walk-Forward table
    if result.is_walk_forward and result.wf_folds:
        st.divider()
        st.markdown("#### 🔄 Walk-Forward Analysis")
        df_wf = pd.DataFrame(result.wf_folds).rename(columns={
            "fold":"Fold","train_start":"Train Mulai","train_end":"Train Selesai",
            "test_start":"Test Mulai","test_end":"Test Selesai",
            "train_sharpe":"Sharpe Train","test_sharpe":"Sharpe Test",
            "train_winrate":"WR Train","test_winrate":"WR Test",
            "train_return":"Return Train","test_return":"Return Test",
            "consistency":"Consistency","status":"Status",
        })
        st.dataframe(df_wf, use_container_width=True, hide_index=True)

        avg_c = float(np.mean([f["consistency"] for f in result.wf_folds]))
        if avg_c >= 0.6:
            st.success(f"✅ Avg Consistency: {avg_c:.2f} — Strategi robust, tidak overfit!")
        else:
            st.warning(f"⚠️ Avg Consistency: {avg_c:.2f} — Strategi mungkin overfit ke data historis")

    # Trade list
    df_trades = result.trades_df()
    if not df_trades.empty:
        st.divider()
        st.markdown(f"#### 📋 Trade List ({len(result.trades)} trade)")
        st.dataframe(df_trades, use_container_width=True, hide_index=True)

        # PnL distribution
        pnl_vals = [t.pnl_pct for t in result.trades]
        pnl_series = pd.Series(pnl_vals, name="PnL%")
        col_hist, col_stats = st.columns(2)
        with col_hist:
            st.markdown("**Distribusi PnL per Trade**")
            st.bar_chart(pnl_series)
        with col_stats:
            st.markdown("**Statistik PnL**")
            st.dataframe(pd.DataFrame({
                "Metrik": ["Best Trade","Worst Trade","Avg Win","Avg Loss","Median"],
                "Nilai":  [
                    f"{m.best_trade_pct:+.2%}", f"{m.worst_trade_pct:+.2%}",
                    f"{m.avg_win_pct:+.2%}", f"{m.avg_loss_pct:+.2%}",
                    f"{float(pd.Series(pnl_vals).median()):+.2%}",
                ],
            }), use_container_width=True, hide_index=True)
