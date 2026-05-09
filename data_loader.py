# =============================================================================
# QuantPulse Pro V3 — Data Loader
# =============================================================================
# Perubahan dari V2:
#   - Crypto: ccxt (Binance→OKX→Bybit fallback, tidak ada geo-block)
#   - Saham/Forex/Gold/Oil: yfinance (gratis, tidak butuh API key)
#   - Semua return pd.DataFrame — tidak ada object kompleks
#   - Short-term focus: support 15m, 30m, 1h, 4h, 1d
#
# Install: pip install ccxt yfinance pandas numpy requests
# =============================================================================

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

import numpy as np
import pandas as pd

logger = logging.getLogger("QuantPulse.V3.DataLoader")
logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s")

# =============================================================================
# SYMBOL REGISTRY — Peta simbol ke sumber data yang benar
# =============================================================================

SYMBOL_REGISTRY = {
    # Crypto (via ccxt)
    "BTCUSDT":  {"source": "ccxt",     "symbol": "BTC/USDT",  "market": "crypto"},
    "ETHUSDT":  {"source": "ccxt",     "symbol": "ETH/USDT",  "market": "crypto"},
    "BNBUSDT":  {"source": "ccxt",     "symbol": "BNB/USDT",  "market": "crypto"},
    "SOLUSDT":  {"source": "ccxt",     "symbol": "SOL/USDT",  "market": "crypto"},
    "ADAUSDT":  {"source": "ccxt",     "symbol": "ADA/USDT",  "market": "crypto"},
    "XRPUSDT":  {"source": "ccxt",     "symbol": "XRP/USDT",  "market": "crypto"},
    "DOGEUSDT": {"source": "ccxt",     "symbol": "DOGE/USDT", "market": "crypto"},
    # Forex (via yfinance)
    "EURUSD":   {"source": "yfinance", "symbol": "EURUSD=X",  "market": "forex"},
    "GBPUSD":   {"source": "yfinance", "symbol": "GBPUSD=X",  "market": "forex"},
    "USDJPY":   {"source": "yfinance", "symbol": "JPY=X",     "market": "forex"},
    "AUDUSD":   {"source": "yfinance", "symbol": "AUDUSD=X",  "market": "forex"},
    "USDSGD":   {"source": "yfinance", "symbol": "SGD=X",     "market": "forex"},
    "USDIDR":   {"source": "yfinance", "symbol": "IDR=X",     "market": "forex"},
    # Gold & Komoditas (via yfinance)
    "XAUUSD":   {"source": "yfinance", "symbol": "GC=F",      "market": "commodity"},
    "GOLD":     {"source": "yfinance", "symbol": "GC=F",      "market": "commodity"},
    "XAGUSD":   {"source": "yfinance", "symbol": "SI=F",      "market": "commodity"},
    "OIL":      {"source": "yfinance", "symbol": "CL=F",      "market": "commodity"},
    "USOIL":    {"source": "yfinance", "symbol": "CL=F",      "market": "commodity"},
    "NGAS":     {"source": "yfinance", "symbol": "NG=F",      "market": "commodity"},
    # Saham US (via yfinance)
    "AAPL":     {"source": "yfinance", "symbol": "AAPL",      "market": "stock_us"},
    "MSFT":     {"source": "yfinance", "symbol": "MSFT",      "market": "stock_us"},
    "NVDA":     {"source": "yfinance", "symbol": "NVDA",      "market": "stock_us"},
    "TSLA":     {"source": "yfinance", "symbol": "TSLA",      "market": "stock_us"},
    "GOOGL":    {"source": "yfinance", "symbol": "GOOGL",     "market": "stock_us"},
    "AMZN":     {"source": "yfinance", "symbol": "AMZN",      "market": "stock_us"},
    "META":     {"source": "yfinance", "symbol": "META",      "market": "stock_us"},
    # Saham IDX (via yfinance)
    "BBCA":     {"source": "yfinance", "symbol": "BBCA.JK",   "market": "stock_id"},
    "BBRI":     {"source": "yfinance", "symbol": "BBRI.JK",   "market": "stock_id"},
    "TLKM":     {"source": "yfinance", "symbol": "TLKM.JK",   "market": "stock_id"},
    "ASII":     {"source": "yfinance", "symbol": "ASII.JK",   "market": "stock_id"},
    "BMRI":     {"source": "yfinance", "symbol": "BMRI.JK",   "market": "stock_id"},
    "GOTO":     {"source": "yfinance", "symbol": "GOTO.JK",   "market": "stock_id"},
    "BREN":     {"source": "yfinance", "symbol": "BREN.JK",   "market": "stock_id"},
    "BUMI":     {"source": "yfinance", "symbol": "BUMI.JK",   "market": "stock_id"},
    "WBSA":     {"source": "yfinance", "symbol": "WBSA.JK",   "market": "stock_id"},
    "ANTM":     {"source": "yfinance", "symbol": "ANTM.JK",   "market": "stock_id"},
    "UNVR":     {"source": "yfinance", "symbol": "UNVR.JK",   "market": "stock_id"},
    "INDF":     {"source": "yfinance", "symbol": "INDF.JK",   "market": "stock_id"},
    "KLBF":     {"source": "yfinance", "symbol": "KLBF.JK",   "market": "stock_id"},
    "PTBA":     {"source": "yfinance", "symbol": "PTBA.JK",   "market": "stock_id"},
    "ADRO":     {"source": "yfinance", "symbol": "ADRO.JK",   "market": "stock_id"},
    "SMGR":     {"source": "yfinance", "symbol": "SMGR.JK",   "market": "stock_id"},
    "EXCL":     {"source": "yfinance", "symbol": "EXCL.JK",   "market": "stock_id"},
    "INCO":     {"source": "yfinance", "symbol": "INCO.JK",   "market": "stock_id"},
    "PWON":     {"source": "yfinance", "symbol": "PWON.JK",   "market": "stock_id"},
    "MDKA":     {"source": "yfinance", "symbol": "MDKA.JK",   "market": "stock_id"},
}

