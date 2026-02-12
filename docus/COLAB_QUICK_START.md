# Google Colab Quick Start Guide

This guide shows how to use the financial data collection system in Google Colab with the new configuration system.

## 🚀 Quick Setup (Copy-Paste Ready)

### Method 1: Using Dict Override (Recommended for Colab)

```python
# Cell 1: Setup and Install
!pip install --upgrade yfinance>=1.1.0

# Upload your project folder or clone from git
# If using git:
# !git clone <your-repo-url>
# %cd downloadData_v1

# Cell 2: Import
from main import main

# Cell 3: Run with custom config (NO CSV EDITING NEEDED!)
main({
    'ticker_choice': '2',           # NASDAQ 100
    'yf_hist_data': True,
    'yf_daily_data': True,
    'yf_weekly_data': False,
    'yf_monthly_data': False,
    'fin_data_enrich': False,       # Skip financial data for faster testing
    'write_info_file': True
})
```

### Method 2: Using Presets (Fastest)

```python
# Cell 1: Setup and Install
!pip install --upgrade yfinance>=1.1.0

# Cell 2: Import
from main import main

# Cell 3: Run with preset - ONE LINE!
main(preset='nasdaq_daily')

# Other presets:
# main(preset='quick_test')          # Fast test with test tickers
# main(preset='sp500_full')          # S&P 500 with all data
# main(preset='full_canslim')        # Complete CANSLIM analysis
```

### Method 3: Using Command Line in Colab

```python
# Cell 1: Setup
!pip install --upgrade yfinance>=1.1.0

# Cell 2: Run via command line
!python main.py --preset nasdaq_daily

# Or with custom arguments
!python main.py --ticker-choice 2 --daily --no-weekly
```

---

## 📋 Complete Colab Notebook Template

```python
# ==============================================================================
# CELL 1: Environment Setup
# ==============================================================================
# Install/upgrade dependencies
!pip install --upgrade yfinance>=1.1.0
!pip install pandas>=2.0.0 numpy>=1.24.0

# If using git repository
# !git clone https://github.com/your-username/your-repo.git
# %cd your-repo/downloadData_v1


# ==============================================================================
# CELL 2: Verify Installation
# ==============================================================================
import yfinance as yf
print(f"yfinance version: {yf.__version__}")

# Quick test
test_ticker = yf.Ticker('AAPL')
data = test_ticker.history(period='1d')
print(f"✅ Successfully fetched data: {len(data)} row(s)")


# ==============================================================================
# CELL 3: Import Main Function
# ==============================================================================
from main import main


# ==============================================================================
# CELL 4A: OPTION 1 - Quick Test (Small Dataset)
# ==============================================================================
# Use this for initial testing with minimal data
main(preset='quick_test')


# ==============================================================================
# CELL 4B: OPTION 2 - NASDAQ 100 Daily Only (Recommended for Colab)
# ==============================================================================
# Use this for most Colab use cases - fast and efficient
main(preset='nasdaq_daily')


# ==============================================================================
# CELL 4C: OPTION 3 - Custom Configuration
# ==============================================================================
# Full control over what gets downloaded
main({
    # Ticker selection
    'ticker_choice': '2',           # 2=NASDAQ 100, 1=S&P500, 1-2=Both

    # Historical data
    'yf_hist_data': True,
    'yf_daily_data': True,
    'yf_weekly_data': False,
    'yf_monthly_data': False,

    # TradingView data (if you have bulk files)
    'tw_hist_data': False,

    # Financial data enrichment
    'fin_data_enrich': False,       # Set True for CANSLIM analysis

    # Info files
    'write_info_file': True,
    'ticker_info_YF': True          # Use YFinance for ticker info
})


# ==============================================================================
# CELL 4D: OPTION 4 - Full CANSLIM Analysis
# ==============================================================================
# Complete fundamental analysis (takes longer)
main(preset='full_canslim')


# ==============================================================================
# CELL 5: Verify Downloaded Data
# ==============================================================================
import os
import pandas as pd

# Check what was downloaded
data_dir = 'data/market_data/daily/'
if os.path.exists(data_dir):
    files = os.listdir(data_dir)
    print(f"✅ Downloaded {len(files)} ticker files")

    # Read a sample file
    if files:
        sample_file = os.path.join(data_dir, files[0])
        sample_data = pd.read_csv(sample_file)
        print(f"\n📊 Sample data from {files[0]}:")
        print(sample_data.head())
        print(f"\nDate range: {sample_data['Date'].min()} to {sample_data['Date'].max()}")
else:
    print("❌ No data directory found. Check if download completed successfully.")


# ==============================================================================
# CELL 6: Load and Analyze Data
# ==============================================================================
# Example: Load AAPL data
ticker_file = 'data/market_data/daily/AAPL.csv'
if os.path.exists(ticker_file):
    aapl = pd.read_csv(ticker_file, parse_dates=['Date'], index_col='Date')
    print(f"📈 AAPL Data: {len(aapl)} rows")
    print(f"Latest close: ${aapl['Close'].iloc[-1]:.2f}")

    # Plot if you want
    import matplotlib.pyplot as plt
    aapl['Close'].plot(figsize=(12, 6), title='AAPL Close Price')
    plt.ylabel('Price ($)')
    plt.show()
else:
    print("❌ AAPL.csv not found")


# ==============================================================================
# CELL 7: Download Files to Your Computer
# ==============================================================================
# If you want to download the data files
from google.colab import files
import shutil

# Create a zip file with all data
!zip -r market_data.zip data/market_data/
files.download('market_data.zip')
print("✅ Data downloaded to your computer!")
```

