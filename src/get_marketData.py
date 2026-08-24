import yfinance as yf
import pandas as pd
import datetime as dt
from datetime import timedelta
import time
import os
from src.config import user_choice
from src.config import PARAMS_DIR
import logging
from src import market_data_io
from src.market_data_io import fetch_ohlcv
from src import ticker_manifest

# Shares-outstanding/splits change a few times a year at most (real filing
# events), so refetching yf.Ticker.get_shares_full's whole series on every
# daily run would be pure waste against every other ticker's price update -
# refreshed at this cadence instead once a ticker already has data on file
# (see MarketDataRetriever._update_shares_and_splits). Mirrors
# get_financial_data.py's FinancialDataRetriever refresh_days pattern for
# the same reason (fundamentals also change slowly).
SHARES_REFRESH_DAYS = 30


def _read_header(file_path):
    """Read just the first line of a CSV - O(1) regardless of file size."""
    with open(file_path, 'r', encoding='utf-8', errors='ignore') as fh:
        return fh.readline().strip().split(',')


def _tail_lines(file_path, max_bytes=8192):
    """
    Read only the last `max_bytes` of a file and split into lines - avoids a full parse.
    The first split element is dropped: for any file bigger than max_bytes it's a
    truncated fragment of a row, not a complete one.
    """
    with open(file_path, 'rb') as fh:
        fh.seek(0, os.SEEK_END)
        size = fh.tell()
        fh.seek(max(0, size - max_bytes))
        chunk = fh.read().decode('utf-8', errors='ignore')
    lines = chunk.strip().split('\n')
    return lines[1:] if size > max_bytes else lines


def scan_for_corrupted_tickers(folder, since_date):
    """
    Find CSVs in `folder` with rows on/after `since_date` whose Open/High/Low/Close
    are blank or all-zero (signature of a degraded yfinance API response).

    Deliberately avoids pandas.read_csv per file (~24ms/file, ~2min for ~4.7k
    tickers in this project) in favor of a raw tail-read (~0.01ms/file) since we
    only need to inspect the last few rows, not the full history. Date comparison
    is done as ISO-format string comparison (not pd.to_datetime) for the same
    reason - per-call datetime parsing dominated an earlier version of this scan.
    """
    since_date_str = pd.to_datetime(since_date).strftime('%Y-%m-%d')
    needed = ['Date', 'Open', 'High', 'Low', 'Close']
    corrupted = []

    for entry in os.scandir(folder):
        if not entry.name.endswith('.csv'):
            continue
        ticker = entry.name[:-4]
        try:
            header = _read_header(entry.path)
            if not all(c in header for c in needed):
                continue
            col_idx = {name: i for i, name in enumerate(header)}
            max_idx = max(col_idx[c] for c in needed)

            for raw_line in _tail_lines(entry.path):
                if raw_line.startswith('Date,') or not raw_line.strip():
                    continue
                fields = raw_line.split(',')
                if len(fields) <= max_idx:
                    continue
                row_date_str = fields[col_idx['Date']][:10]
                if len(row_date_str) != 10 or row_date_str < since_date_str:
                    continue
                ohlc = [fields[col_idx[c]] for c in ['Open', 'High', 'Low', 'Close']]
                is_bad = all(v.strip() in ('', '0', '0.0') for v in ohlc)
                if is_bad:
                    corrupted.append(ticker)
                    break
        except Exception:
            continue

    return sorted(set(corrupted))


