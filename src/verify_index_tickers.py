"""
Verify and auto-repair the ^YH industry/sector index tickers used by yf-gics.

^YH<code> tickers (Yahoo's own per-industry/per-sector index quotes, e.g.
^YH31130020 for Semiconductors) are known to return degenerate OHLC on
Yahoo's side even when healthy (Open == High == Low == Close every day,
since this quote type carries no real intraday range) - that's normal, not
corruption, and downstream SCTR/RRG only ever use Close anyway. What *would*
matter is Close itself going blank/zero, which is exactly what
scan_for_corrupted_tickers()/repair_from_date() already detect and fix for
every ticker in the universe (the "degraded yfinance API response" signature)
- no separate mechanism needed for ^YH specifically. This module just scopes
that existing, general-purpose check to the ^YH tickers on every daily run,
so a bad row gets caught and repaired automatically instead of only when
someone remembers to run --repair-from by hand.

No new download path, no new folder: this reads/repairs the same
data/market_data/daily/{current,archive}/<ticker>.csv files every other
ticker already uses.
"""

import glob
import os
from datetime import datetime, timedelta

from src.config import PARAMS_DIR
from src.get_marketData import scan_for_corrupted_tickers, repair_from_date

DAILY_DIR = PARAMS_DIR["MARKET_DATA_DIR_1d"]

# How far back to look for a degraded row each run. Generous relative to the
# daily cadence (catches a missed run or a multi-day weekend/holiday gap)
# without rescanning full history.
SCAN_LOOKBACK_DAYS = 10


def _yh_tickers_on_disk() -> list[str]:
    """All ^YH<code> tickers that currently have a price file, discovered
    directly from the file store - no dependency on any other project's
    reference files (e.g. yf-gics's industries.csv)."""
    pattern = os.path.join(DAILY_DIR, 'current', '^YH*.csv')
    return sorted(os.path.basename(p)[:-4] for p in glob.glob(pattern))


def verify_and_repair(since_date: str | None = None) -> dict:
    """Scan ^YH tickers for a degraded (all-zero/blank OHLC) recent row and
    repair any found via the existing repair_from_date() path.

    Returns the repair summary dict ({'fixed', 'still_broken', 'no_data'}),
    or an empty dict if nothing needed repair.
    """
    since_date = since_date or (datetime.now() - timedelta(days=SCAN_LOOKBACK_DAYS)).strftime('%Y-%m-%d')

    yh_tickers = set(_yh_tickers_on_disk())
    print(f"Verifying {len(yh_tickers)} ^YH index ticker(s) since {since_date}...")

    corrupted = set(scan_for_corrupted_tickers(DAILY_DIR, since_date))
    yh_corrupted = sorted(yh_tickers & corrupted)

    if not yh_corrupted:
        print(f"  OK — no corrupted ^YH tickers found in the last {SCAN_LOOKBACK_DAYS} days")
        return {}

    print(f"  Found {len(yh_corrupted)} corrupted ^YH ticker(s): {yh_corrupted}")
    return repair_from_date(DAILY_DIR, since_date, tickers=yh_corrupted)


if __name__ == '__main__':
    verify_and_repair()
