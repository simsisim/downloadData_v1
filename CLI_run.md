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

```bash
# Daily only — NASDAQ 100
python main.py --hist-data --daily --no-weekly --no-monthly --ticker-choice 2

# Daily only — S&P 500
python main.py --hist-data --daily --no-weekly --no-monthly --ticker-choice 1

# Daily only — TradingView universe (all ~4,700)
python main.py --hist-data --daily --no-weekly --no-monthly --ticker-choice 0

# Weekly only — NASDAQ 100
python main.py --hist-data --no-daily --weekly --no-monthly --ticker-choice 2

# Monthly only — S&P 500
python main.py --hist-data --no-daily --no-weekly --monthly --ticker-choice 1

# Daily + Weekly — NASDAQ 100
python main.py --hist-data --daily --weekly --no-monthly --ticker-choice 2

# Daily + Weekly + Monthly — S&P 500
python main.py --hist-data --daily --weekly --monthly --ticker-choice 1

# Daily + Weekly + Monthly — S&P 500 + NASDAQ 100 combined
python main.py --hist-data --daily --weekly --monthly --ticker-choice 1-2

# Portfolio tickers — daily only
python main.py --hist-data --daily --no-weekly --no-monthly --ticker-choice 6

# Index ETFs — daily + weekly
python main.py --hist-data --daily --weekly --no-monthly --ticker-choice 5

# Quick smoke test (8 test tickers)
python main.py --preset quick_test

# Daily only — Index ETFs, capped at a specific end date
python main.py --hist-data --daily --no-weekly --no-monthly --ticker-choice 5 --end-date 2026-06-11
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

```bash
# Slow daily (NASDAQ 100) + Batch daily (TradingView universe)
python main.py --hist-data --daily --ticker-choice 2 --batch-data --batch-daily --batch-ticker-choice 0

# Slow daily+weekly (S&P 500) + Batch daily+weekly (same universe)
python main.py --hist-data --daily --weekly --ticker-choice 1 --batch-data --batch-daily --batch-weekly --batch-ticker-choice 1
```

---

## Financial data (CANSLIM)

```bash
# Financial data only — NASDAQ 100
python main.py --fin-data --no-hist-data --ticker-choice 2

# Daily + financial data — S&P 500
python main.py --hist-data --daily --fin-data --ticker-choice 1
```

---

## Notes

- `--end-date YYYY-MM-DD` caps the end date for **all** slow-pipeline (YF historical) intervals; defaults to today
- `--batch-only` disables slow YF, TW, and financial pipelines regardless of `user_data.csv`
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
