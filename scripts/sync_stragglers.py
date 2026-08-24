"""
Pre-batch straggler sync for the non-batch (slow) pipeline - daily, weekly,
and monthly.

The batch pipeline's --batch-gap-fill computes its download window from
"how far behind is the most-lagging ticker" (see main.py / get_batchData).
A handful of tickers stuck behind the rest of the universe in
data/market_data/<interval>/ can therefore drag a whole batch run's date
range back needlessly. This script narrows that gap cheaply, before the
batch run starts: for each interval, find tickers whose last downloaded
date doesn't match the majority ("stragglers"), and - if there are few
enough to finish in a few minutes - top them up with the slow, incremental,
per-ticker yfinance path (the same one main.py's normal pipeline uses),
appending straight into current/ via market_data_io.write_incremental.

Always exits 0 and never blocks the batch run that follows it: if the slow
sync can't make a ticker current (still broken, or too many stragglers to
attempt), that's left to the next manually-triggered full slow-pipeline run.

Maintains ONE unified manifest (src/ticker_manifest.py) shared with the
batch pipeline's own gap-fill path across all three intervals -
data/gapfill/tickers_latestDate_downloads.csv - rather than one file per
interval: last_data_date_1d / _1wk / _1mo track each interval separately,
but last_attempt_date and consecutive_failures are shared per ticker, and
across pipelines. Delisting is a fact about the ticker, not about "daily"
vs "weekly", or "slow" vs "batch" - the same tickers have been observed
failing everywhere, so a single failure streak (incremented at most once
per calendar day, no matter how many intervals or pipelines touch a ticker
that day) is what the delisting sweep keys off of.

Usage:
    python scripts/sync_stragglers.py
    python scripts/sync_stragglers.py --intervals 1d,1wk
    python scripts/sync_stragglers.py --max-stragglers 250
"""
import argparse
import datetime as dt
import os
import sys
from collections import Counter

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.config import PARAMS_DIR
from src import market_data_io
from src import get_marketData
from src import ticker_manifest

DEFAULT_UNIVERSE = os.path.join(PARAMS_DIR["TICKERS_DIR"], "combined_tickers_0-5.csv")

# interval -> (PARAMS_DIR key, backfill start_date used for brand-new tickers,
# mirrors the start dates main.py's normal daily/weekly/monthly params use)
INTERVALS = {
    '1d':  ('MARKET_DATA_DIR_1d',  '2020-01-01'),
    '1wk': ('MARKET_DATA_DIR_1wk', '2000-01-01'),
    '1mo': ('MARKET_DATA_DIR_1mo', '2000-01-01'),
}
DATE_COL = {iv: ticker_manifest.slow_date_col(iv) for iv in INTERVALS}


def load_universe(path):
    df = pd.read_csv(path)
    col = 'ticker' if 'ticker' in df.columns else 'Symbol'
    return df[col].astype(str).str.strip().tolist()


def scan_latest_dates(folder, tickers):
    return {t: market_data_io.get_latest_date(folder, t) for t in tickers}


def majority_date(latest_dates):
    known = [d for d in latest_dates.values() if d is not None]
    if not known:
        return None
    return Counter(known).most_common(1)[0][0]


def run_slow_sync(stragglers, folder, interval, start_date):
    """Top up `stragglers` via the same slow, incremental per-ticker path
    main.py's normal pipeline uses - only fetches what's actually missing
    per ticker, appends into current/ (market_data_io.write_incremental).

    Returns the set of tickers that raised a real fetch error this run (read
    back from the problematic-tickers file get_marketData writes) - as
    opposed to tickers that simply had nothing new to fetch because they're
    already current. Only the former is a real delisting signal; conflating
    "didn't advance" with "actually failed" would flag perfectly healthy
    tickers that just happen to sit off the universe's majority date."""
    # Scratch files for this run live under PARAMS_DIR["GAPFILL_DIR"] -
    # shared with the batch pipeline's equivalent scratch files (see
    # src/get_batchData.py's _run_group) rather than TICKERS_DIR (ticker
    # universe definitions) or a pipeline-specific market_data/ subfolder.
    tmp_dir = PARAMS_DIR["GAPFILL_DIR"]
    os.makedirs(tmp_dir, exist_ok=True)

    tmp_ticker_file = os.path.join(tmp_dir, f"_stragglers_{interval}_sync.csv")
    pd.DataFrame({'ticker': stragglers}).to_csv(tmp_ticker_file, index=False)

    # Tag output/clean-ticker files distinctly per interval so this doesn't
    # collide with whatever combined_tickers_clean_<choice>.csv the main
    # pipeline (or another interval's sync) writes. get_marketData always
    # writes these into TICKERS_DIR itself (shared code path with the real
    # pipeline, not worth threading an output-dir override through) - moved
    # into tmp_dir right after the run instead.
    tag = f"stragglers_{interval}"
    get_marketData.user_choice = tag

    problematic_file = os.path.join(tmp_dir, f"problematic_tickers_{tag}.csv")
    if os.path.isfile(problematic_file):
        os.remove(problematic_file)  # stale from a prior run - don't misattribute its contents to this one

    config = {
        'interval': interval,
        'start_date': start_date,
        'end_date': dt.datetime.now().strftime('%Y-%m-%d'),
        'folder': folder,
        'ticker_file': tmp_ticker_file,
        'write_file_info': False,
    }
    get_marketData.run_market_data_retrieval(config)

    # get_marketData wrote these (if at all) into TICKERS_DIR under the tag
    # name - relocate them into tmp_dir alongside this run's other scratch
    # files.
    for fname in (f"problematic_tickers_{tag}.csv", f"combined_tickers_clean_{tag}.csv"):
        src_path = os.path.join(PARAMS_DIR["TICKERS_DIR"], fname)
        if os.path.isfile(src_path):
            os.replace(src_path, os.path.join(tmp_dir, fname))

    if os.path.isfile(problematic_file):
        return set(pd.read_csv(problematic_file)['ticker'].astype(str))
    return set()


