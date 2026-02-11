import ftplib
import re
import csv
import pandas as pd
import os

class TickerRetriever:
    #def __init__(self):
    #    os.makedirs('./tickers', exist_ok=True)
    #    self.sp500_file_path = "sp500_tickers.csv"
    #    self.nasdaq100_file_path = "nasdaq100_tickers.csv"
    #    self.iwm1000_file_path = "iwm1000_tickers.csv"
    #    self.nasdaq_all_file_path = "nasdaq_all_tickers.csv"
    #    self.combined_file_path = "combined_tickers.csv"
    #    self.ftp_server = "ftp.nasdaqtrader.com"
    #    self.remote_file_path = "/symboldirectory/nasdaqtraded.txt"
    #    self.local_file_path = "nasdaqtraded.txt"
    #    self.indexes_file_path  = "indexes_tickers.csv"

    def __init__(self, tickers_folder='data/tickers'):
        self.tickers_folder = tickers_folder
        os.makedirs(f'./{self.tickers_folder}', exist_ok=True)
        self.sp500_file_path = os.path.join(self.tickers_folder, "sp500_tickers.csv")
        self.sp600_file_path = os.path.join(self.tickers_folder, "sp600_tickers.csv")
        self.nasdaq100_file_path = os.path.join(self.tickers_folder, "nasdaq100_tickers.csv")
        self.iwm1000_file_path = os.path.join(self.tickers_folder, "iwm1000_tickers.csv")
        self.nasdaq_all_file_path = os.path.join(self.tickers_folder, "nasdaq_all_tickers.csv")
        #self.combined_file_path = os.path.join(self.tickers_folder, "combined_tickers.csv")
        self.indexes_file_path = os.path.join(self.tickers_folder, "indexes_tickers.csv")
        self.portofolio_file_path = os.path.join(self.tickers_folder, "portofolio_tickers.csv")
        self.tradingview_universe_file_path = os.path.join(self.tickers_folder, "tradingview_universe.csv") 
    
        self.ftp_server = "ftp.nasdaqtrader.com"
        self.remote_file_path = "/symboldirectory/nasdaqtraded.txt"
        self.local_file_path = os.path.join(self.tickers_folder, "nasdaqtraded.txt")



    def download_nasdaq_file(self):
        ftp = ftplib.FTP(self.ftp_server)
        ftp.login()
        ftp.sendcmd("TYPE i")
        with open(self.local_file_path, 'wb') as local_file:
            ftp.retrbinary(f"RETR {self.remote_file_path}", local_file.write)
        ftp.quit()
        print(f"File downloaded successfully to {self.local_file_path}")

    def get_nasdaq_all_tickers(self):
        tickers = {}
        with open(self.local_file_path, 'r') as file:
            results = file.readlines()
        for entry in results[1:]:
            values = entry.strip().split('|')
            if len(values) > 7:
                ticker = values[1]
                if re.match(r'^[A-Z]+$', ticker) and values[5] == "N" and values[7] == "N":
                    tickers[ticker] = {
                        "ticker": ticker,
                        "sector": "UNKNOWN",
                        "industry": "UNKNOWN",
                        "universe": self.exchange_from_symbol(values[3])
                    }
        return list(tickers.keys())

    @staticmethod
    def exchange_from_symbol(symbol):
        if symbol == 'Q':
            return 'NASDAQ'
        elif symbol == 'N':
            return 'NYSE'
        else:
            return 'OTHER'

    def get_sp500_tickers(self):
        url = 'http://en.wikipedia.org/wiki/List_of_S%26P_500_companies'
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
        table = pd.read_html(url, storage_options=headers)[0]
        return table['Symbol'].tolist()
    
    def get_sp600_tickers(self):
        url = 'https://en.wikipedia.org/wiki/List_of_S%26P_600_companies'
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
        table = pd.read_html(url, storage_options=headers)[0]
        return table['Symbol'].tolist()
    

    def get_nasdaq100_tickers(self):
        url = 'https://en.wikipedia.org/wiki/Nasdaq-100'
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
        table = pd.read_html(url, storage_options=headers)[4]
        return table['Ticker'].tolist()

    def get_iwm1000_tickers(self):
        url = 'https://en.wikipedia.org/wiki/Russell_1000_Index'
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
        table = pd.read_html(url, storage_options=headers)[3]
        return table['Symbol'].tolist()
              
    def get_indexes_tickers(self):
       file_path_manual = 'indexes_tickers_manual.csv'
       table = pd.read_csv(file_path_manual)
       return table['ticker'].tolist() 
   
    def get_portofolio_tickers(self):
       from src.user_defined_data import read_user_data
       config = read_user_data()
       file_path_manual = os.path.join(config.user_input_path, 'portofolio_tickers.csv')
       table = pd.read_csv(file_path_manual)
       return table['ticker'].tolist() 

    def get_tradingview_universe_tickers(self):
       from src.user_defined_data import read_user_data
       config = read_user_data()
       file_path_manual = os.path.join(config.user_input_path, config.tw_universe_file)
       table = pd.read_csv(file_path_manual)
       
       # Clean ticker symbols and create info files
       cleaned_data = []
       cleaned_tickers = []
       
       for index, row in table.iterrows():
           ticker_str = str(row['Symbol']).strip()
           
           # Skip tickers containing / or \ symbols
           if '/' in ticker_str or '\\' in ticker_str:
               print(f"Removing ticker with slash: {ticker_str}")
               continue
           
           # Replace dots with hyphens (e.g., BRK.A -> BRK-A)
           original_ticker = ticker_str
           if '.' in ticker_str:
               ticker_str = ticker_str.replace('.', '-')
               print(f"Converting ticker: {original_ticker} -> {ticker_str}")
           
           # Update the row with cleaned ticker
           cleaned_row = row.copy()
           cleaned_row['ticker'] = ticker_str
           cleaned_data.append(cleaned_row)
           cleaned_tickers.append(ticker_str)
       
       # Create cleaned DataFrame
       cleaned_df = pd.DataFrame(cleaned_data)
       
       # Save tradingview_universe_info.csv (copy with cleaned tickers)
       tradingview_info_path = os.path.join(self.tickers_folder, 'tradingview_universe_info.csv')
       cleaned_df.to_csv(tradingview_info_path, index=False)
       print(f"Saved tradingview info to: {tradingview_info_path}")
       
       # Store cleaned TradingView data for later use
       self.tradingview_data = cleaned_df
       
       print(f"Original tickers: {len(table)}, After cleaning: {len(cleaned_tickers)}")
       return cleaned_tickers
   
    def _convert_to_yahoo_format(self, tradingview_df):
   #    """Convert TradingView format to Yahoo Finance info format"""
       yahoo_format = []
       
       for _, row in tradingview_df.iterrows():
           yahoo_row = {
               'ticker': row['Symbol'],
               'longName': row['Description'],
               'sector': row['Sector'],
               'industry': row['Industry'],
               'exchange': row['Exchange'],
               'marketCap': row['Market capitalization'] if pd.notna(row['Market capitalization']) else 'N/A',
               'upcoming earnings': row['Upcoming earnings date'] if pd.notna(row['Upcoming earnings date']) else 'N/A',
               'recent earnings': row['Recent earnings date'] if pd.notna(row['Recent earnings date']) else 'N/A',
               # Add other standard Yahoo fields with default values
               #'currency': 'USD',
               #'country': 'US',
               #'website': 'N/A',
               #'longBusinessSummary': row['description']
           }
           yahoo_format.append(yahoo_row)
       
       return pd.DataFrame(yahoo_format)
       
    def generate_combined_info_from_tradingview(self, final_ticker_list, user_choice):
        """Generate combined_info_tickers file using TradingView data for any user choice"""
        if not hasattr(self, 'tradingview_data') or self.tradingview_data is None:
            print("Warning: No TradingView data available. Skipping info file generation.")
            return
            
        # Filter TradingView data to match only the tickers in final_ticker_list
        final_tickers_set = set(final_ticker_list)
        filtered_tradingview = self.tradingview_data[
            self.tradingview_data['ticker'].isin(final_tickers_set)
        ]
        
        if len(filtered_tradingview) == 0:
            print(f"Warning: No matching tickers found in TradingView data for user_choice {user_choice}")
            return
            
        # Generate combined_info_tickers file  
        safe_user_choice = str(user_choice).replace('-', '_')
        combined_info_path = os.path.join(self.tickers_folder, f'combined_info_tickers_{safe_user_choice}.csv')
        yahoo_format_df = self._convert_to_yahoo_format(filtered_tradingview)
        yahoo_format_df.to_csv(combined_info_path, index=False)
        
        print(f"Generated combined_info_tickers_{user_choice}.csv with {len(yahoo_format_df)} tickers from TradingView data")
        print(f"Saved to: {combined_info_path}")

    def _get_current_ticker_files(self, user_choice):
        """Get the ticker files for the current user choice. Supports dash-separated combinations."""
        # Get filenames from centralized config (avoiding hard-coding)
        from src.user_defined_data import _get_default_ticker_filenames
        default_filenames = _get_default_ticker_filenames()
        
        # Define ticker groups using centralized filenames
        group_files = {group_id: [filename] for group_id, filename in default_filenames.items()}

        # Parse ticker choice (handle both string and int)
        ticker_choice_str = str(user_choice).strip()
        
        try:
            # Split by dash to get individual group IDs
            group_ids = [int(id_str.strip()) for id_str in ticker_choice_str.split('-')]
        except ValueError:
            print(f"Warning: Invalid ticker_choice format: '{ticker_choice_str}'. Using default group 2.")
            return group_files.get(2, [])

        # Validate all group IDs and combine files
        combined_files = []
        for group_id in group_ids:
            if group_id in group_files:
                for file in group_files[group_id]:
                    if file not in combined_files:
                        combined_files.append(file)
            else:
                print(f"Warning: Invalid group ID: {group_id}. Valid groups are 0-8.")

        return combined_files

    def save_tickers(self, tickers, file_path):
        df = pd.DataFrame({'ticker': tickers})
        df.to_csv(file_path, index=False)
        print(f'Saved tickers to {file_path}')


            
    def fetch_and_save_all(self):

        sp500_tickers = self.get_sp500_tickers()
        sp600_tickers = self.get_sp600_tickers()
        nasdaq100_tickers = self.get_nasdaq100_tickers()
        iwm1000_tickers = self.get_iwm1000_tickers()
        indexes_tickers = self.get_indexes_tickers()
        portofolio_tickers = self.get_portofolio_tickers()
        tradingview_universe_tickers = self.get_tradingview_universe_tickers()
        self.download_nasdaq_file()
        nasdaq_all_tickers = self.get_nasdaq_all_tickers()
       
           #print(f'Saved index tickers to {self.indexes_file_path}')

        self.save_tickers(sp500_tickers, self.sp500_file_path)
        self.save_tickers(sp600_tickers, self.sp500_file_path)
        self.save_tickers(nasdaq100_tickers, self.nasdaq100_file_path)
        self.save_tickers(iwm1000_tickers, self.iwm1000_file_path)
        self.save_tickers(nasdaq_all_tickers, self.nasdaq_all_file_path)
        self.save_tickers(indexes_tickers, self.indexes_file_path)       
        self.save_tickers(portofolio_tickers, self.portofolio_file_path)       
        self.save_tickers(tradingview_universe_tickers, self.tradingview_universe_file_path)
        sp500Nasdaq_tickers = list(set(sp500_tickers + nasdaq100_tickers))
        #self.save_tickers(sp500Nasdaq_tickers, self.combined_file_path)
        
        # Generate combined_info_tickers file from TradingView data for any user_choice
        from src.config import user_choice
        from src.combined_tickers import combine_tickers
        
        # Get the final combined ticker list that will be used
        ticker_files = self._get_current_ticker_files(user_choice)
        if ticker_files:
            combined_file = combine_tickers(ticker_files, {'TICKERS_DIR': self.tickers_folder})
            
            # Read the final combined ticker list
            if os.path.exists(combined_file):
                final_tickers_df = pd.read_csv(combined_file)
                final_ticker_list = final_tickers_df['ticker'].tolist()
                
                # Generate info file from TradingView data
                self.generate_combined_info_from_tradingview(final_ticker_list, user_choice)

