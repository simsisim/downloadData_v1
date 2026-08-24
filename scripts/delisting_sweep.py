"""
Delisting sweep: flags tickers that have been failing the slow-pipeline
straggler sync (scripts/sync_stragglers.py) continuously for a long time.

Reads data/gapfill/tickers_latestDate_downloads.csv (the manifest
sync_stragglers.py maintains) and looks at, per ticker, first_failure_date -
the date its CURRENT unbroken failure streak began (cleared back to
nothing the moment it ever advances again in any interval) - and
consecutive_failures - how many sync attempts in a row have failed.

A ticker only becomes a candidate once its current streak has run for at
least --min-days (default 90, "3 months") calendar days, not attempt-count -
sync_stragglers.py's run cadence isn't guaranteed, so measuring elapsed
wall-clock time from first_failure_date is what actually corresponds to
"3 months," not counting invocations.

Purely a read of the manifest - no network calls, cheap enough to run every
time the job pipeline runs; the 90-day threshold itself is what naturally
rate-limits how often anything new gets flagged.

Writes data/tickers/delisted_tickers.csv as a full recompute each run (not
an append log): a ticker that starts advancing again disappears from it
automatically, since its failure streak reset in the manifest clears
first_failure_date.

Detection only - does NOT exclude these tickers from universe generation.
That's a deliberate follow-up, not done here: nothing can realistically
reach --min-days worth of tracked failures for months yet (first_failure_date
tracking only started today), so wiring an exclusion now would be
untestable against real candidates.

Usage:
    python scripts/delisting_sweep.py
    python scripts/delisting_sweep.py --min-days 0   # demo/testing: flag every current failure
"""
import argparse
import datetime as dt
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.config import PARAMS_DIR
from src.ticker_manifest import MANIFEST_PATH

DELISTED_PATH = os.path.join(PARAMS_DIR["TICKERS_DIR"], "delisted_tickers.csv")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--min-days', type=int, default=90,
                         help='Minimum unbroken failure-streak length (calendar days since '
                              'first_failure_date) to flag as a delisting candidate (default: 90)')
    args = parser.parse_args()

    if not os.path.isfile(MANIFEST_PATH):
        print(f"No manifest found at {MANIFEST_PATH} - nothing to sweep.")
        return

    df = pd.read_csv(MANIFEST_PATH, dtype={'ticker': str})
    today = dt.date.today()

    failing = df[df['consecutive_failures'].fillna(0) > 0].copy()
    failing = failing[failing['first_failure_date'].notna()]
    failing['days_failing'] = failing['first_failure_date'].apply(
        lambda d: (today - dt.date.fromisoformat(d)).days)

    print(f"Manifest: {len(df)} tickers tracked, {len(failing)} currently mid-failure-streak")

    candidates = failing[failing['days_failing'] >= args.min_days].sort_values('days_failing', ascending=False)
    print(f"Delisting candidates (streak >= {args.min_days} days): {len(candidates)}")

    if len(candidates):
        cols = ['ticker', 'first_failure_date', 'days_failing', 'consecutive_failures',
                'last_data_date_1d', 'last_data_date_1wk', 'last_data_date_1mo']
        out = candidates[cols].copy()
        out.insert(1, 'flagged_date', today.isoformat())
        out.to_csv(DELISTED_PATH, index=False)
        print(f"Wrote {len(out)} candidate(s) to {DELISTED_PATH}")
        print(out.to_string(index=False))
    else:
        # No candidates this run - an existing file would otherwise describe
        # stale state (e.g. every prior candidate has since recovered).
        if os.path.isfile(DELISTED_PATH):
            os.remove(DELISTED_PATH)
            print(f"No candidates - removed stale {DELISTED_PATH}")
        else:
            print("No candidates.")

    if failing['days_failing'].notna().any() and len(candidates) < len(failing):
        closest = failing.sort_values('days_failing', ascending=False).iloc[0]
        print(f"\nClosest to threshold (not yet a candidate): {closest['ticker']} "
              f"- {closest['days_failing']} day(s) into its current streak")


if __name__ == '__main__':
    main()