def sync_interval(interval, folder, start_date, universe, max_stragglers):
    """Returns (latest_dates, outcome) where outcome is
    {ticker: 'advanced' | 'confirmed_current' | 'error'} for every ticker
    actually attempted this interval. 'confirmed_current' (fetched cleanly,
    yfinance just had nothing newer than what's on disk) is proof of life,
    not a failure - only 'error' (a real fetch exception) counts toward the
    delisting clock."""
    print(f"\n--- {interval} ({folder}) ---")
    latest = scan_latest_dates(folder, universe)
    known = {t: d for t, d in latest.items() if d is not None}
    missing = [t for t in universe if t not in known]
    maj = majority_date(latest)
    at_majority = sum(1 for d in known.values() if d == maj)
    print(f"Majority last-data-date: {maj}  ({at_majority}/{len(known)} tickers)")
    print(f"No data at all yet (excluded): {len(missing)} tickers")

    stragglers = [t for t, d in known.items() if d != maj]
    print(f"Stragglers (behind majority): {len(stragglers)}")

    outcome = {}
    if not stragglers:
        print("Nothing to sync - already in sync.")
    elif len(stragglers) > max_stragglers:
        print(f"{len(stragglers)} stragglers > --max-stragglers {max_stragglers} - "
              f"skipping slow sync for {interval}, leaving it to the next manual full slow-pipeline run.")
    else:
        print(f"Attempting slow-path catch-up for {len(stragglers)} straggler ticker(s): {stragglers}")
        errored = None
        try:
            errored = run_slow_sync(stragglers, folder, interval, start_date)
        except Exception as e:
            # Whole-run failure (not per-ticker) - can't attribute it to any
            # specific ticker, so don't count it against anyone's streak.
            print(f"Slow sync raised an error (non-fatal, not counted against any ticker's streak): {e}")

        if errored is not None:
            after = scan_latest_dates(folder, stragglers)
            for t in stragglers:
                before_d = known.get(t)
                after_d = after.get(t)
                if after_d is not None and after_d != before_d:
                    outcome[t] = 'advanced'
                elif t in errored:
                    outcome[t] = 'error'
                else:
                    outcome[t] = 'confirmed_current'
                if after_d is not None:
                    latest[t] = after_d

    return latest, outcome


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--universe', type=str, default=DEFAULT_UNIVERSE,
                         help='Ticker universe CSV to check (default: batch-ticker-choice 0-5 universe)')
    parser.add_argument('--max-stragglers', type=int, default=250,
                         help='Per interval: skip the slow sync (leave it to the next manual full '
                              'slow-pipeline run) if more than this many tickers are behind the majority date')
    parser.add_argument('--intervals', type=str, default='1d,1wk,1mo',
                         help='Comma-separated subset of 1d,1wk,1mo to check (default: all three)')
    args = parser.parse_args()

    if not os.path.isfile(args.universe):
        print(f"Universe file not found: {args.universe} - nothing to sync, continuing.")
        return

    universe = load_universe(args.universe)
    print(f"Universe: {len(universe)} tickers ({args.universe})")

    intervals = [iv.strip() for iv in args.intervals.split(',') if iv.strip()]
    manifest = ticker_manifest.load_manifest()
    today = dt.date.today().isoformat()

    # ticker -> best outcome across whichever intervals it was attempted in
    # this run - 'advanced' or 'confirmed_current' (either is proof of life)
    # beats 'error', so one interval succeeding clears the streak even if
    # another interval errored for the same ticker this run.
    OUTCOME_RANK = {'error': 0, 'confirmed_current': 1, 'advanced': 1}
    best_outcome = {}

    for interval in intervals:
        if interval not in INTERVALS:
            print(f"Skipping unknown interval '{interval}' (expected one of {list(INTERVALS)})")
            continue
        dir_key, start_date = INTERVALS[interval]
        folder = PARAMS_DIR[dir_key]
        try:
            latest, outcome = sync_interval(interval, folder, start_date, universe, args.max_stragglers)
        except Exception as e:
            # Don't let one interval's failure (e.g. a bad local CSV during
            # the plain disk scan, not just the network fetch) discard
            # progress already made scanning/syncing the OTHER intervals -
            # save_manifest() only runs once, after this whole loop, so an
            # unguarded exception here used to lose everything, not just
            # this interval.
            print(f"{interval}: sync_interval raised (non-fatal, skipping this interval): {e}")
            continue

        for t, d in latest.items():
            ticker_manifest.set_date(manifest, t, DATE_COL[interval], d)

        for t, o in outcome.items():
            if t not in best_outcome or OUTCOME_RANK[o] > OUTCOME_RANK[best_outcome[t]]:
                best_outcome[t] = o

    for t, o in best_outcome.items():
        ticker_manifest.record_outcome(manifest, t, is_success=(o != 'error'), today=today)

    ticker_manifest.save_manifest(manifest)
    print(f"\nManifest updated: {ticker_manifest.MANIFEST_PATH}")


if __name__ == '__main__':
    main()