# Metadata per market
MARKET_META = {
    "crypto":    {"currency": "USDT", "lot": 1.0,   "fee": 0.001,  "pip": 1.0},
    "forex":     {"currency": "USD",  "lot": 100000, "fee": 0.00005,"pip": 0.0001},
    "commodity": {"currency": "USD",  "lot": 100.0,  "fee": 0.0001, "pip": 0.01},
    "stock_us":  {"currency": "USD",  "lot": 1.0,   "fee": 0.0005, "pip": 0.01},
    "stock_id":  {"currency": "IDR",  "lot": 100.0,  "fee": 0.002,  "pip": 1.0},
}

# =============================================================================
# TIMEFRAME MAPPING
# =============================================================================

CCXT_TIMEFRAME = {
    "1m": "1m", "3m": "3m", "5m": "5m", "15m": "15m",
    "30m": "30m", "1h": "1h", "2h": "2h", "4h": "4h",
    "6h": "6h", "8h": "8h", "12h": "12h",
    "1d": "1d", "3d": "3d", "1w": "1w",
}

YFINANCE_INTERVAL = {
    "1m": "1m", "5m": "5m", "15m": "15m", "30m": "30m",
    "1h": "60m", "4h": "60m",  # yfinance tidak punya 4h, pakai 1h
    "1d": "1d", "1w": "1wk",
}

YFINANCE_PERIOD = {
    "1m": "7d", "5m": "60d", "15m": "60d", "30m": "60d",
    "60m": "730d", "1d": "max", "1wk": "max",
}

# =============================================================================
# FX RATE — IDR/USD untuk normalisasi
# =============================================================================

_fx_cache: dict = {}

def get_idr_rate() -> float:
    """Ambil kurs IDR/USD terkini."""
    import time
    now = time.time()
    if "IDR" in _fx_cache and now - _fx_cache["IDR"]["t"] < 3600:
        return _fx_cache["IDR"]["rate"]
    try:
        import requests
        r = requests.get(
            "https://api.frankfurter.app/latest",
            params={"base": "IDR", "symbols": "USD"},
            timeout=8
        )
        rate = float(r.json()["rates"]["USD"])
        _fx_cache["IDR"] = {"rate": rate, "t": now}
        return rate
    except Exception:
        return 1 / 16200  # Fallback

