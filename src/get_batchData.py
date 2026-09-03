import os
import time
from collections import Counter

import pandas as pd
import yfinance as yf
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from src import ticker_manifest, market_data_io, period_calendar
from src.config import PARAMS_DIR

CHUNK_SIZE = 100
SLEEP_BETWEEN_CHUNKS = 3
MAX_RETRIES = 3
RETRY_BACKOFF = [30, 60, 120]

INTERVAL_TO_SUBDIR = {'1d': 'daily', '1wk': 'weekly', '1mo': 'monthly'}

US_EASTERN = ZoneInfo("America/New_York")
US_MARKET_CLOSE = (16, 15)  # 4:00pm ET close + 15min settle buffer before yfinance has the final daily bar


def _last_closed_us_trading_date(now=None):
    """Most recent calendar date (US/Eastern) whose regular session has
    actually finished as of `now`: today if the US market has already
    closed (past US_MARKET_CLOSE, US/Eastern), otherwise yesterday. This
    machine runs on local (e.g. German) time, hours ahead of US market
    hours, so date.today() alone would treat a US trading day as available
    hours before it's actually closed. Doesn't special-case
    weekends/holidays - those already come back empty from yfinance same
    as before this check existed, harmlessly."""
    now = (now or datetime.now(US_EASTERN)).astimezone(US_EASTERN)
    close_today = now.replace(hour=US_MARKET_CLOSE[0], minute=US_MARKET_CLOSE[1], second=0, microsecond=0)
    return now.date() if now >= close_today else now.date() - timedelta(days=1)


def _pending_daily_data(start_iso, now=None):
    """True if at least one CLOSED US trading session falls on/after
    `start_iso` as of `now` - i.e. whether a daily gap-fill request
    starting there could possibly get back new data right now. False means
    the request's start date is today (or later) and the US market hasn't
    closed yet, so firing it would just ask yfinance for a session that
    isn't final."""
    return date.fromisoformat(start_iso) <= _last_closed_us_trading_date(now)


def _parse_interval_cfg(start, end, period):
    end = end.strip()
    if end.lower() == "today":
        end = datetime.now().strftime("%Y-%m-%d")
    start = start.strip()
    use_range = bool(start and start.lower() not in ("", "nan"))
    return start, end, period, use_range


def _get_sub(df, t, chunk):
    if isinstance(df.columns, pd.MultiIndex):
        lvl0 = df.columns.get_level_values(0).unique()
        lvl1 = df.columns.get_level_values(1).unique()
        if t in lvl0:
            return df[t].dropna(subset=["Close"])
        elif t in lvl1:
            return df.xs(t, level=1, axis=1).dropna(subset=["Close"])
        return None
    else:
        return df.dropna(subset=["Close"]) if len(chunk) == 1 else None


def _normalize_period_date(d, interval):
    """Snap a yfinance-returned bar date to its period's canonical start
    date. yfinance dates a CLOSED week/month by its Monday/1st (confirmed:
    every completed week in the batch cache lands on a Monday), but dates
    the still-OPEN current week/month by whatever the latest trading day
    happened to be at fetch time instead - so the same in-progress weekly
    bar gets a different Date depending on which day of the week the batch
    job ran (e.g. 2026-08-17 one day, 2026-08-18 the next), fragmenting one
    evolving bar across a new date-sharded file every run instead of
    updating the same file in place. Weekly data isn't daily data, so its
    storage granularity shouldn't be either."""
    if interval == '1wk':
        return d - timedelta(days=d.weekday())  # Monday of that week
    if interval == '1mo':
        return d.replace(day=1)
    return d


def _extract_rows(df, chunk, interval):
    rows = []
    for t in chunk:
        try:
            sub = _get_sub(df, t, chunk)
        except Exception:
            continue
        if sub is None or sub.empty:
            continue
        for bar_date, row in sub.iterrows():
            norm_date = _normalize_period_date(bar_date.date(), interval)
            # Drop the still-open week/month - its volume is still growing.
            if not period_calendar.is_period_complete(norm_date, interval):
                continue
            rows.append({
                "Date":      norm_date.isoformat(),
                "Symbol":    t,
                "Open":      row.get("Open"),
                "High":      row.get("High"),
                "Low":       row.get("Low"),
                "Close":     row.get("Close"),
                "Adj Close": row.get("Adj Close"),
                "Volume":    row.get("Volume"),
            })
    return rows