def repair_from_date(folder, since_date, end_date=None, tickers=None, interval='1d'):
    """
    Force-redownload OHLCV data on/after `since_date` and overwrite whatever is
    currently on disk for those rows - for repairing tickers whose data was
    corrupted by a degraded yfinance API response.

    Runs independently of the normal incremental update path in
    update_individual_stock_data(): it always downloads through `end_date`
    (default: today), so it also backfills any days between `since_date` and
    now for the tickers it touches. It does not update tickers outside the
    `tickers` list (or auto-detected set) - run the normal daily pipeline
    separately to update the rest of the universe.

    Args:
        folder (str): directory containing the per-ticker CSVs (e.g. PARAMS_DIR["MARKET_DATA_DIR_1d"])
        since_date (str or date): repair rows on/after this date (YYYY-MM-DD)
        end_date (str, optional): defaults to today
        tickers (list[str], optional): restrict repair to these tickers; if None, auto-detect
            corrupted tickers in `folder` via scan_for_corrupted_tickers()
        interval (str): yfinance interval, default '1d'

    Returns:
        dict with 'fixed', 'still_broken', 'no_data' ticker lists
    """
    since_date_d = pd.to_datetime(since_date).date()
    end_date = end_date or dt.datetime.now().strftime('%Y-%m-%d')

    if tickers is None:
        print(f"🔍 Scanning {folder} for tickers with corrupted OHLC on/after {since_date_d}...")
        t0 = time.time()
        tickers = scan_for_corrupted_tickers(folder, since_date_d)
        print(f"   Scan completed in {time.time() - t0:.2f}s — {len(tickers)} corrupted ticker(s) found")

    if not tickers:
        print("✅ No corrupted tickers found. Nothing to repair.")
        return {'fixed': [], 'still_broken': [], 'no_data': []}

    fixed, still_broken, no_data = [], [], []
    ohlc_cols = ['Open', 'High', 'Low', 'Close']

    for ticker in tickers:
        try:
            existing_data = market_data_io.load_ohlcv(folder, ticker)
            # Drop rows on/after since_date in memory - only written back to
            # disk if the redownload below actually returns data (see the
            # new_data.empty check), so a failed/empty API response leaves
            # the on-disk tiers (corrupted row included) untouched.
            if not existing_data.empty:
                row_dates = market_data_io.safe_row_years_to_dates(existing_data)
                existing_data = existing_data[[d < since_date_d for d in row_dates]]

            new_data = fetch_ohlcv(ticker, since_date_d.isoformat(), end_date, interval=interval)

            if new_data.empty:
                print(f"⚠️  {ticker}: no data returned for {since_date_d}..{end_date} (API may still be degraded)")
                no_data.append(ticker)
                continue

            bad_mask = new_data[ohlc_cols].isna().any(axis=1) | (new_data[ohlc_cols] == 0).all(axis=1)
            if bad_mask.any():
                bad_dates = [d.date().isoformat() for d in new_data.index[bad_mask]]
                print(f"⚠️  {ticker}: yfinance still returned incomplete OHLC for {bad_dates} — API may still be degraded")
                still_broken.append(ticker)
            else:
                fixed.append(ticker)

            updated_data = pd.concat([existing_data, new_data]) if not existing_data.empty else new_data
            market_data_io.rebuild_archive_current(folder, ticker, updated_data, interval=interval)
            print(f"   {ticker}: repaired {since_date_d} → {end_date} -> {market_data_io.legacy_path(folder, ticker)}")

        except Exception as e:
            print(f"❌ {ticker}: repair failed - {e}")
            still_broken.append(ticker)

    print("\n" + "=" * 60)
    print("REPAIR SUMMARY")
    print("=" * 60)
    print(f"✅ Fixed: {len(fixed)} — {fixed}")
    if still_broken:
        print(f"⚠️  Still broken (yfinance still incomplete or errored): {len(still_broken)} — {still_broken}")
    if no_data:
        print(f"⚠️  No data returned at all: {len(no_data)} — {no_data}")
    return {'fixed': fixed, 'still_broken': still_broken, 'no_data': no_data}


