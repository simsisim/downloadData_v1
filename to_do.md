https://www.cboe.com/markets/us/options/market-statistics/daily/?dt=2026-07-14

- retrive: EQUITY PUT/CALL RATIO

- what if i want to only download 1 ticker etc ...

- update tickers files(contains more indexes)- except for the breadth, do we have all the data needed?

- [ ] **Rebuild weekly history** (one-time, long-running). Weekly code fix landed
      2026-09-03; the on-disk weekly archive is still shifted -7 days. Full
      runbook + verify script: see WEEKLY_MONTHLY_REBUILD.md. Monthly is fine.

-


- [ ] **Check the first real daily run with the new safeguards** (2026-09-29).
      In the output look for: "DAILY DATA GAP CHECK" (expect "No missing days
      found" or a few filled), "⏸️ Held back at a missing session" (only if Yahoo
      skipped a day again), no "DataLossRefused" / "rebuild_refused_row_loss".

- [ ] **Re-run dashboard-screener's run_screeners.py** (see its TODO.md) and
      confirm the 50-day indicators are filled now that 08-11 / 09-22 are back.

- [ ] **AVB daily not split-adjusted** (split 2.793 on 2026-08-17). Yahoo no
      longer serves its older history, so a rebuild is refused by the shrink
      guard. Decide: leave as is, drop the ticker, or adjust manually.

- [x] **Backfill missing daily bars 2026-09-22 and 2026-08-11** — DONE 2026-09-28.
      3,775 / 3,776 tickers repaired (GRAF: delisted, no data). Now 08-11 in
      4,148 and 09-22 in 4,138 / 4,164 files. Log: logs/repair_0811.log.

- [x] **Detect + prevent missing mid-series days** — DONE 2026-09-28, merged to
      master (6f8ae18).
      Root cause: the 09-24 run asked Yahoo for 09-22..09-23, got only 09-23;
      appending it hid the gap (update only fetches after the last date).
      - hold_back_at_gap(): daily update writes only rows before a recent
        missing session, next run retries it (>7 days old: accepted).
      - "DAILY DATA GAP CHECK" after every daily run (NYSE calendar, 30 days);
        `--repair-from DATE` auto-detect includes missing days. Gaps Yahoo
        can't fill → data/market_data/daily/missing_days_unfillable.json
        (e.g. every ^YH index on 2026-09-17/18).
      - repair_from_date() merges instead of replacing; rebuild_archive_current()
        refuses to drop existing dates (DataLossRefused).
      - Backups of daily/current → data/backups/*.tar.gz before every repair +
        weekly, newest 8 kept.
      DATA LOSS (before the merge fix, unrecoverable): 14 delisted/acquired
      tickers lost rows 2026-08-03..~08-21 (AACB APGE BBCQ CMII CRNX EQR FBRX
      ISSC JABRU LBRDA NCSM NHIC RMAX TBPH).

- [x] **Split fixes** — DONE 2026-09-28.
      - MNST / SCCO / YYAI daily were never split-adjusted (split fell on a
        missing day) → rebuilt; repair now does a full-history rebuild when a
        split is in the repaired range.
      - Same split no longer rebuilt on every run (IESC weekly was rebuilt 5x):
        skipped if split_events.csv already has rebuilt_ok for it.
      - Monthly: APH (split 2026-09-03) rebuilds at the next monthly run.
