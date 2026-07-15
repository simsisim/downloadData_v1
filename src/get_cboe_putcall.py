import os
import re
import time
from datetime import date, timedelta

import pandas as pd
import requests

CBOE_URL = "https://www.cboe.com/markets/us/options/market-statistics/daily/"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    )
}
RATIO_RE = re.compile(r'>EQUITY PUT/CALL RATIO</td><td[^>]*>([\d.]+)</td>')
REQUEST_DELAY_SECONDS = 0.5


def _fetch_ratio_for_date(d: date):
    """Return the EPC ratio (float) for date d, or None if not published (weekend/holiday/too recent)."""
    resp = requests.get(CBOE_URL, params={"dt": d.isoformat()}, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    m = RATIO_RE.search(resp.text)
    return float(m.group(1)) if m else None


def run_cboe_putcall_retrieval(output_file=None, lookback_days=10):
    """
    Update the EPC ratio CSV with the most recent trading-day values.
    Always safe to call: returns False on error instead of raising.
    """
    if output_file is None:
        from src.config import PARAMS_DIR
        output_file = os.path.join(PARAMS_DIR["DATA_DIR"], "EPC_ratio.csv")

    try:
        if os.path.exists(output_file):
            existing_df = pd.read_csv(output_file)
        else:
            existing_df = pd.DataFrame(columns=["Date", "EPC_Ratio"])
        existing_dates = set(existing_df["Date"].astype(str))
        have_existing = bool(existing_dates)

        new_rows = []
        checked = 0
        max_requests = lookback_days * 3
        d = date.today()

        # On an empty CSV, backfill the last `lookback_days` values. Once the CSV
        # has data, only fill the gap since the last known date - stop as soon as
        # we reach a date we already have, so reruns don't keep walking further
        # into the past.
        while checked < max_requests and len(new_rows) < lookback_days:
            date_str = d.isoformat()
            if date_str in existing_dates:
                if have_existing:
                    break
                d -= timedelta(days=1)
                continue
            ratio = _fetch_ratio_for_date(d)
            checked += 1
            if ratio is not None:
                new_rows.append({"Date": date_str, "EPC_Ratio": ratio})
            time.sleep(REQUEST_DELAY_SECONDS)
            d -= timedelta(days=1)

        if not new_rows:
            print("CBOE Put/Call Ratio: already up to date, no new values found")
            return True

        new_df = pd.DataFrame(new_rows)
        updated_df = new_df if existing_df.empty else pd.concat([existing_df, new_df], ignore_index=True)
        updated_df = updated_df.drop_duplicates(subset=["Date"], keep="last")
        updated_df = updated_df.sort_values("Date")
        updated_df.to_csv(output_file, index=False)

        latest = updated_df.iloc[-1]
        print(f"CBOE Put/Call Ratio: added {len(new_rows)} new value(s) -> {output_file}")
        print(f"  Latest: {latest['Date']} = {latest['EPC_Ratio']}")
        return True

    except Exception as e:
        print(f"CBOE Put/Call Ratio retrieval failed: {e}")
        return False
