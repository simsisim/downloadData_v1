import logging
import os 
import pandas as pd
from datetime import datetime, timedelta
from src.get_marketData import run_market_data_retrieval
from src.get_financial_data import run_financial_data_retrieval  # New import
from src.config import user_choice, write_file_info, Config
from src.user_defined_data import read_user_data_legacy, read_user_data
from src.config import setup_directories, PARAMS_DIR
from src.unified_ticker_generator import generate_all_ticker_files
import yfinance as yf

# Try to import TickerRetriever, if it fails, we'll handle it
try:
    from src.get_tickers import TickerRetriever
    TICKER_RETRIEVER_AVAILABLE = True
except ImportError as e:
    print(f"Warning: Could not import TickerRetriever: {e}")
    print("Continuing without ticker retrieval functionality...")
    TICKER_RETRIEVER_AVAILABLE = False

# Import TradingView processor
try:
    from src.tradingview_ticker_processor import TradingViewTickerProcessor
    TRADINGVIEW_PROCESSOR_AVAILABLE = True
except ImportError as e:
    print(f"Warning: Could not import TradingViewTickerProcessor: {e}")
    TRADINGVIEW_PROCESSOR_AVAILABLE = False

def test_yfinance_and_financial_data():
    """Test yfinance functionality and the new financial data module"""
    try:
        print('Testing yfinance is working ....download AAPL data')
        test = yf.Ticker('AAPL')
        data = test.history(period='3d')

        if data.empty:
            print("Error: No data returned from yfinance. Please check your internet connection or update yfinance.")
            exit(1)
        
        print(data['Close'])  # Print closing prices
        print(data['Volume'])
        # Print the exchange of the ticker
        print("\nExchange of the Ticker:")
        print(test.info['fullExchangeName'])
        
        # Test the new CANSLIM financial data extraction
        print("\n" + "="*60)
        print("TESTING NEW CANSLIM FINANCIAL DATA EXTRACTION")
        print("="*60)
        
        # Import the new FinancialDataRetriever to test financial data
        from src.get_financial_data import FinancialDataRetriever
        
        # Create test directory and dummy ticker file
        test_dir = './test'
        os.makedirs(test_dir, exist_ok=True)
        
        # Create a dummy ticker file for testing
        dummy_ticker_file = os.path.join(test_dir, 'dummy.csv')
        test_tickers_df = pd.DataFrame({'ticker': ['AAPL', 'MSFT', 'GOOGL', 'TSLA']})
        test_tickers_df.to_csv(dummy_ticker_file, index=False)
        print(f"Created test ticker file: {dummy_ticker_file}")
        
        # Create a dummy config for testing
        test_config = {
            'test_mode': True,
            'data_span_quarters': 12,  # 3 years of quarterly data
            'data_span_years': 5       # 5 years of annual data
        }
        
        # Create financial data retriever instance
        test_financial_retriever = FinancialDataRetriever(test_config)
        
        # Test financial data extraction on AAPL
        print("\nTesting comprehensive financial data extraction for AAPL...")
        financial_data = test_financial_retriever.get_comprehensive_financial_data('AAPL')
        
        if financial_data and 'error' not in financial_data:
            print("✅ Financial data extraction successful!")
            
            # Display key CANSLIM metrics
            print("\n📊 KEY CANSLIM METRICS FOR AAPL:")
            print("-" * 50)
            
            # Current Earnings (C)
            print("🔹 CURRENT EARNINGS (C):")
            print(f"  • Quarterly Earnings Growth: {financial_data.get('earningsQuarterlyGrowth', 'N/A')}")
            print(f"  • Quarterly Revenue Growth: {financial_data.get('revenueQuarterlyGrowth', 'N/A')}")
            print(f"  • Trailing EPS: {financial_data.get('trailingEps', 'N/A')}")
            print(f"  • Forward EPS: {financial_data.get('forwardEps', 'N/A')}")
            print(f"  • PEG Ratio: {financial_data.get('pegRatio', 'N/A')}")
            
            # Annual Earnings (A)
            print("\n🔹 ANNUAL EARNINGS (A):")
            print(f"  • Annual Earnings Growth: {financial_data.get('earningsGrowth', 'N/A')}")
            print(f"  • Annual Revenue Growth: {financial_data.get('revenueGrowth', 'N/A')}")
            print(f"  • Return on Equity: {financial_data.get('returnOnEquity', 'N/A')}")
            print(f"  • Profit Margins: {financial_data.get('profitMargins', 'N/A')}")
            
            # New Stock/Supply (N & S)
            print("\n🔹 SUPPLY & DEMAND (N & S):")
            print(f"  • Shares Outstanding: {financial_data.get('sharesOutstanding', 'N/A')}")
            print(f"  • Float Shares: {financial_data.get('floatShares', 'N/A')}")
            print(f"  • Short % of Float: {financial_data.get('shortPercentOfFloat', 'N/A')}")
            print(f"  • Insider Holdings: {financial_data.get('heldPercentInsiders', 'N/A')}")
            
            # Leader/Laggard (L)
            print("\n🔹 LEADER/LAGGARD (L):")
            print(f"  • Market Cap: {financial_data.get('marketCap', 'N/A')}")
            print(f"  • 52-Week High: {financial_data.get('fiftyTwoWeekHigh', 'N/A')}")
            print(f"  • 52-Week Low: {financial_data.get('fiftyTwoWeekLow', 'N/A')}")
            print(f"  • Beta: {financial_data.get('beta', 'N/A')}")
            
            # Institutional (I)
            print("\n🔹 INSTITUTIONAL SPONSORSHIP (I):")
            print(f"  • Institutional Holdings: {financial_data.get('heldPercentInstitutions', 'N/A')}")
            print(f"  • Analyst Opinions: {financial_data.get('numberOfAnalystOpinions', 'N/A')}")
            print(f"  • Target Mean Price: {financial_data.get('targetMeanPrice', 'N/A')}")
            
            # Market Direction (M) - Company fundamentals
            print("\n🔹 MARKET/FUNDAMENTALS (M):")
            print(f"  • Sector: {financial_data.get('sector', 'N/A')}")
            print(f"  • Industry: {financial_data.get('industry', 'N/A')}")
            print(f"  • Enterprise Value: {financial_data.get('enterpriseValue', 'N/A')}")
            print(f"  • Free Cash Flow: {financial_data.get('freeCashflow', 'N/A')}")
            
            # CANSLIM Score
            print("\n🎯 CANSLIM ANALYSIS:")
            canslim_score = financial_data.get('canslim_score', 'N/A')
            canslim_percentage = financial_data.get('canslim_score_percentage', 'N/A')
            print(f"  • CANSLIM Score: {canslim_score}/100 ({canslim_percentage}%)")
            
            # Quarterly data if available
            print("\n🔹 QUARTERLY TRENDS (Extended History):")
            quarters_found = False
            for i in range(1, 9):  # Check first 8 quarters
                q_earnings = financial_data.get(f'q{i}_net_income', 'N/A')
                q_revenue = financial_data.get(f'q{i}_revenue', 'N/A')
                q_date = financial_data.get(f'q{i}_date', 'N/A')
                if q_earnings != 'N/A' or q_revenue != 'N/A':
                    print(f"  • Q{i} ({q_date}): Net Income={q_earnings}, Revenue={q_revenue}")
                    quarters_found = True
            
            if not quarters_found:
                print("  • No quarterly data available")
            
            # Growth acceleration
            earnings_accel = financial_data.get('earnings_acceleration', 'N/A')
            revenue_accel = financial_data.get('revenue_acceleration', 'N/A')
            print(f"\n🚀 GROWTH ACCELERATION:")
            print(f"  • Earnings Acceleration: {earnings_accel}%")
            print(f"  • Revenue Acceleration: {revenue_accel}%")
            
            print("\n✅ CANSLIM financial data test completed successfully!")
            
        else:
            print("❌ Financial data extraction failed!")
            if 'error' in financial_data:
                print(f"Error: {financial_data['error']}")
        
        # Test a few more tickers for variety
        test_tickers = ['MSFT', 'GOOGL', 'TSLA']
        print(f"\n🔍 Quick test on additional tickers: {', '.join(test_tickers)}")
        
        for ticker in test_tickers:
            try:
                print(f"\nTesting {ticker}...")
                quick_data = test_financial_retriever.get_comprehensive_financial_data(ticker)
                if quick_data and 'error' not in quick_data:
                    q_growth = quick_data.get('earningsQuarterlyGrowth', 'N/A')
                    r_growth = quick_data.get('revenueQuarterlyGrowth', 'N/A')
                    market_cap = quick_data.get('marketCap', 'N/A')
                    canslim_score = quick_data.get('canslim_score', 'N/A')
                    print(f"  ✅ {ticker}: Q Growth={q_growth}, R Growth={r_growth}, Market Cap={market_cap}, CANSLIM={canslim_score}")
                else:
                    print(f"  ❌ {ticker}: Failed to extract data")
            except Exception as e:
                print(f"  ❌ {ticker}: Error - {e}")
                
    except Exception as e:
        print(f"An error occurred while testing yfinance: {e}")
        print("Please update yfinance or check your internet connection.")
        exit(1)
    
    print('✅ yfinance and financial data module tests completed successfully.')

