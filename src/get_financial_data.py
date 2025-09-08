import yfinance as yf
import pandas as pd
import datetime as dt
import time
import os
import logging
from src.config import user_choice, PARAMS_DIR


class FinancialDataRetriever:
    """
    Dedicated class for retrieving comprehensive financial data for CANSLIM analysis.
    Focuses on fundamental metrics, earnings, revenue, growth rates, and other
    financial indicators needed for stock screening and analysis.
    """
    
    def __init__(self, config=None):
        self.logger = logging.getLogger(__name__)
        self.config = config or {}
        self.PARAMS_DIR = PARAMS_DIR
        
        # File paths for financial data storage
        # Sanitize user_choice for filenames (replace dashes with underscores)
        safe_user_choice = str(user_choice).replace('-', '_')
        self.financial_data_file = os.path.join(
            self.PARAMS_DIR["TICKERS_DIR"], 
            f'financial_data_{safe_user_choice}.csv'
        )
        self.financial_summary_file = os.path.join(
            self.PARAMS_DIR["TICKERS_DIR"], 
            f'financial_data_summary_{safe_user_choice}.csv'
        )
        self.canslim_screened_file = os.path.join(
            self.PARAMS_DIR["TICKERS_DIR"], 
            f'canslim_screened_{safe_user_choice}.csv'
        )
        
        # Debug: Print file paths
        print(f"🔧 FinancialDataRetriever initialized with user_choice: {user_choice}")
        print(f"🔧 Financial data file: {self.financial_data_file}")
        print(f"🔧 Summary file: {self.financial_summary_file}")
        print(f"🔧 Screened file: {self.canslim_screened_file}")
        print(f"🔧 Tickers directory: {self.PARAMS_DIR['TICKERS_DIR']}")
        
        # Test directory access
        tickers_dir = self.PARAMS_DIR["TICKERS_DIR"]
        if os.path.exists(tickers_dir):
            print(f"✅ Tickers directory exists: {tickers_dir}")
            if os.access(tickers_dir, os.W_OK):
                print(f"✅ Tickers directory is writable")
            else:
                print(f"❌ Tickers directory is NOT writable")
        else:
            print(f"❌ Tickers directory does NOT exist: {tickers_dir}")
            print(f"🔧 Attempting to create directory...")
            try:
                os.makedirs(tickers_dir, exist_ok=True)
                print(f"✅ Created tickers directory")
            except Exception as e:
                print(f"❌ Failed to create directory: {e}")
        
        # Data collection settings for CANSLIM (more history needed)
        self.quarters_to_collect = 12  # 3 years of quarterly data
        self.years_to_collect = 5      # 5 years of annual data
        
    def load_tickers_from_file(self, ticker_file_path):
        """Load tickers from a CSV file"""
        try:
            ticker_data = pd.read_csv(ticker_file_path)
            return ticker_data['ticker'].tolist()
        except Exception as e:
            self.logger.error(f"Error loading tickers from {ticker_file_path}: {str(e)}")
            return []
    
    def get_comprehensive_financial_data(self, ticker):
        """
        Extract comprehensive financial data needed for CANSLIM analysis.
        Collects 8-12 quarters and 5+ years of historical data for trend analysis.
        
        Args:
            ticker (str): Stock ticker symbol
            
        Returns:
            dict: Comprehensive financial data dictionary
        """
        try:
            ticker_obj = yf.Ticker(ticker)
            info = ticker_obj.info
            
            # Get financial statements with extended history
            quarterly_income_stmt = ticker_obj.quarterly_income_stmt
            annual_income_stmt = ticker_obj.income_stmt
            quarterly_balance_sheet = ticker_obj.quarterly_balance_sheet
            annual_balance_sheet = ticker_obj.balance_sheet
            quarterly_cashflow = ticker_obj.quarterly_cashflow
            annual_cashflow = ticker_obj.cashflow
            
            financial_data = {
                'ticker': ticker,
                'last_updated': dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                
                # ============ BASIC COMPANY INFO ============
                'sector': info.get('sector', 'N/A'),
                'industry': info.get('industry', 'N/A'),
                'marketCap': info.get('marketCap', 'N/A'),
                'enterpriseValue': info.get('enterpriseValue', 'N/A'),
                'shortName': info.get('shortName', 'N/A'),
                'longName': info.get('longName', 'N/A'),
                'exchange': info.get('fullExchangeName', 'N/A'),
                'country': info.get('country', 'N/A'),
                'currency': info.get('currency', 'N/A'),
                
                # ============ C - CURRENT EARNINGS ============
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
                
                # ============ A - ANNUAL EARNINGS ============
                'returnOnEquity': info.get('returnOnEquity', 'N/A'),
                'returnOnAssets': info.get('returnOnAssets', 'N/A'),
                'grossMargins': info.get('grossMargins', 'N/A'),
                'operatingMargins': info.get('operatingMargins', 'N/A'),
                'profitMargins': info.get('profitMargins', 'N/A'),
                'ebitdaMargins': info.get('ebitdaMargins', 'N/A'),
                
                # ============ N & S - NEW STOCK & SUPPLY/DEMAND ============
                'sharesOutstanding': info.get('sharesOutstanding', 'N/A'),
                'floatShares': info.get('floatShares', 'N/A'),
                'sharesShort': info.get('sharesShort', 'N/A'),
                'shortRatio': info.get('shortRatio', 'N/A'),
                'shortPercentOfFloat': info.get('shortPercentOfFloat', 'N/A'),
                'heldPercentInsiders': info.get('heldPercentInsiders', 'N/A'),
                'heldPercentInstitutions': info.get('heldPercentInstitutions', 'N/A'),
                
                # ============ L - LEADER/LAGGARD ============
                'beta': info.get('beta', 'N/A'),
                'averageVolume': info.get('averageVolume', 'N/A'),
                'averageVolume10days': info.get('averageVolume10days', 'N/A'),
                'fiftyTwoWeekHigh': info.get('fiftyTwoWeekHigh', 'N/A'),
                'fiftyTwoWeekLow': info.get('fiftyTwoWeekLow', 'N/A'),
                'fiftyDayAverage': info.get('fiftyDayAverage', 'N/A'),
                'twoHundredDayAverage': info.get('twoHundredDayAverage', 'N/A'),
                
                # ============ I - INSTITUTIONAL SPONSORSHIP ============
                'bookValue': info.get('bookValue', 'N/A'),
                'priceToBook': info.get('priceToBook', 'N/A'),
                'recommendationKey': info.get('recommendationKey', 'N/A'),
                'numberOfAnalystOpinions': info.get('numberOfAnalystOpinions', 'N/A'),
                'targetHighPrice': info.get('targetHighPrice', 'N/A'),
                'targetLowPrice': info.get('targetLowPrice', 'N/A'),
                'targetMeanPrice': info.get('targetMeanPrice', 'N/A'),
                
                # ============ M - MARKET DIRECTION & FUNDAMENTALS ============
                'debtToEquity': info.get('debtToEquity', 'N/A'),
                'totalDebt': info.get('totalDebt', 'N/A'),
                'totalCash': info.get('totalCash', 'N/A'),
                'freeCashflow': info.get('freeCashflow', 'N/A'),
                'operatingCashflow': info.get('operatingCashflow', 'N/A'),
                'revenuePerShare': info.get('revenuePerShare', 'N/A'),
                'totalRevenue': info.get('totalRevenue', 'N/A'),
                'enterpriseToRevenue': info.get('enterpriseToRevenue', 'N/A'),
                'enterpriseToEbitda': info.get('enterpriseToEbitda', 'N/A'),
                'mostRecentQuarter': info.get('mostRecentQuarter', 'N/A'),
                'netIncomeToCommon': info.get('netIncomeToCommon', 'N/A'),
            }
            
            # ============ EXTENDED QUARTERLY DATA (8-12 quarters) ============
            self._extract_quarterly_data(financial_data, quarterly_income_stmt, quarterly_balance_sheet, quarterly_cashflow)
            
            # ============ EXTENDED ANNUAL DATA (5+ years) ============
            self._extract_annual_data(financial_data, annual_income_stmt, annual_balance_sheet, annual_cashflow)
            
            # ============ GROWTH TREND ANALYSIS ============
            #self._calculate_growth_trends(financial_data)
            
            # ============ CANSLIM SCORING ============
            #self._calculate_canslim_score(financial_data)
            
            return financial_data
            
        except Exception as e:
            self.logger.error(f"Error fetching financial data for {ticker}: {str(e)}")
            return {
                'ticker': ticker,
                'error': str(e),
                'last_updated': dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
    
    def _extract_quarterly_data(self, financial_data, quarterly_income_stmt, quarterly_balance_sheet, quarterly_cashflow):
        """Extract extended quarterly data (up to 12 quarters)"""
        
        # Extract quarterly earnings (Net Income)
        if not quarterly_income_stmt.empty:
            net_income_rows = quarterly_income_stmt.loc[
                quarterly_income_stmt.index.str.contains('Net Income', case=False, na=False)
            ]
            
            if not net_income_rows.empty:
                net_income_data = net_income_rows.iloc[0]
                
                # Get up to 12 quarters of earnings data
                for i, (date, net_income) in enumerate(net_income_data.items()):
                    if i < self.quarters_to_collect:
                        quarter_key = f'q{i+1}_net_income'
                        financial_data[quarter_key] = net_income if pd.notna(net_income) else 'N/A'
                        financial_data[f'q{i+1}_date'] = date.strftime('%Y-%m-%d') if pd.notna(date) else 'N/A'
        
        # Extract quarterly revenue
        if not quarterly_income_stmt.empty:
            revenue_rows = quarterly_income_stmt.loc[
                quarterly_income_stmt.index.str.contains('Total Revenue|Revenue', case=False, na=False)
            ]
            if not revenue_rows.empty:
                revenue_data = revenue_rows.iloc[0]
                for i, (date, value) in enumerate(revenue_data.items()):
                    if i < self.quarters_to_collect:
                        financial_data[f'q{i+1}_revenue'] = value if pd.notna(value) else 'N/A'
        
        # Extract quarterly operating income
        if not quarterly_income_stmt.empty:
            operating_income_rows = quarterly_income_stmt.loc[
                quarterly_income_stmt.index.str.contains('Operating Income', case=False, na=False)
            ]
            if not operating_income_rows.empty:
                operating_data = operating_income_rows.iloc[0]
                for i, (date, value) in enumerate(operating_data.items()):
                    if i < self.quarters_to_collect:
                        financial_data[f'q{i+1}_operating_income'] = value if pd.notna(value) else 'N/A'
    
    def _extract_annual_data(self, financial_data, annual_income_stmt, annual_balance_sheet, annual_cashflow):
        """Extract extended annual data (up to 5 years)"""
        
        # Extract annual earnings (Net Income)
        if not annual_income_stmt.empty:
            annual_net_income_rows = annual_income_stmt.loc[
                annual_income_stmt.index.str.contains('Net Income', case=False, na=False)
            ]
            
            if not annual_net_income_rows.empty:
                annual_net_income_data = annual_net_income_rows.iloc[0]
                
                # Get up to 5 years of earnings data
                for i, (year, net_income) in enumerate(annual_net_income_data.items()):
                    if i < self.years_to_collect:
                        year_key = f'y{i+1}_net_income'
                        financial_data[year_key] = net_income if pd.notna(net_income) else 'N/A'
                        financial_data[f'y{i+1}_year'] = year.strftime('%Y') if pd.notna(year) else 'N/A'
        
        # Extract annual revenue
        if not annual_income_stmt.empty:
            revenue_rows = annual_income_stmt.loc[
                annual_income_stmt.index.str.contains('Total Revenue|Revenue', case=False, na=False)
            ]
            if not revenue_rows.empty:
                revenue_data = revenue_rows.iloc[0]
                for i, (year, value) in enumerate(revenue_data.items()):
                    if i < self.years_to_collect:
                        financial_data[f'y{i+1}_revenue'] = value if pd.notna(value) else 'N/A'
    
    #def _calculate_growth_trends(self, financial_data):
    #    """Calculate growth trends over multiple periods"""
    #    try:
    #        # Calculate quarterly growth trends (QoQ and YoY)
    #        quarterly_earnings = []
    #        quarterly_revenues = []
    #        
    #        for i in range(1, min(9, self.quarters_to_collect + 1)):  # Last 8 quarters
    #            earnings = financial_data.get(f'q{i}_net_income', 'N/A')
    #            revenue = financial_data.get(f'q{i}_revenue', 'N/A')
    #            
    #            if earnings != 'N/A' and pd.notna(earnings):
    #                quarterly_earnings.append(float(earnings))
    #            if revenue != 'N/A' and pd.notna(revenue):
    #                quarterly_revenues.append(float(revenue))
    #        
    #        # Calculate growth acceleration
    #        if len(quarterly_earnings) >= 4:
    #            # Recent 2 quarters average growth vs prior 2 quarters
    #            recent_2q_avg = sum(quarterly_earnings[:2]) / 2
    #            prior_2q_avg = sum(quarterly_earnings[2:4]) / 2
    #            
    #            if prior_2q_avg != 0:
    #                earnings_acceleration = ((recent_2q_avg - prior_2q_avg) / abs(prior_2q_avg)) * 100
    #                financial_data['earnings_acceleration'] = earnings_acceleration
    #            else:
    #                financial_data['earnings_acceleration'] = 'N/A'
    #        
    #        # Similar calculation for revenue acceleration
    #        if len(quarterly_revenues) >= 4:
    #            recent_2q_avg = sum(quarterly_revenues[:2]) / 2
    #            prior_2q_avg = sum(quarterly_revenues[2:4]) / 2
    #            
    #            if prior_2q_avg != 0:
    #                revenue_acceleration = ((recent_2q_avg - prior_2q_avg) / abs(prior_2q_avg)) * 100
    #                financial_data['revenue_acceleration'] = revenue_acceleration
    #            else:
    #                financial_data['revenue_acceleration'] = 'N/A'
    #        
    #    except Exception as e:
    #        self.logger.warning(f"Error calculating growth trends for {financial_data.get('ticker', 'Unknown')}: {str(e)}")
    
    #def _calculate_canslim_score(self, financial_data):
    #    """Calculate a CANSLIM score based on key metrics"""
    #    score = 0
    #    max_score = 100
    #    score_breakdown = {}
    #    
    #    try:
    #        # C - Current Earnings (25 points)
    #        earnings_growth = financial_data.get('earningsQuarterlyGrowth', 'N/A')
    #        c_score = 0
    #        if earnings_growth != 'N/A' and isinstance(earnings_growth, (int, float)) and pd.notna(earnings_growth):
    #            if earnings_growth > 0.25:  # >25% growth
    #                c_score = 25
    #            elif earnings_growth > 0.10:  # >10% growth
    #                c_score = 15
    #            elif earnings_growth > 0:  # Positive growth
    #                c_score = 5
    #        score += c_score
    #        score_breakdown['C_current_earnings'] = c_score
    #        
    #        # A - Annual Earnings (20 points)
    #        annual_earnings_growth = financial_data.get('earningsGrowth', 'N/A')
    #        roe = financial_data.get('returnOnEquity', 'N/A')
    #        a_score = 0
    #        
    #        if annual_earnings_growth != 'N/A' and isinstance(annual_earnings_growth, (int, float)) and pd.notna(annual_earnings_growth):
    #            if annual_earnings_growth > 0.20:  # >20% annual growth
    #                a_score += 15
    #            elif annual_earnings_growth > 0.10:
    #                a_score += 10
    #            elif annual_earnings_growth > 0:
    #                a_score += 3
    #        
    #        if roe != 'N/A' and isinstance(roe, (int, float)) and pd.notna(roe) and roe > 0.15:  # >15% ROE
    #            a_score += 5
    #        
    #        score += a_score
    #        score_breakdown['A_annual_earnings'] = a_score
    #        
    #        # N - New (15 points)
    #        # This would require additional data about new products, management, etc.
    #        # For now, we'll use a placeholder score
    #        n_score = 7  # Placeholder
    #        score += n_score
    #        score_breakdown['N_new'] = n_score
    #        
    #        # S - Supply and Demand (15 points)
    #        short_float = financial_data.get('shortPercentOfFloat', 'N/A')
    #        institutional_holdings = financial_data.get('heldPercentInstitutions', 'N/A')
    #        s_score = 0
    #        
    #        if short_float != 'N/A' and isinstance(short_float, (int, float)) and pd.notna(short_float):
    #            if short_float < 0.10:  # Low short interest
    #                s_score += 8
    #            elif short_float < 0.20:
    #                s_score += 5
    #        
    #        if institutional_holdings != 'N/A' and isinstance(institutional_holdings, (int, float)) and pd.notna(institutional_holdings):
    #            if 0.40 <= institutional_holdings <= 0.80:  # Optimal institutional ownership
    #                s_score += 7
    #            elif institutional_holdings > 0.20:
    #                s_score += 3
    #        
    #        score += s_score
    #        score_breakdown['S_supply_demand'] = s_score
    #        
    #        # L - Leader or Laggard (15 points)
    #        market_cap = financial_data.get('marketCap', 'N/A')
    #        l_score = 0
    #        if market_cap != 'N/A' and isinstance(market_cap, (int, float)) and pd.notna(market_cap):
    #            if market_cap > 2000000000:  # > $2B market cap
    #                l_score = 10
    #            elif market_cap > 300000000:  # > $300M market cap
    #                l_score = 5
    #        
    #        score += l_score
    #        score_breakdown['L_leader'] = l_score
    #        
    #        # I - Institutional Sponsorship (10 points)
    #        analyst_opinions = financial_data.get('numberOfAnalystOpinions', 'N/A')
    #        i_score = 0
    #        if analyst_opinions != 'N/A' and isinstance(analyst_opinions, (int, float)) and pd.notna(analyst_opinions):
    #            if analyst_opinions >= 3:  # At least 3 analysts covering
    #                i_score = 10
    #            elif analyst_opinions >= 1:
    #                i_score = 5
    #        
    #        score += i_score
    #        score_breakdown['I_institutional'] = i_score
    #        
    #        financial_data['canslim_score'] = score
    #        financial_data['canslim_score_percentage'] = (score / max_score) * 100
    #        financial_data['canslim_breakdown'] = str(score_breakdown)
    #        
    #        # Debug output for first few tickers
    #        ticker = financial_data.get('ticker', 'Unknown')
    #        if hasattr(self, '_debug_count'):
    #            self._debug_count += 1
    #        else:
    #            self._debug_count = 1
    #        
    #        if self._debug_count <= 3:  # Debug first 3 tickers
    #            print(f"  CANSLIM Score for {ticker}: {score}/100 ({(score/max_score)*100:.1f}%)")
    #            print(f"    Breakdown: {score_breakdown}")
    #        
    #    except Exception as e:
    #        self.logger.warning(f"Error calculating CANSLIM score for {financial_data.get('ticker', 'Unknown')}: {str(e)}")
    #        financial_data['canslim_score'] = 0
    #        financial_data['canslim_score_percentage'] = 0
    #        financial_data['canslim_breakdown'] = str({'error': str(e)})
    
    def generate_financial_data_file(self, ticker_file_path, delay_between_requests=1):
        """
        Generate comprehensive financial data file for CANSLIM analysis
        
        Args:
            ticker_file_path (str): Path to the CSV file containing tickers
            delay_between_requests (float): Delay in seconds between API requests
        """
        print("Generating comprehensive financial data for CANSLIM analysis...")
        
        # Load tickers
        tickers_list = self.load_tickers_from_file(ticker_file_path)
        if not tickers_list:
            print("No tickers found to process.")
            return
        
        financial_data_list = []
        
        for i, ticker in enumerate(tickers_list, 1):
            try:
                print(f"Processing financial data for {ticker} ({i}/{len(tickers_list)})")
                financial_data = self.get_comprehensive_financial_data(ticker)
                
                if 'error' not in financial_data:
                    financial_data_list.append(financial_data)
                    # Show sample of collected data for first few tickers
                    #if i <= 3:
                    #    score = financial_data.get('canslim_score', 'N/A')
                    #    q_growth = financial_data.get('earningsQuarterlyGrowth', 'N/A')
                    #    print(f"  ✅ {ticker}: CANSLIM Score={score}, Q Growth={q_growth}")
                    if i <= 3:
                        print(f"  ✅ {ticker}: Financial data collected")
                else:
                    print(f"  ⚠️ Error with {ticker}: {financial_data.get('error', 'Unknown error')}")
                
                # Add delay to avoid overwhelming the API
                time.sleep(delay_between_requests)
                
                # Longer break every 50 tickers
                if i % 50 == 0:
                    print(f"Processed {i} tickers. Taking a longer break...")
                    time.sleep(10)
                    
            except Exception as e:
                self.logger.error(f"Error processing financial data for {ticker}: {str(e)}")
                print(f"  ❌ Exception processing {ticker}: {str(e)}")
                continue
        
        if financial_data_list:
            # Save comprehensive data
            financial_df = pd.DataFrame(financial_data_list)
            financial_df.to_csv(self.financial_data_file, index=False)
            print(f"✅ Financial data saved to {self.financial_data_file}")
            print(f"Generated financial data for {len(financial_data_list)} tickers")
            print(f"Dataframe shape: {financial_df.shape}")
            
            # Create summary file - BASIC IMPLEMENTATION (without CANSLIM calculations)
            print("\n" + "="*50)
            print("CREATING SUMMARY FILE")
            print("="*50)
            
            # SUMMARY FILE - Basic implementation without CANSLIM calculations
            try:
                print("Creating financial data summary...")
                summary_columns = [
                    'ticker', 'sector', 'industry', 'marketCap', 'earningsGrowth', 
                    'revenueGrowth', 'earningsQuarterlyGrowth', 'revenueQuarterlyGrowth',
                    'trailingPE', 'pegRatio', 'returnOnEquity', 'profitMargins',
                    'shortPercentOfFloat', 'heldPercentInstitutions'
                    #'canslim_score', 'canslim_score_percentage', 'earnings_acceleration', 'revenue_acceleration'
                ]
                
                existing_columns = [col for col in summary_columns if col in financial_df.columns]
                missing_columns = [col for col in summary_columns if col not in financial_df.columns]
                
                print(f"Found {len(existing_columns)} matching columns for summary")
                if missing_columns:
                    print(f"Missing columns: {missing_columns}")
                
                if existing_columns:
                    summary_df = financial_df[existing_columns].copy()
                else:
                    summary_df = financial_df.copy()
                
                # Sort by market cap if available
                #if 'canslim_score' in summary_df.columns:
                #    summary_df = summary_df.sort_values('canslim_score', ascending=False, na_position='last')
                if 'marketCap' in summary_df.columns:
                    # Convert marketCap to numeric, coercing errors to NaN
                    summary_df['marketCap'] = pd.to_numeric(summary_df['marketCap'], errors='coerce')
                    summary_df = summary_df.sort_values('marketCap', ascending=False, na_position='last')
                
                # Save summary file
                summary_df.to_csv(self.financial_summary_file, index=False)
                
                if os.path.exists(self.financial_summary_file):
                    file_size = os.path.getsize(self.financial_summary_file)
                    print(f"📊 Financial data summary saved to {self.financial_summary_file} (Size: {file_size} bytes)")
                else:
                    print(f"❌ Summary file was not created")
                    
            except Exception as e:
                print(f"❌ Error creating summary file: {e}")
                import traceback
                traceback.print_exc()
            
            # SCREENED FILE - COMMENTED OUT  
            #try:
            #    print("Creating CANSLIM screened file...")
            #    screened_df = financial_df.copy()
            #    original_count = len(screened_df)
            #    
            #    # Apply CANSLIM screening criteria
            #    conditions = []
            #    
            #    # Convert columns to numeric and apply filters
            #    for col in ['earningsQuarterlyGrowth', 'earningsGrowth', 'shortPercentOfFloat', 'marketCap']:
            #        if col in screened_df.columns:
            #            screened_df[col] = pd.to_numeric(screened_df[col], errors='coerce')
            #    
            #    # C - Current Earnings: Quarterly growth > 20%
            #    if 'earningsQuarterlyGrowth' in screened_df.columns:
            #        condition = (screened_df['earningsQuarterlyGrowth'].notna()) & (screened_df['earningsQuarterlyGrowth'] > 0.20)
            #        conditions.append(condition)
            #        meeting = condition.sum()
            #        total = screened_df['earningsQuarterlyGrowth'].notna().sum()
            #        print(f"  • Quarterly Earnings Growth > 20%: {meeting}/{total} stocks")
            #    
            #    # A - Annual Earnings: Annual growth > 15%
            #    if 'earningsGrowth' in screened_df.columns:
            #        condition = (screened_df['earningsGrowth'].notna()) & (screened_df['earningsGrowth'] > 0.15)
            #        conditions.append(condition)
            #        meeting = condition.sum()
            #        total = screened_df['earningsGrowth'].notna().sum()
            #        print(f"  • Annual Earnings Growth > 15%: {meeting}/{total} stocks")
            #    
            #    # S - Supply: Short interest < 20%
            #    if 'shortPercentOfFloat' in screened_df.columns:
            #        condition = (screened_df['shortPercentOfFloat'].notna()) & (screened_df['shortPercentOfFloat'] < 0.20)
            #        conditions.append(condition)
            #        meeting = condition.sum()
            #        total = screened_df['shortPercentOfFloat'].notna().sum()
            #        print(f"  • Short Interest < 20%: {meeting}/{total} stocks")
            #    
            #    # L - Leader: Market cap > $300M
            #    if 'marketCap' in screened_df.columns:
            #        condition = (screened_df['marketCap'].notna()) & (screened_df['marketCap'] > 300000000)
            #        conditions.append(condition)
            #        meeting = condition.sum()
            #        total = screened_df['marketCap'].notna().sum()
            #        print(f"  • Market Cap > $300M: {meeting}/{total} stocks")
            #    
            #    # Apply all conditions
            #    if conditions:
            #        print(f"Applying {len(conditions)} CANSLIM criteria...")
            #        combined_condition = conditions[0]
            #        for i, condition in enumerate(conditions[1:], 1):
            #            combined_condition = combined_condition & condition
            #            remaining = combined_condition.sum()
            #            print(f"  After {i+1} criteria: {remaining} stocks remaining")
            #        
            #        screened_df = screened_df[combined_condition]
            #    else:
            #        print("No screening criteria could be applied - using market cap filter")
            #        if 'marketCap' in screened_df.columns:
            #            screened_df = screened_df[screened_df['marketCap'] > 300000000]
            #    
            #    # Sort by CANSLIM score if available
            #    if 'canslim_score' in screened_df.columns:
            #        screened_df = screened_df.sort_values('canslim_score', ascending=False, na_position='last')
            #    
            #    # Save screened file
            #    screened_df.to_csv(self.canslim_screened_file, index=False)
            #    
            #    if os.path.exists(self.canslim_screened_file):
            #        file_size = os.path.getsize(self.canslim_screened_file)
            #        print(f"🎯 CANSLIM screened stocks saved to {self.canslim_screened_file} (Size: {file_size} bytes)")
            #        print(f"Screened {original_count} → {len(screened_df)} stocks meeting criteria")
            #        
            #        # Show top candidates
            #        if len(screened_df) > 0:
            #            print(f"Top 5 CANSLIM candidates:")
            #            for i, (_, row) in enumerate(screened_df.head(5).iterrows()):
            #                ticker = row.get('ticker', 'N/A')
            #                score = row.get('canslim_score', 'N/A')
            #                q_growth = row.get('earningsQuarterlyGrowth', 'N/A')
            #                print(f"  {i+1}. {ticker}: CANSLIM Score={score}, Q Growth={q_growth}")
            #    else:
            #        print(f"❌ Screened file was not created")
            #        
            #except Exception as e:
            #    print(f"❌ Error creating screened file: {e}")
            #    import traceback
            #    traceback.print_exc()
            
            print("="*50)
            
        else:
            print("❌ No financial data generated.")
    
    #def create_financial_data_summary(self, financial_df):
    #    """Create a summary of the financial data for quick analysis"""
    #    print("🔍 ENTERING create_financial_data_summary function")
    #    print(f"🔍 Received DataFrame with shape: {financial_df.shape}")
    #    print(f"🔍 Summary file path: {self.financial_summary_file}")
    #    
    #    try:
    #        # Key columns for summary
    #        summary_columns = [
    #            'ticker', 'sector', 'industry', 'marketCap', 'earningsGrowth', 
    #            'revenueGrowth', 'earningsQuarterlyGrowth', 'revenueQuarterlyGrowth',
    #            'trailingPE', 'pegRatio', 'returnOnEquity', 'profitMargins',
    #            'shortPercentOfFloat', 'heldPercentInstitutions', 'canslim_score',
    #            'canslim_score_percentage', 'earnings_acceleration', 'revenue_acceleration'
    #        ]
    #        
    #        # Filter to only include columns that exist in the dataframe
    #        existing_columns = [col for col in summary_columns if col in financial_df.columns]
    #        summary_df = financial_df[existing_columns].copy()
    #        
    #        # Sort by CANSLIM score (descending)
    #        if 'canslim_score' in summary_df.columns:
    #            summary_df = summary_df.sort_values('canslim_score', ascending=False, na_last=True)
    #        elif 'earningsQuarterlyGrowth' in summary_df.columns:
    #            summary_df = summary_df.sort_values('earningsQuarterlyGrowth', ascending=False, na_last=True)
    #        
    #        summary_df.to_csv(self.financial_summary_file, index=False)
    #        print(f"📊 Financial data summary saved to {self.financial_summary_file}")
    #        
    #    except Exception as e:
    #        self.logger.error(f"Error creating financial data summary: {str(e)}")
    
    #def create_canslim_screened_file(self, financial_df):
    #    """Create a file with stocks that meet CANSLIM criteria"""
    #    print("🔍 ENTERING create_canslim_screened_file function")
    #    print(f"🔍 Received DataFrame with shape: {financial_df.shape}")
    #    print(f"🔍 Screened file path: {self.canslim_screened_file}")
    #    
    #    try:
    #        # CANSLIM screening criteria
    #        screened_df = financial_df.copy()
    #        
    #        # Apply filters
    #        conditions = []
    #        
    #        # C - Current Earnings: Quarterly growth > 20%
    #        if 'earningsQuarterlyGrowth' in screened_df.columns:
    #            conditions.append(
    #                (screened_df['earningsQuarterlyGrowth'].notna()) & 
    #                (screened_df['earningsQuarterlyGrowth'] > 0.20)
    #            )
    #        
    #        # A - Annual Earnings: Annual growth > 15%
    #        if 'earningsGrowth' in screened_df.columns:
    #            conditions.append(
    #                (screened_df['earningsGrowth'].notna()) & 
    #                (screened_df['earningsGrowth'] > 0.15)
    #            )
    #        
    #        # S - Supply: Short interest < 20%
    #        if 'shortPercentOfFloat' in screened_df.columns:
    #            conditions.append(
    #                (screened_df['shortPercentOfFloat'].notna()) & 
    #                (screened_df['shortPercentOfFloat'] < 0.20)
    #            )
    #        
    #        # L - Leader: Market cap > $300M
    #        if 'marketCap' in screened_df.columns:
    #            conditions.append(
    #                (screened_df['marketCap'].notna()) & 
    #                (screened_df['marketCap'] > 300000000)
    #            )
    #        
    #        # Apply all conditions
    #        if conditions:
    #            combined_condition = conditions[0]
    #            for condition in conditions[1:]:
    #                combined_condition = combined_condition & condition
    #            
    #            screened_df = screened_df[combined_condition]
    #        
    #        # Sort by CANSLIM score
    #        if 'canslim_score' in screened_df.columns:
    #            screened_df = screened_df.sort_values('canslim_score', ascending=False)
    #        
    #        screened_df.to_csv(self.canslim_screened_file, index=False)
    #        print(f"🎯 CANSLIM screened stocks saved to {self.canslim_screened_file}")
    #        print(f"Found {len(screened_df)} stocks meeting CANSLIM criteria")
    #        
    #    except Exception as e:
    #        self.logger.error(f"Error creating CANSLIM screened file: {str(e)}")


def run_financial_data_retrieval(ticker_file_path, config=None):
    """
    Main function to run financial data retrieval
    
    Args:
        ticker_file_path (str): Path to the CSV file containing tickers
        config (dict): Configuration dictionary
    """
    retriever = FinancialDataRetriever(config)
    retriever.generate_financial_data_file(ticker_file_path)
