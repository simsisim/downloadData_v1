# Project Structure

Complete directory tree and file organization for the Financial Market Data Collection System.

## 📁 Directory Tree

```
downloadData_v1/
├── user_input/                          # USER INPUT FILES (you create/edit these)
│   ├── user_data.csv                    # Main configuration file ⚙️
│   ├── tradingview_universe.csv         # Your TradingView ticker universe
│   ├── portofolio_tickers.csv          # Your personal portfolio tickers
│   └── indexes_tickers.csv             # Index tickers you want to track
│
├── data/                                # DATA STORAGE (system generates)
│   ├── tickers/                        # Generated ticker lists
│   │   ├── sp500_tickers.csv          # S&P 500 tickers
│   │   ├── nasdaq100_tickers.csv      # NASDAQ 100 tickers
│   │   ├── nasdaq_all_tickers.csv     # All NASDAQ tickers
│   │   ├── iwm1000_tickers.csv        # Russell 1000 tickers
│   │   ├── russell2000_tickers.csv    # Russell 2000 tickers
│   │   ├── russell3000_tickers.csv    # Russell 3000 tickers
│   │   ├── etf_tickers.csv            # ETF list
│   │   ├── tradingview_universe_bool.csv  # TW universe with boolean columns
│   │   ├── combined_tickers_{N}.csv   # Combined list for choice N
│   │   ├── financial_data_{N}.csv     # Financial metrics dataset
│   │   ├── financial_data_summary_{N}.csv  # Key metrics summary
│   │   └── problematic_tickers_{N}.csv # Tickers that failed
│   │
│   ├── market_data/                   # Yahoo Finance OHLCV data
│   │   ├── daily/                     # Daily (1d) interval
│   │   │   ├── AAPL.csv              # Individual ticker files
│   │   │   ├── MSFT.csv
│   │   │   ├── GOOGL.csv
│   │   │   └── ...                    # One file per ticker
│   │   ├── weekly/                    # Weekly (1wk) interval
│   │   │   └── {ticker}.csv
│   │   └── monthly/                   # Monthly (1mo) interval
│   │       └── {ticker}.csv
│   │
│   ├── market_data_tw/                # TradingView OHLCV data
│   │   ├── daily/                     # Daily data from TW
│   │   │   ├── AAPL.csv              # Individual ticker files
│   │   │   ├── MSFT.csv
│   │   │   └── ...
│   │   ├── weekly/                    # Weekly data from TW
│   │   │   └── {ticker}.csv
│   │   └── monthly/                   # Monthly data from TW
│   │       └── {ticker}.csv
│   │
│   └── tw_files/                      # TradingView bulk CSV files (INPUT)
│       ├── daily/                     # Place your daily TW files here
│       │   ├── all_stocks_OHLCV_2025-02-11.csv
│       │   ├── all_ETFs_OHLCV_2025-02-11.csv
│       │   └── ...
│       ├── weekly/                    # Place your weekly TW files here
│       │   └── all_stocks_OHLCV_2025-02-10.csv
│       └── monthly/                   # Place your monthly TW files here
│           └── all_stocks_OHLCV_2025-01-31.csv
│
├── src/                               # SOURCE CODE
│   ├── __init__.py                   # Package initialization
│   ├── config.py                     # Configuration management & directory setup
│   ├── user_defined_data.py          # CSV config file reader
│   ├── get_tickers.py                # Ticker retrieval from web sources
│   ├── get_marketData.py             # Yahoo Finance data downloader
│   ├── get_tradingview_data.py       # TradingView bulk file processor
│   ├── get_financial_data.py         # Financial metrics collector
│   ├── tradingview_ticker_processor.py  # TW universe processor
│   ├── unified_ticker_generator.py   # Ticker list generator
│   └── __pycache__/                  # Python cache (auto-generated)
│
├── docus/                             # DOCUMENTATION
│   ├── CLAUDE.md                     # AI assistant guidance
│   ├── README.md                     # Old documentation
│   ├── IMPLEMENTATION_SUMMARY.md     # TradingView implementation
│   ├── TRADINGVIEW_DATA_INTEGRATION_PLAN.md
│   ├── TRADINGVIEW_UPDATER_REFINED_PLAN.md
│   ├── TW_COLUMN_MAPPING_REFERENCE.md
│   ├── TRADINGVIEW_FIX_SUMMARY.md
│   ├── CHANGES_APPLIED.md
│   ├── RESEARCH_FINDINGS_FILE_REPLACEMENT.md
│   ├── RESEARCH_MULTI_FILE_APPROACH.md
│   └── MULTI_FILE_IMPLEMENTATION_SUMMARY.md
│
├── test/                              # Test files (optional)
│   └── test_*.py
│
├── main.py                            # Main entry point - run this! 🚀
├── requirements.txt                   # Python dependencies
├── README.md                          # Project overview
├── USER_GUIDE.md                      # Configuration guide
├── PROJECT_STRUCTURE.md               # This file
├── .gitignore                         # Git ignore rules
└── __init__.py                        # Package marker
```

