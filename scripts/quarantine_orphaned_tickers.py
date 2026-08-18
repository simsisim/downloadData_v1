"""
Quarantine per-ticker OHLCV files whose ticker has fallen out of the
tradingview_universe + indexes (0-5) universe - i.e. still sitting in
data/market_data/<interval>/{current,archive}/ from some past run, but no
longer in data/tickers/combined_tickers_0-5.csv (that file is fully
regenerated from TradingView's live export each run, so a ticker TradingView
has since dropped just silently stops being requested by any pipeline,
slow or batch - nothing deletes its old cache, it just goes stale forever).

Moves (never deletes) matched files to a quarantine tree that mirrors the
interval/tier structure, and appends one row per moved file to
data/tickers/orphaned_tickers_removed.csv for audit/restore.

Only touches files inside <folder>/current/ and <folder>/archive/ - the
interval folder's own top-level files (e.g. market_data/daily/EPC_ratio.csv,
an unrelated CBOE-sourced series, not a per-ticker file) are never scanned,
so nothing there can ever be matched or moved.

Usage:
    python scripts/quarantine_orphaned_tickers.py --folder data/market_data/daily --dry-run
    python scripts/quarantine_orphaned_tickers.py --folder data/market_data/daily
"""
import argparse
import datetime as dt
import os
import shutil
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.config import PARAMS_DIR

DEFAULT_UNIVERSE = os.path.join(PARAMS_DIR["TICKERS_DIR"], "combined_tickers_0-5.csv")
QUARANTINE_ROOT = os.path.join("data", "market_data_orphaned")
MANIFEST_PATH = os.path.join(PARAMS_DIR["TICKERS_DIR"], "orphaned_tickers_removed.csv")


def load_universe(path):
    df = pd.read_csv(path)
    col = 'ticker' if 'ticker' in df.columns else 'Symbol'
    return set(df[col].astype(str).str.strip())


def find_orphans(folder, universe):
    """{tier: [ticker, ...]} for current/ and archive/ only."""
    orphans = {}
    for tier in ("current", "archive"):
        d = os.path.join(folder, tier)
        if not os.path.isdir(d):
            orphans[tier] = []
            continue
        tickers = [e.name[:-4] for e in os.scandir(d) if e.name.endswith(".csv")]
        orphans[tier] = sorted(t for t in tickers if t not in universe)
    return orphans


def quarantine(folder, orphans, interval_name, dry_run):
    today = dt.date.today().isoformat()
    rows = []
    moved = 0
    for tier, tickers in orphans.items():
        for ticker in tickers:
            src = os.path.join(folder, tier, f"{ticker}.csv")
            dst_dir = os.path.join(QUARANTINE_ROOT, interval_name, tier)
            dst = os.path.join(dst_dir, f"{ticker}.csv")
            rows.append({
                "ticker": ticker, "interval": interval_name, "tier": tier,
                "quarantined_date": today, "original_path": src, "quarantine_path": dst,
            })
            if not dry_run:
                os.makedirs(dst_dir, exist_ok=True)
                shutil.move(src, dst)
            moved += 1
    return rows, moved


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--folder', type=str, required=True,
                         help='Interval folder, e.g. data/market_data/daily')
    parser.add_argument('--universe', type=str, default=DEFAULT_UNIVERSE)
    parser.add_argument('--dry-run', action='store_true', help='Report counts only, move nothing')
    args = parser.parse_args()

    universe = load_universe(args.universe)
    interval_name = os.path.basename(os.path.normpath(args.folder))
    print(f"Universe (0-5): {len(universe)} tickers")
    print(f"Scanning: {args.folder} (interval tag: {interval_name})")

    orphans = find_orphans(args.folder, universe)
    for tier, tickers in orphans.items():
        print(f"  {tier}: {len(tickers)} orphaned ticker(s)")

    rows, moved = quarantine(args.folder, orphans, interval_name, args.dry_run)

    if args.dry_run:
        print(f"\nDRY RUN - would move {moved} file(s) to {QUARANTINE_ROOT}/{interval_name}/. Nothing touched.")
        return

    if rows:
        manifest_df = pd.DataFrame(rows)
        os.makedirs(os.path.dirname(MANIFEST_PATH), exist_ok=True)
        header = not os.path.isfile(MANIFEST_PATH)
        manifest_df.to_csv(MANIFEST_PATH, mode='a', header=header, index=False)
        print(f"\nMoved {moved} file(s) to {QUARANTINE_ROOT}/{interval_name}/")
        print(f"Logged to {MANIFEST_PATH}")
    else:
        print("\nNothing to quarantine.")


if __name__ == '__main__':
    main()
