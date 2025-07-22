# Define a global variable for the user's choice
import os
from src.user_defined_data import read_user_data

# Directory configuration
PARAMS_DIR = {
    "DATA_DIR": "data",
    "TICKERS_DIR": os.path.join("data", "tickers"),
    "MARKET_DATA_DIR": os.path.join("data", "market_data")
}

def setup_directories():
    """Create required directories if they don't exist."""
    os.makedirs(PARAMS_DIR["DATA_DIR"], exist_ok=True)
    os.makedirs(PARAMS_DIR["TICKERS_DIR"], exist_ok=True)
    os.makedirs(PARAMS_DIR["MARKET_DATA_DIR"], exist_ok=True)

# Generate filenames (example)
#TICKER_FILE = os.path.join(PARAMS_DIR["TICKERS_DIR"], "combined_tickers.csv")

user_choice = read_user_data()
def get_ticker_files():
    """
    Returns a list of ticker files based on the user's choice.
    """
    #global user_choice  # Declare the variable as global to modify it

    files = {
        0: ['portofolio_tickers.csv'],
        1: ['sp500_tickers.csv'],
        2: ['nasdaq100_tickers.csv'],
        3: ['nasdaq_all_tickers.csv'],
        4: ['iwm1000_tickers.csv'],
        5: ['sp500_tickers.csv', 'nasdaq100_tickers.csv'],
        6: ['sp500_tickers.csv', 'nasdaq_all_tickers.csv'],
        7: ['sp500_tickers.csv', 'iwm1000_tickers.csv'],
        8: ['nasdaq100_tickers.csv', 'nasdaq_all_tickers.csv'],
        9: ['nasdaq100_tickers.csv', 'iwm1000_tickers.csv'],
        10: ['nasdaq_all_tickers.csv', 'iwm1000_tickers.csv'],
        11: ['sp500_tickers.csv', 'nasdaq100_tickers.csv', 'nasdaq_all_tickers.csv'],
        12: ['sp500_tickers.csv', 'nasdaq100_tickers.csv', 'iwm1000_tickers.csv'],
        13: ['sp500_tickers.csv', 'nasdaq_all_tickers.csv', 'iwm1000_tickers.csv'],
        14: ['nasdaq100_tickers.csv', 'nasdaq_all_tickers.csv', 'iwm1000_tickers.csv'],
        15: ['sp500_tickers.csv', 'nasdaq100_tickers.csv', 'iwm1000_tickers.csv','nasdaq_all_tickers.csv'],
        16: ['indexes_tickers.csv']
    }

    # Ensure the choice is valid
    if user_choice not in files:
        raise ValueError("Invalid choice. Please choose a number between 1 and 16.")

    # Add 'index_tickers.csv' to the list of files
    files[user_choice]#.append('indexes_tickers.csv')
    return files[user_choice]


