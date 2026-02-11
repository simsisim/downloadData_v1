import pandas as pd
import os
from typing import Dict, List, Set, Optional
from src.config import PARAMS_DIR


class TradingViewTickerProcessor:
    """
    Processes TradingView universe file to generate individual ticker files
    matching the web-downloaded format.
    """
    
    def __init__(self, config):
        self.config = config
        self.universe_file = config.tw_universe_file
        self.tickers_dir = PARAMS_DIR["TICKERS_DIR"]
        
        # Index mapping with proper spacing as observed in data
        self.INDEX_MAPPING = {
            'S&P 500': 'sp500_tickers.csv',
            'NASDAQ 100': 'nasdaq100_tickers.csv',
            'NASDAQ Composite': 'nasdaq_all_tickers.csv',
            'Russell 1000': 'iwm1000_tickers.csv',
            'Russell 3000': 'russell3000_tickers.csv',
            'Russell 2000': 'russell2000_tickers.csv',
            'S&P MidCap 400': 'sp_midcap_tickers.csv',
        }
        
        # Additional index patterns we might encounter
        self.ADDITIONAL_INDEXES = {
            'NASDAQ Bank': 'nasdaq_bank_tickers.csv',
            'NASDAQ Biotechnology': 'nasdaq_biotech_tickers.csv',
            'S&P 500 Consumer Discretionary': 'sp500_consumer_disc_tickers.csv',
            'S&P 500 Health Care': 'sp500_healthcare_tickers.csv',
            'S&P 500 ESG': 'sp500_esg_tickers.csv',
        }
        
        # Combine mappings
        self.ALL_INDEX_MAPPING = {**self.INDEX_MAPPING, **self.ADDITIONAL_INDEXES}
    
    def clean_ticker_name(self, ticker: str) -> Optional[str]:
        """
        Clean ticker name according to rules:
        - Exclude tickers containing '/' (preferred shares, depositary shares)
        - Transform '.' to '-' (class shares like BRK.A -> BRK-A)
        
        Args:
            ticker: Raw ticker symbol from TradingView
            
        Returns:
            Cleaned ticker name or None if ticker should be excluded
        """
        if pd.isna(ticker) or not isinstance(ticker, str):
            return None
            
        ticker = ticker.strip()
        
        # Exclude tickers with '/' (preferred shares, depositary shares)
        if '/' in ticker:
            return None
            
        # Transform '.' to '-' for class shares
        cleaned_ticker = ticker.replace('.', '-')
        
        return cleaned_ticker
    
    def load_tradingview_universe(self) -> pd.DataFrame:
        """Load TradingView universe file."""
        # First try to find the file in tickers directory
        universe_path = os.path.join(self.tickers_dir, self.universe_file)

        # If not found, try user_input directory and copy it
        if not os.path.exists(universe_path):
            # Import config to get user_input_path
            from src.user_defined_data import read_user_data
            config = read_user_data()
            root_path = os.path.join(config.user_input_path, self.universe_file)

            if os.path.exists(root_path):
                print(f"📁 Found TradingView universe in user_input: {root_path}")
                print(f"🔄 Copying to tickers directory: {universe_path}")
                
                # Read from root and save to tickers directory
                df_temp = pd.read_csv(root_path)
                
                # Transform Symbol to ticker column if needed and clean ticker names
                if 'Symbol' in df_temp.columns and 'ticker' not in df_temp.columns:
                    df_temp['ticker'] = df_temp['Symbol']
                
                # Apply ticker cleaning (filter out '/' tickers and transform '.' to '-')
                if 'ticker' in df_temp.columns:
                    df_temp['cleaned_ticker'] = df_temp['ticker'].apply(self.clean_ticker_name)
                    # Remove rows where ticker should be excluded (None values)
                    original_count = len(df_temp)
                    df_temp = df_temp.dropna(subset=['cleaned_ticker'])
                    df_temp['ticker'] = df_temp['cleaned_ticker']
                    df_temp.drop('cleaned_ticker', axis=1, inplace=True)
                    filtered_count = original_count - len(df_temp)
                    if filtered_count > 0:
                        print(f"🚫 Filtered out {filtered_count} tickers with '/' characters")
                
                # Ensure we keep all columns including Index for processing
                # Save to tickers directory
                df_temp.to_csv(universe_path, index=False)
                print(f"✅ File copied and processed: {universe_path}")
            else:
                print(f"❌ TradingView universe file not found at: {root_path}")
                raise FileNotFoundError(f"TradingView universe file not found at: {root_path}")
        
        try:
            df = pd.read_csv(universe_path)
            print(f"✅ Loaded TradingView universe file: {universe_path}")
            print(f"📊 Found {len(df)} tickers in universe")
            return df
        except Exception as e:
            print(f"❌ Error loading TradingView universe file: {e}")
            raise
    
    def parse_index_column(self, index_str: str) -> Set[str]:
        """
        Parse comma-separated index string into set of individual indexes.
        
        Args:
            index_str: String like "S&P 500, NASDAQ 100, Russell 3000"
            
        Returns:
            Set of individual index names
        """
        if pd.isna(index_str) or not index_str.strip():
            return set()
        
        # Split by comma and clean whitespace
        indexes = [idx.strip() for idx in str(index_str).split(',')]
        return set(idx for idx in indexes if idx)  # Remove empty strings
    
    def create_boolean_index_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Transform Index column into boolean columns for each index.
        
        Args:
            df: DataFrame with Index column
            
        Returns:
            DataFrame with additional boolean columns for each index
        """
        print("🔄 Creating boolean index columns...")
        
        # Create a copy to avoid modifying original
        processed_df = df.copy()
        
        # Initialize all boolean columns as False
        for index_name in self.ALL_INDEX_MAPPING.keys():
            # Create column name (replace spaces and special chars)
            col_name = self.create_column_name(index_name)
            processed_df[col_name] = False
        
        # Process each row
        matches_found = 0
        for idx, row in processed_df.iterrows():
            if 'Index' in row:
                indexes_in_row = self.parse_index_column(row['Index'])
                
                # Set boolean columns to True for matching indexes
                for index_name in indexes_in_row:
                    if index_name in self.ALL_INDEX_MAPPING:
                        col_name = self.create_column_name(index_name)
                        processed_df.at[idx, col_name] = True
                        matches_found += 1
        
        print(f"  🎯 Total index matches found: {matches_found}")
        
        # Print summary
        boolean_cols = [self.create_column_name(name) for name in self.ALL_INDEX_MAPPING.keys()]
        for col in boolean_cols:
            count = processed_df[col].sum()
            if count > 0:
                print(f"  📈 {col}: {count} tickers")
        
        return processed_df
    
    def create_column_name(self, index_name: str) -> str:
        """
        Create a clean column name from index name.
        
        Args:
            index_name: Original index name like "S&P 500"
            
        Returns:
            Clean column name like "SP500"
        """
        # Replace common patterns
        name = index_name.replace('S&P ', 'SP')
        name = name.replace('NASDAQ ', 'NASDAQ')
        name = name.replace('Russell ', 'Russell')
        name = name.replace(' ', '')
        name = name.replace('&', '')
        return name
    
    def generate_ticker_files(self, processed_df: pd.DataFrame):
        """
        Generate individual ticker CSV files from processed DataFrame.
        
        Args:
            processed_df: DataFrame with boolean index columns
        """
        print("📝 Generating individual ticker files...")
        
        # Generate files for main indexes
        for index_name, filename in self.INDEX_MAPPING.items():
            col_name = self.create_column_name(index_name)
            
            print(f"  🔍 Processing {index_name} -> column {col_name}")
            
            if col_name in processed_df.columns:
                # Filter tickers for this index
                index_tickers = processed_df[processed_df[col_name] == True]
                
                print(f"    📊 Found {len(index_tickers)} tickers for {col_name}")
                
                if len(index_tickers) > 0:
                    # Create ticker list
                    ticker_list = index_tickers['ticker'].tolist()
                    
                    # Create DataFrame with same format as web-downloaded files
                    ticker_df = pd.DataFrame({'ticker': ticker_list})
                    
                    # Save to file
                    output_path = os.path.join(self.tickers_dir, filename)
                    ticker_df.to_csv(output_path, index=False)
                    
                    print(f"  ✅ {filename}: {len(ticker_list)} tickers")
                else:
                    print(f"  ⚠️  {filename}: 0 tickers found")
            else:
                print(f"  ❌ Column {col_name} not found for {index_name}")
                print(f"    Available columns: {list(processed_df.columns)[:10]}...")
    
    def generate_tradingview_universe_file(self, processed_df: pd.DataFrame):
        """
        Generate a comprehensive TradingView universe file with original columns + boolean index columns.
        
        Args:
            processed_df: DataFrame with all tickers and boolean index columns
        """
        print("\n📋 Generating comprehensive TradingView universe file...")
        
        # Start with all original columns and add boolean index columns
        universe_df = processed_df.copy()
        
        # Ensure we have the ticker column (should already exist)
        if 'ticker' not in universe_df.columns:
            print("  ❌ Error: ticker column missing from processed DataFrame")
            return
        
        # Get list of all boolean index columns that were created
        boolean_index_columns = []
        for index_name in self.ALL_INDEX_MAPPING.keys():
            col_name = self.create_column_name(index_name)
            if col_name in universe_df.columns:
                boolean_index_columns.append(col_name)
        
        # Organize columns: ticker, original columns, then boolean index columns
        original_columns = [col for col in universe_df.columns if not col.startswith(('SP', 'NASDAQ', 'Russell')) and col != 'ticker']
        
        # Final column order: ticker, original data, boolean indexes
        column_order = ['ticker'] + original_columns + sorted(boolean_index_columns)
        
        # Reorder columns
        universe_df = universe_df[column_order]
        
        # Remove any rows where ticker is NaN
        universe_df = universe_df.dropna(subset=['ticker'])
        
        # Sort by ticker for consistency
        universe_df = universe_df.sort_values('ticker').reset_index(drop=True)
        
        # Save comprehensive universe file with boolean columns for unified system
        bool_output_path = os.path.join(self.tickers_dir, 'tradingview_universe_bool.csv')
        universe_df.to_csv(bool_output_path, index=False)
        
        # Remove the intermediate tradingview_universe.csv file since we only need the boolean version
        intermediate_file = os.path.join(self.tickers_dir, 'tradingview_universe.csv')
        if os.path.exists(intermediate_file):
            os.remove(intermediate_file)
        
        print(f"  ✅ tradingview_universe_bool.csv: {len(universe_df)} tickers")
        print(f"  📊 Columns: {len(universe_df.columns)} total")
        print(f"    • Original TradingView columns: {len(original_columns)}")
        print(f"    • Boolean index columns: {len(boolean_index_columns)}")
        
        # Show sample boolean index columns
        print(f"  🎯 Boolean index columns created:")
        for col in sorted(boolean_index_columns):
            count = universe_df[col].sum()
            index_name = self.get_original_index_name(col)
            print(f"    • {col}: {count} tickers ({index_name})")
    
    def get_original_index_name(self, col_name: str) -> str:
        """
        Get the original index name from a column name.
        
        Args:
            col_name: Column name like "SP500"
            
        Returns:
            Original index name like "S&P 500"
        """
        # Reverse mapping from column name back to original index name
        for original_name, _ in self.ALL_INDEX_MAPPING.items():
            if self.create_column_name(original_name) == col_name:
                return original_name
        return col_name
    
    def process_tradingview_universe(self):
        """
        Main processing function: load, process, and generate ticker files.
        """
        print("\n" + "="*60)
        print("PROCESSING TRADINGVIEW TICKER UNIVERSE")
        print("="*60)
        
        try:
            # Step 1: Load universe file
            df = self.load_tradingview_universe()
            
            # Step 1.5: Clean ticker names (filter '/' and transform '.' to '-')
            print("🧹 Cleaning ticker names...")
            original_count = len(df)
            
            # Ensure we have a ticker column
            if 'ticker' not in df.columns and 'Symbol' in df.columns:
                df['ticker'] = df['Symbol']
            
            # Apply ticker cleaning
            df['cleaned_ticker'] = df['ticker'].apply(self.clean_ticker_name)
            # Remove rows where ticker should be excluded (None values)
            df = df.dropna(subset=['cleaned_ticker'])
            df['ticker'] = df['cleaned_ticker']
            df.drop('cleaned_ticker', axis=1, inplace=True)
            
            filtered_count = original_count - len(df)
            print(f"📊 Original tickers: {original_count}")
            print(f"🚫 Filtered out: {filtered_count} tickers with '/' characters")
            print(f"✅ Clean tickers: {len(df)}")
            
            # Step 2: Create boolean columns for indexes
            processed_df = self.create_boolean_index_columns(df)
            
            # Step 3: Generate individual ticker files
            self.generate_ticker_files(processed_df)
            
            # Step 4: Generate universe file
            self.generate_tradingview_universe_file(processed_df)
            
            print("\n✅ TradingView ticker processing completed successfully!")
            
            return True
            
        except Exception as e:
            print(f"\n❌ TradingView ticker processing failed: {e}")
            return False
    
    def get_index_summary(self) -> Dict[str, str]:
        """
        Get summary of available indexes and their file mappings.
        
        Returns:
            Dictionary mapping index names to filenames
        """
        return self.INDEX_MAPPING.copy()