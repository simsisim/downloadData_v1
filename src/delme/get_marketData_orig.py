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
    def __init__(self, config):
        self.logger = logging.getLogger(__name__)
        self.config = config
        self.tickers_list = self.load_tickers()
        #self.output_file = os.path.join(config['save_location'], config['file_name'])
        #self.info_file = os.path.join(config['save_location_tickers_info'], f'info_tickers_{user_choice}.csv')
        self.PARAMS_DIR = PARAMS_DIR 
        self.info_file = os.path.join(self.PARAMS_DIR["TICKERS_DIR"], f'combined_info_tickers_{user_choice}.csv')
        self.problematic_tickers_file = os.path.join(self.PARAMS_DIR["TICKERS_DIR"], f'problematic_tickers_{user_choice}.csv')
        self.problematic_tickers = []
        self.successful_tickers = []
    def load_tickers(self):
        ticker_data = pd.read_csv(self.config['ticker_file'])
        # Check if BRK-B is already in the list
        if 'BRK-B' not in ticker_data['ticker'].values:
            # Add BRK-B manually if it's not already present
            new_row = pd.DataFrame({'ticker': ['BRK-B']})
            ticker_data = pd.concat([ticker_data, new_row], ignore_index=True)
            
            # Save updated tickers back to the CSV file
            ticker_data.to_csv(self.config['ticker_file'], index=False)
            print("Ticker BRK-B added to the list.")
        else:
            print("Ticker BRK-B already exists in the list.")
        
        # Return the updated list of tickers
        return ticker_data['ticker'].tolist()

    def get_market_data(self, ticker, start_date, end_date):
        #print(ticker)
        ticker_obj = yf.Ticker(ticker)
        #auto_adjust=True, close price is ajusted with the adj close.
        ohlc_data = ticker_obj.history(start=start_date, end=end_date, interval=self.config['interval'])#auto_adjust=True
        # Get additional info
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