# =============================================================================
# CORE DATA LOADER
# =============================================================================

def load_ohlcv(
    symbol:   str,
    interval: str = "1h",
    limit:    int = 500,
    market:   str = "",     # Hint market dari UI — membantu auto-detect
) -> pd.DataFrame:
    """
    Load data OHLCV untuk simbol apapun.
    Return: pd.DataFrame dengan kolom open/high/low/close/volume/returns
            + attrs: symbol, market, currency, fee, pip_value, idr_rate
    """
    sym_upper = symbol.upper().replace("/", "").replace("-", "")
    # Jika simbol diakhiri .JK tapi tidak ada di registry, strip dulu untuk lookup
    lookup_key = sym_upper.replace(".JK","")
    
    # Lookup registry
    info = SYMBOL_REGISTRY.get(sym_upper) or SYMBOL_REGISTRY.get(lookup_key)
    if info is None:
        # Auto-detect berdasarkan format simbol
        sym_clean = sym_upper.replace(".JK","").replace("-","")

        if "USDT" in sym_upper:
            # Perbaiki agar koin 4 huruf seperti AAVE bisa terbaca
            koin = sym_upper.replace("USDT", "")
            info = {"source": "ccxt", "symbol": f"{koin}/USDT", "market": "crypto"}
        elif sym_upper.endswith(".JK") or market == "stock_id":
            # Saham IDX — tambahkan .JK otomatis
            yf_sym = sym_upper if sym_upper.endswith(".JK") else f"{sym_upper}.JK"
            info = {"source": "yfinance", "symbol": yf_sym, "market": "stock_id"}
        elif "=F" in symbol or symbol.upper() in ("OIL","GOLD","GAS","XAUUSD","SILVER"):
            info = {"source": "yfinance", "symbol": symbol, "market": "commodity"}
        elif "USD" in sym_upper and len(sym_upper) == 6:
            # Forex pair 6 karakter seperti EURUSD
            info = {"source": "yfinance", "symbol": f"{sym_upper}=X", "market": "forex"}
        elif market == "stock_id":
            # User sudah pilih market IDX tapi simbol tanpa .JK
            info = {"source": "yfinance", "symbol": f"{sym_upper}.JK", "market": "stock_id"}
        else:
            info = {"source": "yfinance", "symbol": symbol, "market": "stock_us"}

    source = info["source"]
    yf_sym = info["symbol"]
    market = info["market"]

    # Fetch data
    if source == "ccxt":
        df = _fetch_ccxt(yf_sym, interval, limit)
    else:
        df = _fetch_yfinance(yf_sym, interval, limit)

    if df is None or df.empty:
        raise ValueError(f"Data kosong untuk {symbol}. Cek simbol atau koneksi internet.")

    # Wrangling
    df = _wrangle(df)

    # Normalisasi close ke USD
    meta     = MARKET_META.get(market, MARKET_META["stock_us"])
    idr_rate = 1.0
    if meta["currency"] == "IDR":
        idr_rate   = get_idr_rate()
        df["close_usd"] = df["close"] * idr_rate
    else:
        df["close_usd"] = df["close"]

    # Simpan metadata di attrs DataFrame
    df.attrs.update({
        "symbol":     symbol.upper(),
        "yf_symbol":  yf_sym,
        "market":     market,
        "interval":   interval,
        "currency":   meta["currency"],
        "lot_size":   meta["lot"],
        "fee":        meta["fee"],
        "pip_value":  meta["pip"],
        "idr_rate":   idr_rate,
    })

    logger.info(f"[DataLoader] {symbol} ({interval}) — {len(df)} candle | close={df['close'].iloc[-1]:,.4f}")
    return df


def load_mtfa(
    symbol:   str,
    htf:      str = "4h",
    mtf:      str = "1h",
    ltf:      str = "15m",
    limit:    int = 500,
    market:   str = "",
) -> dict[str, pd.DataFrame]:
    """
    Load 3 timeframe sekaligus.
    Return: {"htf": df, "mtf": df, "ltf": df}
    Semua return DataFrame biasa — 100% serializable untuk st.cache_data.
    """
    result = {}
    for tf_name, tf in [("htf", htf), ("mtf", mtf), ("ltf", ltf)]:
        try:
            result[tf_name] = load_ohlcv(symbol, tf, limit, market=market)
        except Exception as e:
            logger.error(f"[MTFA] Gagal load {symbol} {tf}: {e}")
            raise
    return result


