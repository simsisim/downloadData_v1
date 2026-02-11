"""
Unified Ticker File Generator
============================

Flexible system that generates all required ticker files for any user choice format.
Supports both TradingView universe mode and individual ticker files mode.

Core Requirements:
- Support two modes: TradingView universe OR individual downloaded ticker files
- Always generate universe files (choice 0) regardless of user choice
- Handle dash-separated choices (1-2) with dash filenames (1-2) 
- Generate 3 file types: combined_tickers_*.csv, combined_info_tickers_*.csv, combined_info_tickers_clean_*.csv
- Create skeleton info files that get populated later during market data retrieval
"""

import pandas as pd
from pathlib import Path
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class UnifiedTickerGenerator:
    """Generates all ticker files for any user choice format."""
    
    def __init__(self, config, mode='auto'):
        """
        Initialize with config object containing directories.
        
        Args:
            config: Config object with directories
            mode: 'tradingview', 'individual_files', or 'auto' (detect automatically)
        """
        self.config = config
        self.tickers_dir = Path(config.directories['TICKERS_DIR'])
        self.tickers_dir.mkdir(parents=True, exist_ok=True)
        self.mode = mode
        
        # Get filenames from centralized config (avoiding hard-coding)
        from src.user_defined_data import _get_default_ticker_filenames
        default_filenames = _get_default_ticker_filenames()
        
        # Individual ticker files mapping for web download mode
        self.individual_files = {
            0: [default_filenames[1], default_filenames[2], default_filenames[3], default_filenames[4]],  # All major files as universe
            1: [default_filenames[1]],
            2: [default_filenames[2]],  
            3: [default_filenames[3]],
            4: [default_filenames[4]],
            5: [default_filenames[5]],
            6: [default_filenames[6]],
            7: [default_filenames[7]],
            8: [default_filenames[8]]
        }
        
        # Choice mapping for TradingView universe mode: choice -> list of boolean column filters
        self.choice_filters = {
            0: [],                          # Full universe (no filtering)
            1: ['SP500'],                   # S&P 500 only
            2: ['NASDAQ100'],               # NASDAQ 100 only  
            3: ['NASDAQComposite'],         # All NASDAQ
            4: ['Russell1000'],             # Russell 1000
            5: ['SP500', 'NASDAQ100'],      # S&P 500 + NASDAQ 100
            6: ['SP500', 'NASDAQComposite'], # S&P 500 + All NASDAQ
            7: ['SP500', 'Russell1000'],    # S&P 500 + Russell 1000
            8: ['NASDAQ100', 'NASDAQComposite'], # NASDAQ 100 + All NASDAQ
            9: ['NASDAQ100', 'Russell1000'], # NASDAQ 100 + Russell 1000
            10: ['NASDAQComposite', 'Russell1000'], # All NASDAQ + Russell 1000
            11: ['SP500', 'NASDAQ100', 'NASDAQComposite'], # Major indexes
            12: ['SP500', 'NASDAQ100', 'Russell1000'], # Major indexes
            13: ['SP500', 'NASDAQComposite', 'Russell1000'], # Major indexes
            14: ['NASDAQ100', 'NASDAQComposite', 'Russell1000'], # Tech heavy
            15: ['SP500', 'NASDAQ100', 'Russell1000', 'NASDAQComposite'], # All major
        }
    
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
    
    def generate_all_ticker_files(self, user_choice):
        """
        Generate all ticker files for any user choice format.
        
        Args:
            user_choice (int, str): User choice (0, 1, "1-2", etc.)
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            print(f"\n{'='*60}")
            print("UNIFIED TICKER FILE GENERATION")
            print(f"{'='*60}")
            print(f"User choice: {user_choice}")
            
            # Step 1: Determine and set the operating mode
            if not self._determine_mode(user_choice):
                return False
            
            print(f"🔧 Operating mode: {self.mode}")
            
            # Step 2: Ensure data source is ready
            if not self._ensure_data_source():
                return False
            
            # Step 3: Always generate universe files (choice 0)
            print(f"\n📊 STEP 1: Generating universe files (choice 0)...")
            if not self._generate_files_for_choice(0):
                print(f"❌ Failed to generate universe files")
                return False
            
            # Step 4: Parse user choice and generate individual/combined files
            choices = self._parse_user_choice(user_choice)
            if not choices:
                print(f"✅ Only universe files needed for choice {user_choice}")
                return True
            
            print(f"\n📊 STEP 2: Generating files for user choices: {choices}")
            
            # Generate individual choice files
            for choice in choices:
                if choice != 0:  # Skip 0 since we already generated it
                    if not self._generate_files_for_choice(choice):
                        print(f"❌ Failed to generate files for choice {choice}")
                        return False
            
            # Generate combined multi-choice files if needed
            if len(choices) > 1 or (len(choices) == 1 and choices[0] != 0):
                combined_choice = str(user_choice)
                if combined_choice != str(choices[0]):  # Only if different from single choice
                    print(f"\n📊 STEP 3: Generating combined files for {combined_choice}...")
                    if not self._generate_combined_files(choices, combined_choice):
                        print(f"❌ Failed to generate combined files")
                        return False
            
            print(f"\n✅ All ticker files generated successfully!")
            self._print_summary(user_choice, choices)
            return True
            
        except Exception as e:
            print(f"❌ Error generating ticker files: {e}")
            logger.error(f"Error generating ticker files: {e}")
            return False
    
    def _determine_mode(self, user_choice=None):
        """Determine operating mode based on available data sources and user choice."""
        if self.mode != 'auto':
            return True
        
        # Check if user choice requires specific individual files (indexes, portfolio, ETF, test)
        special_file_choices = set()
        if user_choice:
            try:
                # Parse user choice to get individual choices
                choice_str = str(user_choice).strip()
                individual_choices = [int(id_str.strip()) for id_str in choice_str.split('-')]
                special_file_choices = set(individual_choices) & {5, 6, 7, 8}  # Intersection with special choices
            except (ValueError, AttributeError):
                pass
        
        # Check for TradingView universe file
        from src.user_defined_data import read_user_data
        config = read_user_data()
        universe_file = Path(config.user_input_path) / config.tw_universe_file
        tickers_universe_file = self.tickers_dir / 'tradingview_universe.csv'
        
        # Check for individual ticker files
        individual_files_exist = any(
            (self.tickers_dir / file).exists() 
            for file_list in self.individual_files.values() 
            for file in file_list if file != 'tradingview_universe.csv'
        )
        
        # Force individual file mode for special choices (5,6,7,8) even if TradingView universe exists
        if special_file_choices:
            print("🔍 Special ticker files requested (indexes/portfolio/ETF/test)")
            print("🎯 Using individual file mode for specialized tickers")
            self.mode = 'individual_files'
        elif universe_file.exists() or tickers_universe_file.exists():
            if individual_files_exist:
                print("🔍 Both TradingView universe and individual ticker files detected")
                print("🎯 Prioritizing TradingView universe mode for consistency")
                self.mode = 'tradingview'
            else:
                print("🔍 TradingView universe file detected")
                self.mode = 'tradingview'
        elif individual_files_exist:
            print("🔍 Individual ticker files detected")
            self.mode = 'individual_files'
        else:
            print("❌ No data source detected!")
            print("   Need either tradingview_universe.csv OR individual ticker files")
            return False
        
        return True
    
    def _ensure_data_source(self):
        """Ensure the appropriate data source is ready for the chosen mode."""
        if self.mode == 'tradingview':
            return self._ensure_universe_data()
        elif self.mode == 'individual_files':
            return self._verify_individual_files()
        else:
            print(f"❌ Unknown mode: {self.mode}")
            return False
    
    def _verify_individual_files(self):
        """Verify that individual ticker files are available."""
        print("🔍 Verifying individual ticker files...")
        
        available_files = []
        missing_files = []
        
        for choice, files in self.individual_files.items():
            for file in files:
                file_path = self.tickers_dir / file
                if file_path.exists():
                    available_files.append(f"{choice}:{file}")
                else:
                    missing_files.append(f"{choice}:{file}")
        
        if available_files:
            print(f"✅ Found {len(available_files)} individual ticker files")
            if missing_files:
                print(f"⚠️  Missing {len(missing_files)} optional files: {missing_files[:3]}...")
            return True
        else:
            print("❌ No individual ticker files found!")
            print("   Expected files like: sp500_tickers.csv, nasdaq100_tickers.csv, etc.")
            return False
    
    def _ensure_universe_data(self):
        """Force regeneration of TradingView universe data with boolean columns."""
        universe_bool_file = self.tickers_dir / 'tradingview_universe_bool.csv'
        
        # Always regenerate - remove existing file if present
        if universe_bool_file.exists():
            universe_bool_file.unlink()
            print(f"🔄 Removed existing universe data for regeneration")
        
        # Create universe data from user_input/tradingview_universe.csv
        from src.user_defined_data import read_user_data
        config = read_user_data()
        root_universe = Path(config.user_input_path) / config.tw_universe_file
        if not root_universe.exists():
            print(f"❌ Missing root TradingView universe file: {root_universe}")
            return False
        
        print(f"🔄 Creating boolean-enhanced universe data...")
        try:
            # Read root universe
            df = pd.read_csv(root_universe)
            print(f"📊 Loaded {len(df)} tickers from root universe")
            
            # Standardize to 'ticker' column name
            if 'Symbol' in df.columns:
                df = df.rename(columns={'Symbol': 'ticker'})
            
            # Clean ticker names (filter '/' and transform '.' to '-')
            print("🧹 Cleaning ticker names...")
            original_count = len(df)
            
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
            
            # Standardize all column names to lowercase (convention)
            df.columns = df.columns.str.lower()
            
            # Handle special cases after lowercase conversion
            column_renames = {
                'market capitalization - currency': 'market_cap_currency',
                'market capitalization': 'market_cap'  # Standard name for market cap
            }
            
            for old_col, new_col in column_renames.items():
                if old_col in df.columns:
                    df = df.rename(columns={old_col: new_col})
            
            # Create boolean columns from index column (now lowercase)
            if 'index' in df.columns:
                df_bool = self._create_boolean_columns(df)
                df_bool.to_csv(universe_bool_file, index=False)
                print(f"✅ Created boolean-enhanced universe: {len(df_bool)} tickers, {len(df_bool.columns)} columns")
                return True
            else:
                print(f"⚠️  No index column found, using basic universe data")
                df.to_csv(universe_bool_file, index=False)
                return True
                
        except Exception as e:
            print(f"❌ Error creating universe data: {e}")
            return False
    
    def _create_boolean_columns(self, df):
        """Create boolean columns from Index data."""
        # Copy original dataframe
        df_enhanced = df.copy()
        
        # Parse indexes and create boolean columns
        index_counts = {}
        
        for idx, row in df.iterrows():
            if pd.notna(row.get('index')):
                # Split by comma (not semicolon) since the data uses comma-separated values
                indexes = str(row['index']).split(',')
                for index_name in indexes:
                    index_name = index_name.strip()
                    if index_name:
                        # Clean index name for column - more comprehensive cleaning
                        col_name = (index_name
                                   .replace(' ', '')
                                   .replace('&', '')
                                   .replace('-', '')
                                   .replace('.', '')
                                   .replace('/', '')
                                   .replace('(', '')
                                   .replace(')', ''))
                        
                        # Initialize column if not exists
                        if col_name not in df_enhanced.columns:
                            df_enhanced[col_name] = False
                            index_counts[col_name] = 0
                        
                        # Set boolean value
                        df_enhanced.at[idx, col_name] = True
                        index_counts[col_name] += 1
        
        print(f"🏗️  Created {len(index_counts)} boolean index columns")
        if index_counts:
            top_indexes = sorted(index_counts.items(), key=lambda x: x[1], reverse=True)[:10]
            print(f"🎯 Top indexes: {', '.join([f'{name}({count})' for name, count in top_indexes])}")
        
        return df_enhanced
    
    def _parse_user_choice(self, user_choice):
        """Parse user choice into list of individual choices."""
        if user_choice == 0 or user_choice == '0':
            return [0]
        
        # Handle string with dashes
        if isinstance(user_choice, str) and '-' in user_choice:
            try:
                choices = [int(c.strip()) for c in user_choice.split('-') if c.strip().isdigit()]
                return choices
            except ValueError:
                print(f"❌ Invalid choice format: {user_choice}")
                return []
        
        # Handle single choice
        try:
            choice = int(user_choice)
            return [choice] if choice != 0 else [0]
        except ValueError:
            print(f"❌ Invalid choice format: {user_choice}")
            return []
    
    def _generate_files_for_choice(self, choice):
        """Force regenerate all 3 file types for a specific choice."""
        try:
            if self.mode == 'tradingview':
                return self._generate_files_tradingview_mode(choice)
            elif self.mode == 'individual_files':
                return self._generate_files_individual_mode(choice)
            else:
                print(f"❌ Unknown mode: {self.mode}")
                return False
                
        except Exception as e:
            print(f"❌ Error generating files for choice {choice}: {e}")
            return False
    
    def _generate_files_tradingview_mode(self, choice):
        """Generate files using TradingView universe data."""
        # Load universe data
        universe_file = self.tickers_dir / 'tradingview_universe_bool.csv'
        if not universe_file.exists():
            print(f"❌ Universe boolean file not found: {universe_file}")
            return False
        
        df = pd.read_csv(universe_file)
        
        # Apply filtering
        filtered_df = self._filter_by_choice_tradingview(df, choice)
        if filtered_df is None:
            return False
        
        return self._create_three_files(choice, filtered_df)
    
    def _generate_files_individual_mode(self, choice):
        """Generate files using individual ticker files."""
        # Get the files for this choice
        files = self.individual_files.get(choice, [])
        if not files:
            print(f"❌ No file mapping for choice {choice}")
            return False
        
        # Combine tickers from individual files
        all_tickers = []
        found_files = []
        
        for file in files:
            # First check in data/tickers/ directory
            file_path = self.tickers_dir / file
            # If not found, check in root directory as fallback
            if not file_path.exists():
                root_file_path = Path(file)
                if root_file_path.exists():
                    file_path = root_file_path
                    print(f"📁 Using file from root directory: {file}")
            
            if file_path.exists():
                try:
                    df = pd.read_csv(file_path)
                    if 'ticker' in df.columns:
                        all_tickers.extend(df['ticker'].tolist())
                        found_files.append(file)
                    else:
                        print(f"⚠️  No 'ticker' column in {file}")
                except Exception as e:
                    print(f"⚠️  Error reading {file}: {e}")
            else:
                print(f"⚠️  File not found in data/tickers/ or root: {file}")
        
        if not all_tickers:
            print(f"❌ No tickers found for choice {choice}")
            return False
        
        # Remove duplicates while preserving order
        unique_tickers = list(dict.fromkeys(all_tickers))
        
        # Create a simple DataFrame with just tickers (skeleton info files)
        tickers_df = pd.DataFrame({'ticker': unique_tickers})
        
        print(f"  • Combined from files: {', '.join(found_files)}")
        print(f"  • Choice {choice}: {len(unique_tickers)} unique tickers")
        
        return self._create_three_files(choice, tickers_df)
    
    def _create_three_files(self, choice, df):
        """Create the 3 required file types for a choice."""
        choice_str = str(choice)
        
        # Remove existing files if they exist
        files_to_regenerate = [
            self.tickers_dir / f'combined_tickers_{choice_str}.csv',
            self.tickers_dir / f'combined_info_tickers_{choice_str}.csv',
            self.tickers_dir / f'combined_info_tickers_clean_{choice_str}.csv'
        ]
        
        for file_path in files_to_regenerate:
            if file_path.exists():
                file_path.unlink()
        
        # 1. combined_tickers_{choice}.csv (ticker column only)
        tickers_only = pd.DataFrame({'ticker': df['ticker'].tolist()})
        ticker_file = self.tickers_dir / f'combined_tickers_{choice_str}.csv'
        tickers_only.to_csv(ticker_file, index=False)
        
        # 2. combined_info_tickers_{choice}.csv (skeleton - will be populated later)
        info_file = self.tickers_dir / f'combined_info_tickers_{choice_str}.csv'
        if self.mode == 'tradingview' and len(df.columns) > 1:
            # In TradingView mode, we have rich data immediately
            df.to_csv(info_file, index=False)
        else:
            # In individual files mode, create skeleton (ticker only for now)
            # Will be populated during market data retrieval
            tickers_only.to_csv(info_file, index=False)
        
        # 3. combined_info_tickers_clean_{choice}.csv (same as info)
        clean_file = self.tickers_dir / f'combined_info_tickers_clean_{choice_str}.csv'
        if self.mode == 'tradingview' and len(df.columns) > 1:
            df.to_csv(clean_file, index=False)
        else:
            tickers_only.to_csv(clean_file, index=False)
        
        print(f"✅ Generated 3 files for choice {choice}: {len(df)} tickers")
        return True
    
    def _generate_combined_files(self, choices, combined_choice_str):
        """Force regenerate combined files for multi-choice selections."""
        try:
            if self.mode == 'tradingview':
                return self._generate_combined_files_tradingview(choices, combined_choice_str)
            elif self.mode == 'individual_files':
                return self._generate_combined_files_individual(choices, combined_choice_str)
            else:
                print(f"❌ Unknown mode: {self.mode}")
                return False
                
        except Exception as e:
            print(f"❌ Error generating combined files: {e}")
            return False
    
    def _generate_combined_files_tradingview(self, choices, combined_choice_str):
        """Generate combined files using TradingView universe data."""
        # Load universe data
        universe_file = self.tickers_dir / 'tradingview_universe_bool.csv'
        df = pd.read_csv(universe_file)
        
        # Special handling: If choice 0 is included, return full universe
        if 0 in choices:
            # Choice 0 means full universe - no filtering needed
            filtered_df = df
            print(f"  • Choice 0 detected in combination - using full universe ({len(df)} tickers)")
        else:
            # Combine filters from all choices (excluding choice 0)
            combined_filters = []
            for choice in choices:
                filters = self.choice_filters.get(choice, [])
                combined_filters.extend(filters)
            
            # Remove duplicates while preserving order
            combined_filters = list(dict.fromkeys(combined_filters))
            
            # Apply combined filtering
            if not combined_filters:
                # No filters (shouldn't happen since we excluded choice 0)
                filtered_df = df
            else:
                # Create OR mask for all filters
                mask = pd.Series([False] * len(df))
                for filter_col in combined_filters:
                    if filter_col in df.columns:
                        mask = mask | df[filter_col]
                filtered_df = df[mask]
                
                filter_names = [f"{f}({df[f].sum()})" for f in combined_filters if f in df.columns]
                print(f"  • Applied combined filters: {', '.join(filter_names)}")
        
        return self._create_three_files(combined_choice_str, filtered_df)
    
    def _generate_combined_files_individual(self, choices, combined_choice_str):
        """Generate combined files using individual ticker files."""
        # Combine tickers from all choices
        all_tickers = []
        used_files = []
        
        for choice in choices:
            files = self.individual_files.get(choice, [])
            for file in files:
                # First check in data/tickers/ directory
                file_path = self.tickers_dir / file
                # If not found, check in root directory as fallback
                if not file_path.exists():
                    root_file_path = Path(file)
                    if root_file_path.exists():
                        file_path = root_file_path
                        print(f"📁 Using file from root directory: {file}")
                
                if file_path.exists():
                    try:
                        df = pd.read_csv(file_path)
                        if 'ticker' in df.columns:
                            all_tickers.extend(df['ticker'].tolist())
                            if file not in used_files:
                                used_files.append(file)
                    except Exception as e:
                        print(f"⚠️  Error reading {file}: {e}")
                else:
                    print(f"⚠️  File not found in data/tickers/ or root: {file}")
        
        if not all_tickers:
            print(f"❌ No tickers found for combined choice {combined_choice_str}")
            return False
        
        # Remove duplicates while preserving order
        unique_tickers = list(dict.fromkeys(all_tickers))
        
        # Create DataFrame with unique tickers
        combined_df = pd.DataFrame({'ticker': unique_tickers})
        
        print(f"  • Combined from files: {', '.join(used_files)}")
        print(f"  • Combination {combined_choice_str}: {len(unique_tickers)} unique tickers")
        
        return self._create_three_files(combined_choice_str, combined_df)
    
    def _filter_by_choice_tradingview(self, df, choice):
        """Filter dataframe by choice using boolean columns (TradingView mode)."""
        filters = self.choice_filters.get(choice)
        if filters is None:
            print(f"❌ No filter definition for choice {choice}")
            return None
        
        # Handle choice 0 (no filtering)
        if choice == 0 or not filters:
            print(f"  • No filtering applied - using full universe ({len(df)} tickers)")
            return df
        
        # Apply OR filtering for multiple indexes
        mask = pd.Series([False] * len(df))
        found_filters = []
        
        for filter_col in filters:
            if filter_col in df.columns:
                mask = mask | df[filter_col]
                count = df[filter_col].sum()
                found_filters.append(f"{filter_col}({count})")
            else:
                print(f"  ⚠️  Column {filter_col} not found in universe file")
        
        filtered_df = df[mask]
        print(f"  • Applied filters: {', '.join(found_filters)}")
        print(f"  • Choice {choice}: {len(filtered_df)} tickers after filtering")
        
        return filtered_df
    
    def _print_summary(self, user_choice, choices):
        """Print summary of generated files."""
        print(f"\n📋 FILE GENERATION SUMMARY")
        print(f"{'='*40}")
        print(f"User choice: {user_choice}")
        print(f"Individual choices processed: {choices}")
        
        # Count generated files
        total_files = 0
        for choice in [0] + [c for c in choices if c != 0]:
            choice_files = list(self.tickers_dir.glob(f'*_{choice}.csv'))
            total_files += len(choice_files)
            print(f"  Choice {choice}: {len(choice_files)} files")
        
        # Combined files
        if len(choices) > 1 or (len(choices) == 1 and choices[0] != 0):
            combined_name = str(user_choice)
            if combined_name not in [str(c) for c in choices]:
                combined_files = list(self.tickers_dir.glob(f'*_{combined_name}.csv'))
                total_files += len(combined_files)
                print(f"  Combined {combined_name}: {len(combined_files)} files")
        
        print(f"Total files generated: {total_files}")


def generate_all_ticker_files(config, user_choice, mode='auto'):
    """
    Main entry point for unified ticker file generation.
    
    Args:
        config: Config object with directories
        user_choice: User choice (int, str) - any format
        mode: 'tradingview', 'individual_files', or 'auto' (detect automatically)
        
    Returns:
        bool: True if successful, False otherwise
    """
    generator = UnifiedTickerGenerator(config, mode)
    return generator.generate_all_ticker_files(user_choice)