class MarketDataRetriever:
    """
    Dedicated class for retrieving historical market data (OHLCV).
    Focuses on price and volume data for technical analysis and charting.
    """
    
    def __init__(self, config):
        self.logger = logging.getLogger(__name__)
        self.config = config
        self.tickers_list = self.load_tickers()
        self.PARAMS_DIR = PARAMS_DIR 
        # Sanitize user_choice for filenames (replace dashes with underscores)
        safe_user_choice = str(user_choice).replace('-', '_')
        self.info_file = os.path.join(self.PARAMS_DIR["TICKERS_DIR"], f'combined_info_tickers_{safe_user_choice}.csv')
        self.problematic_tickers_file = os.path.join(self.PARAMS_DIR["TICKERS_DIR"], f'problematic_tickers_{safe_user_choice}.csv')
        self.problematic_tickers = []
        self.successful_tickers = []
        self.split_rebuilds = []
        self.split_pending = []
        
    def load_tickers(self):
        ticker_data = pd.read_csv(self.config['ticker_file'])
        # Check if BRK-B is already in the list
        #if 'BRK-B' not in ticker_data['ticker'].values:
        #    # Add BRK-B manually if it's not already present
        #    new_row = pd.DataFrame({'ticker': ['BRK-B']})
        #    ticker_data = pd.concat([ticker_data, new_row], ignore_index=True)
        #    
        #    # Save updated tickers back to the CSV file
        #    ticker_data.to_csv(self.config['ticker_file'], index=False)
        #    print("Ticker BRK-B added to the list.")
        #else:
        #    print("Ticker BRK-B already exists in the list.")
        
        # Return the updated list of tickers
        return ticker_data['ticker'].tolist()

    def get_market_data(self, ticker, start_date, end_date):
        """
        Retrieve historical market data (OHLCV) for a given ticker
        
        Args:
            ticker (str): Stock ticker symbol
            start_date (str): Start date for data retrieval
            end_date (str): End date for data retrieval
            
        Returns:
            pandas.DataFrame: OHLCV data with additional market metrics
        """
        return fetch_ohlcv(ticker, start_date, end_date, interval=self.config['interval'])

    def _update_shares_and_splits(self, ticker, had_existing_data):
        """
        Real per-date shares-outstanding + split history for `ticker` (see
        market_data_io.fetch_shares_and_splits/historical_market_cap).
        Interval-agnostic real-world data, so only pulled from the daily
        ('1d') run even though MarketDataRetriever also runs for weekly/
        monthly - avoids fetching the same data 3x per ticker per pipeline
        invocation (mirrors update_data()'s existing write_file_info
        interval=='1d' gate for the same reason).

        On a ticker's first-ever fetch, pulls the full configured date
        range; afterward, only refetches once the cached file is older than
        SHARES_REFRESH_DAYS - see that constant's docstring for why a daily
        refetch would be wasteful.
        """
        if self.config['interval'] != '1d':
            return

        shares_folder = self.config['shares_folder']
        splits_folder = self.config['splits_folder']

        if had_existing_data:
            shares_file = market_data_io.shares_path(shares_folder, ticker)
            if not market_data_io.is_stale(shares_file, SHARES_REFRESH_DAYS):
                return

        shares, splits = market_data_io.fetch_shares_and_splits(
            ticker, self.config['start_date'], self.config['end_date'])
        market_data_io.write_shares_and_splits(shares_folder, splits_folder, ticker, shares, splits)

    def update_individual_stock_data(self, ticker):
        """
        Update historical market data for an individual stock
        
        Args:
            ticker (str): Stock ticker symbol
        """
        try:
            interval_str = self.config['interval'].replace("/", "")
            ticker_obj = yf.Ticker(ticker)
            # Handle both Timestamp (old yfinance) and string (new yfinance 1.1.0+)
            latest_yf_idx = ticker_obj.history(period="1d").index[0]
            if isinstance(latest_yf_idx, str):
                latest_yf_date = pd.to_datetime(latest_yf_idx).date()
            elif hasattr(latest_yf_idx, 'date'):
                latest_yf_date = latest_yf_idx.date()
            else:
                latest_yf_date = pd.to_datetime(str(latest_yf_idx)).date()

            latest_file_date = market_data_io.get_latest_date(self.config['folder'], ticker)
            had_existing_data = latest_file_date is not None
            if had_existing_data:
                # Ticker already had data on disk: consider it successful regardless of updates
                self.successful_tickers.append(ticker)
                if latest_file_date >= latest_yf_date:
                    self.logger.info(f"{ticker} not updated. Latest data already available.")
                    return
                start_date = latest_file_date + timedelta(days=1)
            else:
                start_date = self.config['start_date']

            new_data = self.get_market_data(ticker, start_date, self.config['end_date'])

            # Real shares-outstanding/splits: interval-agnostic (same real data
            # regardless of daily/weekly/monthly bars), so only fetched once per
            # ticker via the '1d' run - see the interval check inside. Failure
            # here must never block the price update below.
            if self.config.get('shares_folder') and self.config.get('splits_folder'):
                try:
                    self._update_shares_and_splits(ticker, had_existing_data)
                except Exception as e:
                    self.logger.info(f"{ticker}: shares/splits update failed - {e}")

            # Split detection: only relevant for tickers that already had prior
            # data on disk - a brand-new ticker's first-ever fetch is a single
            # already-consistent auto_adjust=True series, no discontinuity risk.
            if had_existing_data and not new_data.empty:
                split_rows = new_data[new_data['Stock Splits'] != 0]
                if not split_rows.empty:
                    audit_log_path = os.path.join(PARAMS_DIR["DATA_DIR"], "market_data", "split_events.csv")
                    result = market_data_io.check_and_handle_split(
                        self.config['folder'], ticker, self.config['interval'],
                        split_rows, market_data_io.fetch_ohlcv,
                        self.config['start_date'], self.config['end_date'],
                        audit_log_path, splits_folder=self.config.get('splits_folder'))
                    if result['status'] == 'rebuilt_ok':
                        self.split_rebuilds.append(ticker)
                    else:
                        self.split_pending.append(ticker)
                    self.successful_tickers.append(ticker)
                    return

            if not new_data.empty:
                market_data_io.write_incremental(self.config['folder'], ticker, new_data,
                                                  interval=self.config['interval'])
                self.logger.info(f"Updated data for {ticker} saved to {market_data_io.legacy_path(self.config['folder'], ticker)}")
                self.logger.info(f"Data updated for {ticker} for the period: {start_date} to {latest_yf_date}")

                self.successful_tickers.append(ticker)
            else:
                self.logger.info(f"No new data available for {ticker}")

        except Exception as e:
            print(f"Error processing {ticker}: {str(e)}")
            self.problematic_tickers.append({'ticker': ticker, 'error': str(e)})
            print(f"Added {ticker} to problematic tickers list")

    def save_problematic_tickers(self):
        """Save list of tickers that had issues during data retrieval"""
        if self.problematic_tickers:
            df = pd.DataFrame(self.problematic_tickers)
            try:
                df.to_csv(self.problematic_tickers_file, index=False)
                print(f"Problematic tickers saved to {self.problematic_tickers_file}")
            except Exception as e:
                print(f"Error saving problematic tickers: {str(e)}")
        else:
            print("No problematic tickers found.")
        print(f"Problematic tickers: {self.problematic_tickers}")

    def generate_clean_tickers_file(self):
        """Generate clean tickers file based on successful downloads"""
        if not hasattr(self, 'info_df') or self.info_df.empty:
            print("Info dataframe not initialized. Run generate_info_file() first.")
            return
    
        ok_df = pd.DataFrame(self.successful_tickers, columns=['ticker'])
        ok_full_df = self.info_df.merge(ok_df, on='ticker')
        ok_full_df = ok_full_df.drop_duplicates(subset=['ticker'])
        
        # Save 1-column (ticker-only) clean file
        safe_user_choice = str(user_choice).replace('-', '_')
        ok_file_1col = os.path.join(self.PARAMS_DIR["TICKERS_DIR"], f'combined_tickers_clean_{safe_user_choice}.csv')
        ok_full_df['ticker'].drop_duplicates().to_csv(ok_file_1col, index=False, header=['ticker'])
        print(f"Clean single-column tickers file: {ok_file_1col}")
    
        # Save full info clean file
        ok_file = os.path.join(self.PARAMS_DIR["TICKERS_DIR"], f'combined_info_tickers_clean_{safe_user_choice}.csv')
        ok_full_df.to_csv(ok_file, index=False)
        print(f"Clean tickers file: {ok_file}")

    def generate_portfolio_clean_tickers_file(self, portfolio_tickers_file=None):
        """
        Generates a clean tickers file specifically for the portfolio tickers.
        """
        from src.user_defined_data import read_user_data

        if portfolio_tickers_file is None:
            config = read_user_data()
            portfolio_tickers_file = os.path.join(config.user_input_path, 'portofolio_tickers.csv')

        portfolio_tickers_path = portfolio_tickers_file if os.path.isabs(portfolio_tickers_file) else portfolio_tickers_file
        try:
            portfolio_tickers_df = pd.read_csv(portfolio_tickers_path)
            portfolio_tickers = portfolio_tickers_df['ticker'].tolist()
        except FileNotFoundError:
            print(f"Portfolio tickers file not found at {portfolio_tickers_path}")
            return
        
        # Filter successful tickers to only include those in the portfolio
        successful_portfolio_tickers = [ticker for ticker in self.successful_tickers if ticker in portfolio_tickers]
        
        # Create a DataFrame from the successful portfolio tickers
        ok_df = pd.DataFrame(successful_portfolio_tickers, columns=['ticker'])
        
        # Check if info_df is initialized
        if not hasattr(self, 'info_df') or self.info_df.empty:
            print("Info dataframe not initialized. Run generate_info_file() first.")
            return
        
        # Merge the info DataFrame with the successful portfolio tickers
        ok_full_df = self.info_df.merge(ok_df, on='ticker', how='inner')
        ok_full_df = ok_full_df.drop_duplicates(subset=['ticker'])
        
        # Define the output file path for the portfolio clean tickers
        ok_file = os.path.join(self.PARAMS_DIR["TICKERS_DIR"], f'combined_info_tickers_clean_portfolio.csv')
        ok_full_df.to_csv(ok_file, index=False)
        print(f"Portfolio clean tickers file: {ok_file}")

    def get_stock_info(self, ticker):
        """
        Get basic stock information for metadata purposes
        
        Args:
            ticker (str): Stock ticker symbol
            
        Returns:
            dict: Basic stock information
        """
        try:
            ticker_obj = yf.Ticker(ticker)
            info = ticker_obj.info
    
            # Only fetch calendar if needed
            try:
                earnings_date = ticker_obj.calendar.get('Earnings Date', 'N/A')
                next_earnings = earnings_date[0] if isinstance(earnings_date, list) else earnings_date
            except Exception:
                next_earnings = 'N/A'
    
            return {
                'ticker': ticker,
                'symbol': ticker,
                'description': info.get('shortName', 'N/A'),
                'market_capitalization': info.get('marketCap', 'N/A'),
                'market_cap_currency': info.get('currency', 'USD'),
                'sector': info.get('sector', 'N/A'),
                'industry': info.get('industry', 'N/A'),
                'exchange': info.get('fullExchangeName', 'N/A'),
                'analyst_rating': 'N/A',  # YFinance doesn't provide this easily
                'upcoming_earnings_date': next_earnings,
                'recent_earnings_date': 'N/A',  # YFinance doesn't provide this easily
            }
        except Exception as e:
            print(f"Error fetching info for {ticker}: {str(e)}")
            return None

    def generate_info_file(self):
        """Generate metadata info file for all tickers based on configuration"""
        ticker_info_TW = self.config.get("ticker_info_TW", False)
        ticker_info_YF = self.config.get("ticker_info_YF", False)
        ticker_info_TW_file = self.config.get("ticker_info_TW_file", "tradingview_universe_info.csv")
        
        info_data = []
        
        if ticker_info_TW and ticker_info_YF:
            print("WARNING: Both ticker_info_TW and ticker_info_YF are enabled!")
            print("Using TradingView as priority source...")
            ticker_info_YF = False  # Disable YF when both are enabled
        
        if ticker_info_TW:
            print("Using TradingView ticker info from file...")
            # Load TradingView info file
            tw_info_path = os.path.join(self.PARAMS_DIR["TICKERS_DIR"], ticker_info_TW_file)
            try:
                tw_df = pd.read_csv(tw_info_path)
                # Filter to only the tickers we need
                ticker_set = set(self.tickers_list)
                tw_filtered = tw_df[tw_df['ticker'].isin(ticker_set)]
                
                # Convert TradingView format including all columns from Symbol to Recent earnings date
                for _, row in tw_filtered.iterrows():
                    info_data.append({
                        'ticker': row.get('ticker', 'N/A'),
                        'symbol': row.get('Symbol', 'N/A'),
                        'description': row.get('Description', 'N/A'),
                        'market_capitalization': row.get('Market capitalization', 'N/A'),
                        'market_cap_currency': row.get('Market capitalization - Currency', 'N/A'),
                        'sector': row.get('Sector', 'N/A'),
                        'industry': row.get('Industry', 'N/A'),
                        'exchange': row.get('Exchange', 'N/A'),
                        'analyst_rating': row.get('Analyst Rating', 'N/A'),
                        'upcoming_earnings_date': row.get('Upcoming earnings date', 'N/A'),
                        'recent_earnings_date': row.get('Recent earnings date', 'N/A'),
                    })
                
                print(f"Loaded {len(info_data)} ticker info records from TradingView file")
                
            except FileNotFoundError:
                print(f"❌ TradingView info file not found: {tw_info_path}")
                print("❌ Cannot generate info file without TradingView data when ticker_info_TW=TRUE")
            except Exception as e:
                print(f"❌ Error loading TradingView info file: {e}")
                print("❌ Cannot generate info file when TradingView source fails")
        
        elif ticker_info_YF:
            print("Using YFinance to download ticker info...")
            for ticker in self.tickers_list:
                info = self.get_stock_info(ticker)
                if info is not None:
                    info_data.append(info)
                time.sleep(0.1)  # To avoid overloading the API
        
        else:
            print("❌ Neither ticker_info_TW nor ticker_info_YF is enabled!")
            print("❌ Cannot generate info file without a data source")

        if info_data:
            self.info_df = pd.DataFrame(info_data)
            self.info_df.to_csv(self.info_file, index=False)
            print(f"Generated info file saved to {self.info_file}")
        else:
            print("No valid ticker information found. Info file not generated.")
            self.info_df = pd.DataFrame()

    def update_data(self):
        """
        Main method to update historical market data for all tickers
        """
        print("Starting to download historical market data...")
    
        ticker_count = 0
        batch_size = 100
    
        for ticker in self.tickers_list:
            self.update_individual_stock_data(ticker)
            ticker_count += 1
            time.sleep(0.2)
    
            if ticker_count % batch_size == 0:
                print(f"Processed {ticker_count} tickers. Taking a longer break...")
                time.sleep(30)
    
        self.save_problematic_tickers()
        print(f"Total problematic tickers: {len(self.problematic_tickers)}")

        if self.split_rebuilds or self.split_pending:
            print("\n" + "=" * 60)
            print("SPLIT REBUILD SUMMARY")
            print("=" * 60)
            print(f"🔀 Rebuilt: {len(self.split_rebuilds)} — {self.split_rebuilds}")
            if self.split_pending:
                print(f"⚠️  Pending (rebuild failed / will retry next run): {len(self.split_pending)} — {self.split_pending}")

        interval = self.config.get("interval", "").lower()
        write_file_info = self.config.get("write_file_info", False)
        
        if write_file_info and interval == "1d":
            print("Generating metadata info and clean info tickers (daily + flag enabled)...")
            self.generate_info_file()
    
            if hasattr(self, 'info_df') and not self.info_df.empty:
                self.generate_clean_tickers_file()
                self.generate_portfolio_clean_tickers_file()
            else:
                print("Info file not generated or empty — skipping clean info files.")
        else:
            print("Skipping metadata and info file generation (either interval ≠ '1d' or write_file_info is False)")
    
        # This section always runs - generate basic clean ticker files
        if hasattr(self, 'tickers_list'):
            if hasattr(self, 'successful_tickers') and self.successful_tickers:
                ok_df = pd.DataFrame(self.successful_tickers, columns=['ticker'])
    
                safe_user_choice = str(user_choice).replace('-', '_')
                clean_file = os.path.join(self.PARAMS_DIR["TICKERS_DIR"], f'combined_tickers_clean_{safe_user_choice}.csv')
                ok_df.drop_duplicates().to_csv(clean_file, index=False)
                print(f"Clean (1-column) tickers file written: {clean_file}")
            else:
                print("No successful_tickers found — combined_tickers_clean_<x>.csv not generated.")


