# User Guide: Configuration via user_data.csv

This guide explains how to configure the Financial Market Data Collection System through the `user_input/user_data.csv` file.

## 📋 Table of Contents

- [Configuration File Location](#configuration-file-location)
- [Configuration Format](#configuration-format)
- [Ticker Data Sources](#ticker-data-sources)
- [Historical Data Collection](#historical-data-collection)
- [Financial Data Enrichment](#financial-data-enrichment)
- [General Settings](#general-settings)
- [Common Configuration Scenarios](#common-configuration-scenarios)
- [Ticker Universe Options](#ticker-universe-options)

---

## 📂 Configuration File Location

**Primary config file:** `user_input/user_data.csv`

This CSV file controls all aspects of data collection. Each line has three columns:
```csv
variable_name,value,description
```

---

## 📝 Configuration Format

### Basic Structure

```csv
# Section Header (ignored by system)
variable_name,value,Description of what this does
```

### Rules

- Lines starting with `#` are comments (ignored)
- Format: `variable,value,description`
- Values are case-sensitive: `TRUE`, `FALSE`
- File paths can be relative or absolute
- Empty lines are ignored

---

## 🎯 Ticker Data Sources

Choose where to get your ticker lists from.

### Configuration Options

```csv
# TICKER DATA SOURCES
WEB_tickers_down,TRUE/FALSE,Download ticker names from web sources
TW_tickers_down,TRUE/FALSE,Use ticker names from TradingView universe file
TW_universe_file,tradingview_universe.csv,TradingView universe filename
```

### How It Works

**Option 1: Web Sources (NASDAQ, Wikipedia)**
```csv
WEB_tickers_down,TRUE
TW_tickers_down,FALSE
```
- Downloads tickers from NASDAQ website, Wikipedia, etc.
- Automatically generates: sp500_tickers.csv, nasdaq100_tickers.csv, etc.

**Option 2: TradingView Universe** ⭐ Recommended
```csv
WEB_tickers_down,FALSE
TW_tickers_down,TRUE
TW_universe_file,tradingview_universe.csv
```
- Uses your custom TradingView universe file
- File must be in `user_input/` directory
- More control over ticker selection

**⚠️ Priority:** If both are TRUE, WEB source takes priority

---

## 📈 Historical Data Collection

Configure which data sources and timeframes to use.

### Yahoo Finance Route

```csv
# HISTORICAL DATA COLLECTION
YF_hist_data,TRUE/FALSE,Master switch for Yahoo Finance
YF_daily_data,TRUE/FALSE,Download daily (1d) data
YF_weekly_data,TRUE/FALSE,Download weekly (1wk) data
YF_monthly_data,TRUE/FALSE,Download monthly (1mo) data
```

**Example: Daily data only**
```csv
YF_hist_data,TRUE
YF_daily_data,TRUE
YF_weekly_data,FALSE
YF_monthly_data,FALSE
```

**Speed:** ~3 hours for 6,000 tickers
**Output:** `data/market_data/{daily,weekly,monthly}/`

### TradingView Route ⚡ Fast Updates

```csv
# TRADINGVIEW DATA UPDATES
TW_hist_data,TRUE/FALSE,Master switch for TradingView
TW_daily_data,TRUE/FALSE,Process daily TradingView files
TW_weekly_data,TRUE/FALSE,Process weekly TradingView files
TW_monthly_data,TRUE/FALSE,Process monthly TradingView files
TW_files_path,data/tw_files,Where to find TradingView bulk CSV files
```

**Example: Daily TradingView updates**
```csv
TW_hist_data,TRUE
TW_daily_data,TRUE
TW_weekly_data,FALSE
TW_monthly_data,FALSE
TW_files_path,data/tw_files
```

**Speed:** ~1-2 minutes for 6,000 tickers
**Output:** `data/market_data_tw/{daily,weekly,monthly}/`

**Workflow:**
1. Download bulk CSV from TradingView
2. Place in `data/tw_files/daily/`
3. System automatically processes and updates individual ticker files

### Intraday Data (Not Implemented Yet)

```csv
TW_intraday_data,FALSE,NOT IMPLEMENTED
TW_intraday_file,intraday_data.csv,NOT IMPLEMENTED
```

⚠️ These settings are placeholders for future functionality.

---

## 💰 Financial Data Enrichment

Collect comprehensive financial metrics for CANSLIM analysis.

### Configuration

```csv
# FINANCIAL DATA ENRICHMENT
fin_data_enrich,TRUE/FALSE,Master switch for financial data
YF_fin_data,TRUE/FALSE,Download from Yahoo Finance
TW_fin_data,FALSE,Download from TradingView (not implemented)
Zacks_fin_data,FALSE,Download from Zacks (future)
```

### Financial Metrics Collected

When `fin_data_enrich = TRUE`:
- **Earnings growth** (quarterly and annual)
- **Revenue growth** (quarterly and annual)
- **Profitability metrics** (margins, ROE, ROA)
- **Balance sheet** (debt, cash, ratios)
- **Share information** (outstanding, float, insider holdings)
- **Valuation** (PE, PEG, price targets)
- **CANSLIM scores** (automated scoring system)

**Output:**
- `data/tickers/financial_data_{choice}.csv` - Full dataset
- `data/tickers/financial_data_summary_{choice}.csv` - Key metrics

**Time:** 5-15 minutes depending on ticker count

---

## ⚙️ General Settings

### Path Configuration

```csv
# GENERAL SETTINGS
user_input_path,user_input,Directory for user input files
TW_files_path,data/tw_files,Directory for TradingView bulk files
```

**Changing paths:**
- Use relative paths (from project root): `my_data/input`
- Or absolute paths: `/home/user/trading_data/input`
- System creates subdirectories automatically

### Info File Settings

```csv
write_info_file,TRUE/FALSE,Write detailed ticker info files
ticker_info_TW,TRUE/FALSE,Get info from TradingView universe
ticker_info_TW_file,tradingview_universe_bool.csv,TW info filename
ticker_info_YF,TRUE/FALSE,Download info from Yahoo Finance
```

**Info files include:**
- Exchange, sector, industry
- Market cap, volume statistics
- Index membership (SP500, NASDAQ100, etc.)

### Ticker Universe Selection

```csv
ticker_choice,N,Which ticker group to process
```

**Options:**

| Choice | Description | Tickers |
|--------|-------------|---------|
| 0 | TradingView Universe only | Your custom list |
| 1 | S&P 500 only | ~500 |
| 2 | NASDAQ 100 only | ~100 |
| 3 | All NASDAQ stocks | ~3,300 |
| 4 | Russell 1000 (IWM) | ~1,000 |
| 5 | Index tickers only | Custom |
| 6 | Portfolio tickers only | Your portfolio |
| 7 | ETF tickers only | Custom |
| 8 | TEST tickers only | Small test set |

**Combinations:** You can combine choices with dashes:
```csv
ticker_choice,1-2,S&P 500 + NASDAQ 100
ticker_choice,1-2-4,S&P 500 + NASDAQ 100 + Russell 1000
```

---

## 🎬 Common Configuration Scenarios

### Scenario 1: Quick Daily Update from TradingView

**Use Case:** Daily morning update before market opens

```csv
# Ticker Source
TW_tickers_down,TRUE
TW_universe_file,tradingview_universe.csv

# Data Collection
YF_hist_data,FALSE
TW_hist_data,TRUE
TW_daily_data,TRUE
TW_files_path,data/tw_files

# Ticker Selection
ticker_choice,2

# Financial Data
fin_data_enrich,FALSE
```

**Steps:**
1. Download TradingView file before market opens
2. Place in `data/tw_files/daily/`
3. Run `python main.py`
4. Updated in 1-2 minutes

---

### Scenario 2: Full Historical Download (Initial Setup)

**Use Case:** First-time setup, need complete history

```csv
# Ticker Source
WEB_tickers_down,TRUE

# Data Collection
YF_hist_data,TRUE
YF_daily_data,TRUE
YF_weekly_data,TRUE
YF_monthly_data,FALSE

# Ticker Selection
ticker_choice,2

# Financial Data
fin_data_enrich,TRUE
YF_fin_data,TRUE
```

**Time:** 30-60 minutes for NASDAQ 100
**Result:** Complete historical database

---

### Scenario 3: Custom Portfolio Only

**Use Case:** Track your personal portfolio

```csv
# Ticker Source
TW_tickers_down,FALSE
WEB_tickers_down,FALSE

# Data Collection
YF_hist_data,TRUE
YF_daily_data,TRUE

# Ticker Selection
ticker_choice,6

# Financial Data
fin_data_enrich,TRUE
YF_fin_data,TRUE
```

**Requirements:**
- Create `user_input/portofolio_tickers.csv` with your tickers
- Format: one column named "ticker"

```csv
ticker
AAPL
MSFT
GOOGL
TSLA
NVDA
```

---

### Scenario 4: Dual Route (Best of Both Worlds)

**Use Case:** Combine fast TradingView updates with comprehensive Yahoo Finance data

```csv
# Ticker Source
TW_tickers_down,TRUE

# Data Collection - Both routes active
YF_hist_data,TRUE
YF_daily_data,TRUE
TW_hist_data,TRUE
TW_daily_data,TRUE

# Ticker Selection
ticker_choice,2

# Financial Data
fin_data_enrich,TRUE
YF_fin_data,TRUE
```

**Result:**
- YF data in `data/market_data/daily/`
- TW data in `data/market_data_tw/daily/`
- Financial metrics in `data/tickers/`

---

### Scenario 5: Large Universe Weekly Updates

**Use Case:** Track entire NASDAQ weekly

```csv
# Ticker Source
TW_tickers_down,TRUE

# Data Collection
YF_hist_data,FALSE
TW_hist_data,TRUE
TW_daily_data,FALSE
TW_weekly_data,TRUE

# Ticker Selection
ticker_choice,3

# Financial Data
fin_data_enrich,FALSE
```

**Benefit:** Lower frequency = faster processing

---

## 🔍 Ticker Universe Options

### Option 0: TradingView Universe

```csv
ticker_choice,0
TW_tickers_down,TRUE
TW_universe_file,tradingview_universe.csv
```

**Use when:** You have a custom universe from TradingView

**File format:**
```csv
Symbol,Description,Market capitalization,...
AAPL,Apple Inc.,1084627562115,...
MSFT,Microsoft Corp.,2876543210987,...
```

### Option 1: S&P 500

```csv
ticker_choice,1
```

**Tickers:** ~500 large-cap US stocks
**Use when:** Focus on established, stable companies

### Option 2: NASDAQ 100

```csv
ticker_choice,2
```

**Tickers:** ~100 largest non-financial NASDAQ stocks
**Use when:** Focus on tech and growth stocks

### Option 3: All NASDAQ

```csv
ticker_choice,3
```

**Tickers:** ~3,300 stocks
**Use when:** Comprehensive NASDAQ coverage

### Option 4: Russell 1000

```csv
ticker_choice,4
```

**Tickers:** ~1,000 large-cap stocks
**Use when:** Broader market coverage than S&P 500

### Option 6: Your Portfolio

```csv
ticker_choice,6
```

**Requires:** `user_input/portofolio_tickers.csv`
**Use when:** Track personal holdings

### Combinations

```csv
# S&P 500 + NASDAQ 100
ticker_choice,1-2

# Complete market coverage
ticker_choice,1-3-4

# Your portfolio + major indexes (for comparison)
ticker_choice,6-1-2
```

---

## 📝 Configuration File Template

Here's a complete template you can copy:

```csv
# Financial Data Collection Configuration
# Set TRUE/FALSE for each option below

# TICKER DATA SOURCES
WEB_tickers_down,FALSE,Download ticker names from web sources
TW_tickers_down,TRUE,Use ticker names from TradingView universe file
TW_universe_file,tradingview_universe.csv,TradingView universe filename

# HISTORICAL DATA COLLECTION
YF_hist_data,TRUE,Download historical OHLCV data via YFinance
YF_daily_data,TRUE,Download daily (1d) historical data
YF_weekly_data,FALSE,Download weekly (1wk) historical data
YF_monthly_data,FALSE,Download monthly (1mo) historical data
TW_hist_data,TRUE,Update from TradingView bulk files
TW_daily_data,TRUE,Process daily TradingView bulk files
TW_weekly_data,FALSE,Process weekly TradingView bulk files
TW_monthly_data,FALSE,Process monthly TradingView bulk files
TW_files_path,data/tw_files,TradingView bulk files directory
user_input_path,user_input,User input files directory

# FINANCIAL DATA ENRICHMENT
fin_data_enrich,FALSE,Enable financial data enrichment
YF_fin_data,FALSE,Download financial data from YFinance
TW_fin_data,FALSE,Download financial data from TradingView
Zacks_fin_data,FALSE,Download financial data from Zacks

# GENERAL SETTINGS
write_info_file,TRUE,Write detailed info files during processing
ticker_info_TW,TRUE,Get ticker info from TradingView universe
ticker_info_TW_file,tradingview_universe_bool.csv,TW info filename
ticker_info_YF,FALSE,Download ticker info from YFinance
ticker_choice,2,Ticker combination choice (see documentation)
```

---

## ⚠️ Important Notes

### Data Source Priority

If multiple ticker sources are enabled:
1. **WEB_tickers_down** takes priority over TW_tickers_down
2. To use TradingView, set WEB_tickers_down = FALSE

### Required Files

Depending on your configuration, you may need:

- `user_input/tradingview_universe.csv` (if TW_tickers_down = TRUE)
- `user_input/portofolio_tickers.csv` (if ticker_choice = 6)
- `user_input/indexes_tickers.csv` (if ticker_choice = 5)

### TradingView Files

Place bulk CSV files in the correct subdirectory:
- Daily: `data/tw_files/daily/all_stocks_OHLCV_YYYY-MM-DD.csv`
- Weekly: `data/tw_files/weekly/all_stocks_OHLCV_YYYY-MM-DD.csv`
- Monthly: `data/tw_files/monthly/all_stocks_OHLCV_YYYY-MM-DD.csv`

**Naming:** Files must contain date in format `YYYY-MM-DD`

### Performance Tips

**For speed:**
- Use TradingView route (100x faster than Yahoo Finance)
- Disable financial enrichment for quick updates
- Use smaller ticker universes for testing

**For completeness:**
- Use Yahoo Finance route for full historical data
- Enable financial enrichment for CANSLIM analysis
- Process all timeframes (daily, weekly, monthly)

---

## 🆘 Troubleshooting Configuration

### "Configuration not found"
```bash
# Check file exists
ls user_input/user_data.csv

# Check file permissions
chmod 644 user_input/user_data.csv
```

### "Invalid boolean value"
- Use `TRUE` or `FALSE` (all caps)
- Not: `true`, `True`, `yes`, `1`

### "Ticker file not found"
- Check filename matches config setting
- Verify file is in `user_input/` directory
- Check for typos in `TW_universe_file` setting

### "Update skipped"
- This is normal if data is current
- System uses smart sampling to avoid unnecessary work
- To force update: delete existing ticker files

### "Both sources enabled"
- Warning appears if WEB_tickers_down and TW_tickers_down are both TRUE
- System uses WEB source as priority
- Set one to FALSE to avoid confusion

---

## 📚 See Also

- [README.md](README.md) - Project overview and quick start
- [PROJECT_STRUCTURE.md](PROJECT_STRUCTURE.md) - Complete directory tree
- [docus/](docus/) - Technical implementation details

---

**Last Updated:** February 2026
