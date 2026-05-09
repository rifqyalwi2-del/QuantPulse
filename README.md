<div align="center">

# ⚡ QuantPulse Pro V3

### AI-Powered Multi-Market Trading Dashboard

**Menghilangkan Emosi dari Investasi, Menghadirkan Presisi Institusi**

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue?logo=python&logoColor=white)](https://python.org)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.35%2B-FF4B4B?logo=streamlit&logoColor=white)](https://streamlit.io)
[![Plotly](https://img.shields.io/badge/Plotly-5.18%2B-3F4F75?logo=plotly&logoColor=white)](https://plotly.com)
[![License](https://img.shields.io/badge/License-MIT-22C55E)](LICENSE)
[![Platform](https://img.shields.io/badge/Platform-Multi--Market-F59E0B)](#market-yang-didukung)

*13 modul · 6,242 baris · 12 tab dashboard*

</div>

---

## 📋 Tentang QuantPulse Pro

QuantPulse Pro adalah dashboard analisis trading berbasis AI yang mendukung **semua jenis market** dalam satu tampilan — Crypto, Forex, Saham IDX, Saham US, Gold, dan Oil. Dirancang untuk trader Indonesia yang ingin analisis berkualitas institusi tanpa biaya langganan mahal.

> **QuantPulse Pro adalah alat analisis, bukan bot trading otomatis.** Semua keputusan eksekusi tetap di tangan trader.

---

## ✨ Fitur Lengkap

### 📡 Signal Engine
- 6 indikator teknikal: RSI, MACD, Bollinger Bands, EMA Crossover, Stochastic, Volume
- Ensemble voting adaptif dengan bobot per market
- **Multi-Timeframe Analysis (MTFA)**: HTF + MTF + LTF sekaligus
- Adaptive confidence scoring (baseline 20%, maks 95%)
- Regime detection: `LOW` / `NORMAL` / `HIGH` / `CRISIS`

### 🛡️ Risk Engine
- Stop Loss dan Take Profit otomatis berbasis ATR
- **Toleransi spread broker** — level BUY/SELL siap pakai di semua exchange dan broker
- Kelly Criterion position sizing
- Estimasi profit/loss dalam **USD dan Rupiah**
- Value at Risk (VaR) 95%
- Veto system — sinyal ditolak otomatis jika kondisi tidak layak

### 📊 Backtester
- Anti look-ahead bias — sinyal dihitung dari `df[:i]`, entry di open candle `i+1`
- **Walk-Forward Analysis** (train/test split, konfigurasi N fold)
- Grade **A–F** untuk penilaian cepat
- Metrik: Sharpe, Sortino, Calmar, Max Drawdown, Win Rate, Profit Factor
- Equity curve + Drawdown chart interaktif

### 📐 Support & Resistance
- 4 metode: Pivot Points, Volume Profile, Round Numbers, Fibonacci Retracement
- Strength scoring dan zone signal otomatis
- Overlay langsung di candlestick chart

### 🕯️ Candlestick Chart & Pattern
- Chart interaktif via **Plotly** — EMA 9 + EMA 21 + Volume bar
- Slider candle (30–300), toggle volume, S/R overlay otomatis
- **18 pola candlestick**: Hammer, Engulfing, Morning Star, Evening Star, Three White Soldiers, dll
- Konfirmasi atau kontradiksi terhadap sinyal engine

### 🔮 Prediksi Trade
- Proyeksi **5 candle ke depan** dengan range harga atas/bawah
- Timestamp dalam **WIB** (Waktu Indonesia Barat)
- Estimasi profit/loss per candle + entry broker dengan spread

### 👁️ Watchlist & Quick Scanner
- Pantau 20+ simbol sekaligus dalam satu tabel
- Scan sinyal BUY/SELL semua simbol dengan satu klik
- Filter per sinyal dan market, highlight 3 sinyal terkuat
- Tambah/hapus simbol sesuka hati

### 📔 Jurnal Trading
- Catat setiap trade: simbol, arah, entry, SL, TP, setup, kesalahan, pelajaran
- Auto-fill dari sinyal aktif
- Statistik pribadi: win rate, profit factor, performa per market
- Export/import CSV

### 🧮 Kalkulator Posisi
- Hitung lot, margin, dan estimasi profit/loss tanpa data live
- Mode "Risk %" atau "Lot Manual", support leverage 1x–100x
- Auto-fill dari sinyal aktif, output dalam USD dan Rupiah

### 📁 Portfolio Manager
- Posisi aktif lintas market + PnL realtime USD + IDR
- Alert: mendekati SL, drawdown besar, alokasi berlebih
- Riwayat trade + Win Rate + Profit Factor otomatis

### 📖 Panduan Eksekusi
- Step-by-step cara buka posisi di broker
- Cara membaca setiap metrik
- 5 rules wajib yang tidak boleh dilanggar
- Rekomendasi broker per market

---

## 🌐 Market yang Didukung

| Market | Contoh Simbol | Sumber Data |
|--------|--------------|-------------|
| **Crypto** | BTCUSDT, ETHUSDT, SOLUSDT, BNBUSDT | ccxt (OKX → Bybit → KuCoin) |
| **Forex** | EURUSD, GBPUSD, USDJPY, AUDUSD | yfinance |
| **Gold & Silver** | XAUUSD, XAGUSD | yfinance |
| **Oil** | OIL Crude | yfinance |
| **Saham US** | AAPL, NVDA, TSLA, MSFT, GOOGL | yfinance |
| **Saham IDX** | BBCA, BBRI, BUMI, WBSA, ANTM, ADRO | yfinance (.JK) |

---

## 🖥️ Platform Eksekusi yang Kompatibel

| Kategori | Platform |
|----------|----------|
| **Crypto Exchange** | Binance, OKX, Bybit, KuCoin, Kraken |
| **Forex / CFD** | MetaTrader 5, cTrader, TradingView, OANDA, IC Markets, XM |
| **Saham IDX** | Stockbit, IPOT, Mirae Asset, BNI Sekuritas |
| **Saham US** | Interactive Brokers, Webull, eToro |

---

## 🏗️ Arsitektur

```
QuantPulse Pro V3 — 13 Modul, 6,242 Baris

data_loader.py         → Fetch data OHLCV dari exchange
signal_engine.py       → 6 indikator + Ensemble + MTFA
risk_engine.py         → SL/TP + sizing + spread tolerance
backtester.py          → Simulasi historis + Walk-Forward
portfolio_manager.py   → PnL realtime + riwayat trade
predictive_trade.py    → Proyeksi 5 candle ke depan
sr_detector.py         → Support & Resistance 4 metode
candle_detector.py     → 18 pola candlestick
auto_refresh.py        → Auto-refresh sidebar
app.py                 → Dashboard Streamlit (10 tab)
```

### Alur Data

```
Exchange/yfinance
      ↓
data_loader.py  →  OHLCV DataFrame
      ↓
signal_engine.py  →  SignalResult (BUY/SELL/HOLD + confidence)
      ↓
risk_engine.py   →  RiskResult (entry, SL, TP, sizing, spread)
      ↓
app.py           →  Dashboard 10 tab
```

---

## 🚀 Quick Start

### 1. Clone

```bash
git clone https://github.com/rifqyalwi2-del/QuantPulse.git
cd QuantPulse
```

### 2. Virtual Environment

```bash
# Windows (PowerShell)
python -m venv .venv
.venv\Scripts\Activate.ps1

# Mac / Linux
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install

```bash
pip install -r requirements.txt
```

### 4. Jalankan

```bash
streamlit run app.py
```

Buka **http://localhost:8501**

---

## ☁️ Deploy ke Streamlit Cloud

```bash
git add .
git commit -m "feat: QuantPulse Pro V3"
git push origin main
```

Lalu di [share.streamlit.io](https://share.streamlit.io):
1. **New app** → pilih repo → `app.py`
2. **Advanced settings → Secrets** → tambahkan `GOOGLE_API_KEY`
3. Klik **Deploy** → tunggu 3–5 menit

---

## 📦 Requirements

```
streamlit>=1.35.0
pandas>=2.0.0
numpy>=1.26.0
ccxt>=4.0.0
yfinance>=0.2.40
requests>=2.31.0
streamlit-autorefresh>=1.0.1
plotly>=5.18.0
```

---

## 📁 Struktur Project

```
QuantPulse/
├── .streamlit/
│   └── secrets.toml        ← API keys (jangan di-commit)
├── app.py                  ← Dashboard utama (10 tab)
├── signal_engine.py        ← Engine sinyal teknikal
├── risk_engine.py          ← Engine manajemen risiko
├── data_loader.py          ← Fetch data dari exchange
├── backtester.py           ← Backtesting & Walk-Forward
├── portfolio_manager.py    ← Manajemen portofolio
├── predictive_trade.py     ← Prediksi candle ke depan
├── sr_detector.py          ← Deteksi Support & Resistance
├── candle_detector.py      ← Deteksi pola candlestick
├── auto_refresh.py         ← Auto-refresh helper
├── requirements.txt        ← Dependencies
├── .gitignore
└── README.md
```

---

## 📊 Dashboard — 12 Tab

| Tab | Fungsi |
|-----|--------|
| 📡 **Sinyal** | Candlestick chart + sinyal BUY/SELL/HOLD + breakdown indikator |
| 🛡️ **Risk & Eksekusi** | Entry/SL/TP + level broker + estimasi profit IDR/USD |
| 📁 **Portfolio** | PnL realtime + posisi aktif + riwayat trade |
| 📊 **Backtest** | Simulasi historis + Walk-Forward + Grade A–F |
| 📐 **S&R** | Support & Resistance 4 metode + Fibonacci |
| 🕯️ **Candle** | 18 pola candlestick + konfirmasi sinyal |
| 🔮 **Prediksi** | Proyeksi 5 candle + entry broker siap pakai |
| 📖 **Panduan** | Step-by-step eksekusi + rekomendasi broker |
| 🔧 **Debug** | Status modul + data source info |

---

## ⚠️ Disclaimer

> QuantPulse Pro adalah **alat analisis**, bukan saran investasi atau jaminan profit.
>
> - Semua sinyal dan prediksi bersifat estimasi berdasarkan data historis
> - **Selalu pasang Stop Loss** — tidak ada pengecualian
> - Jangan investasikan uang yang tidak siap hilang
> - Backtesting bagus tidak menjamin performa di masa depan
> - Penggunaan sepenuhnya menjadi tanggung jawab pengguna

---

## 📜 License

MIT License — bebas digunakan, dimodifikasi, dan didistribusikan.

---

<div align="center">

**Dibuat dengan ❤️ untuk trader Indonesia**

*QuantPulse Pro V3 · Multi-Market · Multi-Platform · AI-Powered*

⭐ Jika bermanfaat, berikan star di GitHub!

</div>