#    def update_individual_stock_data(self, ticker):
#        file_path = os.path.join(self.config['save_location'], f"{ticker}.csv")
#        ticker_obj = yf.Ticker(ticker)
#        latest_yf_date = yf.Ticker(ticker).history(period="1d").index[0].date()#
#
#        if os.path.isfile(file_path):
#            existing_data = pd.read_csv(file_path, index_col='Date', parse_dates=True)
#            if not existing_data.empty:
#                latest_file_date = existing_data.index.max().date()
#                if latest_file_date >= latest_yf_date:
#                    print(f"{ticker} not updated. Latest data already available.")
#                    return
#                start_date = latest_file_date + timedelta(days=1)
#            else:
#                start_date = self.config['start_date']
#        else:
#            start_date = self.config['start_date']
#
#        new_data = self.get_market_data(ticker, start_date, self.config['end_date'])
#
#        if not new_data.empty:
#            if os.path.isfile(file_path):
#                updated_data = pd.concat([existing_data, new_data])
#                updated_data = updated_data[~updated_data.index.duplicated(keep='last')]
#            else:
#                updated_data = new_data
#            updated_data.to_csv(file_path)
#            print(f"Updated data for {ticker} saved to {file_path}")
#            print(f"Data updated for {ticker} for the period: {start_date} to {latest_yf_date}")
#        else:
#            print(f"No new data available for {ticker}")


    def update_individual_stock_data(self, ticker):
        try:
            interval_str = self.config['interval'].replace("/", "")
            file_path = os.path.join(self.config['folder'], f"{ticker}.csv")
            #file_path = os.path.join(self.PARAMS_DIR["MARKET_DATA_DIR"], f"{ticker}.csv")
            ticker_obj = yf.Ticker(ticker)
            latest_yf_date = ticker_obj.history(period="1d").index[0].date()

            if os.path.isfile(file_path):
                #If the file exists, consider it successful regardless of updates
                self.successful_tickers.append(ticker)
                existing_data = pd.read_csv(file_path, index_col='Date', parse_dates=True)
                if not existing_data.empty:
                    latest_file_date = existing_data.index.max().date()
                    if latest_file_date >= latest_yf_date:
                        #print(f"{ticker} not updated. Latest data already available.")
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
                #print(f"Updated data for {ticker} saved to {file_path}")
                #print(f"Data updated for {ticker} for the period: {start_date} to {latest_yf_date}")
                self.logger.info(f"Updated data for {ticker} saved to {file_path}")
                self.logger.info(f"Data updated for {ticker} for the period: {start_date} to {latest_yf_date}")

                self.successful_tickers.append(ticker)
            else:
                self.logger.info(f"No new data available for {ticker}")

        except Exception as e:
            print(f"Error processing {ticker}: {str(e)}")
            self.problematic_tickers.append({'ticker': ticker, 'error': str(e)})
        # Add this line to verify the ticker is added to the list
            print(f"Added {ticker} to problematic tickers list")
    #def update_data(self):
    #    print("Starting to download market data...")
    #    for ticker in self.tickers_list:
    #        self.update_individual_stock_data(ticker)
    #        time.sleep(0.5)
    #    self.generate_info_file()
    #    self.save_problematic_tickers()





    def save_problematic_tickers(self):
        if self.problematic_tickers:
            df = pd.DataFrame(self.problematic_tickers)
            try:
                df.to_csv(self.problematic_tickers_file, index=False)
                print(f"Problematic tickers saved to {self.problematic_tickers_file}")
            except Exception as e:
                print(f"Error saving problematic tickers: {str(e)}")
        else:
            print("No problematic tickers found.")
    
    # Add this line to always print the contents of problematic_tickers
        print(f"Problematic tickers: {self.problematic_tickers}")

    def generate_clean_tickers_file(self):
        if not hasattr(self, 'info_df') or self.info_df.empty:
            print("Info dataframe not initialized. Run generate_info_file() first.")
            return
    
        ok_df = pd.DataFrame(self.successful_tickers, columns=['ticker'])
        ok_full_df = self.info_df.merge(ok_df, on='ticker')
    
        #ok_file = os.path.join(self.PARAMS_DIR["TICKERS_DIR"], f'combined_info_tickers_clean_{user_choice}.csv')
        ##ok_file_1col = os.path.join(self.PARAMS_DIR["TICKERS_DIR"], f'combined_tickers_clean_{user_choice}.csv')
    
        #ok_full_df.to_csv(ok_file, index=False)
        #ok_full_df['ticker'].to_csv(ok_file, index=False, header=['ticker'])
        
            # Remove duplicates
        ok_full_df = ok_full_df.drop_duplicates(subset=['ticker'])
        # Save 1-column (ticker-only) clean file
        ok_file_1col = os.path.join(self.PARAMS_DIR["TICKERS_DIR"], f'combined_tickers_clean_{user_choice}.csv')
        ok_full_df['ticker'].drop_duplicates().to_csv(ok_file_1col, index=False, header=['ticker'])
        print(f"Clean single-column tickers file: {ok_file_1col}")
    
        # Save full info clean file
        ok_file = os.path.join(self.PARAMS_DIR["TICKERS_DIR"], f'combined_info_tickers_clean_{user_choice}.csv')
        ok_full_df.to_csv(ok_file, index=False)
        print(f"Clean tickers file: {ok_file}")


    def generate_portfolio_clean_tickers_file(self, portfolio_tickers_file='portofolio_tickers.csv'):
        """
        Generates a clean tickers file specifically for the portfolio tickers.
        """
        portfolio_tickers_path = os.path.join(self.PARAMS_DIR["TICKERS_DIR"], portfolio_tickers_file)
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
        
        # Remove duplicates
        ok_full_df = ok_full_df.drop_duplicates(subset=['ticker'])
        
        # Define the output file path for the portfolio clean tickers
        ok_file = os.path.join(self.PARAMS_DIR["TICKERS_DIR"], f'combined_info_tickers_clean_portfolio.csv')
        
        # Save the resulting DataFrame to a CSV file
        ok_full_df.to_csv(ok_file, index=False)
        
        # Print a message indicating the file has been saved
        print(f"Portfolio clean tickers file: {ok_file}")


    # def get_stock_info(self, ticker):
    #     try:
    #         ticker_obj = yf.Ticker(ticker)
    #         info = ticker_obj.info

    #     # Get next earnings date
    #         earnings_date = ticker_obj.calendar.get('Earnings Date', 'N/A')
    #         next_earnings = earnings_date[0] if isinstance(earnings_date, list) else earnings_date

    #         return {
    #             'ticker': ticker,
    #             'sector': info.get('sector', 'N/A'),
    #             'industry': info.get('industry', 'N/A'),
    #             'next_earnings': next_earnings,
    #             'marketCap': info.get('marketCap', 'N/A'),
    #             'shortName': info.get('shortName', 'N/A'),
    #            'longName': info.get('longName', 'N/A'),
    #            'exchange1': info.get('fullExchangeName', 'N/A'),
    #            'exchange2': info.get('quoteSourceName', 'N/A'),
    #         }
    #     except Exception as e:
    #         print(f"Error fetching info for {ticker}: {str(e)}")
    #         return None

    def get_stock_info(self, ticker):
        try:
            ticker_obj = yf.Ticker(ticker)
            info = ticker_obj.info  # Slow
    
            # Only fetch calendar if needed
            try:
                earnings_date = ticker_obj.calendar.get('Earnings Date', 'N/A')
                next_earnings = earnings_date[0] if isinstance(earnings_date, list) else earnings_date
            except Exception:
                next_earnings = 'N/A'
    
            return {
                'ticker': ticker,
                'sector': info.get('sector', 'N/A'),
                'industry': info.get('industry', 'N/A'),
                'next_earnings': next_earnings,
                'marketCap': info.get('marketCap', 'N/A'),
                'shortName': info.get('shortName', 'N/A'),
                'longName': info.get('longName', 'N/A'),
                'exchange1': info.get('fullExchangeName', 'N/A'),
                'exchange2': info.get('quoteSourceName', 'N/A'),
            }
        except Exception as e:
            print(f"Error fetching info for {ticker}: {str(e)}")
            return None


    def generate_info_file(self):
        info_data = []
        for ticker in self.tickers_list:
            info = self.get_stock_info(ticker)
            if info is not None:
                info_data.append(info)
            time.sleep(0.1)  # To avoid overloading the API

        if info_data:
            self.info_df = pd.DataFrame(info_data)
            self.info_df.to_csv(self.info_file, index=False)
            print(f"Generated info file saved to {self.info_file}")
        else:
            print("No valid ticker information found. Info file not generated.")
            self.info_df = pd.DataFrame()  # Initialize empty DataFrame

