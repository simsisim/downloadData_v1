"""
Unit tests for scan_for_missing_days() / fill_missing_days() in
src/get_marketData.py -- synthetic CSVs in tmp_path, no network.

Run: python -m pytest test_missing_days.py -q
"""
import json

import pandas as pd

from src import get_marketData as gm

# NYSE sessions 2026-09-14..2026-09-25 (no holidays in that range)
SESSIONS = [d.date().isoformat() for d in pd.bdate_range("2026-09-14", "2026-09-25")]


def _write(folder, ticker, dates):
    cur = folder / "current"
    cur.mkdir(exist_ok=True)
    lines = ["Date,Open,High,Low,Close,Volume"]
    lines += [f"{d} 00:00:00-04:00,1,1,1,1,100" for d in dates]
    (cur / f"{ticker}.csv").write_text("\n".join(lines) + "\n")


def _scan(folder, since="2026-09-15"):
    return gm.scan_for_missing_days(str(folder), since, until_date="2026-09-25")


def test_flags_day_missing_mid_series(tmp_path):
    _write(tmp_path, "AAA", [d for d in SESSIONS if d != "2026-09-22"])
    assert _scan(tmp_path) == {"AAA": ["2026-09-22"]}


def test_flags_day_missing_from_most_files(tmp_path):
    # The 2026-09-22 case: calendar-driven, so a day most files lack is still caught.
    for t in ("AAA", "BBB", "CCC"):
        _write(tmp_path, t, [d for d in SESSIONS if d != "2026-09-22"])
    _write(tmp_path, "DDD", SESSIONS)
    assert set(_scan(tmp_path)) == {"AAA", "BBB", "CCC"}


def test_first_day_of_window_missing_is_flagged(tmp_path):
    _write(tmp_path, "AAA", [d for d in SESSIONS if d != "2026-09-15"])
    assert _scan(tmp_path) == {"AAA": ["2026-09-15"]}


def test_complete_and_stale_and_new_tickers_not_flagged(tmp_path):
    _write(tmp_path, "FULL", SESSIONS)
    _write(tmp_path, "STALE", [d for d in SESSIONS if d <= "2026-09-18"])   # delisted
    _write(tmp_path, "NEW", [d for d in SESSIONS if d >= "2026-09-21"])     # listed mid-window
    assert _scan(tmp_path) == {}


def test_fill_skips_recorded_unfillable_gaps(tmp_path, monkeypatch):
    _write(tmp_path, "AAA", [d for d in SESSIONS if d != "2026-09-22"])
    monkeypatch.setattr(gm.period_calendar, "last_closed_us_trading_date", lambda: pd.Timestamp("2026-09-25").date())
    calls = []
    monkeypatch.setattr(gm, "repair_from_date", lambda *a, **k: calls.append(k["tickers"]) or {})

    # First run: attempts the fill; gap survives (repair is a no-op) -> recorded.
    gm.fill_missing_days(str(tmp_path), "2026-09-15")
    assert calls == [["AAA"]]
    recorded = json.loads((tmp_path / gm.UNFILLABLE_GAPS_FILE).read_text())
    assert recorded == {"AAA": ["2026-09-22"]}

    # Second run: gap is known-unfillable -> no re-download.
    gm.fill_missing_days(str(tmp_path), "2026-09-15")
    assert calls == [["AAA"]]


def test_repair_keeps_rows_yahoo_no_longer_serves(tmp_path, monkeypatch):
    # Delisted-ticker case (CRNX, 2026-09-28): Yahoo returns only the last
    # few days, so rows it doesn't return must survive the repair.
    _write(tmp_path, "AAA", SESSIONS)
    last = pd.DataFrame({"Open": [2.0], "High": [2.0], "Low": [2.0], "Close": [2.0], "Volume": [5]},
                        index=pd.DatetimeIndex([pd.Timestamp("2026-09-25", tz="America/New_York")], name="Date"))
    monkeypatch.setattr(gm, "fetch_ohlcv", lambda *a, **k: last)
    monkeypatch.setattr(gm.market_data_io, "BACKUP_DIR", str(tmp_path / "backups"))
    monkeypatch.setattr(gm.market_data_io.backup_current, "__defaults__",
                        (None, str(tmp_path / "backups"), gm.market_data_io.BACKUP_KEEP))

    gm.repair_from_date(str(tmp_path), "2026-09-15", tickers=["AAA"])

    rows = (tmp_path / "current" / "AAA.csv").read_text().splitlines()[1:]
    assert [r[:10] for r in rows] == SESSIONS
    assert rows[-1].split(",")[4] in ("2", "2.0")   # 09-25 overwritten with the fresh bar


def test_rebuild_refuses_to_drop_existing_rows(tmp_path):
    from src import market_data_io as mio
    _write(tmp_path, "AAA", SESSIONS)
    before = (tmp_path / "current" / "AAA.csv").read_text()
    short = pd.DataFrame({"Open": [2.0], "High": [2.0], "Low": [2.0], "Close": [2.0], "Volume": [5]},
                         index=pd.DatetimeIndex([pd.Timestamp("2026-09-25", tz="America/New_York")], name="Date"))
    import pytest
    with pytest.raises(mio.DataLossRefused):
        mio.rebuild_archive_current(str(tmp_path), "AAA", short, interval="1d")
    assert (tmp_path / "current" / "AAA.csv").read_text() == before


