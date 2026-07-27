# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Python-based financial data collection system that downloads historical market data (OHLCV) and comprehensive financial data for CANSLIM stock analysis. The system retrieves stock tickers from various sources and collects both price data and fundamental financial metrics for investment analysis.

The system supports two data routes:
- **Yahoo Finance route** (`data/market_data/`) - Full historical downloads via yfinance API
- **TradingView route** (`data/market_data_tw/`) - Daily updates from TradingView bulk CSV files

## Common Commands

### Run the main data collection pipeline:
```bash
python main.py
```

### Test yfinance connectivity (included in main.py):
The main script automatically tests yfinance and financial data retrieval functionality before running the full pipeline.

### Dependencies:
```bash
pip install -r requirements.txt
```

## Architecture Overview

### Core Components

**main.py**: Main orchestrator that:
- Tests yfinance connectivity and financial data modules
- Fetches ticker lists (if TickerRetriever available)
- Downloads historical market data (daily, weekly, monthly intervals)
- Retrieves comprehensive financial data for CANSLIM analysis
- Combines ticker files based on user configuration

**src/config.py**: Configuration management:
- Directory structure setup (`data/`, `data/tickers/`, `data/market_data/`)
- User choice mapping (0-17) for different ticker combinations
- File path definitions for data storage

**src/get_marketData.py**: Historical price data collection:
- MarketDataRetriever class for OHLCV data
- Supports daily (1d), weekly (1wk), and monthly (1mo) intervals
- Automatic BRK-B ticker addition
- Error handling for problematic tickers

**src/get_tradingview_data.py**: TradingView bulk file updates:
- TradingViewDataRetriever class for processing TW bulk CSV files
- Smart sampling (5 random tickers) to determine if update needed
- Timezone-aware date handling for mixed EST/EDT files
- Appends new data to existing ticker files
- Date extraction from TW filenames

**src/get_financial_data.py**: Comprehensive financial metrics:
- FinancialDataRetriever class for CANSLIM (CANSI subset - C/A/N/S/I; L and M are explicitly out of scope) analysis
- Collects 3+ years of quarterly data and 5+ years of annual data, plus a deep quarterly EPS history (`qh{i}_` fields via `ticker.get_earnings_dates()`) that goes beyond yfinance's ~5-quarter statement cap
- Calculates real YoY growth/acceleration (`eps_growth_accelerating`), annual quality checks (ROE, cash-flow-vs-EPS), supply trend (buyback/dilution), sponsorship level, and a simple composite `cansi_criteria_met` signal
- Extracts 300+ financial metrics per ticker - see `docus/CANSI_RAW_DATA_REQUIREMENTS.md` for the full field-by-field mapping
- **Incremental refresh**: a per-ticker JSON cache (`data/fin_data/tickers/<TICKER>.json`) is the freshness source of truth, independent of `ticker_choice` - a ticker already fresh under one ticker universe is recognized as fresh under any other overlapping universe, not re-fetched per-choice

**src/visualize_financial_data.py**: O'Neil/IBD-style EPS trend charts (log-scale quarterly EPS vs. same-industry/sector peers), saved to `data/charts/eps_trend/`

**src/process_financial_data.py**: Processing stage (charts today, filters/screening planned) - reads already-downloaded financial data, independent of the download stage

**src/get_tickers.py**: Ticker collection from various sources:
- Downloads from NASDAQ, Wikipedia, S&P 500 lists
- TickerRetriever class (optional - graceful fallback if unavailable)

**src/combined_tickers.py**: Preprocessor that combines ticker files based on user selection

**src/user_defined_data.py**: Reads user preferences from user_data.csv

### Data Flow

1. **Configuration**: User selects data source via user_data.csv (choices 0-17)
2. **Ticker Collection**: Download/update ticker lists from various sources
3. **Ticker Combination**: Merge ticker files based on user choice
4. **Market Data**: Download OHLCV data for multiple timeframes
5. **Financial Data**: Collect comprehensive fundamental metrics for CANSLIM analysis

### User Configuration

**user_data.csv**: Controls data collection behavior:
- Line 19: User choice (0-17) determining which ticker sets to process
- Line 22: Boolean flag for writing detailed info files
- `fin_data_download` (renamed from `fin_data_enrich`): enable/disable the financial-data download stage. `fin_data_refresh_days` / `fin_data_force_refresh` control the incremental-refresh threshold and escape hatch.
- `fin_data_process`: independent flag for the processing stage (charts today) - can run with `fin_data_download=FALSE` entirely off previously-downloaded data, or vice versa. `fin_data_chart_top_n` / `fin_data_chart_max_peers` / `fin_data_chart_quarters` control chart scope.