---

## 📂 Directory Details

### `user_input/` - Your Input Files

**Purpose:** All files you create or edit

**Required Files:**
- `user_data.csv` - Main configuration (always required)

**Optional Files:**
- `tradingview_universe.csv` - Required if `TW_tickers_down = TRUE`
- `portofolio_tickers.csv` - Required if `ticker_choice = 6`
- `indexes_tickers.csv` - Custom index tickers

**File Formats:**

`user_data.csv`:
```csv
variable_name,value,description
YF_hist_data,TRUE,Download historical data
```

`tradingview_universe.csv`:
```csv
Symbol,Description,Market capitalization,...
AAPL,Apple Inc.,1084627562115,...
```

`portofolio_tickers.csv`:
```csv
ticker
AAPL
MSFT
GOOGL
```

---

### `data/tickers/` - Generated Ticker Lists

**Purpose:** System-generated ticker lists and metadata

**Generated Files:**

**Individual Index Files:**
- `sp500_tickers.csv` - S&P 500 members (~500)
- `nasdaq100_tickers.csv` - NASDAQ 100 members (~100)
- `nasdaq_all_tickers.csv` - All NASDAQ stocks (~3,300)
- `iwm1000_tickers.csv` - Russell 1000 members (~1,000)
- `russell2000_tickers.csv` - Russell 2000 members (~1,900)
- `russell3000_tickers.csv` - Russell 3000 members (~3,000)

**Combined Files:**
- `combined_tickers_{N}.csv` - Merged ticker list for choice N
- `tradingview_universe_bool.csv` - TW universe with index membership flags

**Financial Data:**
- `financial_data_{N}.csv` - Complete financial metrics (100+ columns)
- `financial_data_summary_{N}.csv` - Key metrics summary

**Error Tracking:**
- `problematic_tickers_{N}.csv` - Tickers that failed to download

**File Format:**
```csv
ticker
AAPL
MSFT
GOOGL
```

---

### `data/market_data/` - Yahoo Finance Data

**Purpose:** Historical OHLCV data from Yahoo Finance

**Structure:**
```
market_data/
├── daily/      # Daily data (1d interval)
├── weekly/     # Weekly data (1wk interval)
└── monthly/    # Monthly data (1mo interval)
```

**File Naming:** One file per ticker: `{TICKER}.csv`

**Example:** `AAPL.csv`
```csv
Date,Open,High,Low,Close,Volume,Dividends,Stock Splits
2025-01-02 00:00:00-05:00,185.58,186.86,182.35,184.08,82488700,0.0,0.0
2025-01-03 00:00:00-05:00,182.67,184.32,181.89,182.70,58414500,0.0,0.0
```

**Data Range:**
- Daily: 2020-01-01 to present
- Weekly: 2000-01-01 to present
- Monthly: 2000-01-01 to present