def _scan_batch_last_seen(folder, interval, tickers=None, lookback_files=120):
    """
    Per-ticker most recent date found in the date-sharded batch cache
    (folder/prices_{interval}_YYYY-MM-DD.csv) - reads the batch cache's own
    storage layout (one file per trading day holding, nominally, the whole
    universe) rather than reusing market_data_io against
    data/market_data/<interval>/, because the two caches are filled
    independently and a stale non-batch ticker has no bearing on what the
    batch cache still needs.

    Scans files newest-to-oldest, stopping once every ticker in `tickers`
    has been found (or `lookback_files` is exhausted - cheap regardless
    while the batch cache only spans a few months).

    Returns {ticker: date}, empty if no matching files exist. Tickers never
    found within the lookback window are simply absent from the result.
    """
    if not os.path.isdir(folder):
        return {}

    prefix = f"prices_{interval}_"
    files = []
    for entry in os.scandir(folder):
        if not (entry.name.startswith(prefix) and entry.name.endswith(".csv")):
            continue
        date_str = entry.name[len(prefix):-4]
        try:
            file_date = date.fromisoformat(date_str)
        except ValueError:
            continue
        files.append((file_date, entry.path))
    if not files:
        return {}
    files.sort(key=lambda x: x[0], reverse=True)

    wanted = set(tickers) if tickers is not None else None
    last_seen = {}
    for file_date, path in files[:lookback_files]:
        try:
            symbols = pd.read_csv(path, usecols=["Symbol"])["Symbol"].astype(str)
        except Exception:
            continue
        for symbol in symbols.unique():
            if symbol in last_seen:
                continue
            if wanted is None or symbol in wanted:
                last_seen[symbol] = file_date
        if wanted is not None and wanted <= last_seen.keys():
            break

    return last_seen


def compute_batch_gap_start_date(folder, interval, tickers=None, lookback_files=120):
    """
    The earliest 'latest date already covered' across `tickers` (see
    _scan_batch_last_seen), +1 day - the date a single uniform
    --batch-gap-fill request should start from.

    Superseded by run_batch_gap_fill_interval for the main gap-fill path
    (which splits majority vs straggler tickers into separate requests
    instead of dragging the whole universe back to the worst ticker's gap).
    Kept for any caller that still wants the plain single-date-for-everyone
    behavior.

    Returns None if no matching files exist, or none of `tickers` were found.
    """
    last_seen = _scan_batch_last_seen(folder, interval, tickers, lookback_files)
    if not last_seen:
        return None
    return min(last_seen.values()) + timedelta(days=1)


def _write_date_files(out, out_dir, interval):
    """Merge-safe write: a date's file may already hold rows for tickers not
    in this call's results (e.g. a separate majority-group vs stragglers-group
    call touching the same date) - read-merge-write instead of blind
    overwrite, so neither call's data clobbers the other's."""
    for date, group in out.groupby("Date"):
        fname = os.path.join(out_dir, f"prices_{interval}_{date}.csv")
        if os.path.isfile(fname):
            try:
                existing = pd.read_csv(fname)
                group = pd.concat([existing, group]).drop_duplicates(subset=["Symbol"], keep="last")
            except Exception:
                pass
        group.sort_values("Symbol").to_csv(fname, index=False)