def run_market_data_retrieval(config):
    """
    Main function to run historical market data retrieval
    
    Args:
        config (dict): Configuration dictionary containing:
            - interval: Data interval (1d, 1wk, etc.)
            - start_date: Start date for data collection
            - end_date: End date for data collection
            - folder: Directory to save market data files
            - ticker_file: Path to ticker CSV file
            - write_file_info: Whether to generate metadata files
    """
    retriever = MarketDataRetriever(config)
    retriever.update_data()
    _update_manifest_after_run(config, retriever)


def _update_manifest_after_run(config, retriever):
    """Keep data/gapfill/tickers_latestDate_downloads.csv current after
    EVERY slow-pipeline run, not just scripts/sync_stragglers.py's - this
    function is the one place both main.py's normal --daily/--weekly/
    --monthly flow and sync_stragglers.py funnel through, so hooking the
    manifest update here means it can't go stale just because a particular
    caller/CLI mode forgot to update it separately (see [[project-batch-
    slow-pipeline-integrity]] memory - that's exactly how it went stale
    before this fix)."""
    interval = config.get("interval")
    folder = config.get("folder")
    if interval not in ticker_manifest.SLOW_INTERVALS or not folder:
        return

    manifest = ticker_manifest.load_manifest()
    today = dt.date.today().isoformat()
    date_col = ticker_manifest.slow_date_col(interval)
    failed = {p['ticker'] for p in retriever.problematic_tickers}

    for ticker in retriever.tickers_list:
        latest_date = market_data_io.get_latest_date(folder, ticker)
        ticker_manifest.set_date(manifest, ticker, date_col, latest_date)
        ticker_manifest.record_outcome(manifest, ticker, is_success=(ticker not in failed), today=today)

    ticker_manifest.save_manifest(manifest)
    print(f"Manifest updated: {ticker_manifest.MANIFEST_PATH}")
