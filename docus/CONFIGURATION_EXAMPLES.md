# Configuration Examples

This document shows how to run the financial data collection system using different configuration methods.

## 📋 Table of Contents

1. [CSV Configuration (Original Method)](#csv-configuration)
2. [Command-Line Arguments](#command-line-arguments)
3. [Python Dict Override (Colab-Friendly)](#python-dict-override)
4. [Presets](#presets)
5. [Priority Order](#priority-order)

---

## CSV Configuration (Original Method)

**Method:** Edit `user_input/user_data.csv` and run without arguments.

```bash
# Edit user_data.csv, then run:
python main.py
```

✅ **Backward compatible** - existing workflows unchanged

---

## Command-Line Arguments

### Basic Usage

```bash
# Show help and all options
python main.py --help

# Download NASDAQ 100 with daily data only
python main.py --ticker-choice 2 --daily --no-weekly --no-monthly

# Download S&P 500 with daily and weekly data
python main.py --ticker-choice 1 --daily --weekly --no-monthly

# Download S&P 500 + NASDAQ 100 combined
python main.py --ticker-choice 1-2 --daily --weekly

# Disable historical data download
python main.py --no-hist-data

# Enable financial data enrichment
python main.py --ticker-choice 2 --daily --fin-data
```

### Available Arguments

**Ticker Selection:**
- `--ticker-choice <value>` - Ticker group: `1`=S&P500, `2`=NASDAQ100, `1-2`=Both, etc.

**Historical Data:**
- `--hist-data` / `--no-hist-data` - Enable/disable historical data download
- `--daily` / `--no-daily` - Enable/disable daily (1d) data
- `--weekly` / `--no-weekly` - Enable/disable weekly (1wk) data
- `--monthly` / `--no-monthly` - Enable/disable monthly (1mo) data

**TradingView Data:**
- `--tw-data` / `--no-tw-data` - Enable/disable TradingView data processing

**Financial Data:**
- `--fin-data` / `--no-fin-data` - Enable/disable financial data enrichment

**Other:**
- `--write-info` / `--no-write-info` - Enable/disable info file generation
- `--preset <name>` - Use a preset configuration (see below)

---

## Python Dict Override (Colab-Friendly)

**Method:** Import main() and pass a config dictionary.

### Google Colab Usage

```python
# In your Colab notebook
from main import main

# Minimal override - just ticker and interval
main({
    'ticker_choice': '2',
    'yf_daily_data': True,
    'yf_weekly_data': False,
    'yf_monthly_data': False
})

# Full control
main({
    'ticker_choice': '1-2',        # S&P 500 + NASDAQ 100
    'yf_hist_data': True,
    'yf_daily_data': True,
    'yf_weekly_data': True,
    'yf_monthly_data': False,
    'tw_hist_data': False,
    'fin_data_enrich': True,
    'yf_fin_data': True,
    'write_info_file': True
})

# Quick test
main({
    'ticker_choice': '8',          # Test tickers
    'yf_daily_data': True,
    'fin_data_enrich': False
})
```

### Local Python Script

```python
#!/usr/bin/env python
from main import main

# Download NASDAQ 100 daily data
config = {
    'ticker_choice': '2',
    'yf_daily_data': True,
    'yf_weekly_data': False,
    'yf_monthly_data': False,
    'fin_data_enrich': False
}

main(config_override=config)
```

---

## Presets

**Method:** Use predefined configurations by name.

### Available Presets

#### 1. `quick_test`
- **Ticker Group:** Test tickers (8)
- **Data:** Daily only
- **Financial Data:** No
- **Use Case:** Quick testing/debugging

```bash
# Command line
python main.py --preset quick_test

# Python
main(preset='quick_test')
```

#### 2. `nasdaq_daily`
- **Ticker Group:** NASDAQ 100
- **Data:** Daily only
- **Financial Data:** No
- **Use Case:** Quick daily data collection

```bash
# Command line
python main.py --preset nasdaq_daily

# Python
main(preset='nasdaq_daily')
```

#### 3. `sp500_full`
- **Ticker Group:** S&P 500
- **Data:** Daily, Weekly, Monthly
- **Financial Data:** Yes
- **Use Case:** Complete S&P 500 analysis

```bash
# Command line
python main.py --preset sp500_full

# Python
main(preset='sp500_full')
```

#### 4. `nasdaq_sp500_daily`
- **Ticker Group:** S&P 500 + NASDAQ 100 combined
- **Data:** Daily only
- **Financial Data:** No
- **Use Case:** Combined major indexes, daily updates

```bash
# Command line
python main.py --preset nasdaq_sp500_daily

# Python
main(preset='nasdaq_sp500_daily')
```

#### 5. `portfolio_only`
- **Ticker Group:** Portfolio tickers (6)
- **Data:** Daily, Weekly
- **Financial Data:** Yes
- **Use Case:** Personal portfolio analysis

```bash
# Command line
python main.py --preset portfolio_only

# Python
main(preset='portfolio_only')
```

#### 6. `full_canslim`
- **Ticker Group:** NASDAQ 100
- **Data:** Daily, Weekly, Monthly
- **Financial Data:** Yes (YFinance)
- **Use Case:** Complete CANSLIM fundamental analysis

```bash
# Command line
python main.py --preset full_canslim

# Python
main(preset='full_canslim')
```

### Combining Presets with Overrides

```bash
# Start with preset, override specific settings
python main.py --preset nasdaq_daily --weekly --fin-data

# In Python
main(preset='nasdaq_daily', config_override={'yf_weekly_data': True})
```

---

## Priority Order

Configuration sources are merged with the following priority (highest to lowest):

1. **Command-Line Arguments** (highest priority)
2. **Preset** (specified via `--preset` or `preset=` parameter)
3. **Config Override Dict** (Python dict passed to `main()`)
4. **CSV File** (user_input/user_data.csv - default/base config)

### Example Priority

```python
# CSV says: ticker_choice = "1" (S&P 500)
# Preset says: ticker_choice = "2" (NASDAQ 100)
# Dict override says: ticker_choice = "1-2" (Both)
# CLI says: --ticker-choice 8 (Test)

# Final result: ticker_choice = "8" (CLI wins)
```

---

## Ticker Choice Values

| Value | Description |
|-------|-------------|
| `0` | TradingView Universe |
| `1` | S&P 500 |
| `2` | NASDAQ 100 |
| `3` | All NASDAQ stocks |
| `4` | Russell 1000 (IWM) |
| `5` | Index tickers |
| `6` | Portfolio tickers |
| `7` | ETF tickers |
| `8` | Test tickers |
| `1-2` | S&P 500 + NASDAQ 100 (combined) |
| `1-2-3` | S&P 500 + NASDAQ 100 + All NASDAQ (combined) |

---

## Google Colab Complete Example

```python
# Cell 1: Install/upgrade dependencies
!pip install --upgrade yfinance>=1.1.0

# Cell 2: Upload your code
# (Upload the entire project folder or clone from git)

# Cell 3: Quick configuration and run
from main import main

# Option A: Use preset
main(preset='nasdaq_daily')

# Option B: Custom configuration
main({
    'ticker_choice': '2',           # NASDAQ 100
    'yf_hist_data': True,
    'yf_daily_data': True,
    'yf_weekly_data': False,
    'yf_monthly_data': False,
    'tw_hist_data': False,
    'fin_data_enrich': False,
    'write_info_file': True,
    'ticker_info_TW': False,        # Use YFinance for ticker info
    'ticker_info_YF': True
})

# Option C: Command line in Colab
!python main.py --preset nasdaq_daily

# Option D: Mix preset with overrides
main(preset='nasdaq_daily', config_override={'yf_weekly_data': True})
```

---

## Testing Your Configuration

```python
# Dry run - see what configuration will be used
from src.user_defined_data import read_user_data
from main import merge_configs, CONFIG_PRESETS

# Load base config
base = read_user_data()

# Test preset
test_config = merge_configs(base, preset='nasdaq_daily')
print(f"Ticker Choice: {test_config.ticker_choice}")
print(f"Daily: {test_config.yf_daily_data}")
print(f"Weekly: {test_config.yf_weekly_data}")
print(f"Financial Data: {test_config.fin_data_enrich}")

# Test custom override
test_config2 = merge_configs(base, config_override={'ticker_choice': '8'})
print(f"Ticker Choice: {test_config2.ticker_choice}")
```

---

## Tips & Best Practices

### For Local Development
- Keep common configs in CSV
- Use CLI args for quick changes
- Use presets for standard workflows

### For Google Colab
- Use dict override (cleanest Python API)
- Use presets for standard tasks
- No need to edit/upload CSV files

### For Automation
- Use presets for consistency
- Use CLI args in shell scripts
- Use dict override in Python scripts

### For Testing
- Use `quick_test` preset
- Override ticker_choice to `'8'` (test tickers)
- Disable fin_data_enrich for faster testing

---

## Troubleshooting

**"Unknown config key 'xyz' ignored"**
- You're using a key that doesn't exist in UserConfiguration
- Check spelling and available keys in `src/user_defined_data.py`

**"Unknown preset 'xyz'"**
- Preset name doesn't exist
- Available presets: `quick_test`, `nasdaq_daily`, `sp500_full`, `nasdaq_sp500_daily`, `portfolio_only`, `full_canslim`

**No data being downloaded**
- Check that `yf_hist_data=True` (or use `--hist-data`)
- Check that at least one interval is enabled (daily/weekly/monthly)
- Verify ticker_choice points to valid ticker file

---

## See Also

- `README.md` - Project overview
- `user_input/user_data.csv` - CSV configuration file
- `src/user_defined_data.py` - UserConfiguration dataclass definition
- Run `python main.py --help` for complete CLI documentation
