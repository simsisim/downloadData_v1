import yfinance as yf
import pandas as pd
import datetime as dt
import time
import os
import json
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
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
        fin_data_dir = self.PARAMS_DIR["FIN_DATA_DIR"]
        self.financial_data_file = os.path.join(
            fin_data_dir,
            f'financial_data_{safe_user_choice}.csv'
        )
        self.financial_summary_file = os.path.join(
            fin_data_dir,
            f'financial_data_summary_{safe_user_choice}.csv'
        )
        self.canslim_screened_file = os.path.join(
            fin_data_dir,
            f'canslim_screened_{safe_user_choice}.csv'
        )

        # Debug: Print file paths
        print(f"🔧 FinancialDataRetriever initialized with user_choice: {user_choice}")
        print(f"🔧 Financial data file: {self.financial_data_file}")
        print(f"🔧 Summary file: {self.financial_summary_file}")
        print(f"🔧 Screened file: {self.canslim_screened_file}")
        print(f"🔧 Financial data directory: {fin_data_dir}")

        # Test directory access
        if os.path.exists(fin_data_dir):
            print(f"✅ Financial data directory exists: {fin_data_dir}")
            if os.access(fin_data_dir, os.W_OK):
                print(f"✅ Financial data directory is writable")
            else:
                print(f"❌ Financial data directory is NOT writable")
        else:
            print(f"❌ Financial data directory does NOT exist: {fin_data_dir}")
            print(f"🔧 Attempting to create directory...")
            try:
                os.makedirs(fin_data_dir, exist_ok=True)
                print(f"✅ Created financial data directory")
            except Exception as e:
                print(f"❌ Failed to create directory: {e}")
        
        # Data collection settings for CANSLIM (more history needed)
        self.quarters_to_collect = 12  # 3 years of quarterly data
        self.years_to_collect = 5      # 5 years of annual data

        # Institutional sponsorship detail (major/institutional/mutualfund holders)
        # requires 3 extra yfinance calls per ticker - opt-in to avoid slowing down
        # large-universe runs / hitting rate limits.
        self.collect_sponsorship_detail = bool(self.config.get('collect_sponsorship_detail', False))

        # quarterly_income_stmt only exposes ~5 trailing quarters via yfinance's free
        # feed, too few for O'Neil's 3-quarter acceleration check (needs 7+). This
        # separate deep-history source (ticker.get_earnings_dates) covers years of
        # reported EPS instead - always-on, since it's central to the "C" criterion
        # and costs just 1 extra request/ticker (vs. 3 for sponsorship detail).
        self.earnings_history_limit = int(self.config.get('earnings_history_limit', 12))

        # Incremental refresh: skip re-fetching a ticker if its stored data is
        # already fresher than this many days (fundamentals change slowly - no
        # need to burn 7-10 yfinance calls/ticker on data that hasn't changed).
        self.refresh_days = int(self.config.get('refresh_days', 7))
        self.force_refresh = bool(self.config.get('force_refresh', False))

        # Concurrent fetches: each ticker's ~10s cost is almost entirely network
        # wait (profiled directly - see get_comprehensive_financial_data's 8-11
        # separate yfinance/HTTP calls), not CPU, so overlapping several tickers'
        # I/O gives a near-linear speedup (measured ~4x at 5 workers on a live
        # test). 1 = fully sequential, identical to the old behavior. Kept
        # modest by default since a short burst test can't fully rule out
        # Yahoo rate-limiting under sustained full-universe load.
        self.max_workers = max(1, int(self.config.get('max_workers', 1)))

    @staticmethod
    def _get_row_by_exact_name(df, row_name):
        """Return a Series for an exact statement row name, or None if absent/empty."""
        if df is None or df.empty or row_name not in df.index:
            return None
        return df.loc[row_name]

    def _ticker_cache_path(self, ticker):
        return os.path.join(self.PARAMS_DIR["FIN_DATA_TICKERS_DIR"], f"{ticker}.json")

    def _load_ticker_cache(self, ticker):
        """
        Return the cached financial_data dict for a ticker, or None if absent/
        unreadable. This is the freshness source of truth - one file per ticker,
        independent of ticker_choice, so a ticker fetched under one ticker_choice
        is recognized as fresh under any other choice that also includes it.
        """
        path = self._ticker_cache_path(ticker)
        if not os.path.exists(path):
            return None
        try:
            with open(path, 'r') as f:
                return json.load(f)
        except Exception as e:
            self.logger.warning(f"Could not read cache for {ticker}: {str(e)}")
            return None

    def _save_ticker_cache(self, ticker, financial_data):
        """
        Write a ticker's financial_data dict to its cache file. Called right
        after a successful fetch (not batched at the end) so a run that dies
        partway through doesn't lose already-fetched tickers.
        """
        try:
            with open(self._ticker_cache_path(ticker), 'w') as f:
                json.dump(financial_data, f)
        except Exception as e:
            self.logger.warning(f"Could not save cache for {ticker}: {str(e)}")

    def _is_fresh(self, last_updated_str):
        """True if a stored 'last_updated' timestamp is within self.refresh_days of now."""
        try:
            last_updated = dt.datetime.strptime(str(last_updated_str), '%Y-%m-%d %H:%M:%S')
        except (ValueError, TypeError):
            return False
        return (dt.datetime.now() - last_updated) <= dt.timedelta(days=self.refresh_days)

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
                
                # ============ N - NEW (PRODUCTS/MANAGEMENT/NEW HIGHS) ============
                'fiftyTwoWeekHighChangePercent': info.get('fiftyTwoWeekHighChangePercent', 'N/A'),
                'allTimeHigh': info.get('allTimeHigh', 'N/A'),
                'firstTradeDateMilliseconds': info.get('firstTradeDateMilliseconds', 'N/A'),

                # ============ S - SUPPLY/DEMAND ============
                'sharesOutstanding': info.get('sharesOutstanding', 'N/A'),
                'floatShares': info.get('floatShares', 'N/A'),
                'sharesShort': info.get('sharesShort', 'N/A'),
                'shortRatio': info.get('shortRatio', 'N/A'),
                'shortPercentOfFloat': info.get('shortPercentOfFloat', 'N/A'),
                'heldPercentInsiders': info.get('heldPercentInsiders', 'N/A'),

                # ============ L - LEADER/LAGGARD ============
                'beta': info.get('beta', 'N/A'),
                'averageVolume': info.get('averageVolume', 'N/A'),
                'averageVolume10days': info.get('averageVolume10days', 'N/A'),
                'fiftyTwoWeekHigh': info.get('fiftyTwoWeekHigh', 'N/A'),
                'fiftyTwoWeekLow': info.get('fiftyTwoWeekLow', 'N/A'),
                'fiftyDayAverage': info.get('fiftyDayAverage', 'N/A'),
                'twoHundredDayAverage': info.get('twoHundredDayAverage', 'N/A'),

                # ============ I - INSTITUTIONAL SPONSORSHIP ============
                'heldPercentInstitutions': info.get('heldPercentInstitutions', 'N/A'),
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
            
            # N - derive years since IPO/listing from firstTradeDateMilliseconds
            first_trade_ms = info.get('firstTradeDateMilliseconds', None)
            if first_trade_ms:
                first_trade_date = dt.datetime.fromtimestamp(first_trade_ms / 1000)
                financial_data['yearsSincePublic'] = round((dt.datetime.now() - first_trade_date).days / 365.25, 1)
            else:
                financial_data['yearsSincePublic'] = 'N/A'

            # ============ EXTENDED QUARTERLY DATA (8-12 quarters) ============
            self._extract_quarterly_data(financial_data, quarterly_income_stmt, quarterly_balance_sheet, quarterly_cashflow)

            # ============ EXTENDED ANNUAL DATA (5+ years) ============
            self._extract_annual_data(financial_data, annual_income_stmt, annual_balance_sheet, annual_cashflow)

            # ============ C - DEEP QUARTERLY EARNINGS HISTORY (beyond the ~5-quarter statement cap) ============
            self._extract_earnings_history(financial_data, ticker_obj)

            # ============ I - INSTITUTIONAL SPONSORSHIP DETAIL (gated, extra API calls) ============
            if self.collect_sponsorship_detail:
                self._extract_sponsorship_detail(financial_data, ticker_obj)

            # ============ C/A - EPS GROWTH (YoY + acceleration, diluted & basic) ============
            self._calculate_eps_growth(financial_data)

            # ============ A - ANNUAL EARNINGS QUALITY (ROE + cash-flow-per-share vs EPS) ============
            self._calculate_annual_quality(financial_data)

            # ============ N - NEW-HIGH / RECENT-IPO THRESHOLD FLAGS ============
            self._calculate_n_flags(financial_data)

            # ============ S - SUPPLY TREND (BUYBACK VS DILUTION) ============
            self._calculate_supply_trend(financial_data)

            # ============ I - SPONSORSHIP LEVEL CLASSIFICATION ============
            self._calculate_sponsorship_level(financial_data)

            # ============ CANSI COMPOSITE SIGNAL ============
            self._calculate_cansi_score(financial_data)

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

        # C - Extract quarterly diluted EPS (YoY comparison + acceleration checks)
        eps_data = self._get_row_by_exact_name(quarterly_income_stmt, 'Diluted EPS')
        if eps_data is not None:
            for i, (date, value) in enumerate(eps_data.items()):
                if i < self.quarters_to_collect:
                    financial_data[f'q{i+1}_eps'] = value if pd.notna(value) else 'N/A'

        # C - Extract quarterly basic EPS (undiluted - kept alongside diluted, undecided yet which O'Neil intended)
        basic_eps_data = self._get_row_by_exact_name(quarterly_income_stmt, 'Basic EPS')
        if basic_eps_data is not None:
            for i, (date, value) in enumerate(basic_eps_data.items()):
                if i < self.quarters_to_collect:
                    financial_data[f'q{i+1}_eps_basic'] = value if pd.notna(value) else 'N/A'

        # C - Extract quarterly pretax income (margin-expansion / quality-of-earnings check)
        pretax_data = self._get_row_by_exact_name(quarterly_income_stmt, 'Pretax Income')
        if pretax_data is not None:
            for i, (date, value) in enumerate(pretax_data.items()):
                if i < self.quarters_to_collect:
                    financial_data[f'q{i+1}_pretax_income'] = value if pd.notna(value) else 'N/A'

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

        # A - Extract annual diluted EPS (3-5yr growth consistency check)
        annual_eps_data = self._get_row_by_exact_name(annual_income_stmt, 'Diluted EPS')
        if annual_eps_data is not None:
            for i, (year, value) in enumerate(annual_eps_data.items()):
                if i < self.years_to_collect:
                    financial_data[f'y{i+1}_eps'] = value if pd.notna(value) else 'N/A'

        # A - Extract annual basic EPS (undiluted - kept alongside diluted, undecided yet which O'Neil intended)
        annual_basic_eps_data = self._get_row_by_exact_name(annual_income_stmt, 'Basic EPS')
        if annual_basic_eps_data is not None:
            for i, (year, value) in enumerate(annual_basic_eps_data.items()):
                if i < self.years_to_collect:
                    financial_data[f'y{i+1}_eps_basic'] = value if pd.notna(value) else 'N/A'

        # A - Extract annual pretax income (margin trend)
        annual_pretax_data = self._get_row_by_exact_name(annual_income_stmt, 'Pretax Income')
        if annual_pretax_data is not None:
            for i, (year, value) in enumerate(annual_pretax_data.items()):
                if i < self.years_to_collect:
                    financial_data[f'y{i+1}_pretax_income'] = value if pd.notna(value) else 'N/A'

        # A - Extract annual stockholders' equity (real ROE-trend basis)
        equity_data = self._get_row_by_exact_name(annual_balance_sheet, 'Stockholders Equity')
        if equity_data is not None:
            for i, (year, value) in enumerate(equity_data.items()):
                if i < self.years_to_collect:
                    financial_data[f'y{i+1}_stockholders_equity'] = value if pd.notna(value) else 'N/A'

        # A - Extract annual long-term debt (falling debt is a supporting "A" signal)
        ltd_data = self._get_row_by_exact_name(annual_balance_sheet, 'Long Term Debt')
        if ltd_data is not None:
            for i, (year, value) in enumerate(ltd_data.items()):
                if i < self.years_to_collect:
                    financial_data[f'y{i+1}_long_term_debt'] = value if pd.notna(value) else 'N/A'

        # A - Extract annual operating cash flow (cash-flow-per-share vs EPS quality check)
        ocf_data = self._get_row_by_exact_name(annual_cashflow, 'Operating Cash Flow')
        if ocf_data is not None:
            for i, (year, value) in enumerate(ocf_data.items()):
                if i < self.years_to_collect:
                    financial_data[f'y{i+1}_operating_cashflow'] = value if pd.notna(value) else 'N/A'

        # S - Extract annual ordinary shares outstanding (buyback/dilution trend)
        shares_data = self._get_row_by_exact_name(annual_balance_sheet, 'Ordinary Shares Number')
        if shares_data is not None:
            for i, (year, value) in enumerate(shares_data.items()):
                if i < self.years_to_collect:
                    financial_data[f'y{i+1}_shares_outstanding'] = value if pd.notna(value) else 'N/A'

        # S - Extract annual treasury shares (confirms buyback activity)
        treasury_data = self._get_row_by_exact_name(annual_balance_sheet, 'Treasury Shares Number')
        if treasury_data is not None:
            for i, (year, value) in enumerate(treasury_data.items()):
                if i < self.years_to_collect:
                    financial_data[f'y{i+1}_treasury_shares'] = value if pd.notna(value) else 'N/A'

        # S - Extract annual stock buyback $ (direct evidence, stronger than share-count diffing)
        buyback_data = self._get_row_by_exact_name(annual_cashflow, 'Repurchase Of Capital Stock')
        if buyback_data is not None:
            for i, (year, value) in enumerate(buyback_data.items()):
                if i < self.years_to_collect:
                    financial_data[f'y{i+1}_buyback'] = value if pd.notna(value) else 'N/A'

    def _extract_earnings_history(self, financial_data, ticker_obj):
        """
        C - Deep quarterly EPS history via ticker.get_earnings_dates(), which covers
        years of reported EPS vs. the ~5 trailing quarters yfinance's free feed
        exposes through quarterly_income_stmt. 'Reported EPS' here is diluted-basis
        (cross-verified against q{i}_eps). Keys use a 'qh{i}_' (quarter-history)
        prefix so they don't collide with the statement-based q{i}_eps series.
        """
        ticker = financial_data.get('ticker', 'Unknown')
        try:
            earnings_dates = ticker_obj.get_earnings_dates(limit=self.earnings_history_limit)
        except Exception as e:
            self.logger.warning(f"Error fetching earnings_dates for {ticker}: {str(e)}")
            return

        if earnings_dates is None or earnings_dates.empty:
            return

        # Drop future/upcoming rows (estimate present, nothing reported yet)
        reported = earnings_dates[earnings_dates['Reported EPS'].notna()]

        for i, (date, row) in enumerate(reported.iterrows()):
            idx = i + 1
            financial_data[f'qh{idx}_date'] = date.strftime('%Y-%m-%d') if pd.notna(date) else 'N/A'
            financial_data[f'qh{idx}_eps'] = row['Reported EPS'] if pd.notna(row['Reported EPS']) else 'N/A'
            financial_data[f'qh{idx}_eps_estimate'] = row['EPS Estimate'] if pd.notna(row['EPS Estimate']) else 'N/A'
            financial_data[f'qh{idx}_surprise_pct'] = row['Surprise(%)'] if pd.notna(row['Surprise(%)']) else 'N/A'

    def _extract_sponsorship_detail(self, financial_data, ticker_obj):
        """
        Extract institutional/mutual-fund sponsorship detail (I).
        Requires 3 extra yfinance calls per ticker - only called when
        self.collect_sponsorship_detail is True. Each sub-call is isolated
        so one failure never drops the ticker's already-collected data.
        """
        ticker = financial_data.get('ticker', 'Unknown')

        try:
            major_holders = ticker_obj.major_holders
            if major_holders is not None and not major_holders.empty and 'institutionsCount' in major_holders.index:
                financial_data['institutionsCount'] = major_holders.loc['institutionsCount', 'Value']
                financial_data['institutionsPercentHeld'] = major_holders.loc['institutionsPercentHeld', 'Value']
            else:
                financial_data['institutionsCount'] = 'N/A'
                financial_data['institutionsPercentHeld'] = 'N/A'
        except Exception as e:
            self.logger.warning(f"Error fetching major_holders for {ticker}: {str(e)}")
            financial_data['institutionsCount'] = 'N/A'
            financial_data['institutionsPercentHeld'] = 'N/A'

        try:
            inst_holders = ticker_obj.institutional_holders
            if inst_holders is not None and not inst_holders.empty:
                financial_data['institutional_holders_count'] = len(inst_holders)
                financial_data['institutional_holders_avg_pct_change'] = (
                    inst_holders['pctChange'].mean() if 'pctChange' in inst_holders.columns else 'N/A'
                )
            else:
                financial_data['institutional_holders_count'] = 'N/A'
                financial_data['institutional_holders_avg_pct_change'] = 'N/A'
        except Exception as e:
            self.logger.warning(f"Error fetching institutional_holders for {ticker}: {str(e)}")
            financial_data['institutional_holders_count'] = 'N/A'
            financial_data['institutional_holders_avg_pct_change'] = 'N/A'

        try:
            mf_holders = ticker_obj.mutualfund_holders
            if mf_holders is not None and not mf_holders.empty:
                financial_data['mutualfund_holders_count'] = len(mf_holders)
                financial_data['mutualfund_holders_avg_pct_change'] = (
                    mf_holders['pctChange'].mean() if 'pctChange' in mf_holders.columns else 'N/A'
                )
            else:
                financial_data['mutualfund_holders_count'] = 'N/A'
                financial_data['mutualfund_holders_avg_pct_change'] = 'N/A'
        except Exception as e:
            self.logger.warning(f"Error fetching mutualfund_holders for {ticker}: {str(e)}")
            financial_data['mutualfund_holders_count'] = 'N/A'
            financial_data['mutualfund_holders_avg_pct_change'] = 'N/A'

    @staticmethod
    def _safe_growth_rate(current, prior):
        """
        YoY growth rate as a fraction (0.25 = +25%). Returns 'N/A' when not
        numeric or when the prior-period value is zero/negative - a percentage
        is not meaningful when earnings swing across zero (e.g. loss -> profit).
        """
        if current in (None, 'N/A') or prior in (None, 'N/A'):
            return 'N/A'
        if not isinstance(current, (int, float)) or not isinstance(prior, (int, float)):
            return 'N/A'
        if pd.isna(current) or pd.isna(prior) or prior <= 0:
            return 'N/A'
        return (current - prior) / prior

    @staticmethod
    def _safe_ratio(numerator, denominator):
        """
        numerator/denominator, e.g. for ROE or cash-flow-per-share. Returns
        'N/A' when not numeric or when denominator <= 0 - ratios involving a
        non-positive denominator (e.g. negative equity from heavy buybacks)
        aren't meaningfully interpretable as a simple ratio.
        """
        if numerator in (None, 'N/A') or denominator in (None, 'N/A'):
            return 'N/A'
        if not isinstance(numerator, (int, float)) or not isinstance(denominator, (int, float)):
            return 'N/A'
        if pd.isna(numerator) or pd.isna(denominator) or denominator <= 0:
            return 'N/A'
        return numerator / denominator

    @staticmethod
    def _is_number(value):
        """True if value is a real, non-NaN int/float (not the 'N/A' sentinel)."""
        return isinstance(value, (int, float)) and not pd.isna(value)

    def _calculate_eps_growth(self, financial_data):
        """
        C - Quarterly YoY EPS growth (statement-based, capped at ~5 quarters by
        yfinance, and deep-history qh-based, which actually has enough quarters
        for O'Neil's 3-quarter acceleration check) + the acceleration flag itself.
        A - Annual YoY EPS growth.
        Computed for both diluted (q{i}_eps / y{i}_eps) and basic
        (q{i}_eps_basic / y{i}_eps_basic) so the two bases can be compared
        before deciding which one to standardize on for screening.
        """
        # C - quarterly YoY growth (statement-based): compare q{i} against q{i+4}
        # (same calendar quarter one year earlier). In practice yfinance only
        # returns ~5 quarters here, so usually only q1's pair is fillable - kept
        # for cross-checking against the deep qh-based series below.
        max_quarter_pairs = self.quarters_to_collect - 4
        for i in range(1, max_quarter_pairs + 1):
            for suffix in ('', '_basic'):
                current = financial_data.get(f'q{i}_eps{suffix}', 'N/A')
                prior = financial_data.get(f'q{i+4}_eps{suffix}', 'N/A')
                financial_data[f'q{i}_eps{suffix}_growth_yoy'] = self._safe_growth_rate(current, prior)

        # C - quarterly YoY growth (deep-history, qh-based): same YoY-pairing
        # logic, but against the much longer earnings_dates series so there's
        # actually enough history for a real acceleration check.
        max_qh_pairs = self.earnings_history_limit - 4
        for i in range(1, max_qh_pairs + 1):
            current = financial_data.get(f'qh{i}_eps', 'N/A')
            prior = financial_data.get(f'qh{i+4}_eps', 'N/A')
            financial_data[f'qh{i}_eps_growth_yoy'] = self._safe_growth_rate(current, prior)

        # C - acceleration flag: is YoY growth increasing over the last 3
        # comparable quarters (qh1 > qh2 > qh3) - O'Neil's core "C" test.
        # Based on the qh (deep-history) series since the q (statement) series
        # rarely has enough quarters to fill all three.
        gh1 = financial_data.get('qh1_eps_growth_yoy', 'N/A')
        gh2 = financial_data.get('qh2_eps_growth_yoy', 'N/A')
        gh3 = financial_data.get('qh3_eps_growth_yoy', 'N/A')
        if all(isinstance(g, (int, float)) and not pd.isna(g) for g in (gh1, gh2, gh3)):
            financial_data['eps_growth_accelerating'] = bool(gh1 > gh2 > gh3)
        else:
            financial_data['eps_growth_accelerating'] = 'N/A'

        # A - annual YoY growth: compare y{i} against y{i+1} (already yearly).
        max_year_pairs = self.years_to_collect - 1
        for i in range(1, max_year_pairs + 1):
            for suffix in ('', '_basic'):
                current = financial_data.get(f'y{i}_eps{suffix}', 'N/A')
                prior = financial_data.get(f'y{i+1}_eps{suffix}', 'N/A')
                financial_data[f'y{i}_eps{suffix}_growth_yoy'] = self._safe_growth_rate(current, prior)

    def _calculate_annual_quality(self, financial_data):
        """
        A - Annual earnings quality checks built on already-extracted raw data:
          - ROE per year (net income / stockholders equity), flagged against
            O'Neil's 17%+ minimum bar.
          - Cash-flow-per-share vs. EPS ("cash flow should exceed EPS by ~20%+",
            O'Neil's quality-of-earnings check).
        """
        for i in range(1, self.years_to_collect + 1):
            net_income = financial_data.get(f'y{i}_net_income', 'N/A')
            equity = financial_data.get(f'y{i}_stockholders_equity', 'N/A')
            financial_data[f'y{i}_roe'] = self._safe_ratio(net_income, equity)

            ocf = financial_data.get(f'y{i}_operating_cashflow', 'N/A')
            shares = financial_data.get(f'y{i}_shares_outstanding', 'N/A')
            cfps = self._safe_ratio(ocf, shares)
            financial_data[f'y{i}_cashflow_per_share'] = cfps

            eps = financial_data.get(f'y{i}_eps', 'N/A')
            financial_data[f'y{i}_cashflow_vs_eps_ratio'] = self._safe_ratio(cfps, eps)

        roe_1 = financial_data.get('y1_roe', 'N/A')
        financial_data['roe_meets_threshold'] = roe_1 >= 0.17 if self._is_number(roe_1) else 'N/A'

        cf_ratio_1 = financial_data.get('y1_cashflow_vs_eps_ratio', 'N/A')
        financial_data['cashflow_quality_pass'] = cf_ratio_1 >= 1.2 if self._is_number(cf_ratio_1) else 'N/A'

    def _calculate_n_flags(self, financial_data):
        """
        N - Threshold flags from already-extracted raw fields.
        near_new_high: O'Neil favors stocks within ~15% of a new high (proper-base
        breakout candidates).
        recent_ipo: rough heuristic, not a hard rule from O'Neil's writing - he
        favors relatively young, recently-public leaders but never gave a fixed
        cutoff; 10 years is used here as an approximation.
        """
        high_change_pct = financial_data.get('fiftyTwoWeekHighChangePercent', 'N/A')
        financial_data['near_new_high'] = (
            bool(high_change_pct >= -0.15) if self._is_number(high_change_pct) else 'N/A'
        )

        years_public = financial_data.get('yearsSincePublic', 'N/A')
        financial_data['recent_ipo'] = (
            bool(years_public <= 10) if self._is_number(years_public) else 'N/A'
        )

    def _calculate_supply_trend(self, financial_data):
        """
        S - Classify the multi-year share-count trend (buyback vs. dilution)
        from y{i}_shares_outstanding, and flag whether direct buyback $
        evidence exists in y{i}_buyback.
        """
        valid_years = [
            i for i in range(1, self.years_to_collect + 1)
            if self._is_number(financial_data.get(f'y{i}_shares_outstanding', 'N/A'))
        ]
        if len(valid_years) >= 2:
            newest = financial_data[f'y{min(valid_years)}_shares_outstanding']
            oldest = financial_data[f'y{max(valid_years)}_shares_outstanding']
            change = self._safe_ratio(newest - oldest, oldest)
            if not self._is_number(change):
                financial_data['supply_trend'] = 'N/A'
            elif change <= -0.02:
                financial_data['supply_trend'] = 'shrinking'
            elif change >= 0.02:
                financial_data['supply_trend'] = 'diluting'
            else:
                financial_data['supply_trend'] = 'stable'
        else:
            financial_data['supply_trend'] = 'N/A'

        has_data = False
        buyback_active = False
        for i in range(1, self.years_to_collect + 1):
            buyback = financial_data.get(f'y{i}_buyback', 'N/A')
            if self._is_number(buyback):
                has_data = True
                if buyback < 0:
                    buyback_active = True
        financial_data['buyback_active'] = buyback_active if has_data else 'N/A'

    def _calculate_sponsorship_level(self, financial_data):
        """
        I - Classify institutional ownership level. O'Neil likes healthy
        institutional sponsorship but flags over-ownership (~>70%) as a
        ceiling risk that limits future buying power. Uses the always-on
        heldPercentInstitutions snapshot, so this works even when
        collect_sponsorship_detail is off.
        """
        held_pct = financial_data.get('heldPercentInstitutions', 'N/A')
        if not self._is_number(held_pct):
            financial_data['sponsorship_level'] = 'N/A'
        elif held_pct > 0.70:
            financial_data['sponsorship_level'] = 'over_owned'
        elif held_pct >= 0.20:
            financial_data['sponsorship_level'] = 'healthy'
        else:
            financial_data['sponsorship_level'] = 'low'

    def _calculate_cansi_score(self, financial_data):
        """
        Composite CANSI signal (C/A/N/S/I only - no L/M, and not a full
        weighted CANSLIM score/rank like IBD's). One point per letter whose
        criteria are met, out of however many letters have usable data for
        this ticker - letters with 'N/A' inputs are excluded from the
        denominator rather than counted as failing.
        """
        roe_flag = financial_data.get('roe_meets_threshold', 'N/A')
        cf_flag = financial_data.get('cashflow_quality_pass', 'N/A')
        a_pass = (roe_flag is True and cf_flag is True) if roe_flag in (True, False) and cf_flag in (True, False) else 'N/A'

        supply_trend = financial_data.get('supply_trend', 'N/A')
        s_pass = (supply_trend in ('shrinking', 'stable')) if supply_trend != 'N/A' else 'N/A'

        sponsorship_level = financial_data.get('sponsorship_level', 'N/A')
        i_pass = (sponsorship_level == 'healthy') if sponsorship_level != 'N/A' else 'N/A'

        checks = {
            'C': financial_data.get('eps_growth_accelerating', 'N/A'),
            'A': a_pass,
            'N': financial_data.get('near_new_high', 'N/A'),
            'S': s_pass,
            'I': i_pass,
        }

        available = {letter: passed for letter, passed in checks.items() if passed != 'N/A'}
        financial_data['cansi_criteria_met'] = sum(1 for passed in available.values() if passed is True)
        financial_data['cansi_criteria_available'] = len(available)
        financial_data['cansi_letters_passed'] = (
            ''.join(letter for letter, passed in available.items() if passed is True) or 'N/A'
        )

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
    
    def _fetch_and_cache_one(self, ticker, delay_between_requests):
        """
        Fetch one ticker's comprehensive financial data, cache it if successful,
        and pace it with `delay_between_requests`. Safe to call from a worker
        thread: each ticker only ever touches its own cache file (see
        _ticker_cache_path), so concurrent calls for different tickers never
        share mutable state - only the caller's own aggregation (list/counters)
        needs to happen back on the main thread.

        Returns ('fetched', financial_data) or ('failed', error_message).
        """
        try:
            financial_data = self.get_comprehensive_financial_data(ticker)
            if 'error' not in financial_data:
                self._save_ticker_cache(ticker, financial_data)
                time.sleep(delay_between_requests)
                return ('fetched', financial_data)
            time.sleep(delay_between_requests)
            return ('failed', financial_data.get('error', 'Unknown error'))
        except Exception as e:
            return ('failed', str(e))

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

        # Incremental refresh: reuse a ticker's cached data if it's still fresh,
        # instead of re-fetching everyone. The cache is per-ticker (data/fin_data/
        # tickers/<TICKER>.json) and independent of ticker_choice, so a ticker
        # already fresh under one ticker_choice is recognized as fresh under any
        # other choice that also includes it - not just within the same choice's
        # file. A ticker with no cache file (new to the universe) always gets
        # fetched fresh, same as one whose cache is stale.
        if self.force_refresh:
            print("🔄 force_refresh=True: ignoring freshness, re-fetching every ticker")

        financial_data_list = []
        reused_count = 0
        fetched_count = 0
        failed_count = 0

        # Freshness check is a cheap local file read - resolved up front for
        # every ticker (no threading needed here), leaving only the tickers
        # that actually need a real fetch to go through the (possibly
        # concurrent) network path below.
        to_fetch = []
        for i, ticker in enumerate(tickers_list, 1):
            cached = None if self.force_refresh else self._load_ticker_cache(ticker)
            if cached is not None and self._is_fresh(cached.get('last_updated')):
                financial_data_list.append(cached)
                reused_count += 1
                if i <= 3:
                    print(f"  ♻️  {ticker}: reused cached data (fresh)")
            else:
                to_fetch.append(ticker)

        total_to_fetch = len(to_fetch)
        if reused_count:
            print(f"♻️  {reused_count}/{len(tickers_list)} tickers reused from cache (fresh) - "
                  f"{total_to_fetch} need a real fetch")

        if self.max_workers <= 1:
            # Sequential path - identical behavior to the pre-concurrency version.
            for i, ticker in enumerate(to_fetch, 1):
                print(f"Processing financial data for {ticker} ({i}/{total_to_fetch})")
                status, result = self._fetch_and_cache_one(ticker, delay_between_requests)
                if status == 'fetched':
                    financial_data_list.append(result)
                    fetched_count += 1
                    if i <= 3:
                        print(f"  ✅ {ticker}: Financial data collected")
                else:
                    failed_count += 1
                    print(f"  ⚠️ Error with {ticker}: {result}")

                if i % 50 == 0:
                    print(f"Processed {i}/{total_to_fetch} tickers. Taking a longer break...")
                    time.sleep(10)
        else:
            # Concurrent path. Submitted in batches of 50 (not all at once) so
            # the periodic "longer break" genuinely throttles request issuance -
            # a ThreadPoolExecutor starts pulling from its queue the moment
            # tasks are submitted, so submitting everything up front and only
            # pausing the result-consuming loop would let workers keep firing
            # straight through any intended pause. Waiting for each batch to
            # fully drain before submitting the next, and only then sleeping,
            # keeps that safety margin real. Within a batch, up to
            # self.max_workers tickers are genuinely fetched in parallel.
            print(f"⚡ Fetching {total_to_fetch} tickers with {self.max_workers} concurrent workers...")
            batch_size = 50
            completed = 0
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                for batch_start in range(0, total_to_fetch, batch_size):
                    batch = to_fetch[batch_start:batch_start + batch_size]
                    futures = {
                        executor.submit(self._fetch_and_cache_one, ticker, delay_between_requests): ticker
                        for ticker in batch
                    }
                    for future in as_completed(futures):
                        ticker = futures[future]
                        completed += 1
                        try:
                            status, result = future.result()
                        except Exception as e:
                            status, result = 'failed', str(e)

                        if status == 'fetched':
                            financial_data_list.append(result)
                            fetched_count += 1
                            if completed <= 3:
                                print(f"  ✅ {ticker}: Financial data collected ({completed}/{total_to_fetch})")
                        else:
                            failed_count += 1
                            print(f"  ⚠️ Error with {ticker}: {result} ({completed}/{total_to_fetch})")

                    if completed < total_to_fetch:
                        print(f"Processed {completed}/{total_to_fetch} tickers. Taking a longer break...")
                        time.sleep(10)

        print(f"\n📊 Summary: {reused_count} reused (fresh), {fetched_count} fetched fresh, {failed_count} failed")
        
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
                    'shortPercentOfFloat', 'heldPercentInstitutions',
                    'institutionsCount', 'fiftyTwoWeekHighChangePercent',
                    'y1_eps', 'y1_stockholders_equity',
                    'eps_growth_accelerating', 'roe_meets_threshold', 'cashflow_quality_pass',
                    'near_new_high', 'supply_trend', 'sponsorship_level',
                    'cansi_criteria_met', 'cansi_criteria_available', 'cansi_letters_passed'
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
    # config['delay_between_requests'] was previously never passed here, so it
    # silently had no effect - generate_financial_data_file always ran with its
    # own hardcoded default (1s) regardless of what main.py's financial_config
    # requested (1.5s). Fixed while touching this call site for max_workers.
    delay = (config or {}).get('delay_between_requests', 1)
    retriever.generate_financial_data_file(ticker_file_path, delay_between_requests=delay)