#    def update_data(self):
#        print("Starting to download market data...")
#        ticker_count = 0
#        batch_size = 100
#        for ticker in self.tickers_list:
#            self.update_individual_stock_data(ticker)
#            ticker_count += 1
#            time.sleep(0.5)
#        
#            if ticker_count % batch_size == 0:
#                print(f"Processed {ticker_count} tickers. Taking a longer break...")
#                time.sleep(30)
#    
#        self.generate_info_file()
#        self.save_problematic_tickers()
#    
#    # Add this line to verify the number of problematic tickers
#        print(f"Total problematic tickers: {len(self.problematic_tickers)}")


    def update_data(self):
        print("Starting to download market data...")
    
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
        ### NEW BLOCK BEGIN ###
        interval = self.config.get("interval", "").lower()
    
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
    
        ### THIS SECTION ALWAYS RUNS ###
        if hasattr(self, 'tickers_list'):
            # These depend only on successful tickers, already set
            if hasattr(self, 'successful_tickers') and self.successful_tickers:
                ok_df = pd.DataFrame(self.successful_tickers, columns=['ticker'])
    
                clean_file = os.path.join(self.PARAMS_DIR["TICKERS_DIR"], f'combined_tickers_clean_{user_choice}.csv')
                ok_df.drop_duplicates().to_csv(clean_file, index=False)
                print(f"Clean (1-column) tickers file written: {clean_file}")
            else:
                print("No successful_tickers found – combined_tickers_clean_<x>.csv not generated.")
    ### NEW BLOCK END ###




def run_market_data_retrieval(config, run_metadata=True):
    retriever = MarketDataRetriever(config)
    retriever.update_data()


#if __name__ == "__main__":
#    config = {
#        'interval': '1d',
#        'start_date': '2025-01-01',
#        'end_date': dt.datetime.now().strftime('%Y-%m-%d'),
#        'save_location': './data',
#        'file_name': 'OHLC_yfinance_data.csv',
#        'ticker_file': 'S&P500Tickers.csv'
#    }
#    run_market_data_retrieval(config)