def seed_batch_from_slow_pipeline(interval, tickers, slow_folder, batch_dir, manifest,
                                   last_seen=None, today_iso=None):
    """
    For tickers behind batch's own majority date - whether batch has never
    seen them at all, or saw them once and they've since fallen behind -
    copy just their most recent row from the slow pipeline's archive/current
    store (data/market_data/<interval>/) into the batch cache instead of
    hitting the network. The slow pipeline has likely already tracked these
    tickers for months, so a network request would just re-fetch what's
    already on disk under a different layout - including for a batch
    STRAGGLER (some old prior batch date, not "never seen"): if the slow
    pipeline is already caught up, seeding advances the ticker for free
    instead of batch redundantly re-fetching the whole gap itself, one week
    at a time, over the network. Only the latest row is copied (not full
    history): batch's date-sharded cache is a recent-window store, not a
    second full archive, and one row is all `run_batch_gap_fill_interval`
    needs to compute a real majority date and gap-fill forward from there.

    Two eligibility conditions, both required:
      1. CURRENT in the slow pipeline - at ITS OWN majority date across
         `tickers`. A ticker that's itself a slow-pipeline straggler
         (stuck behind on some older date, usually because it's genuinely
         broken/delisted) is scripts/sync_stragglers.py's job to catch up
         first (wired into batchJobs_calc/jobs.yaml to run before the
         batch job) - copying its stale row here instead would silently
         scatter a one-ticker date file into the batch cache at whatever
         old date it's stuck on, rather than surfacing it as the straggler
         it actually is.
      2. Actually AHEAD of what batch already has for that ticker (per
         `last_seen`, batch's current per-ticker date) - otherwise this
         would blindly overwrite/no-op a ticker batch already has equally
         current or fresher data for.
    Skipped tickers are simply left unseeded, for the caller's normal
    network-based straggler handling.

    Note: the slow pipeline fetches with auto_adjust=True (Close already
    split/dividend-adjusted), while batch's own yf.download calls use
    auto_adjust=False plus a separate Adj Close column. Seeded rows have no
    unadjusted counterpart, so Close/Open/High/Low here are the adjusted
    values and Adj Close is set equal to Close - an approximation only at
    the seed boundary, harmless for gap-fill's own date-tracking purpose.

    Returns the set of tickers actually seeded.
    """
    today_iso = today_iso or date.today().isoformat()
    last_seen = last_seen or {}

    dfs = {}
    for t in tickers:
        df = market_data_io.load_ohlcv(slow_folder, t)
        if not df.empty:
            dfs[t] = df
    if not dfs:
        return set()

    last_dates = {t: pd.to_datetime(df.index[-1], utc=True).date() for t, df in dfs.items()}
    slow_majority = Counter(last_dates.values()).most_common(1)[0][0]
    current_tickers = [
        t for t, d in last_dates.items()
        if d == slow_majority and (t not in last_seen or last_seen[t] < slow_majority)
    ]
    skipped = len(dfs) - len(current_tickers)
    if skipped:
        print(f"  Seed {interval}: {skipped} ticker(s) skipped (behind slow's own {slow_majority} "
              f"majority - sync_stragglers.py's job, not seeded here - or already current in batch)")
    if not current_tickers:
        return set()

    rows = []
    for t in current_tickers:
        last_row = dfs[t].iloc[-1]
        close = last_row.get("Close")
        rows.append({
            "Date":      slow_majority.isoformat(),
            "Symbol":    t,
            "Open":      last_row.get("Open"),
            "High":      last_row.get("High"),
            "Low":       last_row.get("Low"),
            "Close":     close,
            "Adj Close": close,
            "Volume":    last_row.get("Volume"),
        })

    out = (pd.DataFrame(rows)
           .drop_duplicates(subset=["Date", "Symbol"])
           .sort_values(["Date", "Symbol"]))
    os.makedirs(batch_dir, exist_ok=True)
    _write_date_files(out, batch_dir, interval)

    seeded = set(current_tickers)
    fresh = _scan_batch_last_seen(batch_dir, interval, tickers=seeded)
    for t in seeded:
        ticker_manifest.set_date(manifest, t, ticker_manifest.batch_date_col(interval), fresh.get(t))
        ticker_manifest.record_outcome(manifest, t, is_success=True, today=today_iso)

    print(f"  Seeded {interval} from slow pipeline (no network): {len(seeded)}/{len(tickers)} tickers @ {slow_majority}")
    return seeded