---

## 🎯 Common Use Cases

### Use Case 1: Quick Daily Update (Morning Routine)

```python
# Download latest daily data for NASDAQ 100
main(preset='nasdaq_daily')
```

**Time:** 5-10 minutes
**Data:** NASDAQ 100 daily OHLCV

---

### Use Case 2: Weekend Analysis (Full Dataset)

```python
# Download S&P 500 with all intervals
main(preset='sp500_full')
```

**Time:** 20-30 minutes
**Data:** S&P 500 daily/weekly/monthly + financial metrics

---

### Use Case 3: Portfolio Monitoring

```python
# First, upload your portfolio_tickers.csv to user_input/

# Then run:
main(preset='portfolio_only')
```

**Time:** 1-2 minutes
**Data:** Your portfolio tickers with financial data

---

### Use Case 4: Testing New Strategy

```python
# Use test tickers for rapid iteration
main({
    'ticker_choice': '8',           # Test tickers only
    'yf_daily_data': True,
    'yf_weekly_data': True,
    'fin_data_enrich': True
})
```

**Time:** < 1 minute
**Data:** Small dataset for testing

---

### Use Case 5: CANSLIM Stock Screening

```python
# Full CANSLIM analysis
main(preset='full_canslim')

# Then load the screened results
screened = pd.read_csv('data/tickers/canslim_screened_2.csv')
print(f"Found {len(screened)} CANSLIM candidates")
print(screened.head())
```

**Time:** 30-45 minutes
**Output:** Stocks meeting CANSLIM criteria

---

## 💡 Pro Tips for Colab

### 1. Mount Google Drive (Optional)
Save data to Google Drive to persist across sessions:

```python
from google.colab import drive
drive.mount('/content/drive')

# Then modify paths to use Drive
import os
os.chdir('/content/drive/MyDrive/stock_data')
```

### 2. Suppress Verbose Output

```python
import warnings
warnings.filterwarnings('ignore')

import logging
logging.getLogger().setLevel(logging.ERROR)

# Then run main()
main(preset='nasdaq_daily')
```

### 3. Run Multiple Configurations

