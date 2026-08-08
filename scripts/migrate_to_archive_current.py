"""
One-time migration: split existing flat per-ticker market_data CSVs into the
archive/ (frozen, through last year-end) + current/ (this year only) tiers
used by src/market_data_io.py.

Safe to interrupt and rerun: already-migrated tickers (archive/ or current/
already present) are skipped unless --force, and the original flat CSV is
never modified or deleted - it stays the read-only source of truth for the
migration and remains in place afterward as the materialized-cache copy.

Usage:
    python scripts/migrate_to_archive_current.py
    python scripts/migrate_to_archive_current.py --folder data/market_data/daily
    python scripts/migrate_to_archive_current.py --tickers AAPL,MSFT --dry-run
    python scripts/migrate_to_archive_current.py --force
"""
import argparse
import datetime as dt
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.config import PARAMS_DIR
from src import market_data_io

NON_TICKER_FILES = {'EPC_ratio.csv', 'split_events.csv', 'migration_report.csv'}


def migrate_folder(folder, tickers=None, dry_run=False, force=False):
    migrated, already_migrated, mismatches, skipped = [], [], [], []

    if tickers is not None:
        entries = [f"{t}.csv" for t in tickers]
    else:
        entries = sorted(
            e.name for e in os.scandir(folder)
            if e.is_file() and e.name.endswith('.csv') and e.name not in NON_TICKER_FILES
        )

    for name in entries:
        ticker = name[:-4]
        flat_path = os.path.join(folder, name)

        if not os.path.isfile(flat_path):
            print(f"⚠️  {ticker}: flat file not found at {flat_path}, skipping")
            continue

        already_present = os.path.isfile(market_data_io.archive_path(folder, ticker)) or \
            os.path.isfile(market_data_io.current_path(folder, ticker))
        if already_present and not force:
            already_migrated.append(ticker)
            continue

        flat_df = market_data_io.read_ticker_csv(flat_path)
        if flat_df.empty:
            skipped.append(ticker)
            continue

        if dry_run:
            this_year = dt.date.today().year
            years = pd.Series(market_data_io.safe_row_years(flat_df), index=flat_df.index)
            rolls, stays = (years < this_year).sum(), (years >= this_year).sum()
            print(f"[dry-run] {ticker}: {rolls} archive row(s), {stays} current row(s)")
            migrated.append(ticker)
            continue

        market_data_io.rebuild_archive_current(folder, ticker, flat_df)

        reloaded = market_data_io.load_ohlcv(folder, ticker)
        flat_sorted = market_data_io._dedupe_sorted(flat_df)
        row_count_ok = len(reloaded) == len(flat_sorted)
        last_close_ok = True
        if row_count_ok and len(reloaded) > 0:
            reloaded_close = float(reloaded['Close'].iloc[-1])
            flat_close = float(flat_sorted['Close'].iloc[-1])
            # A blank/corrupted last row (pre-existing data-quality issue,
            # unrelated to this migration - see --repair-from) reads back as
            # NaN on both sides; abs(nan - nan) is never < tolerance, so
            # compare equal-or-both-NaN rather than flagging a false mismatch.
            both_nan = pd.isna(reloaded_close) and pd.isna(flat_close)
            last_close_ok = both_nan or abs(reloaded_close - flat_close) < 1e-6

        if row_count_ok and last_close_ok:
            migrated.append(ticker)
        else:
            mismatches.append((ticker, len(flat_sorted), len(reloaded)))
            print(f"❌ {ticker}: MISMATCH — flat rows={len(flat_sorted)}, reloaded rows={len(reloaded)}")

    return migrated, already_migrated, mismatches, skipped


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--folder', type=str, default=None,
                         help='Single market_data interval folder to migrate (default: daily+weekly+monthly)')
    parser.add_argument('--tickers', type=str, default=None,
                         help='Comma-separated ticker list to restrict migration to (default: every CSV in folder)')
    parser.add_argument('--dry-run', action='store_true', help='Report the partition without writing anything')
    parser.add_argument('--force', action='store_true', help='Re-migrate tickers that already have archive/current tiers')
    args = parser.parse_args()

    folders = [args.folder] if args.folder else [
        PARAMS_DIR["MARKET_DATA_DIR_1d"],
        PARAMS_DIR["MARKET_DATA_DIR_1wk"],
        PARAMS_DIR["MARKET_DATA_DIR_1mo"],
    ]
    tickers = [t.strip().upper() for t in args.tickers.split(',')] if args.tickers else None

    report_rows = []
    for folder in folders:
        print("\n" + "=" * 60)
        print(f"MIGRATING {folder}")
        print("=" * 60)
        migrated, already_migrated, mismatches, skipped = migrate_folder(
            folder, tickers=tickers, dry_run=args.dry_run, force=args.force)

        print(f"✅ Migrated: {len(migrated)}")
        print(f"⏭️  Already migrated: {len(already_migrated)}")
        print(f"⚠️  Skipped (empty/unreadable): {len(skipped)} — {skipped}")
        if mismatches:
            print(f"❌ Mismatches: {len(mismatches)} — {[m[0] for m in mismatches]}")
        for ticker, flat_rows, reloaded_rows in mismatches:
            report_rows.append({'folder': folder, 'ticker': ticker, 'status': 'MISMATCH',
                                 'rows_flat': flat_rows, 'rows_reloaded': reloaded_rows})

    if report_rows and not args.dry_run:
        import pandas as pd
        report_path = os.path.join(PARAMS_DIR["DATA_DIR"], "market_data", "migration_report.csv")
        pd.DataFrame(report_rows).to_csv(report_path, index=False)
        print(f"\nMismatch report written to {report_path}")


if __name__ == '__main__':
    main()