# =============================================================================
# CCXT FETCHER — Crypto via exchange fallback chain
# =============================================================================

def _fetch_ccxt(symbol: str, interval: str, limit: int) -> Optional[pd.DataFrame]:
    """
    Fetch crypto OHLCV via ccxt dengan fallback chain.
    Urutan: Binance → OKX → Bybit → KuCoin
    """
    try:
        import ccxt
    except ImportError:
        logger.error("ccxt tidak terinstall. Jalankan: pip install ccxt")
        return None

    tf = CCXT_TIMEFRAME.get(interval, "1h")

    exchanges = [
        ccxt.kraken(),                                            # Kraken — Paling aman buat server US
        ccxt.kucoin(),                                            # KuCoin — Cadangan
        ccxt.binance({"options": {"defaultType": "spot"}}),       # Binance — Pilihan terakhir
    ]

    for exchange in exchanges:
        try:
            exchange.load_markets()
            # Normalisasi simbol
            sym = symbol if "/" in symbol else f"{symbol[:3]}/{symbol[3:]}"
            if sym not in exchange.markets:
                # Coba format berbeda
                parts = symbol.replace("/", "")
                sym = f"{parts[:-4]}/USDT" if parts.endswith("USDT") else f"{parts}/USDT"

            ohlcv = exchange.fetch_ohlcv(sym, tf, limit=min(limit, 1000))
            if not ohlcv:
                continue

            df = pd.DataFrame(ohlcv, columns=["timestamp", "open", "high", "low", "close", "volume"])
            df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
            df.set_index("timestamp", inplace=True)
            logger.info(f"[ccxt] {symbol} dari {exchange.id}")
            return df

        except Exception as e:
            logger.warning(f"[ccxt] {exchange.id} gagal: {type(e).__name__}: {str(e)[:60]}")
            continue

    return None


# =============================================================================
# YFINANCE FETCHER — Saham, Forex, Gold, Oil
# =============================================================================

def _fetch_yfinance(symbol: str, interval: str, limit: int) -> Optional[pd.DataFrame]:
    """Fetch data via yfinance."""
    try:
        import yfinance as yf
    except ImportError:
        logger.error("yfinance tidak terinstall. Jalankan: pip install yfinance")
        return None

    iv  = YFINANCE_INTERVAL.get(interval, "1d")
    per = YFINANCE_PERIOD.get(iv, "1y")

    try:
        df = yf.Ticker(symbol).history(
            period=per, interval=iv, auto_adjust=True, timeout=15
        )
        if df.empty:
            raise ValueError(f"yfinance mengembalikan data kosong untuk {symbol}")

        df.index = pd.to_datetime(df.index, utc=True)
        df.index.name = "timestamp"
        df = df.rename(columns=str.lower)[["open", "high", "low", "close", "volume"]]
        return df.tail(limit)

    except Exception as e:
        logger.error(f"[yfinance] {symbol} gagal: {e}")
        return None


# =============================================================================
# WRANGLING PIPELINE
# =============================================================================

