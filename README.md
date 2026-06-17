# Financial Market Data Collection System

A Python-based system for downloading and managing historical OHLCV market data. Supports three pipelines: slow per-ticker Yahoo Finance, fast batch Yahoo Finance, and TradingView bulk CSV files.

## Key Features

- **Three data pipelines**: slow YF (per-ticker), fast YF batch (`yf.download`), TradingView bulk files
- **Multiple timeframes**: daily, weekly, monthly — independently configurable per pipeline
- **Flexible universe selection**: ticker choice groups (0–8), custom universe files, or combined
- **CANSLIM financial metrics**: earnings, revenue, institutional data
- **CLI-first**: all settings overridable from command line — no Python editing needed
- **Colab-friendly**: same CLI flags work in notebooks via `!python main.py ...`

---

## Project Structure

```
downloadData_v1/
├── main.py                          # Main entry point
├── CLI_run.md                       # Full CLI command reference
├── user_input/                      # Configuration and universe files
│   ├── user_data.csv               # Main config (all settings)
│   ├── tradingview_universe.csv    # TradingView export (~4,700 tickers)
│   ├── symbols_universe.csv        # Combined universe (TV + ETFs + indexes, ~4,850)
│   ├── ETF_universe.csv            # Industry/sector ETFs
│   ├── indexes_tickers.csv         # Benchmark indexes and sector ETFs
│   └── portofolio_tickers.csv      # Personal portfolio tickers
│
├── data/                            # All generated output
│   ├── tickers/                    # Generated ticker lists and metadata
│   ├── market_data/                # Slow YF pipeline — one CSV per ticker
│   │   ├── daily/
│   │   ├── weekly/
│   │   └── monthly/
│   ├── market_data_batch/          # Fast batch pipeline — one CSV per date
│   │   ├── daily/
│   │   ├── weekly/
│   │   └── monthly/
│   ├── market_data_tw/             # TradingView pipeline — one CSV per ticker
│   │   ├── daily/
│   │   ├── weekly/
│   │   └── monthly/
│   └── tw_files/                   # TradingView bulk CSV input files
│       ├── daily/
│       ├── weekly/
│       └── monthly/
│
└── src/
    ├── config.py                   # Directory config and setup
    ├── user_defined_data.py        # CSV config parser / UserConfiguration
    ├── get_marketData.py           # Slow YF pipeline (yf.Ticker per ticker)
    ├── get_batchData.py            # Fast batch pipeline (yf.download)
    ├── get_tradingview_data.py     # TradingView bulk file pipeline
    ├── get_financial_data.py       # CANSLIM financial metrics
    ├── get_tickers.py              # Web ticker retrieval (NASDAQ, SP500, etc.)
    └── unified_ticker_generator.py # Ticker file generation for all groups
```

---

## Ticker Choice Values

| Value | Universe |
|---|---|
| `0` | TradingView Universe (~4,700 tickers) |
| `1` | S&P 500 |
| `2` | NASDAQ 100 |
| `3` | All NASDAQ stocks |
| `4` | Russell 1000 |
| `5` | Index / benchmark ETFs |
| `6` | Portfolio tickers |
| `7` | ETF tickers |
| `8` | Test tickers (quick smoke test) |

Combine with dash: `1-2` (S&P 500 + NASDAQ 100), `1-2-3`, etc.

---

## Quick Start

```bash
pip install -r requirements.txt

# Smoke test
python main.py --preset quick_test

# Slow pipeline — NASDAQ 100, daily only
python main.py --hist-data --daily --no-weekly --no-monthly --ticker-choice 2

# Fast batch — TradingView universe, daily only
python main.py --batch-only --batch-daily --batch-ticker-choice 0

# Fast batch — custom universe file
python main.py --batch-only --batch-daily --batch-universe symbols_universe.csv
```

See `CLI_run.md` for the full command reference.

---

## Configuration — `user_input/user_data.csv`

All settings can be set in the CSV or overridden by CLI flags. CLI always wins.

### Slow YF pipeline

| Parameter | Default | Description |
|---|---|---|
| `YF_hist_data` | TRUE | Enable slow YF pipeline |
| `YF_daily_data` | TRUE | Download daily bars |
| `YF_weekly_data` | TRUE | Download weekly bars |
| `YF_monthly_data` | FALSE | Download monthly bars |
| `ticker_choice` | 2 | Ticker group (0–8 or dash-separated) |

### Fast batch pipeline

| Parameter | Default | Description |
|---|---|---|
| `YF_batch_data` | FALSE | Enable fast batch pipeline |
| `YF_batch_ticker_choice` | _(empty)_ | Ticker group for batch only — leave empty to use `ticker_choice` |
| `YF_batch_universe` | _(empty)_ | Universe file in `user_input/` — overrides `ticker_choice` |
| `YF_batch_use_failed_file` | TRUE | Exclude known-failed tickers |
| `YF_batch_output_path` | `data/market_data_batch` | Output folder |
| `YF_batch_daily` | TRUE | Download daily batch bars |
| `YF_batch_weekly` | FALSE | Download weekly batch bars |
| `YF_batch_monthly` | FALSE | Download monthly batch bars |
| `YF_batch_daily_start_date` | _(empty)_ | Leave empty to use `YF_batch_daily_period` |
| `YF_batch_daily_end_date` | today | |
| `YF_batch_daily_period` | 5d | `1d` / `5d` / `1mo` / `3mo` / `6mo` / `1y` / `2y` / `5y` / `10y` / `ytd` / `max` |
| `YF_batch_weekly_start_date` | _(empty)_ | |
| `YF_batch_weekly_end_date` | today | |
| `YF_batch_weekly_period` | 1y | |
| `YF_batch_monthly_start_date` | _(empty)_ | |
| `YF_batch_monthly_end_date` | today | |
| `YF_batch_monthly_period` | 5y | |

