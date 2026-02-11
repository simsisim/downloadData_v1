# Financial Market Data Collection System

A Python-based automated system for downloading and managing historical market data (OHLCV) and comprehensive financial metrics for stock analysis. Supports multiple data sources including Yahoo Finance and TradingView with smart update mechanisms.

## 🎯 Key Features

- **Dual Data Sources**: Yahoo Finance API and TradingView bulk CSV files
- **Smart Updates**: Efficient sampling to avoid unnecessary data pulls
- **Flexible Configuration**: Simple CSV-based configuration system
- **Multiple Timeframes**: Daily, weekly, and monthly data collection
- **CANSLIM Analysis**: Comprehensive financial metrics for investment analysis
- **Ticker Management**: Automated ticker list generation from multiple indexes
- **Error Handling**: Robust error tracking and recovery mechanisms

## 📊 Supported Data Sources

### Yahoo Finance (yfinance)
- Historical OHLCV data (Open, High, Low, Close, Volume)
- Multiple timeframes: daily, weekly, monthly
- Full historical data download
- Comprehensive financial metrics

### TradingView
- Bulk CSV file processing
- Fast daily updates (1-2 minutes vs 3 hours for Yahoo Finance)
- Smart sampling for efficient updates
- Multiple files support (stocks + ETFs)

## 🚀 Quick Start

### Prerequisites

- Python 3.8+
- pip package manager

### Installation

1. Clone the repository:
```bash
git clone <your-repo-url>
cd downloadData_v1
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Set up your configuration:
```bash
# Edit the main configuration file
nano user_input/user_data.csv
```

4. Add your input files to `user_input/`:
   - `tradingview_universe.csv` - Your TradingView universe data
   - `portofolio_tickers.csv` - Your portfolio tickers
   - `indexes_tickers.csv` - Index tickers you want to track

5. Run the system:
```bash
python main.py
```

## 📁 Project Structure

```
downloadData_v1/
├── user_input/              # User configuration and input files
│   ├── user_data.csv       # Main configuration file
│   ├── tradingview_universe.csv
│   ├── portofolio_tickers.csv
│   └── indexes_tickers.csv
│
├── data/                    # Generated data (outputs)
│   ├── tickers/            # Generated ticker lists
│   ├── market_data/        # Yahoo Finance data
│   │   ├── daily/
│   │   ├── weekly/
│   │   └── monthly/
│   ├── market_data_tw/     # TradingView data
│   │   ├── daily/
│   │   ├── weekly/
│   │   └── monthly/
│   └── tw_files/           # TradingView bulk CSV files (input)
│       ├── daily/
│       ├── weekly/
│       └── monthly/
│
├── src/                     # Source code
│   ├── config.py           # Configuration management
│   ├── user_defined_data.py # Config file reader
│   ├── get_tickers.py      # Ticker retrieval
│   ├── get_marketData.py   # Yahoo Finance data
│   ├── get_tradingview_data.py # TradingView data
│   ├── get_financial_data.py # Financial metrics
│   └── unified_ticker_generator.py
│
├── main.py                  # Main entry point
├── requirements.txt         # Python dependencies
└── README.md               # This file
```

## ⚙️ Configuration

All configuration is done through `user_input/user_data.csv`. See [USER_GUIDE.md](USER_GUIDE.md) for detailed configuration options.

### Quick Configuration Examples

**Enable Yahoo Finance daily data:**
```csv
YF_hist_data,TRUE,Download historical OHLCV data via YFinance
YF_daily_data,TRUE,Download daily (1d) historical data
```

**Enable TradingView updates:**
```csv
TW_hist_data,TRUE,Update historical OHLCV data from TradingView bulk files
TW_daily_data,TRUE,Process daily TradingView bulk files
```

**Select ticker universe:**
```csv
ticker_choice,2,Ticker combination choice (2 = NASDAQ 100)
```

## 📈 Usage Examples

### Example 1: Download Yahoo Finance Data for NASDAQ 100

1. Edit `user_input/user_data.csv`:
```csv
YF_hist_data,TRUE
YF_daily_data,TRUE
ticker_choice,2
```

2. Run:
```bash
python main.py
```

3. Output: Individual CSV files in `data/market_data/daily/`

### Example 2: Update from TradingView Bulk Files

1. Download TradingView data and place in `data/tw_files/daily/`:
   - `all_stocks_OHLCV_2025-02-11.csv`
   - `all_ETFs_OHLCV_2025-02-11.csv`

2. Edit `user_input/user_data.csv`:
```csv
TW_hist_data,TRUE
TW_daily_data,TRUE
```

3. Run:
```bash
python main.py
```

4. Output: Updated ticker files in `data/market_data_tw/daily/`

### Example 3: Custom Ticker Universe

1. Create your universe file: `user_input/tradingview_universe.csv`
2. Set ticker source:
```csv
TW_tickers_down,TRUE
TW_universe_file,tradingview_universe.csv
```

3. Run the system

## 🔧 Advanced Features

### Smart Sampling
- Checks 5 random tickers to determine if update is needed
- Skips update if all tickers are current
- Saves significant processing time

### Multi-File Processing
- Automatically processes multiple TradingView files for the same date
- Merges stocks and ETFs seamlessly
- Handles different file structures

### Timezone Awareness
- Preserves timezone information in date fields
- Handles EST/EDT transitions automatically
- No data corruption from timezone mismatches

### Error Recovery
- Tracks problematic tickers
- Saves error logs for review
- Continues processing on errors

## 📊 Output Data Format

### Individual Ticker Files
Each ticker gets its own CSV file with historical data:

```csv
Date,Open,High,Low,Close,Volume
2025-01-02 00:00:00-05:00,185.58,186.86,182.35,184.08,82488700
2025-01-03 00:00:00-05:00,182.67,184.32,181.89,182.70,58414500
```

### Generated Ticker Lists
```csv
ticker
AAPL
MSFT
GOOGL
```

## 🔍 Troubleshooting

### "Configuration file not found"
- Ensure `user_input/user_data.csv` exists
- Check file permissions

### "TradingView universe file not found"
- Place `tradingview_universe.csv` in `user_input/` directory
- Verify `TW_universe_file` setting in config

### "No data downloaded"
- Check internet connection
- Verify ticker symbols are valid
- Review `data/tickers/problematic_tickers_*.csv` for errors

### "Update skipped"
- System detected all tickers are current
- This is normal if data is up-to-date
- To force update, manually delete ticker files

## 📚 Documentation

- [USER_GUIDE.md](USER_GUIDE.md) - Detailed configuration guide
- [PROJECT_STRUCTURE.md](PROJECT_STRUCTURE.md) - Complete project tree
- [docus/](docus/) - Technical documentation and implementation notes

## 🤝 Contributing

This is a personal project, but suggestions and improvements are welcome!

## 📝 License

[Add your license here]

## ⚠️ Disclaimer

This tool is for educational and research purposes only. Always verify financial data from official sources before making investment decisions.

## 🙏 Acknowledgments

- Data sources: Yahoo Finance (yfinance library), TradingView
- Built with Python, pandas, and yfinance

## 📧 Contact

[Add your contact information]

---

**Last Updated:** February 2026
**Version:** 1.0.0
