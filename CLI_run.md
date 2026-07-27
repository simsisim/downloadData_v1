# CLI Run Reference

All commands are run from `/home/imagda/_invest2024/python/downloadData_v1/`.

Ticker choice values:
- `0` TradingView Universe (~4,700 tickers)
- `1` S&P 500
- `2` NASDAQ 100
- `3` All NASDAQ stocks
- `4` Russell 1000
- `5` Index / benchmark ETFs
- `6` Portfolio tickers
- `7` ETF tickers
- `8` Test tickers (quick smoke test)
- Combine with dash: `1-2` (S&P 500 + NASDAQ 100), `1-2-3`

---

## Slow pipeline only (yf.Ticker per-ticker)

Every command below explicitly disables both financial-data flags (`--no-fin-data --no-fin-process`) so behavior is self-contained regardless of what `fin_data_download`/`fin_data_process` currently are in `user_data.csv` — without this, whichever value is sitting in the CSV would silently apply.

```bash
# Daily only — NASDAQ 100
python main.py --hist-data --daily --no-weekly --no-monthly --ticker-choice 2 --no-fin-data --no-fin-process

# Daily only — S&P 500
python main.py --hist-data --daily --no-weekly --no-monthly --ticker-choice 1 --no-fin-data --no-fin-process

# Daily only — TradingView universe (all ~4,700)
python main.py --hist-data --daily --no-weekly --no-monthly --ticker-choice 0 --no-fin-data --no-fin-process

# Weekly only — NASDAQ 100
python main.py --hist-data --no-daily --weekly --no-monthly --ticker-choice 2 --no-fin-data --no-fin-process

# Monthly only — S&P 500
python main.py --hist-data --no-daily --no-weekly --monthly --ticker-choice 1 --no-fin-data --no-fin-process

# Daily + Weekly — NASDAQ 100
python main.py --hist-data --daily --weekly --no-monthly --ticker-choice 2 --no-fin-data --no-fin-process

# Daily + Weekly + Monthly — S&P 500
python main.py --hist-data --daily --weekly --monthly --ticker-choice 1 --no-fin-data --no-fin-process

# Daily + Weekly + Monthly — S&P 500 + NASDAQ 100 combined
python main.py --hist-data --daily --weekly --monthly --ticker-choice 1-2 --no-fin-data --no-fin-process

# Portfolio tickers — daily only
python main.py --hist-data --daily --no-weekly --no-monthly --ticker-choice 6 --no-fin-data --no-fin-process

# Index ETFs — daily + weekly
python main.py --hist-data --daily --weekly --no-monthly --ticker-choice 5 --no-fin-data --no-fin-process

# Quick smoke test (8 test tickers) — preset already sets fin_data_download/
# fin_data_process explicitly, no extra flags needed
python main.py --preset quick_test

# Daily only — Index ETFs, capped at a specific end date
python main.py --hist-data --daily --no-weekly --no-monthly --ticker-choice 5 --end-date 2026-06-11 --no-fin-data --no-fin-process
```

---

## Slow pipeline — use presets

```bash
# NASDAQ 100, daily only
python main.py --preset nasdaq_daily

# S&P 500, daily + weekly + monthly + financial data
python main.py --preset sp500_full

# S&P 500 + NASDAQ 100, daily only
python main.py --preset nasdaq_sp500_daily

# Portfolio tickers, daily + weekly + financial data
python main.py --preset portfolio_only

# NASDAQ 100, all intervals + CANSLIM financial data
python main.py --preset full_canslim
```

---

## Batch pipeline only (yf.download — fast)