```python
# Download multiple ticker groups efficiently
configs = [
    {'ticker_choice': '1', 'yf_daily_data': True},  # S&P 500
    {'ticker_choice': '2', 'yf_daily_data': True},  # NASDAQ 100
    {'ticker_choice': '4', 'yf_daily_data': True}   # Russell 1000
]

for config in configs:
    print(f"\n{'='*60}")
    print(f"Processing ticker choice: {config['ticker_choice']}")
    print(f"{'='*60}")
    main(config_override=config)
```

### 4. Check Memory Usage

```python
# Before running large datasets
!free -h
!df -h

# If running out of memory, use smaller ticker groups
# or download one interval at a time
```

---

## 🐛 Troubleshooting

### "No such file or directory: user_data.csv"

```python
# Create minimal user_data.csv if needed
import pandas as pd
import os

os.makedirs('user_input', exist_ok=True)

# Create basic config file
config_data = """# Config
WEB_tickers_down,FALSE,
TW_tickers_down,TRUE,
TW_universe_file,tradingview_universe.csv,
YF_hist_data,TRUE,
YF_daily_data,TRUE,
ticker_choice,2,"""

with open('user_input/user_data.csv', 'w') as f:
    f.write(config_data)

# Then run with overrides
main({'ticker_choice': '2', 'yf_daily_data': True})
```

### "Ticker files not found"

```python
# You need ticker list files in user_input/
# Option 1: Upload your own
from google.colab import files
print("Upload your ticker CSV files:")
uploaded = files.upload()

# Move to user_input/
import shutil
for filename in uploaded.keys():
    shutil.move(filename, f'user_input/{filename}')

# Option 2: Create test file
import pandas as pd
test_tickers = pd.DataFrame({
    'ticker': ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'TSLA']
})
test_tickers.to_csv('user_input/test_tickers.csv', index=False)

# Then use ticker_choice='8' for test tickers
main({'ticker_choice': '8', 'yf_daily_data': True})
```

### "yfinance version issues"

```python
# Force reinstall
!pip uninstall -y yfinance
!pip install yfinance>=1.1.0

# Verify
import yfinance as yf
print(yf.__version__)  # Should be 1.1.0 or higher
```

---

## 📊 Data Output Structure

After running, your data will be in:

```
data/
├── market_data/
│   ├── daily/          # Daily OHLCV data
│   │   ├── AAPL.csv
│   │   ├── MSFT.csv
│   │   └── ...
│   ├── weekly/         # Weekly OHLCV data
│   └── monthly/        # Monthly OHLCV data
└── tickers/
    ├── financial_data_2.csv           # Complete financial metrics
    ├── financial_data_summary_2.csv   # Key metrics summary
    ├── canslim_screened_2.csv         # CANSLIM candidates
    └── combined_tickers_clean_2.csv   # Successfully downloaded tickers
```

---

## 🎓 Learning Resources

- `CONFIGURATION_EXAMPLES.md` - Complete configuration guide
- `README.md` - Project overview
- Run `!python main.py --help` - See all CLI options
- `test_config.py` - Configuration system tests

---

## ⚡ Quick Reference

| Preset | Tickers | Data | Time | Use Case |
|--------|---------|------|------|----------|
| `quick_test` | Test (8) | Daily | <1 min | Testing |
| `nasdaq_daily` | NASDAQ 100 | Daily | 5-10 min | Daily updates |
| `sp500_full` | S&P 500 | All intervals + Fin | 20-30 min | Weekly analysis |
| `nasdaq_sp500_daily` | Both | Daily | 10-15 min | Combined daily |
| `portfolio_only` | Portfolio | Daily/Weekly + Fin | 1-5 min | Portfolio tracking |
| `full_canslim` | NASDAQ 100 | All + Financials | 30-45 min | Stock screening |

---

**Need help?** See `CONFIGURATION_EXAMPLES.md` for more examples!
