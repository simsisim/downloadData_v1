"""
Unit tests for src/period_calendar.py -- pure date logic, no network, no CSV.

Run: python -m pytest test_period_calendar.py -q
"""
import datetime as dt

import pandas as pd
import pytest

from src import period_calendar as pc


# --------------------------------------------------------------------------
# week_start / month_start
# --------------------------------------------------------------------------
@pytest.mark.parametrize("d, expected", [
    ("2026-09-03", "2026-08-31"),   # Thursday  -> Monday of that week
    ("2026-08-31", "2026-08-31"),   # Monday    -> itself
    ("2026-09-06", "2026-08-31"),   # Sunday    -> Monday of that week
    ("2000-01-01", "1999-12-27"),   # Saturday  -> previous Monday
    ("2026-01-01", "2025-12-29"),   # Thursday New Year -> previous Monday
])
def test_week_start(d, expected):
    assert pc.week_start(d) == dt.date.fromisoformat(expected)


@pytest.mark.parametrize("d, expected", [
    ("2026-09-03", "2026-09-01"),
    ("2026-09-01", "2026-09-01"),
    ("2026-12-31", "2026-12-01"),
    ("2026-01-01", "2026-01-01"),
])
def test_month_start(d, expected):
    assert pc.month_start(d) == dt.date.fromisoformat(expected)


# --------------------------------------------------------------------------
# align_fetch_start -- the core fix
# --------------------------------------------------------------------------
def test_align_snaps_weekly_start_to_monday():
    # the exact hard-coded value in main.py -- a Saturday
    assert pc.align_fetch_start("2000-01-01", "1wk") == "1999-12-27"
    assert dt.date.fromisoformat(pc.align_fetch_start("2000-01-01", "1wk")).weekday() == 0


def test_align_snaps_ytd_thursday_start_to_monday():
    assert pc.align_fetch_start("2026-01-01", "1wk") == "2025-12-29"


def test_align_monthly_start_to_first():
    assert pc.align_fetch_start("2026-06-15", "1mo") == "2026-06-01"
    assert pc.align_fetch_start("2026-06-01", "1mo") == "2026-06-01"


def test_align_passes_daily_through_untouched():
    assert pc.align_fetch_start("2026-06-15", "1d") == "2026-06-15"


@pytest.mark.parametrize("empty", ["", "   ", "nan", "NaN", None])
def test_align_passes_period_based_fetch_through(empty):
    # empty start => period= fetch, already correctly anchored by yfinance
    assert pc.align_fetch_start(empty, "1wk") == empty


def test_align_accepts_date_objects():
    assert pc.align_fetch_start(dt.date(2026, 9, 3), "1wk") == "2026-08-31"


def test_align_is_idempotent():
    once = pc.align_fetch_start("2026-01-01", "1wk")
    assert pc.align_fetch_start(once, "1wk") == once


# --------------------------------------------------------------------------
# is_period_complete / latest_complete_period_start
# --------------------------------------------------------------------------
AS_OF = dt.date(2026, 9, 3)   # a Thursday; current week starts Mon 2026-08-31


@pytest.mark.parametrize("wk, complete", [
    ("2026-08-17", True),
    ("2026-08-24", True),    # last fully-closed week
    ("2026-08-31", False),   # current, in-progress week
    ("2026-09-07", False),   # future
])
def test_weekly_completeness(wk, complete):
    assert pc.is_period_complete(dt.date.fromisoformat(wk), "1wk", AS_OF) is complete


@pytest.mark.parametrize("mo, complete", [
    ("2026-07-01", True),
    ("2026-08-01", True),    # last fully-closed month
    ("2026-09-01", False),   # current month
])
def test_monthly_completeness(mo, complete):
    assert pc.is_period_complete(dt.date.fromisoformat(mo), "1mo", AS_OF) is complete


def test_completeness_on_friday_of_the_week_is_conservative():
    # Fri 2026-09-04: the week 08-31..09-04 has just closed, but a strictly
    # later week has not started yet -> treated as NOT complete until Monday.
    fri = dt.date(2026, 9, 4)
    assert pc.is_period_complete(dt.date(2026, 8, 31), "1wk", fri) is False
    mon = dt.date(2026, 9, 7)
    assert pc.is_period_complete(dt.date(2026, 8, 31), "1wk", mon) is True


def test_latest_complete_period_start():
    assert pc.latest_complete_period_start("1wk", AS_OF) == dt.date(2026, 8, 24)
    assert pc.latest_complete_period_start("1mo", AS_OF) == dt.date(2026, 8, 1)
    # month rollover
    assert pc.latest_complete_period_start("1mo", dt.date(2026, 1, 5)) == dt.date(2025, 12, 1)


def test_non_period_interval_is_always_complete():
    assert pc.is_period_complete(dt.date(2026, 9, 3), "1d", AS_OF) is True


# --------------------------------------------------------------------------
# drop_incomplete_periods
# --------------------------------------------------------------------------
def _wk_frame(dates):
    return pd.DataFrame({"Close": range(len(dates)), "Volume": range(len(dates))},
                        index=pd.Index(dates, name="Date"))


def test_drop_incomplete_removes_only_the_open_week():
    df = _wk_frame(["2026-08-17", "2026-08-24", "2026-08-31"])
    out = pc.drop_incomplete_periods(df, "1wk", AS_OF)
    assert list(out.index) == ["2026-08-17", "2026-08-24"]


def test_drop_incomplete_keeps_all_closed():
    df = _wk_frame(["2026-08-10", "2026-08-17", "2026-08-24"])
    out = pc.drop_incomplete_periods(df, "1wk", AS_OF)
    assert len(out) == 3


def test_drop_incomplete_noop_for_daily_and_empty():
    df = _wk_frame(["2026-08-31"])
    assert len(pc.drop_incomplete_periods(df, "1d", AS_OF)) == 1
    assert pc.drop_incomplete_periods(df.iloc[0:0], "1wk", AS_OF).empty


def test_drop_incomplete_handles_tz_suffixed_index():
    df = _wk_frame(["2026-08-24 00:00:00-04:00", "2026-08-31 00:00:00-04:00"])
    out = pc.drop_incomplete_periods(df, "1wk", AS_OF)
    assert len(out) == 1 and str(out.index[0]).startswith("2026-08-24")


# --------------------------------------------------------------------------
# last_closed_us_trading_date
# --------------------------------------------------------------------------
def test_last_closed_us_trading_date_before_and_after_close():
    from zoneinfo import ZoneInfo
    et = ZoneInfo("America/New_York")
    before = dt.datetime(2026, 9, 3, 10, 0, tzinfo=et)   # 10am ET, market open
    after = dt.datetime(2026, 9, 3, 17, 0, tzinfo=et)    # 5pm ET, closed
    assert pc.last_closed_us_trading_date(before) == dt.date(2026, 9, 2)
    assert pc.last_closed_us_trading_date(after) == dt.date(2026, 9, 3)
