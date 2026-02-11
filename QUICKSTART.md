# Quick Start Guide

Get up and running in 5 minutes!

## ⚡ 5-Minute Setup

### 1. Install Dependencies (1 minute)

```bash
cd downloadData_v1
pip install -r requirements.txt
```

### 2. Configure System (2 minutes)

Edit `user_input/user_data.csv`:

```csv
# Choose ticker source
TW_tickers_down,TRUE
TW_universe_file,tradingview_universe.csv

# Enable daily data collection
YF_hist_data,TRUE
YF_daily_data,TRUE

# Select NASDAQ 100
ticker_choice,2

# Disable financial data for now (faster)
fin_data_enrich,FALSE
```

### 3. Add Your Data (1 minute)

**Option A: Use TradingView Universe**
- Place your `tradingview_universe.csv` in `user_input/`

**Option B: Use Built-in Lists**
- Set `WEB_tickers_down,TRUE` in config
- System will download automatically

### 4. Run! (1 minute)

```bash
python main.py
```

Watch the progress:
```
============================================================
TICKER DATA SOURCE SELECTION
============================================================
📊 Using TradingView ticker source

✅ Loaded 6344 tickers
...
✅ All data collection completed!
```

### 5. Check Results

Your data is ready in:
```
data/
├── tickers/
│   └── combined_tickers_2.csv      # Your ticker list
└── market_data/
    └── daily/
        ├── AAPL.csv                 # Historical data
        ├── MSFT.csv
        └── ...
```

---

## 🚀 Common Use Cases

### Daily Morning Update (TradingView)

**Time: 1-2 minutes**

1. Download TradingView file before market opens
2. Place in `data/tw_files/daily/`
3. Config:
```csv
TW_hist_data,TRUE
TW_daily_data,TRUE
YF_hist_data,FALSE
```
4. Run: `python main.py`

### Initial Full Download (Yahoo Finance)

**Time: 30-60 minutes for NASDAQ 100**

1. Config:
```csv
YF_hist_data,TRUE
YF_daily_data,TRUE
YF_weekly_data,TRUE
ticker_choice,2
```
2. Run: `python main.py`
3. Go get coffee ☕

### Track Your Portfolio

**Time: 5-10 minutes**

1. Create `user_input/portofolio_tickers.csv`:
```csv
ticker
AAPL
MSFT
GOOGL
TSLA
NVDA
```

2. Config:
```csv
ticker_choice,6
YF_hist_data,TRUE
YF_daily_data,TRUE
fin_data_enrich,TRUE
```

3. Run: `python main.py`

---

## 📊 What You Get

### Individual Ticker Files

Each ticker gets its own file with complete history:

`data/market_data/daily/AAPL.csv`:
```csv
Date,Open,High,Low,Close,Volume
2025-01-02 00:00:00-05:00,185.58,186.86,182.35,184.08,82488700
2025-01-03 00:00:00-05:00,182.67,184.32,181.89,182.70,58414500
...
```

### Combined Ticker List

`data/tickers/combined_tickers_2.csv`:
```csv
ticker
AAPL
MSFT
GOOGL
...
```

### Financial Metrics (if enabled)

`data/tickers/financial_data_2.csv`:
- 100+ columns of financial data
- CANSLIM scores
- Growth metrics
- Valuation ratios

---

## ⚙️ Configuration Presets

### Preset 1: Speed (TradingView Only)

```csv
WEB_tickers_down,FALSE
TW_tickers_down,TRUE
YF_hist_data,FALSE
TW_hist_data,TRUE
TW_daily_data,TRUE
fin_data_enrich,FALSE
ticker_choice,2
```

**Time:** 1-2 minutes
**Use:** Daily quick updates

### Preset 2: Complete (Yahoo Finance)

```csv
WEB_tickers_down,TRUE
TW_tickers_down,FALSE
YF_hist_data,TRUE
YF_daily_data,TRUE
YF_weekly_data,TRUE
YF_monthly_data,TRUE
fin_data_enrich,TRUE
YF_fin_data,TRUE
ticker_choice,2
```

