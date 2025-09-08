# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Python-based financial data collection system that downloads historical market data (OHLCV) and comprehensive financial data for CANSLIM stock analysis. The system retrieves stock tickers from various sources and collects both price data and fundamental financial metrics for investment analysis.

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

**src/get_financial_data.py**: Comprehensive financial metrics:
- FinancialDataRetriever class for CANSLIM analysis
- Collects 3+ years of quarterly data and 5+ years of annual data
- Calculates growth acceleration, CANSLIM scoring
- Extracts 100+ financial metrics per ticker

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

### Ticker Selection Options (0-17):
- 0, 17: Portfolio tickers only
- 1: S&P 500 only  
- 2: NASDAQ 100 only
- 3: All NASDAQ stocks
- 4: Russell 1000 (IWM) only
- 5-15: Various combinations of the above
- 16: Index tickers only

### Output Structure

**data/tickers/**: Ticker lists and financial data
- `combined_tickers_{choice}.csv`: Final ticker list used
- `financial_data_{choice}.csv`: Complete financial dataset
- `financial_data_summary_{choice}.csv`: Key metrics summary
- `problematic_tickers_{choice}.csv`: Failed ticker retrievals

**data/market_data/**: Historical price data organized by timeframe
- `daily/`, `weekly/`, `monthly/` subdirectories
- Individual CSV files per ticker with OHLCV data

### Key Dependencies

- **yfinance**: Primary data source for market and financial data
- **pandas**: Data manipulation and CSV handling
- **datetime**: Date range calculations for historical data

### CANSLIM Analysis Features

The financial data retrieval focuses on CANSLIM methodology:
- **C**: Current quarterly earnings growth
- **A**: Annual earnings growth trends  
- **N**: New products, management, or price highs
- **S**: Supply and demand (shares outstanding, float)
- **L**: Leader or laggard (market cap, beta, price performance)
- **I**: Institutional sponsorship
- **M**: Market direction and fundamentals

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

- Market data collection: 2-10 minutes depending on ticker count
- Financial data collection: 5-15 minutes (comprehensive CANSLIM analysis)
- Total pipeline: 10-25 minutes for full execution