def run_batch_data_retrieval(params):
    """
    Fast batch OHLCV download using yf.download() for one or more intervals.

    params keys:
        ticker_file         path to CSV with 'Symbol' or 'ticker' column
        output_dir          base output dir; daily/, weekly/, monthly/ created automatically
        failed_file         path to problematic_tickers_batch.csv
        use_failed_file     bool — whether to exclude known-failed tickers
        interval_cfg        dict {yf_interval: (start_date, end_date, period, use_range)}
        chunk_size          int (default 100)
        batch_start         optional str — override start date for all intervals (from CLI)
        batch_end           optional str — override end date for all intervals (from CLI)
        batch_period        optional str — override period for all intervals (from CLI)
        update_failed_file  bool (default True) — write newly-failed tickers to failed_file.
                             The gap-fill split path (run_batch_gap_fill_interval) handles
                             failure tracking itself via the shared ticker manifest instead.

    Returns {interval: {'attempted': set(tickers whose chunk actually executed),
                         'succeeded': set(tickers present in the results)}} -
    'attempted' excludes tickers whose chunk never ran (gave up after
    retries) so callers doing their own failure bookkeeping don't blacklist
    tickers that were simply never reached.
    """
    ticker_file    = params["ticker_file"]
    output_dir     = params["output_dir"]
    failed_file    = params["failed_file"]
    use_failed     = params.get("use_failed_file", True)
    update_failed  = params.get("update_failed_file", True)
    interval_cfg   = params["interval_cfg"]
    chunk_size     = params.get("chunk_size", CHUNK_SIZE)
    cli_start      = params.get("batch_start", "")
    cli_end        = params.get("batch_end", "")
    cli_period     = params.get("batch_period", "")

    # Apply CLI overrides to all intervals
    if cli_start or cli_end or cli_period:
        interval_cfg = {
            iv: _parse_interval_cfg(
                cli_start or start,
                cli_end   or end,
                cli_period or period,
            )
            for iv, (start, end, period, _) in interval_cfg.items()
        }

    # --- failed tickers ---
    if use_failed:
        try:
            failed_known = set(pd.read_csv(failed_file)["Symbol"].tolist())
            print(f"  Excluding {len(failed_known)} previously failed tickers")
        except FileNotFoundError:
            failed_known = set()
    else:
        failed_known = set()
        print("  Ignoring failed tickers file — all tickers will be retried")

    # --- load and clean universe ---
    raw = pd.read_csv(ticker_file)
    if "Symbol" not in raw.columns and "ticker" in raw.columns:
        raw = raw.rename(columns={"ticker": "Symbol"})
    raw["Symbol"] = raw["Symbol"].astype(str).str.strip()
    raw = raw[raw["Symbol"].notna() & (raw["Symbol"].str.lower() != "nan")]
    raw = raw[~raw["Symbol"].str.contains("/")]
    raw["Symbol"] = raw["Symbol"].str.replace(".", "-", regex=False)
    raw = raw.drop_duplicates(subset=["Symbol"])
    raw = raw[~raw["Symbol"].isin(failed_known)]
    print(f"  Clean universe: {len(raw)} tickers")

    tickers = raw["Symbol"].tolist()
    chunks  = [tickers[i:i + chunk_size] for i in range(0, len(tickers), chunk_size)]
    print(f"  {len(tickers)} tickers → {len(chunks)} chunks of {chunk_size}")

    daily_downloaded = set()
    all_downloaded   = set()
    interval_results = {}

    # Manifest bookkeeping shares the same update_failed gate as the failed-
    # tickers-file block below: when False, this is a sub-call from
    # run_batch_gap_fill_interval's _run_group, which already records
    # outcomes into the caller's own manifest object via
    # _record_group_outcomes - doing it again here would just be a
    # redundant duplicate write (idempotent, but wasteful). When True (the
    # plain/direct call path - e.g. main.py's non-gap-fill batch branch),
    # nothing else updates the manifest for this call, so this is the only
    # place it happens - previously that path never touched the manifest
    # at all, letting last_data_date_*_batch and the failure streak go
    # stale for anyone not using --batch-gap-fill.
    manifest = ticker_manifest.load_manifest() if update_failed else None
    today_iso = datetime.now().strftime("%Y-%m-%d")

    for interval, (start_date, end_date, period, use_range) in interval_cfg.items():
        # yfinance anchors a '1wk'/'1mo' series to the weekday/day-of-month of
        # `start`; a non-aligned start yields bars that straddle calendar weeks.
        if use_range:
            start_date = period_calendar.align_fetch_start(start_date, interval)
        subdir  = INTERVAL_TO_SUBDIR.get(interval, interval)
        out_dir = os.path.join(output_dir, subdir)
        os.makedirs(out_dir, exist_ok=True)

        print(f"\n{'='*50}")
        print(f"  Batch {interval} → {out_dir}")
        if use_range:
            print(f"  Date range: {start_date} → {end_date}")
        else:
            print(f"  Period: {period}")
        print(f"{'='*50}")

        results = []
        attempted = set()

        for i, chunk in enumerate(chunks):
            for attempt in range(MAX_RETRIES):
                try:
                    kwargs = dict(
                        tickers=chunk,
                        interval=interval,
                        group_by="ticker",
                        threads=True,
                        auto_adjust=False,
                        prepost=False,
                        progress=False,
                    )
                    if use_range:
                        kwargs["start"] = start_date
                        kwargs["end"]   = end_date
                    else:
                        kwargs["period"] = period
                    df = yf.download(**kwargs)
                    attempted.update(chunk)  # chunk executed, whether or not it returned data for every ticker
                    if not df.empty:
                        results.extend(_extract_rows(df, chunk, interval))
                    break
                except Exception as e:
                    if "Too Many Requests" in str(e) or "RateLimit" in type(e).__name__:
                        wait = RETRY_BACKOFF[min(attempt, len(RETRY_BACKOFF) - 1)]
                        print(f"    chunk {i+1}: rate limited — waiting {wait}s (attempt {attempt+1}/{MAX_RETRIES})")
                        time.sleep(wait)
                    else:
                        print(f"    chunk {i+1}: failed — {e}")
                        break
            else:
                print(f"    chunk {i+1}: gave up after {MAX_RETRIES} attempts — not counted as attempted")

            if i < len(chunks) - 1:
                time.sleep(SLEEP_BETWEEN_CHUNKS)

            if (i + 1) % 10 == 0:
                print(f"    progress: {i+1}/{len(chunks)} chunks, {len(results)} rows collected")

        succeeded = set(r["Symbol"] for r in results)
        interval_results[interval] = {"attempted": attempted, "succeeded": succeeded}

        if update_failed:
            _record_group_outcomes(manifest, out_dir, interval, tickers, interval_results[interval], today_iso)

        if not results:
            print(f"  No data collected for {interval}")
            continue

        out = (pd.DataFrame(results)
               .drop_duplicates(subset=["Date", "Symbol"])
               .sort_values(["Date", "Symbol"]))
        _write_date_files(out, out_dir, interval)
        print(f"  Done {interval}: {out['Date'].nunique()} files, {out['Symbol'].nunique()} tickers")

        all_downloaded.update(succeeded)
        if interval == "1d":
            daily_downloaded.update(succeeded)

    # --- update failed tickers (daily results only; weekly/monthly gaps don't blacklist) ---
    # Only tickers whose chunk actually executed count - one that was never
    # reached (chunk gave up after retries) isn't evidence it's broken.
    if update_failed:
        daily_attempted = interval_results.get("1d", {}).get("attempted", set())
        ref_attempted = daily_attempted if daily_attempted else set().union(
            *(r["attempted"] for r in interval_results.values())) if interval_results else set()
        ref_succeeded = daily_downloaded if daily_downloaded else all_downloaded
        newly_failed = [t for t in tickers if t in ref_attempted and t not in ref_succeeded]

        if newly_failed:
            today    = datetime.now().strftime("%Y-%m-%d")
            new_rows = pd.DataFrame({"Symbol": newly_failed, "Date": today})
            try:
                existing = pd.read_csv(failed_file)
                combined = pd.concat([existing, new_rows]).drop_duplicates(subset=["Symbol"])
            except FileNotFoundError:
                combined = new_rows
            os.makedirs(os.path.dirname(failed_file), exist_ok=True)
            combined.to_csv(failed_file, index=False)
            print(f"\n  Failed tickers: {len(newly_failed)} added to {failed_file}")

    if update_failed:
        ticker_manifest.save_manifest(manifest)
        print(f"  Manifest updated: {ticker_manifest.MANIFEST_PATH}")

    return interval_results