**Time:** 30-60 minutes
**Use:** Initial setup, full history

### Preset 3: Hybrid (Best of Both)

```csv
TW_tickers_down,TRUE
YF_hist_data,TRUE
YF_daily_data,TRUE
TW_hist_data,TRUE
TW_daily_data,TRUE
fin_data_enrich,TRUE
ticker_choice,2
```

**Time:** 15-30 minutes
**Use:** Comprehensive daily routine

### Preset 4: Portfolio Only

```csv
WEB_tickers_down,FALSE
TW_tickers_down,FALSE
YF_hist_data,TRUE
YF_daily_data,TRUE
fin_data_enrich,TRUE
YF_fin_data,TRUE
ticker_choice,6
```

**Time:** 2-5 minutes
**Use:** Personal holdings tracking

---

## 🎯 Ticker Universe Options

Quick reference:

| Choice | Description | Count | Use Case |
|--------|-------------|-------|----------|
| 0 | TradingView Universe | Custom | Your own list |
| 1 | S&P 500 | ~500 | Large cap stocks |
| 2 | NASDAQ 100 | ~100 | Tech/growth stocks ⭐ |
| 3 | All NASDAQ | ~3,300 | Full NASDAQ |
| 4 | Russell 1000 | ~1,000 | Broad market |
| 6 | Portfolio | Custom | Your holdings |

**Combinations:** `ticker_choice,1-2` (S&P 500 + NASDAQ 100)

---

## 🔧 Troubleshooting

### "Configuration file not found"

```bash
# Check if file exists
ls user_input/user_data.csv

# If missing, copy template from docus/
cp docus/README.md user_input/
```

### "No data downloaded"

1. Check internet connection
2. Verify ticker symbols are valid
3. Look at `data/tickers/problematic_tickers_*.csv`

### "TradingView file not found"

Place your TradingView CSV file in correct directory:
```bash
data/tw_files/daily/all_stocks_OHLCV_2025-02-11.csv
```

File must contain date in format `YYYY-MM-DD`.

### System runs but skips update

```
⏭️  Decision: SKIP UPDATE (all current)
```

This is normal! System detected data is already up-to-date.

To force update:
```bash
rm data/market_data_tw/daily/*.csv
python main.py
```

---

## 📚 Next Steps

**After your first run:**

1. ✅ Verify data: Check `data/market_data/daily/AAPL.csv`
2. ✅ Review logs: Look for any errors
3. ✅ Enable financial data: Set `fin_data_enrich,TRUE`
4. ✅ Set up TradingView: For faster updates
5. ✅ Automate: Add to crontab for daily runs

**Read the full guides:**
- [USER_GUIDE.md](USER_GUIDE.md) - Complete configuration options
- [PROJECT_STRUCTURE.md](PROJECT_STRUCTURE.md) - Understanding the layout
- [README.md](README.md) - Full documentation

---

## 💡 Pro Tips

**Speed Tips:**
- Use TradingView for daily updates (100x faster)
- Use Yahoo Finance for initial download only
- Start with small ticker universe (NASDAQ 100)
- Disable financial data for quick updates

**Quality Tips:**
- Enable all timeframes (daily, weekly, monthly)
- Enable financial data for comprehensive analysis
- Use both Yahoo Finance and TradingView
- Keep historical data files as backup

**Organization Tips:**
- Use custom paths for different projects
- Keep raw TradingView files for auditing
- Export financial data regularly
- Document your configuration changes

---

## 🎉 You're Ready!

```bash
python main.py
```

Watch your data collection system work! 🚀

---

**Need Help?**
- 📖 [Full Documentation](README.md)
- ⚙️ [Configuration Guide](USER_GUIDE.md)
- 🗂️ [Project Structure](PROJECT_STRUCTURE.md)

---

**Last Updated:** February 2026
