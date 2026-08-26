"""
Enrich the TradingView universe file with Yahoo Finance's own sector/industry
classification and market cap.

TradingView and Yahoo Finance use different classification schemes (verified:
e.g. AAPL is "Electronic technology / Telecommunications equipment" per
TradingView vs "Technology / Consumer Electronics" per Yahoo) — they are not
interchangeable, so callers need to pick one explicitly rather than get
whichever one happened to be plumbed through. Same reasoning applies to
market cap: TradingView's own 'Market capitalization' column is only as
fresh as the last manual re-export of the raw universe file (~quarterly),
while Yahoo's is refreshed daily (see below) — a stock near a cap-tier
boundary (e.g. $10B) could sit in the wrong bucket for a whole quarter on
the stale figure.

Yahoo's sector/industry/market cap for each ticker are all read straight off
that ticker's own daily price file
(data/market_data/daily/{current,archive}/<ticker>.csv), which
update_individual_stock_data() already refreshes from a live yf.Ticker().info
call on every daily update — so this step costs no new API calls for any
ticker that already has a price file, and all three columns come from one
read per ticker (not three).

Deliberately doesn't compute a cap-tier bucket (large/mid/small) here — that
threshold logic (e.g. StockCharts' $10B/$2B/$250M cutoffs) is a downstream
project's business rule, not something this generic reference file should
bake in. Callers wanting a bucket apply their own thresholds to
`market_cap_yf`.

Input:  data/tickers/tradingview_universe_bool.csv  (rebuilt by
        tradingview_ticker_processor.py from the raw TradingView export)
Output: data/tickers/tradingview_universe_yf.csv    (same rows, 'Sector'/
        'Industry' renamed to sector_tv/industry_tv, plus new sector_yf/
        industry_yf/market_cap_yf columns)

Run after the daily downloadData_v1 update (so price files are current) and
after tradingview_ticker_processor.py (so the bool file exists). Always a
full rebuild — safe to re-run any number of times.
"""

import os

import pandas as pd

from src.config import PARAMS_DIR

TICKERS_DIR = PARAMS_DIR["TICKERS_DIR"]
DAILY_DIR = PARAMS_DIR["MARKET_DATA_DIR_1d"]

INPUT_FILE = os.path.join(TICKERS_DIR, 'tradingview_universe_bool.csv')
OUTPUT_FILE = os.path.join(TICKERS_DIR, 'tradingview_universe_yf.csv')

_PRICE_FILE_COLS = ['sector', 'industry', 'marketCap_asOfDownload']


def _yf_sector_industry_cap(ticker: str):
    """Read (sector, industry, market_cap) off a ticker's own daily price
    file, one read covering all three where available.

    Prefers current/ (freshest), falls back to archive/. Some older/shorter
    price-file schemas have sector/industry but not marketCap_asOfDownload
    (checked live: e.g. AESPU, ARTC) - degrade gracefully to sector/industry
    alone rather than losing all three over one missing column.
    Returns (None, None, None) if no price file exists yet or it lacks even
    sector/industry.
    """
    for tier in ('current', 'archive'):
        path = os.path.join(DAILY_DIR, tier, f'{ticker}.csv')
        if not os.path.exists(path):
            continue
        try:
            df = pd.read_csv(path, usecols=_PRICE_FILE_COLS)
            has_cap = True
        except (ValueError, pd.errors.EmptyDataError):
            try:
                df = pd.read_csv(path, usecols=['sector', 'industry'])
                has_cap = False
            except (ValueError, pd.errors.EmptyDataError):
                continue
        if not df.empty:
            last = df.iloc[-1]
            cap = last.get('marketCap_asOfDownload') if has_cap else None
            return last.get('sector'), last.get('industry'), cap
    return None, None, None


def enrich(input_file: str = INPUT_FILE, output_file: str = OUTPUT_FILE) -> pd.DataFrame:
    df = pd.read_csv(input_file)
    df = df.rename(columns={'Sector': 'sector_tv', 'Industry': 'industry_tv'})

    print(f"Enriching {len(df)} tickers with Yahoo sector/industry/market cap...")
    sectors_yf, industries_yf, caps_yf = [], [], []
    missing = []
    for i, ticker in enumerate(df['ticker']):
        if i % 500 == 0 and i > 0:
            print(f"  {i}/{len(df)} processed ({len(missing)} missing so far)...")
        sector, industry, cap = _yf_sector_industry_cap(ticker)
        if sector is None:
            missing.append(ticker)
        sectors_yf.append(sector)
        industries_yf.append(industry)
        caps_yf.append(cap)

    df['sector_yf'] = sectors_yf
    df['industry_yf'] = industries_yf
    df['market_cap_yf'] = caps_yf

    df.to_csv(output_file, index=False)
    print(f"Saved {output_file}  ({len(df)} tickers, {len(missing)} missing yf sector/industry/cap)")
    if missing:
        preview = missing[:20]
        print(f"  Missing (no price file / no sector-industry-cap columns found): {preview}"
              f"{'...' if len(missing) > 20 else ''}")
    return df


if __name__ == '__main__':
    enrich()
