"""
Shared manifest I/O for data/gapfill/tickers_latestDate_downloads.csv - the
per-ticker tracking sheet both the slow pipeline (scripts/sync_stragglers.py)
and the batch pipeline (src/get_batchData.py's gap-fill path) consult and
update.

One shared consecutive_failures/first_failure_date clock per ticker across
BOTH pipelines: delisting is a fact about the ticker, not about which
pipeline happened to notice it. A ticker that fails in the slow pipeline
today and fails in batch tomorrow is one continuous streak, not two
separate half-length ones that each need their own 90 days to matter.

Columns:
    ticker
    last_data_date_1d / _1wk / _1mo            slow-pipeline coverage (data/market_data/<interval>/)
    last_data_date_1d_batch / _1wk_batch / _1mo_batch   batch coverage (data/market_data_batch/<interval>/)
    last_attempt_date                          last date ANY pipeline attempted this ticker
    consecutive_failures                       unbroken run of failed attempts (see record_outcome)
    first_failure_date                         when the CURRENT streak began (cleared on any success)
"""
import os
import datetime as dt

import pandas as pd

from src.config import PARAMS_DIR

MANIFEST_PATH = os.path.join(PARAMS_DIR["GAPFILL_DIR"], "tickers_latestDate_downloads.csv")

SLOW_INTERVALS = ('1d', '1wk', '1mo')
DATE_COLUMNS = (
    [f'last_data_date_{iv}' for iv in SLOW_INTERVALS]
    + [f'last_data_date_{iv}_batch' for iv in SLOW_INTERVALS]
)
MANIFEST_COLUMNS = ['ticker'] + DATE_COLUMNS + ['last_attempt_date', 'consecutive_failures', 'first_failure_date']


def slow_date_col(interval):
    return f'last_data_date_{interval}'


def batch_date_col(interval):
    return f'last_data_date_{interval}_batch'


def load_manifest():
    date_cols = DATE_COLUMNS + ['last_attempt_date']
    if os.path.isfile(MANIFEST_PATH):
        df = pd.read_csv(MANIFEST_PATH, dtype={'ticker': str})
        # Migrate the original single-interval, slow-only schema in place.
        if 'last_data_date' in df.columns and slow_date_col('1d') not in df.columns:
            df = df.rename(columns={'last_data_date': slow_date_col('1d')})
        for col in MANIFEST_COLUMNS:
            if col not in df.columns:
                df[col] = pd.NA
        df = df[MANIFEST_COLUMNS]
        for col in date_cols:
            df[col] = df[col].astype(str).replace({'nan': pd.NA, 'NaT': pd.NA, '<NA>': pd.NA})
    else:
        df = pd.DataFrame(columns=MANIFEST_COLUMNS)
    df['consecutive_failures'] = df['consecutive_failures'].astype('Int64')
    df = df.set_index('ticker')
    # Backfill first_failure_date for rows already mid-streak from before this
    # column existed - last_attempt_date under-estimates the true streak
    # length, which is the safe direction (sweep waits longer, never flags early).
    needs_backfill = (df['consecutive_failures'].fillna(0) > 0) & df['first_failure_date'].isna()
    df.loc[needs_backfill, 'first_failure_date'] = df.loc[needs_backfill, 'last_attempt_date']
    return df


def save_manifest(df):
    os.makedirs(os.path.dirname(MANIFEST_PATH), exist_ok=True)
    df.reset_index().to_csv(MANIFEST_PATH, index=False)


def set_date(manifest, ticker, col, date_obj):
    if date_obj is None:
        return
    manifest.loc[ticker, col] = date_obj.isoformat() if hasattr(date_obj, 'isoformat') else str(date_obj)


def record_outcome(manifest, ticker, is_success, today=None):
    """
    Update the shared failure-streak fields for one ticker's attempt result.

    is_success=True for ANY proof of life (advanced, or confirmed already
    current - a clean fetch that simply had nothing newer) from EITHER
    pipeline - always resets the streak, unconditionally.

    On failure, increments at most once per calendar day (guarded by
    last_attempt_date already being today) so the slow pipeline and the
    batch pipeline both erroring on the same ticker the same day don't
    double-penalize it.
    """
    today = today or dt.date.today().isoformat()
    already_recorded_today = False
    if ticker in manifest.index:
        prior_attempt = manifest.loc[ticker, 'last_attempt_date']
        already_recorded_today = pd.notna(prior_attempt) and prior_attempt == today
    manifest.loc[ticker, 'last_attempt_date'] = today
    if is_success:
        manifest.loc[ticker, 'consecutive_failures'] = 0
        manifest.loc[ticker, 'first_failure_date'] = pd.NA
    elif not already_recorded_today:
        prev = manifest.loc[ticker, 'consecutive_failures'] if ticker in manifest.index else None
        prev = int(prev) if pd.notna(prev) else 0
        manifest.loc[ticker, 'consecutive_failures'] = prev + 1
        if prev == 0:
            manifest.loc[ticker, 'first_failure_date'] = today