def _run_group(label, tickers, interval_cfg_single, interval, output_dir,
                failed_file, use_failed_file, chunk_size):
    """One run_batch_data_retrieval call scoped to `tickers` - used by
    run_batch_gap_fill_interval to issue the majority-group and
    straggler-group requests separately. Failure bookkeeping is left to the
    caller (via the shared manifest), not problematic_tickers_batch.csv.

    Scratch ticker lists live under PARAMS_DIR["GAPFILL_DIR"] - shared
    with the slow pipeline's equivalent straggler-sync scratch files (see
    scripts/sync_stragglers.py) rather than TICKERS_DIR (ticker universe
    definitions) or a pipeline-specific market_data*/ subfolder."""
    tmp_dir = PARAMS_DIR["GAPFILL_DIR"]
    os.makedirs(tmp_dir, exist_ok=True)
    tmp_file = os.path.join(tmp_dir, f"_batch_gapfill_{interval}_{label}.csv")
    pd.DataFrame({"Symbol": tickers}).to_csv(tmp_file, index=False)
    params = {
        "ticker_file": tmp_file,
        "output_dir": output_dir,
        "failed_file": failed_file,
        "use_failed_file": use_failed_file,
        "interval_cfg": {interval: interval_cfg_single},
        "update_failed_file": False,
        "chunk_size": chunk_size,
    }
    results = run_batch_data_retrieval(params)
    return results.get(interval, {"attempted": set(), "succeeded": set()})


