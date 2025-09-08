import yfinance as yf
import pandas as pd
import datetime as dt
from datetime import timedelta
import time
import os
from src.config import user_choice
from src.config import PARAMS_DIR
import logging
import json


class MarketDataRetriever:
    def __init__(self, config):
        self.logger = logging.getLogger(__name__)
        self.config = config
        self.tickers_list = self.load_tickers()
        self.PARAMS_DIR = PARAMS_DIR 
        self.info_file = os.path.join(self.PARAMS_DIR["TICKERS_DIR"], f'combined_info_tickers_{user_choice}.csv')
        self.financial_data_file = os.path.join(self.PARAMS_DIR["TICKERS_DIR"], f'financial_data_{user_choice}.csv')
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
        ticker_obj = yf.Ticker(ticker)
        ohlc_data = ticker_obj.history(start=start_date, end=end_date, interval=self.config['interval'])
        
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

    def get_financial_data_for_canslim(self, ticker):
        """
        Extract comprehensive financial data needed for CANSLIM analysis
        Focus on growth metrics, earnings, sales, and fundamental indicators
        """
        try:
            ticker_obj = yf.Ticker(ticker)
            info = ticker_obj.info
            
            # Get quarterly and annual financials (avoiding deprecated properties)
            quarterly_income_stmt = ticker_obj.quarterly_income_stmt
            annual_income_stmt = ticker_obj.income_stmt
            quarterly_balance_sheet = ticker_obj.quarterly_balance_sheet
            annual_balance_sheet = ticker_obj.balance_sheet
            quarterly_cashflow = ticker_obj.quarterly_cashflow
            annual_cashflow = ticker_obj.cashflow
            
            financial_data = {
                'ticker': ticker,
                'last_updated': dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                
                # Basic Info for CANSLIM
                'sector': info.get('sector', 'N/A'),
                'industry': info.get('industry', 'N/A'),
                'marketCap': info.get('marketCap', 'N/A'),
                'enterpriseValue': info.get('enterpriseValue', 'N/A'),
                'shortName': info.get('shortName', 'N/A'),
                'longName': info.get('longName', 'N/A'),
                'exchange': info.get('fullExchangeName', 'N/A'),
                
                # Current Metrics (C in CANSLIM - Current Earnings)
                'currentRatio': info.get('currentRatio', 'N/A'),
                'quickRatio': info.get('quickRatio', 'N/A'),
                'trailingEps': info.get('trailingEps', 'N/A'),
                'forwardEps': info.get('forwardEps', 'N/A'),
                'trailingPE': info.get('trailingPE', 'N/A'),
                'forwardPE': info.get('forwardPE', 'N/A'),
                'pegRatio': info.get('pegRatio', 'N/A'),
                'earningsGrowth': info.get('earningsGrowth', 'N/A'),
                'revenueGrowth': info.get('revenueGrowth', 'N/A'),
                'earningsQuarterlyGrowth': info.get('earningsQuarterlyGrowth', 'N/A'),
                'revenueQuarterlyGrowth': info.get('revenueQuarterlyGrowth', 'N/A'),
                
                # Annual Metrics (A in CANSLIM - Annual Earnings)
                'returnOnEquity': info.get('returnOnEquity', 'N/A'),
                'returnOnAssets': info.get('returnOnAssets', 'N/A'),
                'grossMargins': info.get('grossMargins', 'N/A'),
                'operatingMargins': info.get('operatingMargins', 'N/A'),
                'profitMargins': info.get('profitMargins', 'N/A'),
                'ebitdaMargins': info.get('ebitdaMargins', 'N/A'),
                
                # New Stock/Supply & Demand (N & S in CANSLIM)
                'sharesOutstanding': info.get('sharesOutstanding', 'N/A'),
                'floatShares': info.get('floatShares', 'N/A'),
                'sharesShort': info.get('sharesShort', 'N/A'),
                'shortRatio': info.get('shortRatio', 'N/A'),
                'shortPercentOfFloat': info.get('shortPercentOfFloat', 'N/A'),
                'heldPercentInsiders': info.get('heldPercentInsiders', 'N/A'),
                'heldPercentInstitutions': info.get('heldPercentInstitutions', 'N/A'),
                
                # Leader/Laggard (L in CANSLIM)
                'beta': info.get('beta', 'N/A'),
                'averageVolume': info.get('averageVolume', 'N/A'),
                'averageVolume10days': info.get('averageVolume10days', 'N/A'),
                'fiftyTwoWeekHigh': info.get('fiftyTwoWeekHigh', 'N/A'),
                'fiftyTwoWeekLow': info.get('fiftyTwoWeekLow', 'N/A'),
                'fiftyDayAverage': info.get('fiftyDayAverage', 'N/A'),
                'twoHundredDayAverage': info.get('twoHundredDayAverage', 'N/A'),
                
                # Institutional/Market Direction (I & M in CANSLIM)
                'bookValue': info.get('bookValue', 'N/A'),
                'priceToBook': info.get('priceToBook', 'N/A'),
                'debtToEquity': info.get('debtToEquity', 'N/A'),
                'totalDebt': info.get('totalDebt', 'N/A'),
                'totalCash': info.get('totalCash', 'N/A'),
                'freeCashflow': info.get('freeCashflow', 'N/A'),
                'operatingCashflow': info.get('operatingCashflow', 'N/A'),
                
                # Growth Metrics for High-Growth Companies
                'revenuePerShare': info.get('revenuePerShare', 'N/A'),
                'totalRevenue': info.get('totalRevenue', 'N/A'),
                'recommendationKey': info.get('recommendationKey', 'N/A'),
                'numberOfAnalystOpinions': info.get('numberOfAnalystOpinions', 'N/A'),
                'targetHighPrice': info.get('targetHighPrice', 'N/A'),
                'targetLowPrice': info.get('targetLowPrice', 'N/A'),
                'targetMeanPrice': info.get('targetMeanPrice', 'N/A'),
                
                # Additional Growth Indicators
                'enterpriseToRevenue': info.get('enterpriseToRevenue', 'N/A'),
                'enterpriseToEbitda': info.get('enterpriseToEbitda', 'N/A'),
                'mostRecentQuarter': info.get('mostRecentQuarter', 'N/A'),
                'netIncomeToCommon': info.get('netIncomeToCommon', 'N/A'),
            }
            
            # Extract quarterly earnings data from income statement (replacing deprecated earnings)
            if not quarterly_income_stmt.empty:
                # Look for Net Income in the quarterly income statement
                net_income_rows = quarterly_income_stmt.loc[
                    quarterly_income_stmt.index.str.contains('Net Income', case=False, na=False)
                ]
                
                if not net_income_rows.empty:
                    # Get the first Net Income row (most comprehensive)
                    net_income_data = net_income_rows.iloc[0]
                    
                    # Get last 4 quarters of earnings data
                    for i, (date, net_income) in enumerate(net_income_data.items()):
                        if i < 4:  # Last 4 quarters
                            quarter_key = f'q{i+1}_net_income'
                            financial_data[quarter_key] = net_income if pd.notna(net_income) else 'N/A'
                            financial_data[f'q{i+1}_date'] = date.strftime('%Y-%m-%d') if pd.notna(date) else 'N/A'
            
            # Extract quarterly revenue data
            if not quarterly_income_stmt.empty:
                revenue_rows = quarterly_income_stmt.loc[
                    quarterly_income_stmt.index.str.contains('Total Revenue|Revenue', case=False, na=False)
                ]
                if not revenue_rows.empty:
                    revenue_data = revenue_rows.iloc[0]  # Get first revenue row
                    for i, (date, value) in enumerate(revenue_data.items()):
                        if i < 4:  # Last 4 quarters
                            financial_data[f'q{i+1}_revenue'] = value if pd.notna(value) else 'N/A'
            
            # Extract annual earnings data from income statement (replacing deprecated earnings)
            if not annual_income_stmt.empty:
                # Look for Net Income in the annual income statement
                annual_net_income_rows = annual_income_stmt.loc[
                    annual_income_stmt.index.str.contains('Net Income', case=False, na=False)
                ]
                
                if not annual_net_income_rows.empty:
                    annual_net_income_data = annual_net_income_rows.iloc[0]
                    
                    # Get last 3 years of earnings data
                    for i, (year, net_income) in enumerate(annual_net_income_data.items()):
                        if i < 3:  # Last 3 years
                            year_key = f'y{i+1}_net_income'
                            financial_data[year_key] = net_income if pd.notna(net_income) else 'N/A'
                            financial_data[f'y{i+1}_year'] = year.strftime('%Y') if pd.notna(year) else 'N/A'
            
            # Extract key balance sheet items for financial strength
            if not quarterly_balance_sheet.empty:
                try:
                    # Get most recent quarter balance sheet data
                    latest_bs = quarterly_balance_sheet.iloc[:, 0]  # Most recent quarter
                    
                    # Key balance sheet items for CANSLIM analysis
                    bs_items = {
                        'total_assets': ['Total Assets', 'TotalAssets'],
                        'total_debt': ['Total Debt', 'TotalDebt', 'Long Term Debt'],
                        'cash_and_equivalents': ['Cash And Cash Equivalents', 'CashAndCashEquivalents'],
                        'working_capital': ['Working Capital', 'WorkingCapital'],
                        'retained_earnings': ['Retained Earnings', 'RetainedEarnings'],
                        'stockholders_equity': ['Stockholder Equity', 'StockholdersEquity', 'Total Equity Gross Minority Interest']
                    }
                    
                    for key, possible_names in bs_items.items():
                        value = 'N/A'
                        for name in possible_names:
                            matching_rows = latest_bs[latest_bs.index.str.contains(name, case=False, na=False)]
                            if not matching_rows.empty:
                                value = matching_rows.iloc[0]
                                break
                        financial_data[f'latest_quarter_{key}'] = value
                        
                except Exception as e:
                    self.logger.warning(f"Error extracting balance sheet data for {ticker}: {str(e)}")
            
            # Extract cash flow data for financial strength
            if not quarterly_cashflow.empty:
                try:
                    latest_cf = quarterly_cashflow.iloc[:, 0]  # Most recent quarter
                    
                    cf_items = {
                        'operating_cash_flow': ['Operating Cash Flow', 'OperatingCashFlow'],
                        'free_cash_flow': ['Free Cash Flow', 'FreeCashFlow'],
                        'capital_expenditures': ['Capital Expenditures', 'CapitalExpenditures']
                    }
                    
                    for key, possible_names in cf_items.items():
                        value = 'N/A'
                        for name in possible_names:
                            matching_rows = latest_cf[latest_cf.index.str.contains(name, case=False, na=False)]
                            if not matching_rows.empty:
                                value = matching_rows.iloc[0]
                                break
                        financial_data[f'latest_quarter_{key}'] = value
                        
                except Exception as e:
                    self.logger.warning(f"Error extracting cash flow data for {ticker}: {str(e)}")
            
            return financial_data
            
        except Exception as e:
            self.logger.error(f"Error fetching financial data for {ticker}: {str(e)}")
            return {
                'ticker': ticker,
                'error': str(e),
                'last_updated': dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }

    def update_individual_stock_data(self, ticker):
        try:
            interval_str = self.config['interval'].replace("/", "")
            file_path = os.path.join(self.config['folder'], f"{ticker}.csv")
            ticker_obj = yf.Ticker(ticker)
            latest_yf_date = ticker_obj.history(period="1d").index[0].date()

            if os.path.isfile(file_path):
                #If the file exists, consider it successful regardless of updates
                self.successful_tickers.append(ticker)
                existing_data = pd.read_csv(file_path, index_col='Date', parse_dates=True)
                if not existing_data.empty:
                    latest_file_date = existing_data.index.max().date()
                    if latest_file_date >= latest_yf_date:
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
                self.logger.info(f"Updated data for {ticker} saved to {file_path}")
                self.logger.info(f"Data updated for {ticker} for the period: {start_date} to {latest_yf_date}")

                self.successful_tickers.append(ticker)
            else:
                self.logger.info(f"No new data available for {ticker}")

        except Exception as e:
            print(f"Error processing {ticker}: {str(e)}")
            self.problematic_tickers.append({'ticker': ticker, 'error': str(e)})
            print(f"Added {ticker} to problematic tickers list")

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
        print(f"Problematic tickers: {self.problematic_tickers}")

    def generate_financial_data_file(self):
        """
        Generate comprehensive financial data file for CANSLIM analysis
        """
        print("Generating financial data for CANSLIM analysis...")
        financial_data_list = []
        
        for i, ticker in enumerate(self.successful_tickers, 1):
            try:
                print(f"Processing financial data for {ticker} ({i}/{len(self.successful_tickers)})")
                financial_data = self.get_financial_data_for_canslim(ticker)
                financial_data_list.append(financial_data)
                
                # Add delay to avoid overwhelming the API
                time.sleep(1)  # 1 second delay between requests
                
                # Longer break every 50 tickers
                if i % 50 == 0:
                    print(f"Processed {i} tickers. Taking a longer break...")
                    time.sleep(10)
                    
            except Exception as e:
                self.logger.error(f"Error processing financial data for {ticker}: {str(e)}")
                continue
        
        if financial_data_list:
            financial_df = pd.DataFrame(financial_data_list)
            financial_df.to_csv(self.financial_data_file, index=False)
            print(f"Financial data saved to {self.financial_data_file}")
            print(f"Generated financial data for {len(financial_data_list)} tickers")
            
            # Create a summary of the data
            self.create_financial_data_summary(financial_df)
        else:
            print("No financial data generated.")
    
    def create_financial_data_summary(self, financial_df):
        """
        Create a summary of the financial data for quick analysis
        """
        try:
            summary_file = os.path.join(self.PARAMS_DIR["TICKERS_DIR"], f'financial_data_summary_{user_choice}.csv')
            
            # Create summary with key growth metrics
            summary_columns = [
                'ticker', 'sector', 'industry', 'marketCap', 'earningsGrowth', 
                'revenueGrowth', 'earningsQuarterlyGrowth', 'revenueQuarterlyGrowth',
                'trailingPE', 'pegRatio', 'returnOnEquity', 'profitMargins',
                'shortPercentOfFloat', 'heldPercentInstitutions'
            ]
            
            # Filter to only include columns that exist in the dataframe
            existing_columns = [col for col in summary_columns if col in financial_df.columns]
            summary_df = financial_df[existing_columns].copy()
            
            # Sort by quarterly earnings growth (descending) for high-growth companies
            if 'earningsQuarterlyGrowth' in summary_df.columns:
                summary_df = summary_df.sort_values('earningsQuarterlyGrowth', ascending=False, na_last=True)
            
            summary_df.to_csv(summary_file, index=False)
            print(f"Financial data summary saved to {summary_file}")
            
        except Exception as e:
            self.logger.error(f"Error creating financial data summary: {str(e)}")

    def generate_clean_tickers_file(self):
        if not hasattr(self, 'info_df') or self.info_df.empty:
            print("Info dataframe not initialized. Run generate_info_file() first.")
            return
    
        ok_df = pd.DataFrame(self.successful_tickers, columns=['ticker'])
        ok_full_df = self.info_df.merge(ok_df, on='ticker')
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
        ok_full_df = ok_full_df.drop_duplicates(subset=['ticker'])
        
        # Define the output file path for the portfolio clean tickers
        ok_file = os.path.join(self.PARAMS_DIR["TICKERS_DIR"], f'combined_info_tickers_clean_portfolio.csv')
        ok_full_df.to_csv(ok_file, index=False)
        print(f"Portfolio clean tickers file: {ok_file}")

    def get_stock_info(self, ticker):
        try:
            ticker_obj = yf.Ticker(ticker)
            info = ticker_obj.info
    
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
            self.info_df = pd.DataFrame()

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
                
            # Generate comprehensive financial data for CANSLIM analysis
            print("Generating comprehensive financial data for CANSLIM analysis...")
            self.generate_financial_data_file()
        else:
            print("Skipping metadata and info file generation (either interval ≠ '1d' or write_file_info is False)")
    
        # This section always runs
        if hasattr(self, 'tickers_list'):
            if hasattr(self, 'successful_tickers') and self.successful_tickers:
                ok_df = pd.DataFrame(self.successful_tickers, columns=['ticker'])
    
                clean_file = os.path.join(self.PARAMS_DIR["TICKERS_DIR"], f'combined_tickers_clean_{user_choice}.csv')
                ok_df.drop_duplicates().to_csv(clean_file, index=False)
                print(f"Clean (1-column) tickers file written: {clean_file}")
            else:
                print("No successful_tickers found — combined_tickers_clean_<x>.csv not generated.")


def run_market_data_retrieval(config, run_metadata=True):
    retriever = MarketDataRetriever(config)
    retriever.update_data()
