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

### 🤖 AI Analysis *(Opsional — Gratis)*
- 5 AI agent: Technical → Sentiment → Bull → Bear → Trader Agent
- Keputusan final dalam **Bahasa Indonesia** + Entry, SL, TP, alasan
- Biaya **$0** via Google AI Studio (15 req/menit, gratis)

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

data_loader.py           598   Fetch OHLCV — ccxt + yfinance
signal_engine.py         603   6 indikator + Ensemble + MTFA
risk_engine.py           402   SL/TP + sizing + spread broker
backtester.py            693   Walk-Forward + Grade A-F
portfolio_manager.py     344   PnL realtime USD + IDR
predictive_trade.py      424   Proyeksi 5 candle ke depan
sr_detector.py           550   S/R 4 metode + Fibonacci
candle_detector.py       404   18 pola candlestick
watchlist.py             237   Scanner multi-simbol
journal.py               390   Jurnal trading + statistik
calculator.py            163   Kalkulator posisi + margin
auto_refresh.py           37   Auto-refresh sidebar
app.py                 1,397   Dashboard — 12 tab
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

## 🤖 Setup AI Analysis *(Opsional — Gratis)*

1. Buka [aistudio.google.com](https://aistudio.google.com) → Login → **Get API Key** → Copy

2. Buat `.streamlit/secrets.toml`:

```toml
GOOGLE_API_KEY = "AIzaSy_paste_key_kamu_disini"
```

3. Tambahkan ke `.gitignore`:

```bash
echo ".streamlit/secrets.toml" >> .gitignore
```

> ⚠️ Jangan pernah commit API key ke GitHub!

---

## 🔒 Catatan Penggunaan VPN

Beberapa ISP Indonesia memblokir exchange crypto internasional. Jika data crypto tidak muncul padahal Mode Demo OFF, gunakan VPN.

**Kapan perlu VPN:**
- Muncul error `451 Unavailable For Legal Reasons`
- Tab Debug menampilkan `Sumber: DEMO` padahal Mode Demo OFF
- Data crypto tidak update meski sudah Refresh

**Rekomendasi (gratis):**

| VPN | Batas | Keterangan |
|-----|-------|------------|
| **Cloudflare WARP** | Unlimited | Terbaik — cepat dan gratis |
| **ProtonVPN** | Unlimited* | Terpercaya, speed dibatasi |
| **Windscribe** | 10 GB/bulan | Alternatif |

**Setup Cloudflare WARP:**
1. Download di [one.one.one.one](https://one.one.one.one)
2. Install → aktifkan toggle → **Connected**
3. Refresh Data di QuantPulse

> Untuk Forex, Gold, Oil, dan Saham IDX/US — VPN **tidak diperlukan**.

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
google-generativeai>=0.8.0
plotly>=5.18.0
```

---

## 📁 Struktur Project

```
QuantPulse/
├── .streamlit/
│   └── secrets.toml        ← API keys (jangan di-commit)
├── app.py                  ← Dashboard utama — 12 tab
├── signal_engine.py
├── risk_engine.py
├── data_loader.py
├── backtester.py
├── portfolio_manager.py
├── predictive_trade.py
├── sr_detector.py
├── candle_detector.py
├── watchlist.py            ← Scanner multi-simbol (baru)
├── journal.py              ← Jurnal trading (baru)
├── calculator.py           ← Kalkulator posisi (baru)
├── auto_refresh.py
├── requirements.txt
├── .gitignore
└── README.md
```

---

## 📊 Dashboard — 12 Tab

| # | Tab | Fungsi |
|---|-----|--------|
| 1 | 📡 **Sinyal** | Candlestick chart + EMA + Volume + sinyal BUY/SELL/HOLD |
| 2 | 🛡️ **Risk & Eksekusi** | Entry/SL/TP + level broker + estimasi profit IDR/USD |
| 3 | 📁 **Portfolio** | Posisi aktif + PnL realtime + alert + riwayat trade |
| 4 | 📊 **Backtest** | Simulasi historis + Walk-Forward + Grade A–F |
| 5 | 📐 **S&R** | Support & Resistance 4 metode + Fibonacci |
| 6 | 🕯️ **Candle** | 18 pola candlestick + konfirmasi sinyal |
| 7 | 🔮 **Prediksi** | Proyeksi 5 candle + entry broker |
| 8 | 👁️ **Watchlist** | Scan multi-simbol + highlight sinyal terkuat |
| 9 | 📔 **Jurnal** | Catat trade + statistik pribadi + export CSV |
| 10 | 🧮 **Kalkulator** | Hitung lot/margin/profit tanpa data live |
| 11 | 📖 **Panduan** | Step-by-step eksekusi + rekomendasi broker |
| 12 | 🔧 **Debug** | Status modul + data source info |

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