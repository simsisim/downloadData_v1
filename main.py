import logging
import os 
from datetime import datetime, timedelta
from src.get_marketData import run_market_data_retrieval
from src.get_tickers import TickerRetriever
from src.config import get_ticker_files, user_choice
from src.config import setup_directories, PARAMS_DIR
from src.combined_tickers import combine_tickers
from src.get_marketData import run_market_data_retrieval
import yfinance as yf



def main():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    # all messages are suppress
    logging.getLogger().setLevel(logging.CRITICAL)
    setup_directories()# Initialize directories via config
    retriever = TickerRetriever()
    retriever.fetch_and_save_all()
    try:
        print('Testing yfinance is working ....download APPL data')
        test = yf.Ticker('AAPL')
        #cd ..print(test.info)
        data = test.history(period='3d')

        
        if data.empty:
            print("Error: No data returned from yfinance. Please check your internet connection or update yfinance.")
            exit(1)
        
        print(data['Close'])  # Print closing prices
        print(data['Volume'])
        # Print the exchange of the ticker
        print("\nExchange of the Ticker:")
        print(test.info['fullExchangeName'])
    except Exception as e:
        print(f"An error occurred while testing yfinance: {e}")
        print("Please update yfinance or check your internet connection.")
        exit(1)
    print('yfinace is working OK.')
    ticker_files = get_ticker_files()
    
    # Always include indexes tickers
    if 'indexes_tickers.csv' not in ticker_files:
        ticker_files.append('indexes_tickers.csv')
    # Always include portofolio tickers
    if 'portofolio_tickers.csv' not in ticker_files:
        ticker_files.append('portofolio_tickers.csv')
    
    combined_file = combine_tickers(ticker_files, PARAMS_DIR)

    params = {
        'interval': '1d',
        'start_date': '2023-11-30',
        'end_date': datetime.now().strftime('%Y-%m-%d'),#'2023-11-31'#, (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d'), # datetime.now().strftime('%Y-%m-%d'),
        #'save_location': './data/market_data',
        #'save_location_tickers_info': './data/tickers',
        'ticker_file': combined_file
    }

    logging.info(f"Downloading data for combined tickers from files: {', '.join(ticker_files)}")
    run_market_data_retrieval(params)

if __name__ == "__main__":
    main()

