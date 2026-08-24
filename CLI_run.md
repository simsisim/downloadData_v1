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

# Daily only — TradingView universe (all ~4,700) + indexes
python main.py --hist-data --daily --no-weekly --no-monthly --ticker-choice 0-5 --no-fin-data --no-fin-process

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

# TradingView universe (~4,700) + Index/benchmark ETFs combined, daily + weekly + monthly
python main.py --batch-only --batch-daily --batch-weekly --batch-monthly --batch-ticker-choice 0-5

# Gap-fill: auto-compute each interval's start date from the slow-downloaded
# data instead of guessing a period/date range — downloads only what's
# actually missing, per interval, in one run (see note below)
python main.py --batch-only --batch-daily --batch-weekly --batch-monthly --batch-ticker-choice 0-5 --batch-gap-fill

# Gap-fill, quick smoke test against the small test-ticker set
python main.py --batch-only --batch-daily --batch-weekly --batch-monthly --batch-ticker-choice 8 --batch-gap-fill
```

**`--batch-gap-fill`**: for each enabled interval, replaces the configured
period/start date with one computed from `data/market_data/<interval>/`
(archive+current) — specifically the *earliest* "latest date already
covered" across the tickers in scope, +1 day. Using the earliest (not the
typical/majority) date means the whole run is guaranteed to close every
ticker's gap, at the cost of some redundant re-fetching for tickers that
were already more current than the laggard. No more manually checking
"what's the latest date we have" before every batch run. An explicit
`--batch-start` still wins over `--batch-gap-fill` if both are given
(uniform-override behavior takes priority, same as always). If no ticker in
scope has any data yet, falls back to the configured period/start for that
interval.

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

## Daily data repair (fix corrupted rows, e.g. yfinance API glitches)

Standalone mode — runs instead of the normal pipeline and exits immediately after (no CBOE update, ticker generation, or historical download). Only daily (`1d`) data is supported. It force-redownloads and overwrites rows on/after the given date; if yfinance still returns nothing/bad data for that window, the on-disk file is left untouched and the ticker is reported as still broken.

Ticker scope is resolved in this priority order: `--repair-tickers` (explicit list) > `--ticker-choice` (same universe resolution as the normal download) > neither given (auto-detect by scanning every daily CSV for blank/zero OHLC on/after the date — a few hundred ms even across ~4,700 tickers).

```bash
# Auto-detect every corrupted ticker across the whole daily folder, from a date
python main.py --repair-from 2026-07-24

# Restrict to a known universe (NASDAQ 100) instead of the whole folder
python main.py --repair-from 2026-07-24 --ticker-choice 2

# Restrict to specific tickers only
python main.py --repair-from 2026-07-24 --repair-tickers AAPL,MSFT

# Quick smoke test against the small test-ticker set
python main.py --repair-from 2026-07-24 --ticker-choice 8
```

---

## Data storage: archive/current split

Each ticker's OHLCV history under `data/market_data/{daily,weekly,monthly}/` is
split into two tiers, transparently to everything above (no CLI flags involved
— this is automatic on every normal pipeline run):

```
data/market_data/daily/
  archive/{TICKER}.csv   # frozen: all rows through Dec 31 of last calendar year
  current/{TICKER}.csv   # this year's rows only — the only file that changes day to day
  {TICKER}.csv            # unchanged path, auto-regenerated locally = archive+current combined
```

Same under `weekly/` and `monthly/`. The flat `{TICKER}.csv` is kept alive as a
locally materialized cache so anything reading the old single-file-per-ticker
path (including sibling repos `marketHealth`/`metaData_v1`) needs zero changes.

**Colab/Drive sync**: only `archive/` and `current/` need to travel over a
Colab→local sync. `archive/` is untouched between year-boundaries (or a split
rebuild — see below), so a normal day's sync only has to move `current/`'s
small per-ticker deltas instead of the full multi-year history. The flat
`{TICKER}.csv` files are a local-only derived cache — never sync those.

**Stock splits**: detected automatically during the normal daily update (a
non-zero `Stock Splits` value in newly-fetched rows, for a ticker that already
had prior data). Detection forces a full re-fetch of that ticker's history and
a full rebuild of both tiers, so `auto_adjust`-adjusted prices stay consistent
across the split boundary instead of leaving old archive rows unadjusted. Every
detection and outcome is appended to `data/market_data/split_events.csv`
(`timestamp, ticker, interval, split_date, split_ratio, rebuild_status,
rows_before, rows_after`); a run's console output also prints a "SPLIT REBUILD
SUMMARY" if any fired. A failed re-fetch (still-bad API data) writes nothing
and the ticker is retried on the next run — it never gets stuck half-adjusted.

`--repair-from` (above) operates against this same archive/current layout
under the hood — same CLI flags as always, no behavior change from the user's
side.

### One-time migration (existing data → archive/current)

Only needed once per machine (e.g. after pulling this update on a fresh
Colab/Drive copy that still has flat per-ticker files). Safe to interrupt and
rerun — already-migrated tickers are skipped, and the original flat file is
never modified or deleted.

```bash
# Migrate everything (daily + weekly + monthly)
python scripts/migrate_to_archive_current.py

