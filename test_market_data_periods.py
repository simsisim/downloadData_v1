"""
Unit tests for the weekly/monthly period handling in src/market_data_io.py --
synthetic DataFrames, no network, no real CSV store (uses tmp_path).

Run: python -m pytest test_market_data_periods.py -q
"""
import datetime as dt

import pandas as pd
import pytest

from src import market_data_io as mio
from src import period_calendar as pc


def _fresh_weekly(dates, base_vol=100):
    """A freshly-fetched-looking weekly frame: tz-aware DatetimeIndex."""
    idx = pd.DatetimeIndex([pd.Timestamp(d, tz="America/New_York") for d in dates], name="Date")
    n = len(dates)
    return pd.DataFrame({
        "Open": [10.0] * n, "High": [11.0] * n, "Low": [9.0] * n,
        "Close": [10.5] * n, "Volume": [base_vol + i for i in range(n)],
        "Dividends": [0.0] * n, "Stock Splits": [0.0] * n,
    }, index=idx)


# --------------------------------------------------------------------------
# normalize_fetch_dates -- no-op on aligned data, warns/raises on misaligned
# --------------------------------------------------------------------------
def test_normalize_is_noop_on_monday_aligned_weekly():
    df = _fresh_weekly(["2026-08-17", "2026-08-24", "2026-08-31"])
    out = mio.normalize_fetch_dates(df.copy(), "1wk")
    assert [str(d.date()) for d in out.index] == ["2026-08-17", "2026-08-24", "2026-08-31"]
    assert list(out["Volume"]) == list(df["Volume"])


def test_normalize_is_noop_on_first_of_month_monthly():
    df = _fresh_weekly(["2026-07-01", "2026-08-01", "2026-09-01"])
    out = mio.normalize_fetch_dates(df.copy(), "1mo")
    assert [str(d.date()) for d in out.index] == ["2026-07-01", "2026-08-01", "2026-09-01"]


def test_normalize_warns_on_non_monday_weekly(caplog):
    # Thursday-anchored bars -- the signature of a non-aligned fetch start
    df = _fresh_weekly(["2026-01-01", "2026-01-08", "2026-01-15"])
    with caplog.at_level("WARNING"):
        mio.normalize_fetch_dates(df.copy(), "1wk")
    assert any("not on the canonical period start" in r.message for r in caplog.records)


def test_normalize_strict_raises_on_non_monday_weekly():
    df = _fresh_weekly(["2026-01-01", "2026-01-08"])
    with pytest.raises(ValueError, match="canonical period start"):
        mio.normalize_fetch_dates(df.copy(), "1wk", strict=True)


def test_normalize_passes_daily_through():
    df = _fresh_weekly(["2026-09-01", "2026-09-02"])
    out = mio.normalize_fetch_dates(df.copy(), "1d")
    assert [str(d.date()) for d in out.index] == ["2026-09-01", "2026-09-02"]


# --------------------------------------------------------------------------
# write_incremental / rebuild_archive_current drop the still-open period
# --------------------------------------------------------------------------
@pytest.fixture
def as_of(monkeypatch):
    """Pin 'now' so completeness is deterministic: current week starts 2026-08-31."""
    fixed = dt.date(2026, 9, 3)
    monkeypatch.setattr(pc, "last_closed_us_trading_date", lambda now=None: fixed)
    return fixed


def test_rebuild_drops_open_week(tmp_path, as_of):
    folder = str(tmp_path / "weekly")
    df = _fresh_weekly(["2026-08-17", "2026-08-24", "2026-08-31"])
    mio.rebuild_archive_current(folder, "TEST", df, interval="1wk")
    back = mio.load_ohlcv(folder, "TEST")
    got = sorted(str(d)[:10] for d in back.index)
    assert got == ["2026-08-17", "2026-08-24"]     # 08-31 (open) dropped


def test_write_incremental_drops_open_month(tmp_path, as_of):
    folder = str(tmp_path / "monthly")
    df = _fresh_weekly(["2026-07-01", "2026-08-01", "2026-09-01"])
    mio.write_incremental(folder, "TEST", df, interval="1mo")
    back = mio.load_ohlcv(folder, "TEST")
    got = sorted(str(d)[:10] for d in back.index)
    assert got == ["2026-07-01", "2026-08-01"]     # 09-01 (open) dropped


def test_write_incremental_replaces_a_previously_open_bar_once_it_closes(tmp_path, monkeypatch):
    """
    Run 1 (mid-Aug): week 08-24 is still open -> not written.
    Run 2 (early Sep): week 08-24 has closed, with its real (larger) volume
    -> now written. The completeness gate is what makes weekly converge.
    """
    folder = str(tmp_path / "weekly")

    monkeypatch.setattr(pc, "last_closed_us_trading_date", lambda now=None: dt.date(2026, 8, 26))
    run1 = _fresh_weekly(["2026-08-17", "2026-08-24"], base_vol=50)
    mio.write_incremental(folder, "TEST", run1, interval="1wk")
    assert sorted(str(d)[:10] for d in mio.load_ohlcv(folder, "TEST").index) == ["2026-08-17"]

    monkeypatch.setattr(pc, "last_closed_us_trading_date", lambda now=None: dt.date(2026, 9, 3))
    run2 = _fresh_weekly(["2026-08-24", "2026-08-31"], base_vol=999)
    mio.write_incremental(folder, "TEST", run2, interval="1wk")
    back = mio.load_ohlcv(folder, "TEST")
    got = {str(d)[:10]: v for d, v in zip(back.index, back["Volume"])}
    assert set(got) == {"2026-08-17", "2026-08-24"}
    assert got["2026-08-24"] == 999      # the closed-week value, not run1's partial
