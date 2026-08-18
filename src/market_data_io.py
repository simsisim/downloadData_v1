"""
Archive/current split storage for per-ticker OHLCV CSVs.

Each ticker's history is stored in two tiers under a timeframe folder
(e.g. data/market_data/daily/):

    archive/{TICKER}.csv   frozen: all rows through Dec 31 of last calendar year
    current/{TICKER}.csv   this calendar year's rows only

The flat legacy path folder/{TICKER}.csv is kept alive as a locally
materialized cache (archive+current concatenated), rewritten after every
write, so existing readers (in this repo and sibling repos) that expect a
single full-history file per ticker keep working unmodified. Only
archive/ and current/ need to travel over a Colab-to-local sync; the
legacy file is regenerated locally from them.
"""
import os
import datetime as dt
import pandas as pd


def archive_path(folder, ticker):
    return os.path.join(folder, "archive", f"{ticker}.csv")


def current_path(folder, ticker):
    return os.path.join(folder, "current", f"{ticker}.csv")


def legacy_path(folder, ticker):
    return os.path.join(folder, f"{ticker}.csv")


def read_ticker_csv(path):
    """Read a per-ticker OHLCV CSV. Empty DataFrame (Date index) if missing."""
    if not os.path.isfile(path):
        return pd.DataFrame()
    # parse_dates=True is unsafe here: the Date column holds mixed EST/EDT
    # offset strings (e.g. "2025-04-07 00:00:00-04:00"), which pandas can
    # fail to unify into a single DatetimeIndex depending on version (see
    # safe_row_years for the per-element parsing this requires instead).
    return pd.read_csv(path, index_col='Date')


def safe_row_years(df):
    """
    Per-row calendar year, robust to the mixed-offset Date strings/Timestamps
    that can show up in this index depending on pandas version.

    Vectorized (pd.to_datetime(index, utc=True)) rather than a per-element
    Python loop: with ~1500 rows/ticker x ~19000 tickers, a per-element loop
    calling pd.to_datetime() one string at a time falls back to pandas' slow
    generic string parser per call and measured ~250us/row (~30+ min across
    the full universe) vs ~5us/row vectorized - a ~50x difference for an
    identical result.
    """
    if df.empty:
        return []
    return pd.to_datetime(df.index, utc=True).year.tolist()


def _dedupe_sorted(df):
    if df.empty:
        return df
    # Dedupe by normalized (UTC) instant, not the raw index value: a row
    # read back from disk (see read_ticker_csv) has a plain Python string
    # index, while a freshly fetched row has a real tz-aware Timestamp - two
    # entries for the identical date compare unequal by raw value even
    # though they're the same moment, so a duplicate silently survived
    # (verified: concatenating a fresh row for an already-saved date left
    # BOTH rows instead of the new one replacing the old). utc=True also
    # normalizes tz-naive/tz-aware timestamps onto a common basis.
    # Vectorized parse-then-argsort, not a per-element sort key (see
    # safe_row_years for why per-element pd.to_datetime() calls are ~50x slower).
    keys = pd.to_datetime(df.index, utc=True)
    order = keys.argsort(kind='stable')
    df = df.iloc[order]
    return df[~pd.Index(keys[order]).duplicated(keep='last')]