def main():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    # all messages are suppressed
    logging.getLogger().setLevel(logging.CRITICAL)
    setup_directories()  # Initialize directories via config
    
    # Get the full configuration object for fine-grained control
    config = read_user_data()
    
    # ============ TICKER DATA RETRIEVAL ============
    print("\n" + "="*60)
    print("TICKER DATA SOURCE SELECTION")
    print("="*60)
    
    if config.web_tickers_down and config.tw_tickers_down:
        print("⚠️  WARNING: Both WEB_tickers_down and TW_tickers_down are TRUE!")
        print("   Using WEB source (WEB_tickers_down) as priority...")
        print("   To use TradingView source, set WEB_tickers_down=FALSE")
    
    if config.web_tickers_down:
        print("📡 Using WEB ticker source (NASDAQ, Wikipedia, etc.)")
        if TICKER_RETRIEVER_AVAILABLE:
            try:
                retriever = TickerRetriever()
                retriever.fetch_and_save_all()
                print("✅ Web ticker retrieval completed")
            except Exception as e:
                print(f"❌ Error with TickerRetriever: {e}")
                print("Continuing with existing ticker files...")
        else:
            print("⚠️  TickerRetriever not available - using existing ticker files...")
            
    elif config.tw_tickers_down:
        print("📊 Using TradingView ticker source")
        print(f"🗂️  Universe file: {config.tw_universe_file}")
        
        if TRADINGVIEW_PROCESSOR_AVAILABLE:
            try:
                tw_processor = TradingViewTickerProcessor(config)
                success = tw_processor.process_tradingview_universe()
                if success:
                    print("✅ TradingView ticker processing completed")
                else:
                    print("❌ TradingView ticker processing failed")
            except Exception as e:
                print(f"❌ Error with TradingView processor: {e}")
                print("Continuing with existing ticker files...")
        else:
            print("⚠️  TradingView processor not available - using existing ticker files...")
    else:
        print("⏭️  Both ticker sources disabled - using existing ticker files")
        print("   WEB_tickers_down=FALSE, TW_tickers_down=FALSE")
    
    # Test yfinance and financial data functionality
    test_yfinance_and_financial_data()
    
    # Generate ticker files using unified ticker generator
    print("\n" + "="*60)
    print("GENERATING TICKER FILES")
    print("="*60)
    
    try:
        # Create config for unified ticker generator
        unified_config = Config()
        
        # Generate all ticker files for the user choice
        success = generate_all_ticker_files(unified_config, config.ticker_choice)
        
        if not success:
            print("❌ Failed to generate ticker files")
            exit(1)
        
        # Get the combined ticker file path
        combined_file = os.path.join(PARAMS_DIR["TICKERS_DIR"], f"combined_tickers_{config.ticker_choice}.csv")
        
        if not os.path.exists(combined_file):
            print(f"❌ Expected ticker file not found: {combined_file}")
            exit(1)
            
    except Exception as e:
        print(f"❌ Error generating ticker files: {e}")
        print("📁 Checking data/tickers directory contents...")
        
        tickers_dir = os.path.join(os.getcwd(), 'data', 'tickers')
        if os.path.exists(tickers_dir):
            files = os.listdir(tickers_dir)
            print(f"Files in {tickers_dir}: {files}")
        else:
            print(f"Directory {tickers_dir} does not exist")
        
        print("\n⚠️ This usually indicates that ticker file generation failed or")
        print("   the configuration doesn't match available files.")
        print("   Please check your user_input/user_data.csv settings and run again.")
        exit(1)
    
    print(f"✅ Combined ticker file ready: {combined_file}")
    
    # Quick validation
    import pandas as pd
    combined_df = pd.read_csv(combined_file)
    print(f"📊 Total tickers to process: {len(combined_df)}")
    print(f"🔍 Sample tickers: {combined_df['ticker'].head(5).tolist()}")
    
    # ============ HISTORICAL MARKET DATA RETRIEVAL ============
    if config.yf_hist_data:
        print("\n" + "="*60)
        print("DOWNLOADING HISTORICAL MARKET DATA (OHLCV)")
        print("="*60)
        
        # Check which data intervals are enabled
        enabled_intervals = []
        if config.yf_daily_data:
            enabled_intervals.append("Daily (1d)")
        if config.yf_weekly_data:
            enabled_intervals.append("Weekly (1wk)")
        if config.yf_monthly_data:
            enabled_intervals.append("Monthly (1mo)")
            
        if not enabled_intervals:
            print("❌ Historical data collection enabled but no intervals selected!")
            print("   Please enable at least one of: YF_daily_data, YF_weekly_data, YF_monthly_data")
        else:
            print(f"📈 Historical data intervals enabled: {', '.join(enabled_intervals)}")
    
            # Daily market data
            if config.yf_daily_data:
                print("\n📅 Downloading daily (1d) market data...")
                daily_params = {
                    'interval': '1d',
                    'start_date': '2020-01-01',
                    'end_date': datetime.now().strftime('%Y-%m-%d'),
                    'folder': PARAMS_DIR["MARKET_DATA_DIR_1d"],
                    'ticker_file': combined_file,
                    'write_file_info': write_file_info,
                    'ticker_info_TW': config.ticker_info_TW,
                    'ticker_info_TW_file': config.ticker_info_TW_file,
                    'ticker_info_YF': config.ticker_info_YF
                }
                logging.info(f"Downloading daily market data for combined tickers from choice: {config.ticker_choice}")
                run_market_data_retrieval(daily_params)
            else:
                print("⏭️  Daily data collection disabled (YF_daily_data = FALSE)")
    
            # Weekly market data
            if config.yf_weekly_data:
                print("\n📅 Downloading weekly (1wk) market data...")
                weekly_params = {
                    'interval': '1wk',
                    'start_date': '2000-01-01',
                    'end_date': datetime.now().strftime('%Y-%m-%d'),
                    'folder': PARAMS_DIR["MARKET_DATA_DIR_1wk"],
                    'ticker_file': combined_file,
                    'write_file_info': write_file_info,
                    'ticker_info_TW': config.ticker_info_TW,
                    'ticker_info_TW_file': config.ticker_info_TW_file,
                    'ticker_info_YF': config.ticker_info_YF
                }
                run_market_data_retrieval(weekly_params)
            else:
                print("⏭️  Weekly data collection disabled (YF_weekly_data = FALSE)")
 
             
            # Monthly market data  
            if config.yf_monthly_data:
                print("\n📅 Downloading monthly (1mo) market data...")
                monthly_params = {
                    'interval': '1mo',
                    'start_date': '2000-01-01',
                    'end_date': datetime.now().strftime('%Y-%m-%d'),
                    'folder': PARAMS_DIR["MARKET_DATA_DIR_1mo"],
                    'ticker_file': combined_file,
                    'write_file_info': write_file_info,
                    'ticker_info_TW': config.ticker_info_TW,
                    'ticker_info_TW_file': config.ticker_info_TW_file,
                    'ticker_info_YF': config.ticker_info_YF
                }
                run_market_data_retrieval(monthly_params)
            else:
                print("⏭️  Monthly data collection disabled (YF_monthly_data = FALSE)")
    else:
        print("\n" + "="*60)
        print("HISTORICAL DATA COLLECTION DISABLED")
        print("="*60)
        print("⏭️  Skipping historical market data collection (YF_hist_data = FALSE)")
        print("   To enable: Set YF_hist_data = TRUE in user_input/user_data.csv")

    # ============ ROUTE 2: TRADINGVIEW DATA UPDATES ============
    if config.tw_hist_data:
        print("\n" + "="*60)
        print("UPDATING DATA FROM TRADINGVIEW BULK FILES")
        print("="*60)
        print(f"📁 TW Files Path: {config.tw_files_path}")

        from src.get_tradingview_data import TradingViewDataRetriever

        # Create TW config
        tw_config = {
            'ticker_file': combined_file,
            'TW_FILES_DIR': config.tw_files_path,
            'MARKET_DATA_TW_DIR': PARAMS_DIR["MARKET_DATA_TW_DIR"],
            'TICKERS_DIR': PARAMS_DIR["TICKERS_DIR"]
        }

        tw_retriever = TradingViewDataRetriever(tw_config)

        # Daily updates
        if config.tw_daily_data:
            print("\n📅 Processing TradingView daily data...")
            tw_retriever.update_from_tw_files('daily')
        else:
            print("\n⏭️  Daily TW data disabled (TW_daily_data = FALSE)")

        # Weekly updates
        if config.tw_weekly_data:
            print("\n📅 Processing TradingView weekly data...")
            tw_retriever.update_from_tw_files('weekly')
        else:
            print("⏭️  Weekly TW data disabled (TW_weekly_data = FALSE)")

        # Monthly updates
        if config.tw_monthly_data:
            print("\n📅 Processing TradingView monthly data...")
            tw_retriever.update_from_tw_files('monthly')
        else:
            print("⏭️  Monthly TW data disabled (TW_monthly_data = FALSE)")
    else:
        print("\n" + "="*60)
        print("TRADINGVIEW DATA UPDATES DISABLED")
        print("="*60)
        print("⏭️  Skipping TradingView updates (TW_hist_data = FALSE)")
        print("   To enable: Set TW_hist_data = TRUE in user_input/user_data.csv")

    # ============ COMPREHENSIVE FINANCIAL DATA RETRIEVAL ============
    if config.fin_data_enrich:
        print("\n" + "="*60)
        print("DOWNLOADING COMPREHENSIVE FINANCIAL DATA FOR CANSLIM")
        print("="*60)
        
        # Check which financial data sources are enabled
        financial_sources = []
        if config.yf_fin_data:
            financial_sources.append("YFinance")
        if config.tw_fin_data:
            financial_sources.append("TradingView")
        if config.zacks_fin_data:
            financial_sources.append("Zacks")
            
        if not financial_sources:
            print("❌ Financial data enrichment enabled but no data sources selected!")
            print("   Please enable at least one of: YF_fin_data, TW_fin_data, Zacks_fin_data")
        else:
            print(f"📊 Financial data sources enabled: {', '.join(financial_sources)}")
            
            # Financial data configuration for extended historical analysis
            financial_config = {
                'quarters_to_collect': 12,  # 3 years of quarterly data for trend analysis
                'years_to_collect': 5,      # 5 years of annual data for sustained growth
                'delay_between_requests': 1.5,  # Slightly longer delay for comprehensive data
                'enable_canslim_scoring': True,
                'enable_growth_acceleration': True,
                'yf_enabled': config.yf_fin_data,
                'tw_enabled': config.tw_fin_data,
                'zacks_enabled': config.zacks_fin_data
            }
            
            print("Starting comprehensive financial data collection...")
            print("This will collect 8-12 quarters and 5+ years of financial history for CANSLIM analysis")
            print("Expected duration: 5-15 minutes depending on number of tickers\n")
            
            # Run financial data retrieval separately
            run_financial_data_retrieval(combined_file, financial_config)
    else:
        print("\n" + "="*60)
        print("FINANCIAL DATA ENRICHMENT DISABLED")
        print("="*60)
        print("⏭️  Skipping financial data collection (fin_data_enrich = FALSE)")
        print("   To enable: Set fin_data_enrich = TRUE in user_input/user_data.csv")
    
    print("\n" + "="*60)
    print("ALL DATA COLLECTION COMPLETED")
    print("="*60)
    # Historical market data summary
    if config.yf_hist_data:
        completed_intervals = []
        saved_dirs = []
        if config.yf_daily_data:
            completed_intervals.append("Daily")
            saved_dirs.append(PARAMS_DIR['MARKET_DATA_DIR_1d'])
        if config.yf_weekly_data:
            completed_intervals.append("Weekly")
            saved_dirs.append(PARAMS_DIR['MARKET_DATA_DIR_1wk'])
        if config.yf_monthly_data:
            completed_intervals.append("Monthly")
            saved_dirs.append(PARAMS_DIR['MARKET_DATA_DIR_1mo'])
            
        if completed_intervals:
            print(f"✅ Historical market data ({', '.join(completed_intervals)}) - COMPLETED")
            print(f"📁 Market data saved to: {', '.join(saved_dirs)}")
        else:
            print("⏭️ Historical market data - SKIPPED (no intervals enabled)")
    else:
        print("⏭️ Historical market data - SKIPPED (YF_hist_data disabled)")
    
    if config.fin_data_enrich:
        print("✅ Comprehensive financial data (CANSLIM) - COMPLETED")
        print(f"📁 Financial data saved to: {PARAMS_DIR['TICKERS_DIR']}")
        print("\nFinancial files generated:")
        print("  • financial_data_<choice>.csv - Complete financial dataset")
        print("  • financial_data_summary_<choice>.csv - Key metrics summary")
    else:
        print("⏭️ Financial data enrichment - SKIPPED")
    print('Finished')

if __name__ == "__main__":
    main()
