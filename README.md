<div align="center">

# ⚡ QuantPulse

### AI-Powered Multi-Market Trading Dashboard

**Menghilangkan Emosi dari Investasi, Menghadirkan Presisi Institusi**

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue?logo=python)](https://python.org)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.35%2B-red?logo=streamlit)](https://streamlit.io)
[![License](https://img.shields.io/badge/License-MIT-green)](LICENSE)
[![Platform](https://img.shields.io/badge/Platform-Multi--Market-orange)](#market-yang-didukung)

[Demo Live](#) · [Dokumentasi](#cara-pakai) · [Lapor Bug](issues)

</div>

---

## 📋 Tentang QuantPulse Pro

QuantPulse Pro adalah dashboard analisis trading berbasis AI yang dirancang untuk semua jenis market dan kompatibel dengan semua platform eksekusi. Tidak seperti tool trading lain yang hanya fokus ke satu market, QuantPulse mendukung **Crypto, Forex, Saham IDX, Saham US, Gold, dan Oil** dalam satu dashboard terintegrasi.

Dashboard ini **bukan bot trading otomatis** — melainkan alat analisis cerdas yang membantu trader membuat keputusan lebih baik dengan data teknikal, AI reasoning, dan manajemen risiko yang terstruktur.

---

## ✨ Fitur Utama

### 📡 Signal Engine
- **6 indikator teknikal**: RSI, MACD, Bollinger Bands, EMA Crossover, Stochastic, Volume
- **Ensemble voting** dengan bobot adaptif per market
- **Multi-Timeframe Analysis (MTFA)**: HTF + MTF + LTF sekaligus
- **Adaptive confidence scoring** dengan baseline 20%
- **Regime detection**: LOW / NORMAL / HIGH / CRISIS

### 🛡️ Risk Engine
- Entry, Stop Loss, Take Profit otomatis berbasis ATR
- **Toleransi spread** per platform (Binance, OKX, MT5, Stockbit, dll)
- Level BUY/SELL siap pakai di semua broker dan exchange
- Kelly Criterion position sizing
- Estimasi profit/loss dalam **USD dan IDR**
- Value at Risk (VaR) 95%
- Veto system — trade ditolak otomatis jika kondisi tidak layak

### 📊 Backtester
- Anti look-ahead bias — sinyal dihitung dari `df[:i]`, entry di open `i+1`
- **Walk-Forward Analysis** (train/test split, N fold)
- Grade **A–F** untuk penilaian cepat
- Metrik lengkap: Sharpe, Sortino, Calmar, Max Drawdown, Win Rate, Profit Factor
- Equity curve + Drawdown chart interaktif

### 📐 Support & Resistance Auto-Detection
- **4 metode**: Pivot Points, Volume Profile, Round Numbers, Fibonacci Retracement
- Strength scoring per level
- Zone signal: NEAR_SUPPORT / NEAR_RESISTANCE / IN_RANGE
- Integrasi otomatis dengan sinyal aktif

### 🕯️ Candlestick Pattern Detector
- **18 pola** klasik: Hammer, Engulfing, Morning Star, Evening Star, Three White Soldiers, dll
- Konfirmasi atau kontradiksi terhadap sinyal engine
- Quick summary di tab Sinyal

### 🔮 Prediksi Trade
- Proyeksi **5 candle ke depan**
- Range harga atas/bawah
- Timestamp dalam **WIB** (Waktu Indonesia Barat)
- Estimasi profit/loss per candle
- **Entry Broker** dengan toleransi spread sudah dihitung

### 📈 Candlestick Chart
- Chart interaktif via **Plotly**
- EMA 9 (kuning) + EMA 21 (biru) overlay
- Volume bar dengan warna arah candle
- S/R level overlay otomatis
- Slider jumlah candle (30–300)

### 📁 Portfolio Manager
- Catat posisi aktif lintas market
- PnL realtime dalam USD + IDR
- Alert: mendekati SL, drawdown besar, alokasi berlebih
- Riwayat trade lengkap
- Win rate + Profit Factor otomatis

### 📖 Panduan Eksekusi
- Step-by-step cara buka posisi di broker
- Cara membaca setiap metrik
- 5 rules wajib yang tidak boleh dilanggar
- Rekomendasi broker per market

---

## 🌐 Market yang Didukung

| Market | Simbol Contoh | Sumber Data |
|--------|--------------|-------------|
| **Crypto** | BTCUSDT, ETHUSDT, SOLUSDT, BNBUSDT | ccxt (OKX → Bybit → KuCoin) |
| **Forex** | EURUSD, GBPUSD, USDJPY, AUDUSD | yfinance |
| **Gold & Silver** | XAUUSD, XAGUSD | yfinance (GC=F, SI=F) |
| **Oil** | OIL (Crude) | yfinance (CL=F) |
| **Saham US** | AAPL, NVDA, TSLA, MSFT, GOOGL | yfinance |
| **Saham IDX** | BBCA, BBRI, BUMI, WBSA, ANTM, ADRO | yfinance (.JK) |

> Simbol IDX bisa diketik bebas — sistem otomatis menambahkan `.JK` untuk yfinance.

---

## 🖥️ Platform Eksekusi yang Kompatibel

QuantPulse memberikan level harga yang bisa langsung digunakan di semua platform:

| Kategori | Platform |
|----------|----------|
| **Crypto Exchange** | Binance, OKX, Bybit, KuCoin, Kraken |
| **Forex / CFD Broker** | MetaTrader 5, cTrader, TradingView, OANDA, IC Markets, Pepperstone |
| **Saham IDX** | Stockbit, IPOT, Mirae Asset, BNI Sekuritas, Mandiri Sekuritas |
| **Saham US** | Interactive Brokers, Webull, eToro, Robinhood |
| **Multi-asset** | TradingView (paper trading), AvaTrade |

---

## 🏗️ Arsitektur

```
QuantPulse Pro V3 — 11 Modul, 5,787 Baris

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

### 1. Clone Repository

```bash
git clone https://github.com/USERNAME/QuantPulse.git
cd QuantPulse
```

### 2. Setup Virtual Environment

```bash
# Windows (PowerShell)
python -m venv .venv
.venv\Scripts\Activate.ps1

# Mac/Linux
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Jalankan Dashboard

```bash
streamlit run app.py
```

Buka browser ke **http://localhost:8501**

---

## ☁️ Deploy ke Streamlit Cloud

### 1. Push ke GitHub

```bash
git add .
git commit -m "init: QuantPulse Pro V3"
git push origin main
```

### 2. Deploy

1. Buka [share.streamlit.io](https://share.streamlit.io)
2. Login dengan GitHub
3. **New app** → pilih repository → main file: `app.py`
4. **Advanced settings → Secrets** → tambahkan `GOOGLE_API_KEY`
5. Klik **Deploy**

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

## 📁 Struktur File

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

## 📊 Dashboard — 10 Tab

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

> **QuantPulse adalah alat analisis, bukan saran investasi.**
>
> - Semua sinyal dan prediksi bersifat **estimasi**, bukan jaminan profit
> - Selalu gunakan **Stop Loss** di setiap posisi
> - Jangan investasikan uang yang tidak siap untuk hilang
> - Backtesting bagus **tidak menjamin** performa di masa depan
> - Penggunaan sepenuhnya menjadi tanggung jawab pengguna

---

## 📜 License

MIT License — bebas digunakan, dimodifikasi, dan didistribusikan.

---

<div align="center">

**Dibuat dengan ❤️ untuk trader Indonesia**

*QuantPulse — Multi-Market · Multi-Platform · AI-Powered*

</div>
