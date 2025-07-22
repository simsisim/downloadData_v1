import pandas as pd
import os
from src.config import user_choice, PARAMS_DIR


def combine_tickers(file_list, save_location):
    save_location = PARAMS_DIR["TICKERS_DIR"]
    combined_tickers = pd.DataFrame(columns=['ticker'])
    
    for file in file_list:
        df = pd.read_csv(os.path.join(save_location, file))
        combined_tickers = pd.concat([combined_tickers, df[['ticker']]], ignore_index=True)
    
    combined_tickers = combined_tickers.drop_duplicates()
    combined_file_path = os.path.join(save_location, f'combined_tickers_{user_choice}.csv')
    combined_tickers.to_csv(combined_file_path, index=False)
    
    return combined_file_path