def _wrangle(df: pd.DataFrame) -> pd.DataFrame:
    """Bersihkan dan tambahkan derived columns."""

    # Pastikan kolom numerik
    for col in ["open", "high", "low", "close", "volume"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # Drop NaN close
    df.dropna(subset=["close"], inplace=True)

    # Fix high < low
    mask = df["high"] < df["low"]
    if mask.any():
        df.loc[mask, ["high", "low"]] = df.loc[mask, ["low", "high"]].values

    # Drop harga nol atau negatif
    df = df[df["close"] > 0]

    # Volume
    if "volume" in df.columns:
        df["volume"] = df["volume"].fillna(0).clip(lower=0)

    # Sort
    df.sort_index(inplace=True)

    # Remove duplicates
    df = df[~df.index.duplicated(keep="last")]

    # Derived columns
    df["returns"]       = df["close"].pct_change()
    df["log_returns"]   = np.log(df["close"] / df["close"].shift(1))
    df["hl_range"]      = df["high"] - df["low"]
    df["typical_price"] = (df["high"] + df["low"] + df["close"]) / 3

    # ATR (14)
    prev_close = df["close"].shift(1)
    tr = pd.concat([
        df["high"] - df["low"],
        (df["high"] - prev_close).abs(),
        (df["low"]  - prev_close).abs(),
    ], axis=1).max(axis=1)
    df["atr"] = tr.ewm(alpha=1/14, adjust=False).mean()

    return df


# =============================================================================
# DEMO DATA — Fallback jika semua API gagal
# =============================================================================

def generate_demo(
    symbol:   str = "BTCUSDT",
    interval: str = "1h",
    n:        int = 300,
    base_price: float = 103000,
) -> pd.DataFrame:
    """
    Generate data simulasi realistis sebagai fallback terakhir.
    Base price sesuai harga aktual pasar.
    """
    BASE_PRICES = {
        # Crypto (USD)
        "BTCUSDT": 103000, "ETHUSDT": 3200, "SOLUSDT": 170,
        "BNBUSDT": 600, "ADAUSDT": 0.45, "XRPUSDT": 0.5,
        "DOGEUSDT": 0.15,
        # Commodity (USD/oz)
        "XAUUSD": 3300, "GOLD": 3300, "OIL": 80,
        "USOIL": 80, "XAGUSD": 32,
        # Forex
        "EURUSD": 1.08, "GBPUSD": 1.27, "USDJPY": 154,
        # Saham US (USD)
        "AAPL": 213, "NVDA": 900, "TSLA": 250,
        "MSFT": 415, "GOOGL": 175, "META": 580, "AMZN": 195,
        # Saham IDX (IDR per lembar)
        "BBCA": 9500, "BBRI": 4800, "TLKM": 3200,
        "ASII": 5200, "BMRI": 6200, "GOTO": 68,
        "BUMI": 185, "WBSA": 950, "ANTM": 1580,
        "ADRO": 3750, "UNVR": 2800, "KLBF": 1560,
    }
    sym = symbol.upper()
    base = BASE_PRICES.get(sym, base_price)

    np.random.seed(42)
    freq_map = {
        "1m":"1min","5m":"5min","15m":"15min","30m":"30min",
        "1h":"1h","4h":"4h","1d":"1D","1w":"1W",
    }
    freq = freq_map.get(interval, "1h")
    ts   = pd.date_range(end=pd.Timestamp.now(tz="UTC"), periods=n, freq=freq)

    # Simulasi tren realistis
    vol     = base * 0.002  # 0.2% volatilitas per candle
    returns = np.random.normal(0.0001, vol/base, n)
    close   = base * np.exp(np.cumsum(returns))
    spread  = abs(np.random.normal(0, base * 0.001, n))

    df = pd.DataFrame({
        "open":   close * (1 - np.random.uniform(0, 0.0005, n)),
        "high":   close + spread,
        "low":    close - spread,
        "close":  close,
        "volume": abs(np.random.normal(1000, 200, n)),
    }, index=ts)
    df.index.name = "timestamp"

    df = _wrangle(df)
    meta = MARKET_META.get("crypto", MARKET_META["crypto"])
    df["close_usd"] = df["close"]
    df.attrs.update({
        "symbol":    sym, "market":   "crypto",
        "interval":  interval, "currency": "USDT",
        "lot_size":  meta["lot"], "fee":  meta["fee"],
        "pip_value": meta["pip"], "idr_rate": 1.0,
        "is_demo":   True,
        "data_source": "demo",
        "data_source_type": "simulation",
    })
    return df


# =============================================================================
# SMART LOAD — Dengan fallback ke demo data
# =============================================================================

def smart_load(
    symbol:   str,
    interval: str = "1h",
    limit:    int = 500,
    use_demo: bool = False,
    market:   str = "",
) -> tuple[pd.DataFrame, bool]:
    
    if use_demo:
        return generate_demo(symbol, interval, limit), True

    try:
        df = load_ohlcv(symbol, interval, limit, market=market)
        return df, False
    except Exception as e:
        import logging
        logging.getLogger("QuantPulse").error(f"Gagal narik data {symbol}: {e}")
        # Kalau API exchange ngadat, otomatis alihkan ke data simulasi agar web tidak crash
        return generate_demo(symbol, interval, limit), True


def smart_load_mtfa(
    symbol: str,
    htf: str = "4h",
    mtf: str = "1h",
    ltf: str = "15m",
    limit: int = 300,
    use_demo: bool = False,
    market: str = "",
) -> tuple[dict, bool]:
    """Load MTFA dengan fallback."""
    if use_demo:
        return {
            "htf": generate_demo(symbol, htf, limit),
            "mtf": generate_demo(symbol, mtf, limit),
            "ltf": generate_demo(symbol, ltf, limit),
        }, True
    try:
        return load_mtfa(symbol, htf, mtf, ltf, limit, market=market), False
    except Exception as e:
        logger.warning(f"[SmartLoad MTFA] Gagal: {e} → pakai demo")
        return {
            "htf": generate_demo(symbol, htf, limit),
            "mtf": generate_demo(symbol, mtf, limit),
            "ltf": generate_demo(symbol, ltf, limit),
        }, True


# =============================================================================
# SYMBOL INFO
# =============================================================================

def get_symbol_info(symbol: str) -> dict:
    """Return info lengkap tentang simbol."""
    sym = symbol.upper().replace("/", "").replace("-", "")
    info = SYMBOL_REGISTRY.get(sym, {})
    market = info.get("market", "unknown")
    meta   = MARKET_META.get(market, {})
    return {
        "symbol":    sym,
        "source":    info.get("source", "unknown"),
        "market":    market,
        "currency":  meta.get("currency", "USD"),
        "lot_size":  meta.get("lot", 1.0),
        "fee":       meta.get("fee", 0.001),
        "pip_value": meta.get("pip", 1.0),
    }


# =============================================================================
# AVAILABLE SYMBOLS PER MARKET
# =============================================================================

AVAILABLE_SYMBOLS = {
    "crypto": [
        "BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT",
        "ADAUSDT", "XRPUSDT", "DOGEUSDT",
    ],
    "forex": [
        "EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDSGD",
    ],
    "commodity": [
        "XAUUSD (Gold)", "XAGUSD (Silver)", "OIL (Crude Oil)", "NGAS (Natural Gas)",
    ],
    "stock_us": [
        "AAPL", "MSFT", "NVDA", "TSLA", "GOOGL", "AMZN", "META",
    ],
    "stock_id": [
        "BBCA", "BBRI", "TLKM", "ASII", "BMRI", "GOTO", "BREN",
    ],
}

TIMEFRAME_OPTIONS = {
    "crypto":    ["5m", "15m", "30m", "1h", "4h", "1d"],
    "forex":     ["15m", "30m", "1h", "4h", "1d"],
    "commodity": ["15m", "30m", "1h", "4h", "1d"],
    "stock_us":  ["30m", "1h", "1d"],
    "stock_id":  ["1d", "1w"],
}

MTFA_DEFAULTS = {
    "crypto":    ("4h",  "1h",  "15m"),
    "forex":     ("1d",  "4h",  "1h"),
    "commodity": ("1d",  "4h",  "1h"),
    "stock_us":  ("1w",  "1d",  "1h"),
    "stock_id":  ("1w",  "1d",  "1d"),
}


# =============================================================================
# DEMO
# =============================================================================

if __name__ == "__main__":
    print("QuantPulse Pro V3 — Data Loader Test")
    print("="*50)

    tests = [
        ("BTCUSDT", "1h"),
        ("XAUUSD",  "1h"),
        ("EURUSD",  "1h"),
        ("BBCA",    "1d"),
        ("AAPL",    "1d"),
        ("OIL",     "1h"),
    ]

    for sym, iv in tests:
        df, is_demo = smart_load(sym, iv, 100)
        src = "DEMO" if is_demo else "LIVE"
        print(f"  [{src}] {sym:<10} {iv:<4} | "
              f"close={df['close'].iloc[-1]:>12,.4f} "
              f"{df.attrs.get('currency','?')} | "
              f"{len(df)} candle")

    print("="*50)