def _atomic_write_csv(df, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if df.index.name != 'Date':
        # Force the index header so read_ticker_csv's index_col='Date' never
        # fails on a file written from a DataFrame whose index lost its name
        # (e.g. after certain pandas concat/filter operations).
        df = df.copy()
        df.index.name = 'Date'
    tmp_path = f"{path}.tmp"
    df.to_csv(tmp_path)
    os.replace(tmp_path, path)


def load_ohlcv(folder, ticker):
    """Archive + current, deduped and sorted. Empty DataFrame if neither exists."""
    archive_df = read_ticker_csv(archive_path(folder, ticker))
    current_df = read_ticker_csv(current_path(folder, ticker))
    if archive_df.empty and current_df.empty:
        return pd.DataFrame()
    combined = pd.concat([archive_df, current_df])
    return _dedupe_sorted(combined)


def get_latest_date(folder, ticker):
    """Most recent row date across current/ (checked first) then archive/. None if no data at all."""
    for path in (current_path(folder, ticker), archive_path(folder, ticker)):
        df = read_ticker_csv(path)
        if not df.empty:
            return max(safe_row_years_to_dates(df))
    return None


def safe_row_years_to_dates(df):
    if df.empty:
        return []
    return pd.to_datetime(df.index, utc=True).date.tolist()


def compute_gap_start_date(folder, tickers=None):
    """
    The earliest 'latest date already covered' across tickers, +1 day - the
    date a supplemental download must start from to guarantee no ticker in
    scope is left with a gap (used by --batch-gap-fill).

    Uses the minimum, not the majority/typical value: a shared start date
    applies to a whole batch chunk at once, so erring toward "some redundant
    overlap for already-current tickers" is preferable to "still-stale
    tickers get skipped". Tickers with no data at all yet are excluded from
    the scan (a supplemental refresh isn't the right tool for initial
    full-history backfill - that's the slow pipeline's job). Returns None
    if none of the given tickers have any data yet.
    """
    if tickers is None:
        current_dir = os.path.join(folder, 'current')
        archive_dir = os.path.join(folder, 'archive')
        tickers = set()
        for d in (current_dir, archive_dir):
            if os.path.isdir(d):
                tickers.update(e.name[:-4] for e in os.scandir(d) if e.name.endswith('.csv'))

    latest_dates = [get_latest_date(folder, t) for t in tickers]
    latest_dates = [d for d in latest_dates if d is not None]
    if not latest_dates:
        return None
    return min(latest_dates) + dt.timedelta(days=1)


def materialize_legacy(folder, ticker, combined=None):
    """
    Rewrite the flat folder/{ticker}.csv cache from archive+current.

    Pass `combined` when the caller already has the deduped/sorted
    archive+current union in memory (e.g. rebuild_archive_current, which
    just partitioned it) to skip re-reading both tiers back off disk.
    """
    if combined is None:
        combined = load_ohlcv(folder, ticker)
    if combined.empty:
        return
    _atomic_write_csv(combined, legacy_path(folder, ticker))


def _partition_by_year(df, this_year):
    """Split df into (stays, rolls): stays = this_year or later, rolls = earlier years."""
    if df.empty:
        return df, df
    years = pd.Series(safe_row_years(df), index=df.index)
    stays_mask = years >= this_year
    return df[stays_mask], df[~stays_mask]


def normalize_fetch_dates(df, interval):
    """
    Snap a FRESHLY FETCHED weekly/monthly DataFrame's index down to its
    period's canonical start (Monday 00:00 for '1wk', the 1st for '1mo').

    yfinance dates a CLOSED period consistently this way already (a no-op
    here - shifting by 0 days for an already-Monday/1st date), but dates a
    still-OPEN current period - or a partial period at the very start of a
    query range - by whatever the actual latest/query-start trading day
    happened to be instead. So the same evolving bar gets a different Date
    depending on when, or with what start date, it's fetched, and without
    this, every incremental update potentially files it under a brand new
    stray date instead of updating the one true row for that period (see
    src/get_batchData.py's _normalize_period_date for the equivalent batch
    fix, and the investigation in project memory that found this - real
    examples: data/market_data/monthly/current/AAPL.csv had stray
    2026-05-20 and 2026-07-17 rows alongside the correct month-start rows).

    Only ever call this on freshly fetched data (a real, homogeneous
    tz-aware DatetimeIndex) - never on data read back from disk, which is
    stored as plain strings (see read_ticker_csv) that pandas can fail to
    uniformly parse.
    """
    if interval not in ('1wk', '1mo') or df.empty:
        return df
    idx = pd.DatetimeIndex(df.index)
    shift_days = idx.weekday if interval == '1wk' else (idx.day - 1)
    df = df.copy()
    df.index = (idx - pd.to_timedelta(shift_days, unit='D')).normalize()
    df.index.name = 'Date'
    return df


def write_incremental(folder, ticker, new_rows, interval=None):
    """
    Merge new_rows into current/{ticker}.csv, rolling any prior-year rows
    (from a stale current/ file, e.g. after an idle pipeline) into archive/.
    Returns a small status dict.

    `interval` ('1d'/'1wk'/'1mo'): when '1wk' or '1mo', new_rows is first
    passed through normalize_fetch_dates - see that function. Omit (or pass
    '1d'/None) to skip normalization, e.g. for callers not fetching a
    period-based interval.

    Does NOT touch the legacy flat file (folder/{ticker}.csv) - downstream
    readers (metaVolume, metaData_v1, marketHealth) already check
    archive/+current/ first and only fall back to the flat file if those are
    missing entirely, so auto-regenerating it on every write was pure
    duplicate storage/IO with no live consumer, and worse, a staleness risk:
    a lingering flat file would silently satisfy that fallback with old data
    instead of correctly reporting "no data" if archive/current ever went
    missing for a ticker. Use scripts/rematerialize_legacy.py if a flat
    export is ever genuinely needed (e.g. for an external tool that can't
    read the two-tier layout).
    """
    this_year = dt.date.today().year

    new_rows = normalize_fetch_dates(new_rows, interval)
    existing_current = read_ticker_csv(current_path(folder, ticker))
    candidate = pd.concat([existing_current, new_rows]) if not existing_current.empty else new_rows
    candidate = _dedupe_sorted(candidate)

    stays, rolls = _partition_by_year(candidate, this_year)

    if not rolls.empty:
        existing_archive = read_ticker_csv(archive_path(folder, ticker))
        merged_archive = pd.concat([existing_archive, rolls]) if not existing_archive.empty else rolls
        merged_archive = _dedupe_sorted(merged_archive)
        _atomic_write_csv(merged_archive, archive_path(folder, ticker))

    if not stays.empty:
        _atomic_write_csv(stays, current_path(folder, ticker))

    return {'rolled_rows': len(rolls), 'current_rows': len(stays)}


def rebuild_archive_current(folder, ticker, full_data, interval=None):
    """
    Full overwrite of both tiers from a freshly fetched complete history,
    partitioned by calendar year. Used for split-triggered rebuilds and by
    repair_from_date (which already holds the complete corrected series).

    `interval`: see write_incremental - passed through to normalize_fetch_dates.
    """
    this_year = dt.date.today().year
    full_data = normalize_fetch_dates(full_data, interval)
    full_data = _dedupe_sorted(full_data)
    stays, rolls = _partition_by_year(full_data, this_year)

    _atomic_write_csv(rolls, archive_path(folder, ticker))
    if not stays.empty:
        _atomic_write_csv(stays, current_path(folder, ticker))
    elif os.path.isfile(current_path(folder, ticker)):
        os.remove(current_path(folder, ticker))

    return {'archive_rows': len(rolls), 'current_rows': len(stays)}


SPLIT_AUDIT_COLUMNS = [
    'timestamp', 'ticker', 'interval', 'split_date', 'split_ratio',
    'rebuild_status', 'rows_before', 'rows_after',
]


def append_split_audit(audit_log_path, rows):
    """Append rows (list of dicts matching SPLIT_AUDIT_COLUMNS) to the split audit CSV."""
    if not rows:
        return
    df = pd.DataFrame(rows, columns=SPLIT_AUDIT_COLUMNS)
    write_header = not os.path.isfile(audit_log_path)
    os.makedirs(os.path.dirname(audit_log_path), exist_ok=True)
    df.to_csv(audit_log_path, mode='a', header=write_header, index=False)


def check_and_handle_split(folder, ticker, interval, split_rows, fetch_fn,
                            start_date, end_date, audit_log_path):
    """
    A split was detected in split_rows (rows of newly-fetched data with a
    non-zero 'Stock Splits' value). Force a full re-fetch of the ticker's
    entire history (so auto_adjust=True re-adjusts the whole series
    consistently) and rebuild both tiers from it. Writes nothing if the
    re-fetch comes back empty or with bad OHLC - a partial/bad stitch would
    be a worse outcome than leaving the existing data untouched.
    """
    timestamp = dt.datetime.now().isoformat(timespec='seconds')
    rows_before = len(load_ohlcv(folder, ticker))

    audit_rows = []
    for split_date, row in split_rows.iterrows():
        audit_rows.append({
            'timestamp': timestamp,
            'ticker': ticker,
            'interval': interval,
            'split_date': pd.to_datetime(split_date).date().isoformat(),
            'split_ratio': row['Stock Splits'],
            'rebuild_status': 'detected',
            'rows_before': rows_before,
            'rows_after': '',
        })
    append_split_audit(audit_log_path, audit_rows)

    full_data = fetch_fn(ticker, start_date, end_date, interval=interval)

    ohlc_cols = ['Open', 'High', 'Low', 'Close']
    is_bad = full_data.empty or (
        full_data[ohlc_cols].isna().any(axis=1) | (full_data[ohlc_cols] == 0).all(axis=1)
    ).all()

    if is_bad:
        append_split_audit(audit_log_path, [{
            'timestamp': timestamp, 'ticker': ticker, 'interval': interval,
            'split_date': audit_rows[-1]['split_date'], 'split_ratio': audit_rows[-1]['split_ratio'],
            'rebuild_status': 'rebuild_failed_bad_data', 'rows_before': rows_before, 'rows_after': 0,
        }])
        return {'status': 'rebuild_failed_bad_data', 'ticker': ticker}

    result = rebuild_archive_current(folder, ticker, full_data, interval=interval)
    rows_after = result['archive_rows'] + result['current_rows']
    append_split_audit(audit_log_path, [{
        'timestamp': timestamp, 'ticker': ticker, 'interval': interval,
        'split_date': audit_rows[-1]['split_date'], 'split_ratio': audit_rows[-1]['split_ratio'],
        'rebuild_status': 'rebuilt_ok', 'rows_before': rows_before, 'rows_after': rows_after,
    }])
    return {'status': 'rebuilt_ok', 'ticker': ticker, 'rows_after': rows_after}


def fetch_ohlcv(ticker, start_date, end_date, interval='1d'):
    """
    Retrieve historical OHLCV data plus market-context fields for a single ticker.
    Standalone (no MarketDataRetriever instance needed) so repair_from_date()
    and split rebuilds can call it directly.
    """
    import yfinance as yf

    ticker_obj = yf.Ticker(ticker)
    ohlc_data = ticker_obj.history(start=start_date, end=end_date, interval=interval)

    info = ticker_obj.info
    additional_params = [
        'volume', 'averageDailyVolume10Day', 'fiftyTwoWeekHigh', 'fiftyTwoWeekLow',
        'fiftyDayAverage', 'twoHundredDayAverage', 'marketCap', 'industry', 'sector', 'exchange',
        'trailingPE', 'forwardPE'
    ]
    for param in additional_params:
        if param in info:
            ohlc_data[param] = info[param]
    ohlc_data['Symbol'] = ticker
    return ohlc_data