**Priority for batch universe** (highest to lowest):
1. `--batch-ticker-choice <N>` — narrows to a specific group (overrides everything)
2. `--batch-universe <file>` / `YF_batch_universe` in CSV — full custom universe (used when no ticker_choice set)
3. slow-pipeline `combined_file` — fallback when neither is set

Typical workflow: set `YF_batch_universe=symbols_universe.csv` in CSV as the default broad universe, then pass `--batch-ticker-choice 2` on CLI when you want only NASDAQ 100.

**Start date priority:** if `*_start_date` is set, date range is used and `*_period` is ignored.

### Universe files in `user_input/`

| File | Tickers | Use case |
|---|---|---|
| `tradingview_universe.csv` | ~4,700 | Full US stock universe |
| `symbols_universe.csv` | ~4,850 | Combined (TV + ETFs + indexes) |
| `ETF_universe.csv` | ~93 | Industry/sector ETF runs |
| `indexes_tickers.csv` | ~27 | Benchmark indexes only |

---

## Output Format

### Slow pipeline (`data/market_data/{daily,weekly,monthly}/`)
One CSV per ticker — full history appended over time:
```
Date,Open,High,Low,Close,Volume,...,Symbol
2026-06-09,300.28,300.75,287.78,290.55,70024200,...,AAPL
```

### Fast batch pipeline (`data/market_data_batch/{daily,weekly,monthly}/`)
One CSV per bar date — all tickers for that date:
```
Date,Symbol,Open,High,Low,Close,Adj Close,Volume
2026-06-09,AAPL,300.28,300.75,287.78,290.55,290.55,70024200
2026-06-09,BRK-B,486.44,490.79,484.60,487.77,487.77,4908100
```
Files named: `prices_1d_2026-06-09.csv`, `prices_1wk_2026-06-02.csv`, etc.

---

## CLI Flags Reference

| Flag | Effect |
|---|---|
| `--preset <name>` | Named preset: `quick_test` / `nasdaq_daily` / `sp500_full` / `nasdaq_sp500_daily` / `portfolio_only` / `full_canslim` |
| `--ticker-choice <N>` | Ticker group for slow pipeline (0–8 or dash-separated) |
| `--hist-data` / `--no-hist-data` | Enable/disable slow YF pipeline |
| `--daily` / `--no-daily` | Slow pipeline daily bars |
| `--weekly` / `--no-weekly` | Slow pipeline weekly bars |
| `--monthly` / `--no-monthly` | Slow pipeline monthly bars |
| `--batch-only` | Disable slow YF, TW, and financial pipelines — batch only |
| `--batch-data` / `--no-batch-data` | Enable/disable batch pipeline |
| `--batch-ticker-choice <N>` | Ticker group for batch only (independent of `--ticker-choice`) |
| `--batch-universe <file>` | Universe file in `user_input/` for batch |
| `--batch-daily` / `--no-batch-daily` | Batch daily bars |
| `--batch-weekly` / `--no-batch-weekly` | Batch weekly bars |
| `--batch-monthly` / `--no-batch-monthly` | Batch monthly bars |
| `--batch-start <YYYY-MM-DD>` | Override start date for all batch intervals |
| `--batch-end <YYYY-MM-DD\|today>` | Override end date for all batch intervals |
| `--batch-period <value>` | Override period for all batch intervals |
| `--tw-data` / `--no-tw-data` | Enable/disable TradingView pipeline |
| `--fin-data` / `--no-fin-data` | Enable/disable CANSLIM financial data |
| `--write-info` / `--no-write-info` | Enable/disable ticker info file generation |

---

## Failed Tickers

- Slow pipeline: `data/tickers/problematic_tickers_{choice}.csv`
- Batch pipeline: `data/tickers/problematic_tickers_batch.csv`

Batch failed tickers are updated from **daily results only** — weekly/monthly gaps do not blacklist tickers. Set `YF_batch_use_failed_file=FALSE` (or omit `--batch-only` and use `--no-hist-data`) to retry all tickers fresh.

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| Slow pipeline runs when only batch wanted | Add `--batch-only` |
| `user_input/nan` error | Empty CSV value read as NaN — fixed in current version |
| Batch universe file not found | Copy file to `user_input/` first |
| No data for a ticker | Check `data/tickers/problematic_tickers_batch.csv` |
| Rate limited | Script retries automatically with backoff (30/60/120s) |

---

## Disclaimer

For educational and research purposes only. Verify financial data from official sources before making investment decisions.