def migrate_existing_financial_data_to_cache(config=None):
    """
    One-time backfill: seed the per-ticker cache (data/fin_data/tickers/<TICKER>.json)
    from any already-downloaded financial_data_<choice>.csv files under FIN_DATA_DIR,
    so previously-fetched tickers aren't needlessly re-fetched after upgrading to the
    per-ticker cache. Skips any ticker that already has a cache file. Not part of the
    normal pipeline - run manually once, e.g.:
        python -c "from src.get_financial_data import migrate_existing_financial_data_to_cache as m; m()"
    """
    retriever = FinancialDataRetriever(config)
    fin_data_dir = retriever.PARAMS_DIR["FIN_DATA_DIR"]
    tickers_dir = retriever.PARAMS_DIR["FIN_DATA_TICKERS_DIR"]
    os.makedirs(tickers_dir, exist_ok=True)

    if not os.path.exists(fin_data_dir):
        print(f"No financial data directory found at {fin_data_dir} - nothing to migrate.")
        return

    csv_files = [
        f for f in os.listdir(fin_data_dir)
        if f.startswith('financial_data_') and not f.startswith('financial_data_summary_') and f.endswith('.csv')
    ]
    if not csv_files:
        print(f"No financial_data_<choice>.csv files found in {fin_data_dir} - nothing to migrate.")
        return

    migrated = 0
    skipped = 0
    for csv_file in csv_files:
        csv_path = os.path.join(fin_data_dir, csv_file)
        print(f"Reading {csv_path}...")
        try:
            df = pd.read_csv(csv_path)
        except Exception as e:
            print(f"  ⚠️ Could not read {csv_path}: {e}")
            continue

        if 'ticker' not in df.columns:
            print(f"  ⚠️ {csv_path} has no 'ticker' column, skipping")
            continue

        for _, row in df.iterrows():
            ticker = row['ticker']
            cache_path = os.path.join(tickers_dir, f"{ticker}.json")
            if os.path.exists(cache_path):
                skipped += 1
                continue
            try:
                with open(cache_path, 'w') as f:
                    json.dump(row.to_dict(), f)
                migrated += 1
            except Exception as e:
                print(f"  ⚠️ Could not write cache for {ticker}: {e}")

    print(f"✅ Migration complete: {migrated} tickers backfilled, {skipped} already cached (skipped)")