def _record_group_outcomes(manifest, batch_dir, interval, requested_tickers, result, today_iso):
    """Refreshes last_data_date_{interval}_batch (via a fresh scan, scoped
    to just the tickers this group touched - cheap) and the shared
    consecutive_failures/first_failure_date streak for every ticker whose
    chunk actually executed this run. Tickers never reached (chunk gave up)
    are left untouched - same policy as the non-batch sync."""
    attempted = result["attempted"]
    succeeded = result["succeeded"]
    if not attempted:
        return
    fresh = _scan_batch_last_seen(batch_dir, interval, tickers=attempted)
    for t in requested_tickers:
        if t not in attempted:
            continue
        ticker_manifest.set_date(manifest, t, ticker_manifest.batch_date_col(interval), fresh.get(t))
        ticker_manifest.record_outcome(manifest, t, is_success=(t in succeeded), today=today_iso)


def run_batch_gap_fill_interval(interval, batch_dir, output_dir, universe, manifest,
                                 configured_start, configured_end, configured_period,
                                 failed_file, use_failed_file=True, chunk_size=CHUNK_SIZE,
                                 today=None, lookback_files=120, slow_folder=None):
    """
    Gap-fill for one interval, split into a majority-group request (the
    whole universe minus stragglers, narrow range from the majority
    ticker's coverage) and a straggler-group request (the few tickers
    behind majority, their own wider range) - instead of one uniform
    request whose range gets dragged back to the single worst ticker's
    gap, which redundantly re-fetches and rewrites every already-complete
    day for the ENTIRE universe just because one or two tickers lag.

    If `slow_folder` is given (data/market_data/<interval>/, the slow
    pipeline's own store), any universe ticker behind batch's own majority
    date - never seen by batch at all, OR seen once and since fallen behind
    - is first seeded from there (see seed_batch_from_slow_pipeline) before
    the majority/straggler split runs - the slow pipeline has usually
    already tracked these tickers for months, so a fresh network pull would
    just redundantly re-fetch what's already on disk, one gap at a time,
    for a ticker the slow pipeline already caught up. Only tickers still
    behind after seeding (nothing usable in the slow pipeline either, or
    itself a slow-pipeline straggler - sync_stragglers.py's job) fall
    through to a real network request, scoped to just those tickers.

    Updates `manifest` in place: last_data_date_{interval}_batch for every
    ticker actually reached this run, and the shared
    consecutive_failures/first_failure_date streak (ticker_manifest.
    record_outcome) - the same clock the slow-pipeline sync contributes to,
    since a ticker failing in batch and a ticker failing in the slow
    pipeline are the same delisting signal, not two separate ones.

    Returns a small summary dict for logging.
    """
    today_iso = (today or date.today()).isoformat()
    last_seen = _scan_batch_last_seen(batch_dir, interval, universe, lookback_files)

    if slow_folder:
        # Seed candidates = batch's own stragglers (behind ITS OWN majority
        # hint, or never seen at all) - the majority group is already
        # current, no need to touch the slow pipeline for it. When batch
        # has no data at all yet, every ticker is a candidate.
        if last_seen:
            majority_hint = Counter(last_seen.values()).most_common(1)[0][0]
            seed_candidates = [t for t in universe if last_seen.get(t) != majority_hint]
        else:
            seed_candidates = universe
        if seed_candidates:
            seeded = seed_batch_from_slow_pipeline(
                interval, seed_candidates, slow_folder, batch_dir, manifest,
                last_seen=last_seen, today_iso=today_iso)
            if seeded:
                last_seen.update(_scan_batch_last_seen(batch_dir, interval, tickers=seeded))

    for t, d in last_seen.items():
        ticker_manifest.set_date(manifest, t, ticker_manifest.batch_date_col(interval), d)

    if not last_seen:
        print(f"  Gap-fill {interval}: no existing batch data found — using configured start/period")
        cfg = _parse_interval_cfg(configured_start, configured_end, configured_period)
        result = _run_group("all", universe, cfg, interval, output_dir, failed_file, use_failed_file, chunk_size)
        _record_group_outcomes(manifest, batch_dir, interval, universe, result, today_iso)
        return {"majority_date": None, "majority_group": 0, "stragglers": len(universe)}

    majority = Counter(last_seen.values()).most_common(1)[0][0]
    stragglers = [t for t in universe if last_seen.get(t) != majority]  # includes never-seen tickers
    majority_group = [t for t in universe if t not in stragglers]

    print(f"  Gap-fill {interval}: batch majority date {majority} "
          f"({len(majority_group)}/{len(universe)} tickers), {len(stragglers)} straggler(s)")

    if majority_group:
        start = (majority + timedelta(days=1)).isoformat()
        if interval == '1d' and not _pending_daily_data(start):
            print(f"  Gap-fill {interval} (majority, {len(majority_group)} tickers): "
                  f"US market hasn't closed yet today — nothing new to fetch, skipping")
        else:
            cfg = _parse_interval_cfg(start, configured_end, configured_period)
            print(f"  Gap-fill {interval} (majority, {len(majority_group)} tickers): starting {start}")
            result = _run_group("majority", majority_group, cfg, interval, output_dir,
                                 failed_file, use_failed_file, chunk_size)
            _record_group_outcomes(manifest, batch_dir, interval, majority_group, result, today_iso)

    if stragglers:
        # Group by each straggler's OWN last_seen date instead of one
        # range dragged back to the single worst straggler - otherwise a
        # ticker missing only the most recent day still forces a
        # read-merge-write on every date file back to some OTHER
        # straggler's older gap, needlessly rewriting days that are
        # already complete for the whole rest of the universe (the same
        # "worst ticker drags the whole request back" bug the
        # majority/straggler split fixes one level up, recurring inside
        # the straggler group itself if left as one bucket).
        by_date = {}
        never_seen = []
        for t in stragglers:
            d = last_seen.get(t)
            if d is None:
                never_seen.append(t)
            else:
                by_date.setdefault(d, []).append(t)
        for d, group_tickers in sorted(by_date.items()):
            start = (d + timedelta(days=1)).isoformat()
            if interval == '1d' and not _pending_daily_data(start):
                print(f"  Gap-fill {interval} (stragglers @ {d}, {len(group_tickers)} tickers): "
                      f"US market hasn't closed yet today — skipping")
                continue
            cfg = _parse_interval_cfg(start, configured_end, configured_period)
            print(f"  Gap-fill {interval} (stragglers @ {d}, {len(group_tickers)} tickers): starting {start}")
            result = _run_group(f"stragglers_{d}", group_tickers, cfg, interval, output_dir,
                                 failed_file, use_failed_file, chunk_size)
            _record_group_outcomes(manifest, batch_dir, interval, group_tickers, result, today_iso)
        if never_seen:
            # Same narrow forward-looking window as the majority group, NOT
            # the full configured_period (e.g. 1y for weekly, 5y for
            # monthly) - that config is meant for a genuine cold-start
            # bootstrap (batch has ZERO data anywhere, see the `if not
            # last_seen` branch above), not for a small residual of
            # already-suspect tickers with nothing in either pipeline.
            # Using the full period here re-creates the exact sprawl this
            # whole redesign exists to avoid: dozens of near-empty date
            # files backfilling a year of history for a handful of tickers
            # that are usually just delisted (see [[project-batch-slow-
            # pipeline-integrity]] memory). If one of these is a genuine
            # brand-new ticker needing real history, that's the slow
            # pipeline's initial-backfill job, not batch's.
            start = (majority + timedelta(days=1)).isoformat()
            if interval == '1d' and not _pending_daily_data(start):
                print(f"  Gap-fill {interval} (stragglers, never seen, {len(never_seen)} tickers): "
                      f"US market hasn't closed yet today — skipping")
            else:
                cfg = _parse_interval_cfg(start, configured_end, configured_period)
                print(f"  Gap-fill {interval} (stragglers, never seen, {len(never_seen)} tickers): {never_seen}")
                result = _run_group("stragglers_new", never_seen, cfg, interval, output_dir,
                                     failed_file, use_failed_file, chunk_size)
                _record_group_outcomes(manifest, batch_dir, interval, never_seen, result, today_iso)

    return {"majority_date": majority, "majority_group": len(majority_group), "stragglers": len(stragglers)}