---

### `data/market_data_tw/` - TradingView Data

**Purpose:** Historical OHLCV data from TradingView bulk files

**Structure:** Identical to `market_data/`
```
market_data_tw/
├── daily/      # Daily TW data
├── weekly/     # Weekly TW data
└── monthly/    # Monthly TW data
```

**File Naming:** One file per ticker: `{TICKER}.csv`

**File Format:** Same as Yahoo Finance format

**Key Differences:**
- Updated from bulk CSV files (faster)
- May have different metadata columns
- Timezone-aware date handling
- Incremental updates only (appends new dates)

---

### `data/tw_files/` - TradingView Bulk Input

**Purpose:** Store TradingView bulk CSV files you download manually

**Structure:**
```
tw_files/
├── daily/      # Place daily bulk files here
├── weekly/     # Place weekly bulk files here
└── monthly/    # Place monthly bulk files here
```

**File Naming Convention:**
- Must contain date in format `YYYY-MM-DD`
- Examples:
  - `all_stocks_OHLCV_2025-02-11.csv`
  - `all_ETFs_OHLCV_2025-02-11.csv`
  - `nasdaq_stocks_2025-02-10.csv`

**File Format (from TradingView):**
```csv
Symbol,Description,Open 1 day,High 1 day,Low 1 day,Price,Volume 1 day
AAPL,Apple Inc.,185.58,186.86,182.35,184.08,82488700
MSFT,Microsoft Corp.,350.12,352.45,348.12,351.23,28567800
```

**Multiple Files:**
- System automatically processes ALL CSV files with the latest date
- Can have separate files for stocks, ETFs, etc.
- All get merged into one dataset

---

### `src/` - Source Code

**Purpose:** Core Python modules

**Main Modules:**

**Configuration:**
- `config.py` - Directory paths, parameter definitions
- `user_defined_data.py` - Read/parse user_data.csv

**Ticker Management:**
- `get_tickers.py` - Download from NASDAQ, Wikipedia, etc.
- `tradingview_ticker_processor.py` - Process TW universe file
- `unified_ticker_generator.py` - Generate combined ticker lists

**Data Collection:**
- `get_marketData.py` - Yahoo Finance OHLCV downloader
- `get_tradingview_data.py` - TradingView bulk file processor
- `get_financial_data.py` - Financial metrics collector (CANSLIM)

**Entry Point:**
- `../main.py` - Main orchestrator, run this file

---

### `docus/` - Technical Documentation

**Purpose:** Implementation notes, design decisions, technical details

**Key Documents:**
- `CLAUDE.md` - AI assistant guidance for code maintenance
- `IMPLEMENTATION_SUMMARY.md` - TradingView feature implementation
- `TRADINGVIEW_DATA_INTEGRATION_PLAN.md` - Original design plan
- `TW_COLUMN_MAPPING_REFERENCE.md` - Data format mappings

**Audience:** Developers, maintainers, technical users

---

## 📊 Data Flow Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                    USER CONFIGURATION                        │
│              user_input/user_data.csv                        │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│                   MAIN.PY ORCHESTRATOR                       │
│  • Reads configuration                                       │
│  • Tests connectivity                                        │
│  • Coordinates data collection                               │
└────────────┬────────────────────────────┬───────────────────┘
             │                            │
             ▼                            ▼
┌────────────────────────┐  ┌────────────────────────────────┐
│  TICKER GENERATION     │  │   DATA COLLECTION              │
│  • Web sources         │  │   ROUTE 1: Yahoo Finance       │
│  • TradingView         │  │   • API calls                  │
│  • Universe files      │  │   • Slow but complete          │
│                        │  │   → data/market_data/          │
│  → data/tickers/       │  │                                │
└────────────────────────┘  │   ROUTE 2: TradingView         │
                            │   • Bulk file processing       │
                            │   • Fast updates               │
                            │   → data/market_data_tw/       │
                            │                                │
                            │   ROUTE 3: Financial Data      │
                            │   • CANSLIM metrics            │
                            │   • Growth analysis            │
                            │   → data/tickers/              │
                            └────────────────────────────────┘
