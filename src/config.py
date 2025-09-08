# Define a global variable for the user's choice
import os
from pathlib import Path
from src.user_defined_data import read_user_data_legacy, read_user_data, _get_default_ticker_filenames

# Directory configuration
PARAMS_DIR = {
    "DATA_DIR": "data",
    "TICKERS_DIR": os.path.join("data", "tickers"),
    "MARKET_DATA_DIR_1d": os.path.join("data", "market_data/daily/"),
    "MARKET_DATA_DIR_1wk": os.path.join("data", "market_data/weekly/"),
    "MARKET_DATA_DIR_1mo": os.path.join("data", "market_data/monthly/")
    
}

class Config:
    """Config class that provides interface expected by unified ticker generator."""
    
    def __init__(self):
        """Initialize config with directory structure."""
        self.directories = {
            'TICKERS_DIR': Path(PARAMS_DIR["TICKERS_DIR"])
        }
        
        # Ensure directories exist
        self.directories['TICKERS_DIR'].mkdir(parents=True, exist_ok=True)

def setup_directories():
    """Create required directories if they don't exist."""
    os.makedirs(PARAMS_DIR["DATA_DIR"], exist_ok=True)
    os.makedirs(PARAMS_DIR["TICKERS_DIR"], exist_ok=True)
    os.makedirs(PARAMS_DIR["MARKET_DATA_DIR_1d"], exist_ok=True)
    os.makedirs(PARAMS_DIR["MARKET_DATA_DIR_1wk"], exist_ok=True)
    os.makedirs(PARAMS_DIR["MARKET_DATA_DIR_1mo"], exist_ok=True)
    #os.makedirs(PARAMS_DIR["MARKET_DATA_DIR_1wk"], exist_ok=True)
    

# Generate filenames (example)
#TICKER_FILE = os.path.join(PARAMS_DIR["TICKERS_DIR"], "combined_tickers.csv")

user_choice, write_file_info = read_user_data_legacy()
def get_ticker_files():
    """
    Returns a list of ticker files based on the user's choice.
    Supports both single numbers and dash-separated combinations (e.g., "1-2-3").
    """
    # Read current user configuration to get both choice and filenames
    config = read_user_data()
    current_user_choice = config.ticker_choice

    # Get ticker group filenames from user configuration (with fallback to defaults)
    ticker_filenames = config.ticker_filenames or _get_default_ticker_filenames()
    
    # Convert to the expected format (group_id -> list of files)
    group_files = {group_id: [filename] for group_id, filename in ticker_filenames.items()}

    # Parse ticker choice (handle both string and int)
    ticker_choice_str = str(current_user_choice).strip()
    
    # Split by dash to get individual group IDs
    try:
        group_ids = [int(id_str.strip()) for id_str in ticker_choice_str.split('-')]
    except ValueError:
        raise ValueError(f"Invalid ticker_choice format: '{ticker_choice_str}'. Use single numbers or dash-separated (e.g., '1-2-3').")

    # Validate all group IDs
    for group_id in group_ids:
        if group_id not in group_files:
            raise ValueError(f"Invalid group ID: {group_id}. Valid groups are 0-8.")

    # Combine files from all selected groups (remove duplicates)
    combined_files = []
    for group_id in group_ids:
        for file in group_files[group_id]:
            if file not in combined_files:
                combined_files.append(file)

    return combined_files