# Preview the split without writing anything
python scripts/migrate_to_archive_current.py --dry-run

# One timeframe only
python scripts/migrate_to_archive_current.py --folder data/market_data/daily

# Specific tickers only
python scripts/migrate_to_archive_current.py --tickers AAPL,MSFT --dry-run

# Re-migrate tickers that already have archive/current tiers
python scripts/migrate_to_archive_current.py --force
```

Each ticker is verified after migrating (row count + last close reloaded and
compared against the original); any mismatch is reported and written to
`data/market_data/migration_report.csv` without touching the original flat
file, so a mismatch never causes data loss — investigate and re-run for that
ticker once resolved.

---

## Running long jobs in the background (nohup + logging)

A first-time backfill against a large ticker group (e.g. `0-5`, ~4,900
tickers once the index/`^YH` group is included) can take hours — the slow
pipeline fetches one ticker at a time with built-in pacing delays. Don't run
these in the foreground of a session you might close.

Every `python main.py ...` invocation automatically writes a full copy of its
console output to `logs/main_<timestamp>.log` — this happens unconditionally,
no manual redirect needed to get a persistent log.

To also survive your terminal closing (SSH drop, closed window, etc.), detach
the process:

```bash
nohup python main.py --hist-data --daily --no-weekly --no-monthly --ticker-choice 0-5 --no-fin-data --no-fin-process > /dev/null 2>&1 &
disown
```

- **`nohup`** — "no hang up": makes the process ignore the `SIGHUP` signal the
  shell sends it when the terminal closes. Without it, closing the terminal
  kills the still-running job.
- **`&`** — runs the command in the background, returning control of the
  terminal immediately instead of blocking until it finishes.
- **`disown`** — removes the just-backgrounded job from the shell's own job
  table, so the shell no longer treats it as a child it owns. Some shells
  still kill background jobs on exit even with `nohup` depending on
  configuration — `disown` closes that gap.
- **`> /dev/null 2>&1`** — discards `nohup`'s own default output file
  (`nohup.out`), since `main.py` already writes its own timestamped log under
  `logs/` regardless of how it's launched.

Check on it anytime:

```bash
tail -f logs/main_*.log      # live-follow the most recent log
ps aux | grep main.py        # confirm it's still running
```

---

## Notes

- `--end-date YYYY-MM-DD` caps the end date for **all** slow-pipeline (YF historical) intervals; defaults to today
- `--batch-only` disables slow YF, TW, and financial pipelines (both `--fin-data` and `--fin-process`) regardless of `user_data.csv`
- `--fin-data-force-refresh` ignores the incremental-refresh cache (`data/fin_data/tickers/<TICKER>.json`) and re-downloads every ticker in the universe
- `--fin-process` with no prior `financial_data_<choice>.csv` for that `--ticker-choice` prints a message and skips — it never triggers a download itself
- `--repair-from` is standalone: when present, it's the only thing that runs — all other flags (`--daily`, `--fin-data`, presets, etc.) are ignored for that invocation
- Per-ticker OHLCV storage is split into `archive/`+`current/` tiers (see "Data storage" above) — no CLI flags needed, this is automatic; only relevant if you're syncing data between machines or inspecting files directly
- `--batch-start` / `--batch-end` / `--batch-period` override date settings for **all** batch intervals
- `--batch-gap-fill` computes a per-interval start date from existing `data/market_data/<interval>/` instead — no manual date lookups (see "Batch pipeline only" above); an explicit `--batch-start` still overrides it
- Per-interval date tuning (daily vs weekly vs monthly independently) is done in `user_input/user_data.csv`
- CLI flags always override `user_data.csv` values
- Priority order: CLI args > preset > `user_data.csv`

**Batch universe priority** (highest to lowest):
1. `--batch-ticker-choice` — use a standard group (0–8); overrides everything
2. `--batch-universe` / `YF_batch_universe` in CSV — use a custom file from `user_input/`
3. slow-pipeline combined file — fallback when neither is set

**Typical setup:** set `YF_batch_universe=symbols_universe.csv` in CSV as your default broad universe.
Then use `--batch-ticker-choice 2` on CLI to narrow to NASDAQ 100 for that run only.
