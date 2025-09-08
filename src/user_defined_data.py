import pandas as pd
from dataclasses import dataclass
from typing import Optional


@dataclass
class UserConfiguration:
    """
    Data class to hold all user configuration settings.
    """
    # Ticker data sources
    web_tickers_down: bool = True
    tw_tickers_down: bool = False  
    tw_universe_file: str = "tradingview_universe.csv"
    
    # Historical data collection
    yf_hist_data: bool = True
    yf_daily_data: bool = True
    yf_weekly_data: bool = True  
    yf_monthly_data: bool = True
    tw_intraday_data: bool = False
    tw_intraday_file: str = "intraday_data.csv"
    
    # Financial data enrichment
    fin_data_enrich: bool = True
    yf_fin_data: bool = True
    tw_fin_data: bool = False
    zacks_fin_data: bool = False
    
    # General settings
    write_info_file: bool = False
    ticker_info_TW: bool = False
    ticker_info_TW_file: str = "tradingview_universe_bool.csv"
    ticker_info_YF: bool = False
    ticker_choice: str = "2"
    
    # Ticker group filenames
    ticker_filenames: dict = None


def parse_boolean(value: str) -> bool:
    """
    Parse string value to boolean.
    Accepts: TRUE, FALSE, true, false, 1, 0, yes, no
    """
    if isinstance(value, bool):
        return value
    
    value_str = str(value).strip().lower()
    return value_str in ['true', '1', 'yes', 'on']


def _get_default_ticker_filenames() -> dict:
    """Get the default ticker filenames mapping."""
    return {
        0: 'tradingview_universe.csv',
        1: 'sp500_tickers.csv',
        2: 'nasdaq100_tickers.csv',
        3: 'nasdaq_all_tickers.csv',
        4: 'iwm1000_tickers.csv',
        5: 'indexes_tickers.csv',
        6: 'portofolio_tickers.csv',
        7: 'etf_tickers.csv',
        8: 'test_tickers.csv'
    }


def _read_ticker_filenames(file_path: str) -> dict:
    """
    Parse ticker group filenames from comment lines in the CSV file.
    
    Looks for lines in format: # N: Description,filename,
    where N is the group ID (0-8) and filename is the CSV filename.
    
    Returns dict mapping group_id -> filename
    """
    ticker_filenames = {}
    
    try:
        with open(file_path, 'r') as f:
            for line in f:
                line = line.strip()
                if line.startswith('#') and ':' in line:
                    # Parse lines like: # 5: Index tickers only,indexes_tickers.csv,
                    parts = line.split(',')
                    if len(parts) >= 2:
                        # Extract the group ID from "# N: Description"
                        prefix_part = parts[0]  # "# 5: Index tickers only"
                        if ':' in prefix_part:
                            try:
                                # Split on ':' and get the part before it
                                before_colon = prefix_part.split(':')[0]  # "# 5"
                                # Extract the number
                                group_id = int(before_colon.replace('#', '').strip())
                                # Get the filename (second column)
                                filename = parts[1].strip()
                                if filename and 0 <= group_id <= 8:
                                    ticker_filenames[group_id] = filename
                            except (ValueError, IndexError):
                                continue  # Skip invalid lines
        
        # If no filenames found, use defaults
        if not ticker_filenames:
            ticker_filenames = _get_default_ticker_filenames()
            
    except FileNotFoundError:
        # Use defaults if file not found
        ticker_filenames = _get_default_ticker_filenames()
    
    return ticker_filenames


def read_user_data(file_path: str = 'user_data.csv') -> UserConfiguration:
    """
    Reads user configuration from the restructured CSV file.
    
    The new format uses key-value pairs with format:
    variable_name,value,description
    
    Returns UserConfiguration object with all settings.
    """
    try:
        # First, read ticker group filenames from comment lines
        ticker_filenames = _read_ticker_filenames(file_path)
        
        # Read CSV file, skipping comment lines that start with #
        df = pd.read_csv(file_path, comment='#', header=None, 
                        names=['variable', 'value', 'description'])
        
        # Remove rows where variable is NaN (empty lines, etc.)
        df = df.dropna(subset=['variable'])
        df['variable'] = df['variable'].str.strip()
        df['value'] = df['value'].str.strip()
        
        # Create configuration object with defaults
        config = UserConfiguration()
        config.ticker_filenames = ticker_filenames
        
        # Parse each configuration variable
        config_map = {
            'WEB_tickers_down': ('web_tickers_down', parse_boolean),
            'TW_tickers_down': ('tw_tickers_down', parse_boolean),
            'TW_universe_file': ('tw_universe_file', str),
            'YF_hist_data': ('yf_hist_data', parse_boolean),
            'YF_daily_data': ('yf_daily_data', parse_boolean),
            'YF_weekly_data': ('yf_weekly_data', parse_boolean),
            'YF_monthly_data': ('yf_monthly_data', parse_boolean),
            'TW_intraday_data': ('tw_intraday_data', parse_boolean),
            'TW_intraday_file': ('tw_intraday_file', str),
            'fin_data_enrich': ('fin_data_enrich', parse_boolean),
            'YF_fin_data': ('yf_fin_data', parse_boolean),
            'TW_fin_data': ('tw_fin_data', parse_boolean),
            'Zacks_fin_data': ('zacks_fin_data', parse_boolean),
            'write_info_file': ('write_info_file', parse_boolean),
            'ticker_info_TW': ('ticker_info_TW', parse_boolean),
            'ticker_info_TW_file': ('ticker_info_TW_file', str),
            'ticker_info_YF': ('ticker_info_YF', parse_boolean),
            'ticker_choice': ('ticker_choice', str)
        }
        
        # Process each row in the dataframe
        for _, row in df.iterrows():
            variable = row['variable']
            value = row['value']
            
            if variable in config_map:
                attr_name, converter = config_map[variable]
                try:
                    converted_value = converter(value)
                    setattr(config, attr_name, converted_value)
                except (ValueError, TypeError) as e:
                    print(f"Warning: Invalid value '{value}' for {variable}. Using default. Error: {e}")
        
        # Validation for ticker_choice
        try:
            # Parse ticker choice to validate format
            group_ids = [int(id_str.strip()) for id_str in str(config.ticker_choice).split('-')]
            
            # Validate all group IDs are in range 0-8
            for group_id in group_ids:
                if not (0 <= group_id <= 8):
                    raise ValueError(f"Group ID {group_id} not in valid range 0-8")
                    
        except (ValueError, AttributeError):
            print(f"Warning: ticker_choice '{config.ticker_choice}' is invalid. Using default ('2').")
            config.ticker_choice = "2"
            
        return config

    except FileNotFoundError:
        print(f"Error: {file_path} not found. Using default configuration.")
        return UserConfiguration()

    except Exception as e:
        print(f"Error reading user data: {e}. Using default configuration.")
        return UserConfiguration()


def read_user_data_legacy() -> tuple:
    """
    Legacy function for backward compatibility.
    Returns (ticker_choice, write_info_file) tuple as expected by existing code.
    """
    config = read_user_data()
    return config.ticker_choice, config.write_info_file

