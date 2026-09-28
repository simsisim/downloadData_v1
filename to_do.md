https://www.cboe.com/markets/us/options/market-statistics/daily/?dt=2026-07-14

- retrive: EQUITY PUT/CALL RATIO

- what if i want to only download 1 ticker etc ...

- update tickers files(contains more indexes)- except for the breadth, do we have all the data needed?

- [ ] **Rebuild weekly history** (one-time, long-running). Weekly code fix landed
      2026-09-03; the on-disk weekly archive is still shifted -7 days. Full
      runbook + verify script: see WEEKLY_MONTHLY_REBUILD.md. Monthly is fine.

-


- [x] **Backfill missing daily bars 2026-09-22 and 2026-08-11** — DONE 2026-09-28.
      3,775 / 3,776 tickers repaired via `--repair-from 2026-08-11 --repair-tickers ...`
      (GRAF: delisted, no data). Now 08-11 in 4,148 and 09-22 in 4,138 / 4,164 files.
      Log: logs/repair_0811.log.
      Still to do: re-run dashboard-screener's run_screeners.py (see its TODO.md).

- [x] **Detect missing mid-series days** — DONE 2026-09-28.
      scan_for_missing_days() (NYSE calendar via pandas_market_calendars) +
      fill_missing_days() run as "DAILY DATA GAP CHECK" after every daily update
      (last 30 days); `--repair-from DATE` auto-detect now includes missing days.
      Gaps yfinance can't fill → data/market_data/daily/missing_days_unfillable.json.
      Also fixed repair_from_date() to merge instead of replacing the whole range.
      Known unfillable: every ^YH index on 2026-09-17/18 (Yahoo has no bar).
      DATA LOSS (before the merge fix): 14 delisted/acquired tickers lost rows
      2026-08-03..~08-21 (AACB APGE BBCQ CMII CRNX EQR FBRX ISSC JABRU LBRDA NCSM
      NHIC RMAX TBPH) — Yahoo only serves their last few days; no local backup
      past 2026-07-31.
      Root cause (found 2026-09-28): the 09-24 run asked Yahoo for 09-22..09-23 and got
      only 09-23; appending it hid the gap. Fixed with hold_back_at_gap(); plus shrink
      guard in rebuild_archive_current() and tar.gz backups in data/backups/.
