import os
import time
import pandas as pd
import yfinance as yf
from datetime import datetime

CHUNK_SIZE = 100
SLEEP_BETWEEN_CHUNKS = 3
MAX_RETRIES = 3
RETRY_BACKOFF = [30, 60, 120]

INTERVAL_TO_SUBDIR = {'1d': 'daily', '1wk': 'weekly', '1mo': 'monthly'}


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


def _extract_rows(df, chunk):
    rows = []
    for t in chunk:
        try:
            sub = _get_sub(df, t, chunk)
        except Exception:
            continue
        if sub is None or sub.empty:
            continue
        for date, row in sub.iterrows():
            rows.append({
                "Date":      date.strftime("%Y-%m-%d"),
                "Symbol":    t,
                "Open":      row.get("Open"),
                "High":      row.get("High"),
                "Low":       row.get("Low"),
                "Close":     row.get("Close"),
                "Adj Close": row.get("Adj Close"),
                "Volume":    row.get("Volume"),
            })
    return rows


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
    """
    ticker_file    = params["ticker_file"]
    output_dir     = params["output_dir"]
    failed_file    = params["failed_file"]
    use_failed     = params.get("use_failed_file", True)
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

    for interval, (start_date, end_date, period, use_range) in interval_cfg.items():
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
                    if not df.empty:
                        results.extend(_extract_rows(df, chunk))
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
                print(f"    chunk {i+1}: gave up after {MAX_RETRIES} attempts")

            if i < len(chunks) - 1:
                time.sleep(SLEEP_BETWEEN_CHUNKS)

            if (i + 1) % 10 == 0:
                print(f"    progress: {i+1}/{len(chunks)} chunks, {len(results)} rows collected")

        if not results:
            print(f"  No data collected for {interval}")
            continue

        out = (pd.DataFrame(results)
               .drop_duplicates(subset=["Date", "Symbol"])
               .sort_values(["Date", "Symbol"]))
        for date, group in out.groupby("Date"):
            fname = os.path.join(out_dir, f"prices_{interval}_{date}.csv")
            group.to_csv(fname, index=False)
        print(f"  Done {interval}: {out['Date'].nunique()} files, {out['Symbol'].nunique()} tickers")

        all_downloaded.update(r["Symbol"] for r in results)
        if interval == "1d":
            daily_downloaded.update(r["Symbol"] for r in results)

    # --- update failed tickers (daily results only; weekly/monthly gaps don't blacklist) ---
    ref = daily_downloaded if daily_downloaded else all_downloaded
    newly_failed = [t for t in tickers if t not in ref]

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
