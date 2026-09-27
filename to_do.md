https://www.cboe.com/markets/us/options/market-statistics/daily/?dt=2026-07-14

- retrive: EQUITY PUT/CALL RATIO

- what if i want to only download 1 ticker etc ...

- update tickers files(contains more indexes)- except for the breadth, do we have all the data needed?

- [ ] **Rebuild weekly history** (one-time, long-running). Weekly code fix landed
      2026-09-03; the on-disk weekly archive is still shifted -7 days. Full
      runbook + verify script: see WEEKLY_MONTHLY_REBUILD.md. Monthly is fine.

-


- [ ] **Backfill missing daily bars 2026-09-22 and 2026-08-11** (found 2026-09-28
      from dashboard-screener: 95% of tickers had empty 50-day indicators).
      Per-ticker files in data/market_data/daily/current/ are missing whole days:
        2026-09-22 → only 372 / 4,164 files have it
        2026-08-11 → only 2,848 / 4,164 files have it
      The normal daily update only appends after the last date, so it never
      fills a hole; `--repair-from` auto-detect only finds *blank* rows, not
      *missing* rows → pass the tickers explicitly.
      Already done + verified (2026-09-28): A, AA, AACI (rows before 08-11
      untouched, header same, 08-11 and 09-22 now present).
      Steps:
        1. Build the list (tickers missing either day, but current as of 09-25):
             cd data/market_data/daily/current
             ls *.csv | sed 's/\.csv$//' | sort > /tmp/all.txt
             grep -l "^2026-09-22" *.csv | sed 's/\.csv$//' | sort > /tmp/has0922.txt
             grep -l "^2026-08-11" *.csv | sed 's/\.csv$//' | sort > /tmp/has0811.txt
             grep -l "^2026-09-25" *.csv | sed 's/\.csv$//' | sort > /tmp/has0925.txt
             sort -u <(comm -23 /tmp/all.txt /tmp/has0922.txt) \
                     <(comm -23 /tmp/all.txt /tmp/has0811.txt) \
               | comm -12 - /tmp/has0925.txt > /tmp/repair.txt   # ~3,776 tickers
        2. Run (long — per-ticker yfinance, one call each):
             cd ../../../..   # back to downloadData_v1/
             python3 main.py --repair-from 2026-08-11 \
               --repair-tickers "$(paste -sd, /tmp/repair.txt)" 2>&1 | tee logs/repair_0811.log
        3. Check the REPAIR SUMMARY (still_broken / no_data), then re-run the
           step-1 greps: both dates should be in ~4,140 files like other days.
      Then: re-run dashboard-screener's run_screeners.py (see its TODO.md).

- [ ] **Detect missing mid-series days** (root cause of the above going unnoticed):
      add a check — e.g. in the daily update or scan_for_corrupted_tickers —
      that flags a trading day present in most files but missing in many,
      and offers the `--repair-from` command for them.
