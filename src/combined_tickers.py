import pandas as pd
import os
from src.config import user_choice, PARAMS_DIR


def combine_tickers(file_list, save_location):
    save_location = PARAMS_DIR["TICKERS_DIR"]
    combined_tickers = pd.DataFrame(columns=['ticker'])
    
    for file in file_list:
        file_path = os.path.join(save_location, file)
        if os.path.exists(file_path):
            df = pd.read_csv(file_path)
            if 'ticker' in df.columns:
                combined_tickers = pd.concat([combined_tickers, df[['ticker']]], ignore_index=True)
            else:
                print(f"Warning: 'ticker' column not found in {file}")
        else:
            print(f"Warning: Ticker file {file} not found, skipping...")
    
    combined_tickers = combined_tickers.drop_duplicates()
    
    # Use sanitized user_choice for filename (replace dashes with underscores)
    safe_user_choice = str(user_choice).replace('-', '_')
    combined_file_path = os.path.join(save_location, f'combined_tickers_{safe_user_choice}.csv')
    combined_tickers.to_csv(combined_file_path, index=False)
    
    return combined_file_path

