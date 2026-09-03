"""
period_calendar.py -- weekly / monthly period alignment and completeness.

Pure date logic, no I/O, no network. Two jobs:

1. ALIGN THE FETCH START.
   yfinance anchors a '1wk' series to the weekday of the `start` you pass it
   (and a '1mo' series to the day-of-month). Pass a Monday -> Monday-labelled
   weekly bars, one per calendar week, volume == that week's daily sum. Pass
   any other weekday (e.g. the hard-coded '2000-01-01', a Saturday, or a
   `period='ytd'` whose Jan 1 is a Thursday) -> bars anchored to that weekday,
   straddling two calendar weeks, which normalize_fetch_dates() then snaps
   onto the WRONG Monday (usually a week early). align_fetch_start() removes
   the cause: it snaps `start` back to Monday / the 1st before the fetch.

2. GATE OUT THE STILL-OPEN PERIOD.
   The last bar yfinance returns for '1wk'/'1mo' is always the current,
   in-progress week/month -- its volume grows every day until the period
   closes. drop_incomplete_periods() removes any bar whose period has not
   finished as of `as_of` (default: the last closed US trading date), so
   only settled bars are ever persisted.

`as_of` is deliberately the trading calendar's leading edge, not wall-clock
"today": a weekly bar is considered complete only once a strictly later
week has started, so no market-holiday table is needed (worst case: a
just-closed Friday week becomes available the following Monday).
"""
from __future__ import annotations

import datetime as _dt
import logging
from zoneinfo import ZoneInfo

import pandas as pd

logger = logging.getLogger(__name__)

_US_EASTERN = ZoneInfo("America/New_York")
# 4:00pm ET close + a settle buffer before yfinance has the final daily bar.
_US_MARKET_CLOSE = (16, 15)

WEEKLY = "1wk"
MONTHLY = "1mo"
_PERIOD_INTERVALS = (WEEKLY, MONTHLY)


def _as_date(d) -> _dt.date:
    if isinstance(d, _dt.datetime):
        return d.date()
    if isinstance(d, _dt.date):
        return d
    return pd.Timestamp(d).date()


def week_start(d) -> _dt.date:
    """Monday of the calendar week containing `d`."""
    d = _as_date(d)
    return d - _dt.timedelta(days=d.weekday())


def month_start(d) -> _dt.date:
    """First day of the calendar month containing `d`."""
    d = _as_date(d)
    return d.replace(day=1)


def period_start(d, interval: str) -> _dt.date:
    if interval == WEEKLY:
        return week_start(d)
    if interval == MONTHLY:
        return month_start(d)
    return _as_date(d)


def align_fetch_start(start, interval: str):
    """
    Snap a fetch `start` back to its period boundary for '1wk'/'1mo' so
    yfinance returns cleanly period-anchored bars.

    Returns an ISO date string. Passes non-period intervals, and empty /
    None / 'nan' starts (period-based fetches), straight through unchanged.
    """
    if interval not in _PERIOD_INTERVALS:
        return start
    if start is None:
        return start
    s = str(start).strip()
    if s == "" or s.lower() == "nan":
        return start
    aligned = period_start(pd.Timestamp(s).date(), interval)
    return aligned.isoformat()


def last_closed_us_trading_date(now=None) -> _dt.date:
    """
    Most recent calendar date (US/Eastern) whose regular session has
    finished as of `now`: today if the US market has already closed,
    otherwise yesterday. Weekends/holidays are not special-cased -- they
    only make this a touch conservative, which is the safe direction for a
    completeness gate.
    """
    now = (now or _dt.datetime.now(_US_EASTERN)).astimezone(_US_EASTERN)
    close_today = now.replace(hour=_US_MARKET_CLOSE[0], minute=_US_MARKET_CLOSE[1],
                              second=0, microsecond=0)
    return now.date() if now >= close_today else now.date() - _dt.timedelta(days=1)


def is_period_complete(p_start, interval: str, as_of=None) -> bool:
    """
    True if the period starting `p_start` has fully closed as of `as_of`
    (default: last_closed_us_trading_date()).

    Complete iff a strictly later period has already begun -- i.e. `as_of`
    falls in a later week / month. No holiday table required.
    """
    if interval not in _PERIOD_INTERVALS:
        return True
    as_of = _as_date(as_of) if as_of is not None else last_closed_us_trading_date()
    p_start = period_start(p_start, interval)
    return period_start(as_of, interval) > p_start


def latest_complete_period_start(interval: str, as_of=None) -> _dt.date:
    """Period-start date of the most recent fully-closed week / month."""
    as_of = _as_date(as_of) if as_of is not None else last_closed_us_trading_date()
    this = period_start(as_of, interval)
    if interval == WEEKLY:
        return this - _dt.timedelta(days=7)
    if interval == MONTHLY:
        return (this - _dt.timedelta(days=1)).replace(day=1)
    return this


def drop_incomplete_periods(df: pd.DataFrame, interval: str, as_of=None) -> pd.DataFrame:
    """
    Return `df` with every '1wk'/'1mo' row whose period has not yet closed
    removed. No-op for other intervals, empty frames, or a frame with no
    open rows. `df` is expected to be indexed by bar date (any parseable
    form). Logs what it drops.
    """
    if interval not in _PERIOD_INTERVALS or df.empty:
        return df
    as_of = _as_date(as_of) if as_of is not None else last_closed_us_trading_date()
    idx_dates = pd.to_datetime(pd.Index(df.index).astype(str).str.slice(0, 10),
                               errors="coerce")
    keep = [
        (not pd.isna(d)) and is_period_complete(d.date(), interval, as_of)
        for d in idx_dates
    ]
    dropped = (~pd.Series(keep, index=df.index)).sum()
    if dropped:
        open_rows = [str(d)[:10] for d, k in zip(df.index, keep) if not k]
        logger.info("drop_incomplete_periods: dropped %d still-open %s bar(s) "
                    "(as_of=%s): %s", dropped, interval, as_of, open_rows)
    return df[pd.Series(keep, index=df.index).values]
