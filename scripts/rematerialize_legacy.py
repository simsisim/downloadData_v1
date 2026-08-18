"""
Rebuild the flat per-ticker legacy cache files (folder/{TICKER}.csv) from the
archive/ + current/ tiers.

market_data_io.write_incremental() / rebuild_archive_current() already
re-materialize this file on every write going forward, but the one-time
archive/current migration (scripts/migrate_to_archive_current.py) left the
flat legacy files in place at that time -- if they were since removed (e.g.
manual cleanup, or a sync that only carried archive/+current/), any reader
outside this repo that expects the flat path (yf-gics, and other sibling
projects) breaks silently until this is rerun.

Safe to interrupt and rerun: purely additive, only (re)writes the flat file
from archive+current, never touches either tier.

Usage:
    python scripts/rematerialize_legacy.py
    python scripts/rematerialize_legacy.py --folder data/market_data/daily
    python scripts/rematerialize_legacy.py --tickers AAPL,MSFT
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.config import PARAMS_DIR
from src import market_data_io


def _tickers_in(folder):
    tickers = set()
    for tier in ("archive", "current"):
        d = os.path.join(folder, tier)
        if os.path.isdir(d):
            tickers.update(e.name[:-4] for e in os.scandir(d) if e.name.endswith(".csv"))
    return sorted(tickers)


def rematerialize_folder(folder, tickers=None):
    tickers = tickers if tickers is not None else _tickers_in(folder)
    written, empty = 0, 0
    for i, ticker in enumerate(tickers):
        if i % 1000 == 0 and i > 0:
            print(f"  {i}/{len(tickers)}...")
        before = market_data_io.load_ohlcv(folder, ticker)
        if before.empty:
            empty += 1
            continue
        market_data_io.materialize_legacy(folder, ticker, combined=before)
        written += 1
    return written, empty


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--folder', type=str, default=None,
                         help='Single market_data interval folder (default: daily+weekly+monthly)')
    parser.add_argument('--tickers', type=str, default=None,
                         help='Comma-separated ticker list (default: every ticker in archive/current)')
    args = parser.parse_args()

    folders = [args.folder] if args.folder else [
        PARAMS_DIR["MARKET_DATA_DIR_1d"],
        PARAMS_DIR["MARKET_DATA_DIR_1wk"],
        PARAMS_DIR["MARKET_DATA_DIR_1mo"],
    ]
    tickers = [t.strip().upper() for t in args.tickers.split(',')] if args.tickers else None

    for folder in folders:
        print(f"\n{'='*60}\nREMATERIALIZING {folder}\n{'='*60}")
        written, empty = rematerialize_folder(folder, tickers=tickers)
        print(f"Written: {written}   Empty/skipped: {empty}")


if __name__ == '__main__':
    main()