### Ticker Selection Options (0-17):
- 0, 17: Portfolio tickers only
- 1: S&P 500 only  
- 2: NASDAQ 100 only
- 3: All NASDAQ stocks
- 4: Russell 1000 (IWM) only
- 5-15: Various combinations of the above
- 16: Index tickers only

### Output Structure

**data/tickers/**: Ticker lists
- `combined_tickers_{choice}.csv`: Final ticker list used
- `problematic_tickers_{choice}.csv`: Failed ticker retrievals

**data/fin_data/**: CANSLIM financial data (moved out of `data/tickers/`)
- `financial_data_{choice}.csv`: Complete financial dataset for that ticker_choice
- `financial_data_summary_{choice}.csv`: Key metrics summary
- `tickers/{ticker}.json`: Per-ticker cache - the incremental-refresh source of truth (see above), one file per symbol regardless of which ticker_choice fetched it

**data/charts/eps_trend/**: EPS trend chart PNGs (`{ticker}_eps_trend.png`), from `src/visualize_financial_data.py` / `src/process_financial_data.py`

**data/market_data/**: Historical price data organized by timeframe
- `daily/`, `weekly/`, `monthly/` subdirectories
- Individual CSV files per ticker with OHLCV data

### Key Dependencies

- **yfinance**: Primary data source for market and financial data
- **pandas**: Data manipulation and CSV handling
- **datetime**: Date range calculations for historical data
- **re**: Regular expressions for timezone extraction and date parsing

### CANSLIM Analysis Features

The financial data retrieval focuses on CANSLIM methodology - deliberately scoped to **C/A/N/S/I** ("CANSI"); **L** (leader/laggard) and **M** (market direction) are explicitly out of scope (see `docus/CANSI_RAW_DATA_REQUIREMENTS.md` for why):
- **C**: Current quarterly earnings growth, with real YoY acceleration (`eps_growth_accelerating`) computed from a deep quarterly EPS history, not just the ~5 quarters yfinance's statement endpoint caps out at
- **A**: Annual earnings growth trends, ROE (`roe_meets_threshold`, ≥17% bar), cash-flow-vs-EPS quality check (`cashflow_quality_pass`)
- **N**: New highs proximity (`near_new_high`) and a recent-IPO heuristic (`recent_ipo`)
- **S**: Supply and demand - share-count trend classification (`supply_trend`: shrinking/stable/diluting) and buyback evidence (`buyback_active`)
- **I**: Institutional sponsorship level (`sponsorship_level`: healthy/over_owned/low)
- A simple composite (`cansi_criteria_met` / `cansi_criteria_available` / `cansi_letters_passed`) counts how many of the above pass - not a full weighted score

### Error Handling

- Graceful degradation when TickerRetriever unavailable
- Comprehensive logging of problematic tickers
- Automatic retry mechanisms for data retrieval
- Fallback to existing ticker files when downloads fail

### Test Mode

The system includes extensive testing functionality in main.py that validates:
- yfinance connectivity
- Financial data extraction capabilities
- CANSLIM metric calculations
- Growth acceleration analysis

### Expected Runtime

- Market data collection (yfinance): 2-10 minutes depending on ticker count
- TradingView updates: 1-2 minutes (bulk file parsing and distribution)
- Financial data collection: 5-15 minutes (comprehensive CANSLIM analysis)
- Total pipeline: 10-25 minutes for full execution

### TradingView Update Process

The TradingView updater (`src/get_tradingview_data.py`) handles timezone-aware date updates:

1. **Smart Sampling**: Checks 5 random ticker files to determine if update needed
2. **Date Extraction**: Extracts date from TW filename (e.g., `all_stocks _OHLCV_2025-10-01.csv`)
3. **Timezone Preservation**: Reads last date from existing file to extract timezone
4. **Format Matching**: Applies existing timezone to new TW date for consistency
5. **String-Based Updates**: Avoids `parse_dates` to handle mixed EST/EDT timezones
6. **Append Logic**: Concatenates new row and sorts by date (ISO strings sort correctly)

**Key Feature**: Mixed timezone support
- Files spanning Jan-Sep contain both EST (`-05:00`) and EDT (`-04:00`)
- New dates match the timezone of the most recent entry
- No datetime parsing issues with mixed timezones
- Example: If last date is `2025-09-05 00:00:00-04:00`, new date becomes `2025-10-01 00:00:00-04:00`