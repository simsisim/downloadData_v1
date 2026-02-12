import yfinance as yf
import pandas as pd
import datetime as dt
from datetime import timedelta
import time
import os
from src.config import user_choice
from src.config import PARAMS_DIR
import logging


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
        ticker_obj = yf.Ticker(ticker)
        ohlc_data = ticker_obj.history(start=start_date, end=end_date, interval=self.config['interval'])
        
        # Get additional info for market context
        info = ticker_obj.info
        additional_params = [
            'volume', 'averageDailyVolume10Day', 'fiftyTwoWeekHigh', 'fiftyTwoWeekLow',
            'fiftyDayAverage', 'twoHundredDayAverage', 'marketCap', 'industry', 'sector', 'exchange'
        ]
    
        for param in additional_params:
            if param in info:
                ohlc_data[param] = info[param]
        ohlc_data['Symbol'] = ticker
        return ohlc_data

    def update_individual_stock_data(self, ticker):
        """
        Update historical market data for an individual stock
        
        Args:
            ticker (str): Stock ticker symbol
        """
        try:
            interval_str = self.config['interval'].replace("/", "")
            file_path = os.path.join(self.config['folder'], f"{ticker}.csv")
            ticker_obj = yf.Ticker(ticker)
            # Handle both Timestamp (old yfinance) and string (new yfinance 1.1.0+)
            latest_yf_idx = ticker_obj.history(period="1d").index[0]
            if isinstance(latest_yf_idx, str):
                latest_yf_date = pd.to_datetime(latest_yf_idx).date()
            elif hasattr(latest_yf_idx, 'date'):
                latest_yf_date = latest_yf_idx.date()
            else:
                latest_yf_date = pd.to_datetime(str(latest_yf_idx)).date()

            if os.path.isfile(file_path):
                # If the file exists, consider it successful regardless of updates
                self.successful_tickers.append(ticker)
                existing_data = pd.read_csv(file_path, index_col='Date', parse_dates=True)
                if not existing_data.empty:
                    # Handle both Timestamp and string date formats
                    latest_file_idx = existing_data.index.max()
                    if isinstance(latest_file_idx, str):
                        latest_file_date = pd.to_datetime(latest_file_idx).date()
                    elif hasattr(latest_file_idx, 'date'):
                        latest_file_date = latest_file_idx.date()
                    else:
                        latest_file_date = pd.to_datetime(str(latest_file_idx)).date()
                    if latest_file_date >= latest_yf_date:
                        self.logger.info(f"{ticker} not updated. Latest data already available.")
                        return
                    start_date = latest_file_date + timedelta(days=1)
                else:
                    start_date = self.config['start_date']
            else:
                start_date = self.config['start_date']

            new_data = self.get_market_data(ticker, start_date, self.config['end_date'])

            if not new_data.empty:
                if os.path.isfile(file_path):
                    updated_data = pd.concat([existing_data, new_data])
                    updated_data = updated_data[~updated_data.index.duplicated(keep='last')]
                else:
                    updated_data = new_data
                updated_data.to_csv(file_path)
                self.logger.info(f"Updated data for {ticker} saved to {file_path}")
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
