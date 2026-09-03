# TODO (run later): rebuild weekly history

**Status:** code fix landed (2026-09-03). The historical **weekly** store on disk
is still corrupted and needs a one-time rebuild. **Monthly is fine** — rebuild
only if you want the extra insurance.

Long-running (~full-universe weekly re-download). Run when you have the time
budget; a normal daily/weekly incremental run in the meantime is now safe.

---

## Why

`fetch_ohlcv` was passing a non-Monday `start` to yfinance for `1wk`
(`'2000-01-01'` in `main.py` — a Saturday). yfinance anchors a weekly series to
the weekday of `start`, so every bar straddled two calendar weeks, and
`normalize_fetch_dates` then snapped each onto the **wrong Monday — one week
early**. Verified across AAPL / MSFT / JPM / XOM, all of 2025:
`stored_vol[label X] == true_vol[label X + 7 days]` on every row.

Separately, the current in-progress week/month was being persisted with partial
volume that never got corrected.

## What the code fix already did

- `src/period_calendar.py` (new): `align_fetch_start()` snaps a weekly `start`
  to Monday / monthly to the 1st; `drop_incomplete_periods()` /
  `is_period_complete()` gate out the still-open bar (`as_of` = last closed US
  trading date — no holiday table needed).
- `fetch_ohlcv()` now calls `align_fetch_start()` before every fetch.
- `write_incremental()` / `rebuild_archive_current()` now drop any weekly/monthly
  bar whose period hasn't closed.
- `normalize_fetch_dates()` now WARNS (or raises with `strict=True`) on a
  non-canonical input bar instead of silently mis-snapping.
- `get_batchData` aligns its weekly/monthly `start` and skips open periods too.
- Tests: `test_period_calendar.py`, `test_market_data_periods.py` (43 tests).

Going forward, incremental runs self-correct: each run re-fetches from the last
stored Monday, so a week that was open last run gets replaced by its complete
value this run. **But** the already-corrupted rows on disk (the −7 shift) are
outside any incremental refetch window and will not heal on their own.

---

## The rebuild

### 1. Back up (optional, ~fast)

```bash
cd ~/_invest2024/python/downloadData_v1
mv data/market_data/weekly  data/market_data/weekly_pre_rebuild_2026-09-03
# monthly too, only if you also rebuild it:
# mv data/market_data/monthly data/market_data/monthly_pre_rebuild_2026-09-03
```

(If disk is tight, `rm -rf` instead — the data is re-downloadable.)

### 2. Re-download weekly from scratch

Every ticker becomes a first-ever fetch → full history from the (now
Monday-aligned) start.

Set in `user_input/config.yaml` (or the CSV):

```
YF_hist_data      = TRUE
YF_daily_data     = FALSE
YF_weekly_data    = TRUE
YF_monthly_data   = FALSE      # TRUE only if you also chose to rebuild monthly
```

```bash
python main.py --ticker-choice 0-5 2>&1 | tee data/logs/weekly_rebuild_2026-09-03.log
```

Expect it to take roughly as long as a full weekly download normally does. Safe
to resume — tickers already written are skipped as "latest data already
available".

### 3. Verify (script below, spot-check ~10 tickers)

```bash
python - <<'EOF'
import pandas as pd, yfinance as yf
from pathlib import Path
D = Path("data/market_data")
def load(sub, t):
    df = pd.read_csv(D/f"weekly/{sub}/{t}.csv", usecols=["Date","Volume"])
    df["Date"] = pd.to_datetime(df["Date"].astype(str).str.slice(0,10))
    return df.set_index("Date").sort_index()
bad = 0
for t in ["AAPL","MSFT","NVDA","JPM","XOM","KO","TSLA","AMD","MRNA","PLTR"]:
    wk = pd.concat([load("archive",t), load("current",t)])
    wk = wk[~wk.index.duplicated()].sort_index()
    dd = yf.Ticker(t).history(start="2025-01-06", end="2026-09-04", interval="1d")
    dd.index = pd.to_datetime([x.strftime("%Y-%m-%d") for x in dd.index])
    for lbl, row in wk[(wk.index >= "2025-02-01") & (wk.index <= "2026-08-24")].iterrows():
        if lbl.weekday() != 0:
            print(f"{t} {lbl.date()}: NOT A MONDAY"); bad += 1; continue
        seg = dd[(dd.index >= lbl) & (dd.index < lbl + pd.Timedelta(days=7))]
        if seg.empty: continue
        if abs(row.Volume - seg.Volume.sum()) > max(seg.Volume.sum()*0.01, 1e5):
            print(f"{t} {lbl.date()}: stored {int(row.Volume):,} != daily sum {int(seg.Volume.sum()):,}")
            bad += 1
print("ALL GOOD" if bad == 0 else f"{bad} MISMATCH(ES)")
EOF
```

Also confirm the open week is absent:
```bash
tail -1 data/market_data/weekly/current/AAPL.csv    # should be a closed Monday, not this week
```

### 4. If verify passes, drop the backup

```bash
rm -rf data/market_data/weekly_pre_rebuild_2026-09-03
```

---

## Downstream follow-up (metaVolume)

After the weekly store is rebuilt:

1. Rebuild the weekly HVE/HVD baseline — it was computed from the shifted data:
   ```bash
   cd ~/_invest2024/python/metaVolume
   python main.py --preset preprocess_full          # rebuilds all timeframes
   ```
2. Clear the stale weekly incrementals:
   ```bash
   rm -f results/post/weekly/HVD_incremental.csv \
         results/post/weekly/HVE_incremental.csv \
         results/post/weekly/last_processed.txt
   ```
3. Separate metaVolume task (not this runbook): add a screener-side
   `period_calendar` gate to `VolChecker` so weekly/monthly never process an
   incomplete period even if a bad bar leaks through. Also delete the current
   bad partial-week rows already in `results/post/weekly/` (snapshots +
   incrementals dated `2026-08-31`).