```

---

## 🔄 File Lifecycle

### Input Files (You Create)

1. **user_data.csv**
   - Created once
   - Modified as needed
   - Never deleted by system

2. **tradingview_universe.csv**
   - Downloaded from TradingView
   - Updated periodically
   - Copied to `data/tickers/` by system

3. **TradingView bulk files**
   - Downloaded from TradingView
   - Placed in `data/tw_files/daily/`
   - Processed then kept for history

### Generated Files (System Creates)

1. **Ticker Lists** (`data/tickers/`)
   - Generated on first run
   - Regenerated when ticker source changes
   - Can be deleted and regenerated

2. **OHLCV Files** (`data/market_data*/`)
   - Created on first run
   - Appended with new data
   - Keep for historical record

3. **Financial Data** (`data/tickers/financial_*.csv`)
   - Created when `fin_data_enrich = TRUE`
   - Updated on each run
   - Overwrites previous version

---

## 💾 Storage Requirements

**Typical Storage Needs:**

| Data Type | Tickers | Timeframe | Size |
|-----------|---------|-----------|------|
| Yahoo Finance Daily | 100 | 5 years | ~50 MB |
| Yahoo Finance Daily | 1,000 | 5 years | ~500 MB |
| Yahoo Finance Daily | 6,000 | 5 years | ~3 GB |
| TradingView Daily | 100 | 5 years | ~40 MB |
| TradingView Daily | 6,000 | 5 years | ~2.5 GB |
| Financial Data | 100 | Latest | ~5 MB |
| Financial Data | 6,000 | Latest | ~300 MB |
| Ticker Lists | All | - | ~10 MB |

**Total Estimate (NASDAQ 100, 5 years):**
- Yahoo Finance: ~50 MB
- TradingView: ~40 MB
- Financial: ~5 MB
- Tickers: ~1 MB
- **Total: ~100 MB**

---

## 🧹 Cleanup & Maintenance

### Safe to Delete

**Temporary/Cache:**
```bash
rm -rf src/__pycache__/
rm -rf __pycache__/
rm -rf .pytest_cache/
```

**Test Data:**
```bash
rm -rf test/
```

**Old Documentation:**
```bash
# Only if you've read it
rm -rf docus/
```

### ⚠️ DO NOT Delete

**User Files:**
- `user_input/` - Your configuration and data

**Historical Data:**
- `data/market_data/` - Yahoo Finance data
- `data/market_data_tw/` - TradingView data

**Unless Regenerating:**
- `data/tickers/` - Can regenerate from sources

---

## 📝 .gitignore Recommendations

```gitignore
# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python

# Data directories (large files)
data/market_data/
data/market_data_tw/
data/tw_files/

# User-specific files (private)
user_input/portofolio_tickers.csv
user_input/tradingview_universe.csv

# Keep template
!user_input/user_data.csv

# Generated files
data/tickers/combined_*
data/tickers/problematic_*
data/tickers/financial_*

# IDE
.vscode/
.idea/
*.swp
*.swo

# OS
.DS_Store
Thumbs.db
```

---

## 🔍 Finding Files

**All Python files:**
```bash
find . -name "*.py" -type f
```

**All CSV files:**
```bash
find . -name "*.csv" -type f
```

**Large files (>100MB):**
```bash
find . -type f -size +100M
```

**Recently modified files:**
```bash
find . -type f -mtime -1  # Last 24 hours
```

---

## 📚 See Also

- [README.md](README.md) - Project overview
- [USER_GUIDE.md](USER_GUIDE.md) - Configuration guide
- [docus/CLAUDE.md](docus/CLAUDE.md) - Technical architecture

---

**Last Updated:** February 2026
