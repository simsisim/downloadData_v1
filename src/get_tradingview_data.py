"""
TradingView Data Updater

Processes TradingView bulk CSV files and updates individual ticker CSV files
in the market_data_tw/ directory structure.

Key Features:
- Smart sampling (5 random tickers) to determine if update needed
- Bulk CSV parsing and distribution to individual ticker files
- Date extraction from TW filenames
- Backfill support for historical TW files
- Problematic ticker tracking
- Timezone-aware date handling for mixed timezone files
"""

import pandas as pd
import os
import random
import re
from datetime import datetime
from pathlib import Path
import logging


class TradingViewDataRetriever:
    """
    Retrieves and processes TradingView bulk data files.
    Updates individual ticker CSV files with new OHLCV data.
    """

    def __init__(self, config):
        """
        Initialize TradingView data retriever

        Args:
            config: Configuration dict with paths and settings
        """
        self.config = config
        self.logger = logging.getLogger(__name__)
        self.problematic_tickers = []
        self.successful_updates = 0
        self.skipped_updates = 0

        # Directory paths
        self.tw_files_dir = config.get('TW_FILES_DIR', 'data/tw_files')
        self.market_data_tw_dir = config.get('MARKET_DATA_TW_DIR', 'data/market_data_tw')

        # Ensure TW files subdirectories exist
        for timeframe in ['daily', 'weekly', 'monthly']:
            tw_subdir = os.path.join(self.tw_files_dir, timeframe)
            os.makedirs(tw_subdir, exist_ok=True)

        # Load ticker universe
        self.ticker_universe = self._load_ticker_universe()

    def _load_ticker_universe(self):
        """Load ticker universe from existing configuration"""
        # Use existing combined_tickers file
        ticker_file = self.config.get('ticker_file')
        if ticker_file and os.path.exists(ticker_file):
            df = pd.read_csv(ticker_file)
            tickers = df['ticker'].tolist()
            print(f"   Loaded {len(tickers)} tickers from universe file")
            return tickers
        else:
            self.logger.warning(f"Ticker universe file not found: {ticker_file}")
            return []

    def find_all_tw_files_for_latest_date(self, timeframe):
        """
        Find ALL TradingView bulk files for the most recent date

        This handles multiple files per date (e.g., separate stocks and ETFs files)

        Args:
            timeframe: 'daily', 'weekly', or 'monthly'

        Returns:
            list: List of tuples [(file_date, file_path, filename), ...] for the latest date
                  Returns empty list if no files found
        """
        tw_dir = os.path.join(self.tw_files_dir, timeframe)

        if not os.path.exists(tw_dir):
            self.logger.warning(f"TW files directory not found: {tw_dir}")
            return []

        # Pattern: any file with YYYY-MM-DD.csv
        pattern = r'(\d{4}-\d{2}-\d{2})'

        files = os.listdir(tw_dir)
        tw_files = []

        for filename in files:
            if not filename.endswith('.csv'):
                continue
            match = re.search(pattern, filename)
            if match:
                date_str = match.group(1)
                file_path = os.path.join(tw_dir, filename)
                file_date = datetime.strptime(date_str, '%Y-%m-%d').date()
                tw_files.append((file_date, file_path, filename))

        if not tw_files:
            self.logger.warning(f"No TW files found in {tw_dir}")
            return []

        # Find the latest date
        latest_date = max(tw_files, key=lambda x: x[0])[0]

        # Return ALL files with the latest date
        files_for_latest_date = [f for f in tw_files if f[0] == latest_date]

        print(f"   Latest date: {latest_date}")
        print(f"   Files found: {len(files_for_latest_date)}")
        for _, _, filename in files_for_latest_date:
            print(f"      - {filename}")

        return files_for_latest_date

    def extract_date_from_filename(self, filepath):
        """
        Extract date from TW filename

        Note: This method is kept for backward compatibility but is no longer
        used internally. The new find_all_tw_files_for_latest_date() method
        returns the date directly.

        Args:
            filepath: Path to TW file

        Returns:
            datetime.date: Extracted date
        """
        filename = os.path.basename(filepath)
        pattern = r'(\d{4}-\d{2}-\d{2})'
        match = re.search(pattern, filename)

        if match:
            date_str = match.group(1)
            return datetime.strptime(date_str, '%Y-%m-%d').date()
        else:
            raise ValueError(f"Could not extract date from filename: {filename}")

    def should_update(self, tw_file_date, timeframe):
        """
        Smart sampling to determine if update is needed

        Args:
            tw_file_date: Date from TW filename
            timeframe: 'daily', 'weekly', or 'monthly'

        Returns:
            bool: True if update needed
        """
        if not self.ticker_universe:
            self.logger.warning("Empty ticker universe - skipping update")
            return False

        # Sample size: 5 tickers or less if universe is smaller
        sample_size = min(5, len(self.ticker_universe))
        sample_tickers = random.sample(self.ticker_universe, sample_size)

        print(f"\n📊 Smart Sampling: Checking {sample_size} random tickers...")
        print(f"   Sample: {', '.join(sample_tickers)}")

        behind_count = 0
        current_count = 0

        for ticker in sample_tickers:
            ticker_file = os.path.join(
                self.market_data_tw_dir,
                timeframe,
                f"{ticker}.csv"
            )

            if not os.path.exists(ticker_file):
                print(f"   ❌ {ticker}: File not found")
                behind_count += 1
                continue

            try:
                # Read WITHOUT parse_dates to avoid mixed timezone issues
                df = pd.read_csv(ticker_file)

                if df.empty:
                    print(f"   ⚠️  {ticker}: Empty file")
                    behind_count += 1
                    continue

                # Get last date as string and extract just the date part
                last_date_str = df['Date'].iloc[-1]
                # Extract YYYY-MM-DD from "2025-09-05 00:00:00-04:00"
                last_date_only = last_date_str[:10]

                # Convert TW file date to string for comparison
                tw_date_str = tw_file_date.strftime('%Y-%m-%d')

                if tw_date_str > last_date_only:
                    print(f"   🔄 {ticker}: Behind (file: {last_date_only}, TW: {tw_date_str})")
                    behind_count += 1
                else:
                    print(f"   ✅ {ticker}: Current (file: {last_date_only})")
                    current_count += 1

            except Exception as e:
                print(f"   ⚠️  {ticker}: Error - {str(e)}")
                behind_count += 1

        # Decision
        print(f"\n📈 Sampling Results:")
        print(f"   Behind/Missing: {behind_count}/{sample_size}")
        print(f"   Current: {current_count}/{sample_size}")

        if behind_count > 0:
            print(f"   🚀 Decision: UPDATE NEEDED\n")
            return True
        else:
            print(f"   ⏭️  Decision: SKIP UPDATE (all current)\n")
            return False

    def parse_tw_bulk_file(self, filepath, file_date):
        """
        Parse TradingView bulk CSV file

        Args:
            filepath: Path to TW bulk CSV
            file_date: Date to assign to all rows

        Returns:
            dict: {ticker: {Date, Open, High, Low, Close, Volume}}
        """
        print(f"📖 Parsing TW bulk file...")

        try:
            df = pd.read_csv(filepath)

            # Strip whitespace from column names
            df.columns = df.columns.str.strip()

            print(f"   Loaded {len(df)} rows from TW file")

            # Validate required columns exist
            required_columns = ['Symbol', 'Open 1 day', 'High 1 day', 'Low 1 day', 'Price', 'Volume 1 day']
            missing_cols = [col for col in required_columns if col not in df.columns]

            if missing_cols:
                print(f"   ❌ Missing required columns: {missing_cols}")
                print(f"   Available columns: {list(df.columns[:10])}...")
                return {}

            ticker_data = {}

            for idx, row in df.iterrows():
                ticker = row.get('Symbol', None)
                if pd.isna(ticker):
                    continue

                # Clean ticker
                ticker = str(ticker).strip()
                ticker = ticker.replace('.', '-')  # BRK.A → BRK-A

                # Skip tickers with slashes (preferred shares)
                if '/' in ticker:
                    continue

                # Extract OHLCV data (using exact column names)
                try:
                    # Check for NaN values
                    if pd.isna(row['Open 1 day']) or pd.isna(row['Price']) or pd.isna(row['Volume 1 day']):
                        continue

                    ticker_data[ticker] = {
                        'Date': file_date,
                        'Open': float(row['Open 1 day']),
                        'High': float(row['High 1 day']),
                        'Low': float(row['Low 1 day']),
                        'Close': float(row['Price']),  # TW uses "Price" for Close
                        'Volume': int(float(row['Volume 1 day']))
                    }
                except (KeyError, ValueError, TypeError) as e:
                    continue

            print(f"   Successfully parsed {len(ticker_data)} valid tickers")
            return ticker_data

        except Exception as e:
            self.logger.error(f"Error parsing TW file: {e}")
            print(f"   ❌ Error parsing file: {e}")
            return {}

    def _extract_timezone(self, date_str):
        """
        Extract timezone from date string

        Args:
            date_str: Date string like "2025-09-05 00:00:00-04:00"

        Returns:
            str: Timezone like "-04:00" or default "-05:00"
        """
        match = re.search(r'([+-]\d{2}:\d{2})$', str(date_str))
        if match:
            return match.group(1)
        return '-05:00'  # Default to EST

    def _format_date_with_timezone(self, date_obj, timezone):
        """
        Format date with timezone

        Args:
            date_obj: datetime.date object
            timezone: Timezone string like "-04:00"

        Returns:
            str: Formatted date like "2025-10-01 00:00:00-04:00"
        """
        if isinstance(date_obj, str):
            # Already a string, just ensure it has timezone
            if timezone in date_obj:
                return date_obj
            date_str = date_obj[:10] if len(date_obj) >= 10 else date_obj
        else:
            # Convert date object to string
            date_str = date_obj.strftime('%Y-%m-%d')

        return f"{date_str} 00:00:00{timezone}"

    def update_ticker_file(self, ticker, new_data, timeframe):
        """
        Update individual ticker CSV file with new data

        Args:
            ticker: Ticker symbol
            new_data: Dict with Date, OHLCV data
            timeframe: 'daily', 'weekly', or 'monthly'

        Returns:
            bool: True if successful
        """
        ticker_file = os.path.join(
            self.market_data_tw_dir,
            timeframe,
            f"{ticker}.csv"
        )

        try:
            if os.path.exists(ticker_file):
                # Read existing data WITHOUT parse_dates to avoid mixed timezone issues
                existing_df = pd.read_csv(ticker_file)

                # Get last date to extract timezone
                last_date_str = existing_df['Date'].iloc[-1]

                # Extract timezone from last date string (e.g., "2025-09-05 00:00:00-04:00")
                timezone = self._extract_timezone(last_date_str)

                # Format new TW date with same timezone as existing data
                tw_date_str = self._format_date_with_timezone(new_data['Date'], timezone)

                # Check if date already exists (simple string comparison)
                if tw_date_str in existing_df['Date'].values:
                    self.skipped_updates += 1
                    return True  # Date already exists, skip

                # Create new row with timezone-formatted date
                new_data_with_tz = new_data.copy()
                new_data_with_tz['Date'] = tw_date_str
                new_row = pd.DataFrame([new_data_with_tz])

                # Append new row
                updated_df = pd.concat([existing_df, new_row], ignore_index=True)

                # Remove duplicates (keep last)
                updated_df = updated_df.drop_duplicates(subset=['Date'], keep='last')

                # Sort by date (ISO format strings sort correctly)
                updated_df = updated_df.sort_values('Date')

            else:
                # Create new file - use default timezone
                timezone = '-05:00'  # Default to EST
                tw_date_str = self._format_date_with_timezone(new_data['Date'], timezone)

                new_data_with_tz = new_data.copy()
                new_data_with_tz['Date'] = tw_date_str
                updated_df = pd.DataFrame([new_data_with_tz])

            # Save to CSV
            updated_df.to_csv(ticker_file, index=False)
            self.successful_updates += 1
            return True

        except Exception as e:
            self.logger.error(f"Error updating {ticker}: {e}")
            self.problematic_tickers.append({
                'ticker': ticker,
                'error': str(e),
                'timeframe': timeframe
            })
            return False

    def update_from_tw_files(self, timeframe):
        """
        Main update process for a timeframe

        Handles multiple TW files for the same date (e.g., separate stocks and ETFs files)

        Args:
            timeframe: 'daily', 'weekly', or 'monthly'
        """
        print(f"\n{'='*60}")
        print(f"TRADINGVIEW DATA UPDATE - {timeframe.upper()}")
        print(f"{'='*60}\n")

        # Step 1: Find ALL TW files for latest date
        tw_files_list = self.find_all_tw_files_for_latest_date(timeframe)
        if not tw_files_list:
            print(f"❌ No TW files found for {timeframe} - skipping\n")
            return

        # Step 2: Extract date (same for all files)
        tw_file_date = tw_files_list[0][0]
        print(f"\n📅 TW File Date: {tw_file_date}")

        # Step 3: Smart sampling - check if update is needed
        if not self.should_update(tw_file_date, timeframe):
            print(f"⏭️  Skipping {timeframe} update - all sampled tickers are current\n")
            return

        # Step 4: Parse ALL TW bulk files and merge ticker data
        print(f"\n📖 Parsing TW bulk files...")
        all_ticker_data = {}

        for file_date, file_path, filename in tw_files_list:
            print(f"\n   Processing: {filename}")
            ticker_data = self.parse_tw_bulk_file(file_path, file_date)

            if not ticker_data:
                print(f"   ⚠️  No valid data extracted from {filename}")
                continue

            # Merge into master dictionary
            all_ticker_data.update(ticker_data)
            print(f"   Running total: {len(all_ticker_data)} unique tickers")

        if not all_ticker_data:
            print(f"\n❌ No valid ticker data parsed from any file\n")
            return

        print(f"\n✅ Total unique tickers parsed: {len(all_ticker_data)}")

        # Step 5: Update ticker files (only for tickers in universe)
        print(f"\n🔄 Updating ticker files...")

        universe_set = set(self.ticker_universe)
        tickers_to_update = [t for t in all_ticker_data.keys() if t in universe_set]

        print(f"   Tickers in universe: {len(universe_set)}")
        print(f"   Tickers to update: {len(tickers_to_update)}")

        self.successful_updates = 0
        self.skipped_updates = 0
        self.problematic_tickers = []

        # Update with progress indicator
        total = len(tickers_to_update)
        for idx, ticker in enumerate(tickers_to_update, 1):
            self.update_ticker_file(ticker, all_ticker_data[ticker], timeframe)

            # Show progress every 1000 tickers
            if idx % 1000 == 0:
                print(f"   Progress: {idx}/{total} tickers...")

        # Step 6: Summary
        print(f"\n✅ Update Complete:")
        print(f"   Files processed: {len(tw_files_list)}")
        print(f"   New/Updated: {self.successful_updates}")
        print(f"   Already current: {self.skipped_updates}")
        print(f"   Problematic: {len(self.problematic_tickers)}")

        # Save problematic tickers
        if self.problematic_tickers:
            self.save_problematic_tickers(timeframe)

        print()

    def save_problematic_tickers(self, timeframe):
        """Save problematic tickers to CSV"""
        if not self.problematic_tickers:
            return

        # Get tickers directory from config
        tickers_dir = self.config.get('TICKERS_DIR', 'data/tickers')
        output_file = os.path.join(
            tickers_dir,
            f'problematic_tickers_tw_{timeframe}.csv'
        )

        df = pd.DataFrame(self.problematic_tickers)
        df.to_csv(output_file, index=False)
        print(f"   📝 Problematic tickers saved: {output_file}")


def run_tradingview_update(config, timeframe):
    """
    Main function to run TradingView data update

    Args:
        config: Configuration dict
        timeframe: 'daily', 'weekly', or 'monthly'
    """
    retriever = TradingViewDataRetriever(config)
    retriever.update_from_tw_files(timeframe)