```bash
# Daily only — NASDAQ 100
python main.py --batch-only --batch-daily --no-batch-weekly --no-batch-monthly --batch-ticker-choice 2

# Daily only — TradingView universe (all ~4,700)
python main.py --batch-only --batch-daily --batch-ticker-choice 0

# Daily only — custom universe file in user_input/
python main.py --batch-only --batch-daily --batch-universe symbols_universe.csv

# Weekly only — NASDAQ 100
python main.py --batch-only --no-batch-daily --batch-weekly --no-batch-monthly --batch-ticker-choice 2

# Monthly only — S&P 500
python main.py --batch-only --no-batch-daily --no-batch-weekly --batch-monthly --batch-ticker-choice 1

# Daily + Weekly — NASDAQ 100
python main.py --batch-only --batch-daily --batch-weekly --no-batch-monthly --batch-ticker-choice 2

# Daily + Weekly + Monthly — TradingView universe
python main.py --batch-only --batch-daily --batch-weekly --batch-monthly --batch-ticker-choice 0

# Daily + Weekly + Monthly — custom universe file
python main.py --batch-only --batch-daily --batch-weekly --batch-monthly --batch-universe symbols_universe.csv

# Daily with custom date range
python main.py --batch-only --batch-daily --batch-ticker-choice 2 --batch-start 2020-01-01 --batch-end today

# Daily — single specific day only (set start and end to the same date)
python main.py --batch-only --batch-daily --batch-start 2026-06-13 --batch-end 2026-06-13

# Weekly with custom date range (e.g. last 3 weeks)
python main.py --batch-only --batch-weekly --batch-ticker-choice 2 --batch-start 2026-05-21 --batch-end today

# Daily with period override
python main.py --batch-only --batch-daily --batch-ticker-choice 0 --batch-period 5d

# Weekly with period override
python main.py --batch-only --batch-weekly --batch-ticker-choice 2 --batch-period 1y

# Monthly with period override
python main.py --batch-only --batch-monthly --batch-ticker-choice 1 --batch-period 5y

# Retry all tickers (ignore failed tickers file)
python main.py --batch-only --batch-daily --batch-ticker-choice 0 --no-hist-data

# S&P 500 + NASDAQ 100 combined, daily
python main.py --batch-only --batch-daily --batch-ticker-choice 1-2

# TradingView universe (~4,700) + Index/benchmark ETFs combined, daily
python main.py --batch-only --batch-daily --batch-ticker-choice 0-5
```

---

## Both pipelines together

`--no-fin-data --no-fin-process` again added explicitly, same reasoning as above.

```bash
# Slow daily (NASDAQ 100) + Batch daily (TradingView universe)
python main.py --hist-data --daily --ticker-choice 2 --batch-data --batch-daily --batch-ticker-choice 0 --no-fin-data --no-fin-process

# Slow daily+weekly (S&P 500) + Batch daily+weekly (same universe)
python main.py --hist-data --daily --weekly --ticker-choice 1 --batch-data --batch-daily --batch-weekly --batch-ticker-choice 1 --no-fin-data --no-fin-process
```

---

## Financial data (CANSLIM)

Download and processing are independent flags — either can run alone off previously-saved data, or together in one invocation. `--ticker-choice` selects the universe for **both** stages (which `financial_data_<choice>.csv` gets written to / read from).

```bash
# Download only — NASDAQ 100 (skips re-fetching tickers still fresh within
# fin_data_refresh_days; see user_data.csv)
python main.py --fin-data --no-hist-data --ticker-choice 2

# Download, ignoring freshness — force re-fetch every ticker
python main.py --fin-data --fin-data-force-refresh --no-hist-data --ticker-choice 2

# Daily historical + financial data download — S&P 500
python main.py --hist-data --daily --fin-data --ticker-choice 1

# Processing only (EPS trend charts) — off data already downloaded for
# NASDAQ 100, no yfinance calls at all. Fails gracefully with a message if
# financial_data_2.csv doesn't exist yet.
python main.py --no-fin-data --fin-process --no-hist-data --ticker-choice 2

# Download AND process in one run — S&P 500
python main.py --fin-data --fin-process --no-hist-data --ticker-choice 1
```

Chart scope (`fin_data_chart_top_n`/`fin_data_chart_max_peers`/`fin_data_chart_quarters`) is set in `user_data.csv`, not on the CLI.

---

## Notes

- `--end-date YYYY-MM-DD` caps the end date for **all** slow-pipeline (YF historical) intervals; defaults to today
- `--batch-only` disables slow YF, TW, and financial pipelines (both `--fin-data` and `--fin-process`) regardless of `user_data.csv`
- `--fin-data-force-refresh` ignores the incremental-refresh cache (`data/fin_data/tickers/<TICKER>.json`) and re-downloads every ticker in the universe
- `--fin-process` with no prior `financial_data_<choice>.csv` for that `--ticker-choice` prints a message and skips — it never triggers a download itself
- `--batch-start` / `--batch-end` / `--batch-period` override date settings for **all** batch intervals
- Per-interval date tuning (daily vs weekly vs monthly independently) is done in `user_input/user_data.csv`
- CLI flags always override `user_data.csv` values
- Priority order: CLI args > preset > `user_data.csv`

**Batch universe priority** (highest to lowest):
1. `--batch-ticker-choice` — use a standard group (0–8); overrides everything
2. `--batch-universe` / `YF_batch_universe` in CSV — use a custom file from `user_input/`
3. slow-pipeline combined file — fallback when neither is set

**Typical setup:** set `YF_batch_universe=symbols_universe.csv` in CSV as your default broad universe.
Then use `--batch-ticker-choice 2` on CLI to narrow to NASDAQ 100 for that run only.