def test_backup_current_snapshots_and_prunes(tmp_path):
    import tarfile
    from src import market_data_io as mio
    _write(tmp_path, "AAA", SESSIONS)
    bdir = tmp_path / "backups"
    paths = [mio.backup_current(str(tmp_path), f"t{i}", backup_dir=str(bdir), keep=2) for i in range(3)]
    left = sorted(p.name for p in bdir.iterdir())
    assert len(left) == 2 and all(p.endswith(".tar.gz") for p in left)
    with tarfile.open(paths[-1]) as tar:
        assert "current/AAA.csv" in tar.getnames()
    # a recent snapshot exists -> periodic call is skipped
    assert mio.backup_current(str(tmp_path), "weekly", max_age_days=7, backup_dir=str(bdir)) is None


def _bars(dates):
    idx = pd.DatetimeIndex([pd.Timestamp(d, tz="America/New_York") for d in dates], name="Date")
    return pd.DataFrame({"Open": 1.0, "High": 1.0, "Low": 1.0, "Close": 1.0, "Volume": 1}, index=idx)


def test_hold_back_stops_before_recent_gap():
    # The 2026-09-24 run: asked for 09-22..09-23, Yahoo returned only 09-23.
    out, gap = gm.hold_back_at_gap(_bars(["2026-09-23"]), "2026-09-22", today=pd.Timestamp("2026-09-24").date())
    assert gap == ["2026-09-22"] and out.empty

    out, gap = gm.hold_back_at_gap(_bars(["2026-09-21", "2026-09-23"]), "2026-09-21",
                                   today=pd.Timestamp("2026-09-24").date())
    assert gap == ["2026-09-22"] and len(out) == 1


def test_hold_back_accepts_old_gap_and_complete_fetch():
    full = _bars(["2026-09-22", "2026-09-23"])
    out, gap = gm.hold_back_at_gap(full, "2026-09-22", today=pd.Timestamp("2026-09-24").date())
    assert gap == [] and len(out) == 2
    # gap older than GAP_HOLD_DAYS -> written anyway so the ticker can't stall
    out, gap = gm.hold_back_at_gap(_bars(["2026-09-23"]), "2026-09-22", today=pd.Timestamp("2026-10-05").date())
    assert gap == ["2026-09-22"] and len(out) == 1


def test_repair_with_split_in_range_does_full_rebuild(tmp_path, monkeypatch):
    # MNST 2026-08-11: split landed on a missing day -> repair must rebuild
    # the whole history, not merge adjusted rows onto pre-split ones.
    _write(tmp_path, "AAA", SESSIONS)
    fresh = _bars(["2026-09-22", "2026-09-23"])
    fresh["Stock Splits"] = [2.0, 0.0]
    monkeypatch.setattr(gm, "fetch_ohlcv", lambda *a, **k: fresh)
    monkeypatch.setattr(gm.market_data_io.backup_current, "__defaults__",
                        (None, str(tmp_path / "backups"), gm.market_data_io.BACKUP_KEEP))
    calls = []
    monkeypatch.setattr(gm.market_data_io, "check_and_handle_split",
                        lambda folder, t, iv, rows, fn, start, end, audit, splits_folder=None:
                        calls.append((t, start)) or {"status": "rebuilt_ok", "ticker": t})

    res = gm.repair_from_date(str(tmp_path), "2026-09-22", tickers=["AAA"])
    assert calls == [("AAA", SESSIONS[0])]
    assert res["fixed"] == ["AAA"]


def test_split_rebuild_runs_once_per_split(tmp_path):
    # IESC: the open week carrying the split was re-fetched every run and
    # triggered a full rebuild each time (5x). Second sighting must skip.
    from src import market_data_io as mio
    _write(tmp_path, "AAA", SESSIONS)
    audit = str(tmp_path / "split_events.csv")
    split_rows = _bars(["2026-09-22"])
    split_rows["Stock Splits"] = 2.0
    fetches = []

    def fetch(t, s, e, interval="1d"):
        fetches.append(s)
        return _bars(SESSIONS)

    r1 = mio.check_and_handle_split(str(tmp_path), "AAA", "1d", split_rows, fetch, SESSIONS[0], SESSIONS[-1], audit)
    r2 = mio.check_and_handle_split(str(tmp_path), "AAA", "1d", split_rows, fetch, SESSIONS[0], SESSIONS[-1], audit)
    assert (r1["status"], r2["status"]) == ("rebuilt_ok", "already_rebuilt")
    assert len(fetches) == 1

    # a different (new) split for the same ticker still rebuilds
    other = _bars(["2026-09-24"]); other["Stock Splits"] = 3.0
    assert mio.check_and_handle_split(str(tmp_path), "AAA", "1d", other, fetch, SESSIONS[0], SESSIONS[-1], audit)["status"] == "rebuilt_ok"
    # ...but not for another interval's record
    assert not mio.split_already_rebuilt(audit, "AAA", "1wk", split_rows)
