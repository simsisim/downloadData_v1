import logging
import os
import pandas as pd
import argparse
from datetime import datetime, timedelta
from src.get_marketData import run_market_data_retrieval
from src.get_financial_data import run_financial_data_retrieval
from src.get_batchData import run_batch_data_retrieval, _parse_interval_cfg
from src.config import user_choice, write_file_info, Config
from src.user_defined_data import read_user_data_legacy, read_user_data
from src.config import setup_directories, PARAMS_DIR
from src.unified_ticker_generator import generate_all_ticker_files
import yfinance as yf
# Verify yfinance version for Pandas 3.0 compatibility
print(f"Using yfinance version: {yf.__version__}")

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


# ============================================================================
# CONFIGURATION PRESETS
# ============================================================================
CONFIG_PRESETS = {
    'quick_test': {
        'ticker_choice': '8',           # Test tickers only
        'yf_hist_data': True,
        'yf_daily_data': True,
        'yf_weekly_data': False,
        'yf_monthly_data': False,
        'tw_hist_data': False,
        'fin_data_enrich': False,
        'write_info_file': False
    },
    'nasdaq_daily': {
        'ticker_choice': '2',           # NASDAQ 100
        'yf_hist_data': True,
        'yf_daily_data': True,
        'yf_weekly_data': False,
        'yf_monthly_data': False,
        'tw_hist_data': False,
        'fin_data_enrich': False,
        'write_info_file': True
    },
    'sp500_full': {
        'ticker_choice': '1',           # S&P 500
        'yf_hist_data': True,
        'yf_daily_data': True,
        'yf_weekly_data': True,
        'yf_monthly_data': True,
        'tw_hist_data': False,
        'fin_data_enrich': True,
        'write_info_file': True
    },
    'nasdaq_sp500_daily': {
        'ticker_choice': '1-2',         # S&P 500 + NASDAQ 100
        'yf_hist_data': True,
        'yf_daily_data': True,
        'yf_weekly_data': False,
        'yf_monthly_data': False,
        'tw_hist_data': False,
        'fin_data_enrich': False,
        'write_info_file': True
    },
    'portfolio_only': {
        'ticker_choice': '6',           # Portfolio tickers
        'yf_hist_data': True,
        'yf_daily_data': True,
        'yf_weekly_data': True,
        'yf_monthly_data': False,
        'tw_hist_data': False,
        'fin_data_enrich': True,
        'write_info_file': True
    },
    'full_canslim': {
        'ticker_choice': '2',           # NASDAQ 100
        'yf_hist_data': True,
        'yf_daily_data': True,
        'yf_weekly_data': True,
        'yf_monthly_data': True,
        'tw_hist_data': False,
        'fin_data_enrich': True,
        'yf_fin_data': True,
        'write_info_file': True
    }
}


# ============================================================================
# COMMAND-LINE ARGUMENT PARSER
# ============================================================================
def parse_arguments():
    """Parse command-line arguments for configuration override."""
    parser = argparse.ArgumentParser(
        description='Financial Market Data Collection System',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  # Use a preset configuration
  python main.py --preset nasdaq_daily

  # Download NASDAQ 100 with daily data only
  python main.py --ticker-choice 2 --daily --no-weekly --no-monthly

  # Download S&P 500 + NASDAQ 100 with daily and weekly data
  python main.py --ticker-choice 1-2 --daily --weekly

  # Quick test with test tickers
  python main.py --preset quick_test

  # Full CANSLIM analysis
  python main.py --preset full_canslim

Available presets: quick_test, nasdaq_daily, sp500_full, nasdaq_sp500_daily, portfolio_only, full_canslim

Ticker choice values:
  0: TradingView Universe
  1: S&P 500
  2: NASDAQ 100
  3: All NASDAQ stocks
  4: Russell 1000
  5: Index tickers
  6: Portfolio tickers
  7: ETF tickers
  8: Test tickers
  Use dash-separated for combinations: "1-2" (S&P 500 + NASDAQ 100)
        '''
    )

    # Preset
    parser.add_argument('--preset', type=str, choices=CONFIG_PRESETS.keys(),
                       help='Use a predefined configuration preset')

    # Ticker selection
    parser.add_argument('--ticker-choice', type=str, dest='ticker_choice',
                       help='Ticker group selection (e.g., "2" for NASDAQ 100, "1-2" for S&P500+NASDAQ100)')

    # Historical data control
    parser.add_argument('--hist-data', dest='yf_hist_data', action='store_true',
                       help='Enable historical data download')
    parser.add_argument('--no-hist-data', dest='yf_hist_data', action='store_false',
                       help='Disable historical data download')

    # Data intervals
    parser.add_argument('--daily', dest='yf_daily_data', action='store_true',
                       help='Enable daily (1d) data download')
    parser.add_argument('--no-daily', dest='yf_daily_data', action='store_false',
                       help='Disable daily data download')

    parser.add_argument('--weekly', dest='yf_weekly_data', action='store_true',
                       help='Enable weekly (1wk) data download')
    parser.add_argument('--no-weekly', dest='yf_weekly_data', action='store_false',
                       help='Disable weekly data download')

    parser.add_argument('--monthly', dest='yf_monthly_data', action='store_true',
                       help='Enable monthly (1mo) data download')
    parser.add_argument('--no-monthly', dest='yf_monthly_data', action='store_false',
                       help='Disable monthly data download')

    # TradingView data
    parser.add_argument('--tw-data', dest='tw_hist_data', action='store_true',
                       help='Enable TradingView data processing')
    parser.add_argument('--no-tw-data', dest='tw_hist_data', action='store_false',
                       help='Disable TradingView data processing')

    # Financial data enrichment
    parser.add_argument('--fin-data', dest='fin_data_enrich', action='store_true',
                       help='Enable financial data enrichment')
    parser.add_argument('--no-fin-data', dest='fin_data_enrich', action='store_false',
                       help='Disable financial data enrichment')

    # Info file
    parser.add_argument('--write-info', dest='write_info_file', action='store_true',
                       help='Enable info file generation')
    parser.add_argument('--no-write-info', dest='write_info_file', action='store_false',
                       help='Disable info file generation')

    # Fast batch downloader
    parser.add_argument('--batch-data', dest='yf_batch_data', action='store_true',
                       help='Enable fast batch downloader (yf.download)')
    parser.add_argument('--no-batch-data', dest='yf_batch_data', action='store_false',
                       help='Disable fast batch downloader')
    parser.add_argument('--batch-daily', dest='yf_batch_daily', action='store_true',
                       help='Enable batch daily bars')
    parser.add_argument('--no-batch-daily', dest='yf_batch_daily', action='store_false',
                       help='Disable batch daily bars')
    parser.add_argument('--batch-weekly', dest='yf_batch_weekly', action='store_true',
                       help='Enable batch weekly bars')
    parser.add_argument('--no-batch-weekly', dest='yf_batch_weekly', action='store_false',
                       help='Disable batch weekly bars')
    parser.add_argument('--batch-monthly', dest='yf_batch_monthly', action='store_true',
                       help='Enable batch monthly bars')
    parser.add_argument('--no-batch-monthly', dest='yf_batch_monthly', action='store_false',
                       help='Disable batch monthly bars')
    parser.add_argument('--batch-only', action='store_true', dest='batch_only',
                       help='Run batch pipeline only — disables slow YF, TW, and financial data pipelines')
    parser.add_argument('--batch-ticker-choice', type=str, dest='yf_batch_ticker_choice',
                       help='Ticker group for batch only (0-8 or dash-separated e.g. 1-2); independent of --ticker-choice')
    parser.add_argument('--batch-universe', type=str, dest='yf_batch_universe',
                       help='Universe file in user_input/ for batch download (overrides CSV)')
    parser.add_argument('--end-date', type=str, dest='end_date',
                       help='End date for YF historical (slow) data download YYYY-MM-DD (default: today)')
    parser.add_argument('--batch-start', type=str, dest='batch_start',
                       help='Start date for all batch intervals YYYY-MM-DD')
    parser.add_argument('--batch-end', type=str, dest='batch_end',
                       help='End date for all batch intervals YYYY-MM-DD or today')
    parser.add_argument('--batch-period', type=str, dest='batch_period',
                       help='Period for all batch intervals when start is empty (e.g. 5d, 1y)')

    args = parser.parse_args()

    # Track which arguments were actually provided by checking sys.argv
    import sys
    provided_args = set()

    # Map CLI flags to their destination names
    flag_to_dest = {
        '--ticker-choice': 'ticker_choice',
        '--hist-data': 'yf_hist_data',
        '--no-hist-data': 'yf_hist_data',
        '--daily': 'yf_daily_data',
        '--no-daily': 'yf_daily_data',
        '--weekly': 'yf_weekly_data',
        '--no-weekly': 'yf_weekly_data',
        '--monthly': 'yf_monthly_data',
        '--no-monthly': 'yf_monthly_data',
        '--tw-data': 'tw_hist_data',
        '--no-tw-data': 'tw_hist_data',
        '--fin-data': 'fin_data_enrich',
        '--no-fin-data': 'fin_data_enrich',
        '--write-info': 'write_info_file',
        '--no-write-info': 'write_info_file',
        '--batch-data': 'yf_batch_data',
        '--no-batch-data': 'yf_batch_data',
        '--batch-daily': 'yf_batch_daily',
        '--no-batch-daily': 'yf_batch_daily',
        '--batch-weekly': 'yf_batch_weekly',
        '--no-batch-weekly': 'yf_batch_weekly',
        '--batch-monthly': 'yf_batch_monthly',
        '--no-batch-monthly': 'yf_batch_monthly',
        '--batch-ticker-choice': 'yf_batch_ticker_choice',
        '--batch-universe': 'yf_batch_universe',
    }

    for arg in sys.argv[1:]:
        if arg in flag_to_dest:
            provided_args.add(flag_to_dest[arg])

    # Convert args to dict, only including values that were explicitly provided
    config_dict = {}
    for key, value in vars(args).items():
        if key != 'preset' and key in provided_args:
            config_dict[key] = value

    # Smart logic: If any interval is enabled, auto-enable yf_hist_data
    intervals_enabled = (
        config_dict.get('yf_daily_data', False) or
        config_dict.get('yf_weekly_data', False) or
        config_dict.get('yf_monthly_data', False)
    )
    if intervals_enabled and 'yf_hist_data' not in config_dict:
        config_dict['yf_hist_data'] = True
        print("ℹ️  Auto-enabling YF historical data (interval specified)")

    # Smart logic: If any batch interval is enabled, auto-enable yf_batch_data
    batch_intervals_enabled = (
        config_dict.get('yf_batch_daily', False) or
        config_dict.get('yf_batch_weekly', False) or
        config_dict.get('yf_batch_monthly', False)
    )
    if batch_intervals_enabled and 'yf_batch_data' not in config_dict:
        config_dict['yf_batch_data'] = True
        print("ℹ️  Auto-enabling YF batch data (batch interval specified)")

    # --batch-only: disable all non-batch pipelines
    if args.batch_only:
        config_dict['yf_hist_data']   = False
        config_dict['tw_hist_data']   = False
        config_dict['fin_data_enrich'] = False
        config_dict['yf_batch_data']  = True
        print("ℹ️  --batch-only: slow YF, TW and financial pipelines disabled")

    # Capture batch date/period CLI overrides (not mapped through UserConfiguration)
    batch_overrides = {}
    if args.batch_start:  batch_overrides['batch_start']  = args.batch_start
    if args.batch_end:    batch_overrides['batch_end']    = args.batch_end
    if args.batch_period: batch_overrides['batch_period'] = args.batch_period
    if args.end_date:     batch_overrides['hist_end_date'] = args.end_date

    return args.preset, config_dict, batch_overrides


# ============================================================================
# CONFIGURATION MERGING
# ============================================================================
def merge_configs(base_config, config_override=None, preset=None, cli_args=None):
    """
    Merge configurations with priority: CLI args > preset > config_override > CSV base

    Args:
        base_config: UserConfiguration object from CSV
        config_override: dict - Python dict override (for Colab usage)
        preset: str - Preset name to use
        cli_args: dict - Command-line arguments

    Returns:
        UserConfiguration object with merged settings
    """
    import copy
    merged = copy.deepcopy(base_config)

    # Priority 1: Apply preset if specified
    if preset:
        if preset not in CONFIG_PRESETS:
            print(f"⚠️  Warning: Unknown preset '{preset}'. Using base config.")
            print(f"   Available presets: {', '.join(CONFIG_PRESETS.keys())}")
        else:
            print(f"📋 Using preset: {preset}")
            preset_config = CONFIG_PRESETS[preset]
            for key, value in preset_config.items():
                if hasattr(merged, key):
                    setattr(merged, key, value)

    # Priority 2: Apply config_override dict (for Colab)
    if config_override:
        print(f"🔧 Applying config overrides: {list(config_override.keys())}")
        for key, value in config_override.items():
            if hasattr(merged, key):
                setattr(merged, key, value)
            else:
                print(f"⚠️  Warning: Unknown config key '{key}' ignored")

    # Priority 3: Apply CLI arguments (highest priority)
    if cli_args:
        print(f"⌨️  Applying CLI arguments: {list(cli_args.keys())}")
        for key, value in cli_args.items():
            if hasattr(merged, key):
                setattr(merged, key, value)
            else:
                print(f"⚠️  Warning: Unknown CLI arg '{key}' ignored")

    return merged


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

def main(config_override=None, preset=None):
    """
    Main data collection function with flexible configuration options.

    Args:
        config_override (dict, optional): Dictionary to override CSV config values.
            Useful for programmatic usage (e.g., Colab notebooks).
            Example: {'ticker_choice': '2', 'yf_daily_data': True}

        preset (str, optional): Named preset configuration to use.
            Available presets: 'quick_test', 'nasdaq_daily', 'sp500_full',
                               'nasdaq_sp500_daily', 'portfolio_only', 'full_canslim'
            Example: preset='nasdaq_daily'

    Priority order: CLI args > preset > config_override > CSV defaults

    Usage examples:
        # Use CSV config (backward compatible)
        main()

        # Use preset
        main(preset='nasdaq_daily')

        # Use dict override (Colab-friendly)
        main({'ticker_choice': '2', 'yf_daily_data': True})

        # Command line
        python main.py --preset nasdaq_daily
        python main.py --ticker-choice 2 --daily --weekly
    """
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    # all messages are suppressed
    logging.getLogger().setLevel(logging.CRITICAL)
    setup_directories()  # Initialize directories via config

    # ============ CONFIGURATION MERGING ============
    print("\n" + "="*60)
    print("CONFIGURATION SETUP")
    print("="*60)

    # Read base configuration from CSV
    base_config = read_user_data()
    print(f"📄 Base config loaded from: user_input/user_data.csv")

    # Parse CLI arguments (if running from command line)
    cli_preset = None
    cli_args = None
    batch_overrides = {}
    try:
        import sys
        if len(sys.argv) > 1:
            cli_preset, cli_args, batch_overrides = parse_arguments()
    except SystemExit:
        pass

    # Merge preset parameter with CLI preset (CLI takes priority)
    final_preset = cli_preset if cli_preset else preset

    # Merge all configurations
    config = merge_configs(base_config, config_override, final_preset, cli_args)

    # Display final configuration
    print(f"\n🎯 Final Configuration:")
    print(f"   Ticker Choice: {config.ticker_choice}")
    print(f"   YF Historical Data: {config.yf_hist_data}")
    if config.yf_hist_data:
        intervals = []
        if config.yf_daily_data: intervals.append("Daily")
        if config.yf_weekly_data: intervals.append("Weekly")
        if config.yf_monthly_data: intervals.append("Monthly")
        print(f"   Intervals: {', '.join(intervals) if intervals else 'None'}")
    print(f"   TW Historical Data: {config.tw_hist_data}")
    print(f"   Financial Data Enrichment: {config.fin_data_enrich}")
    print(f"   Write Info Files: {config.write_info_file}")
    
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
    
            hist_end_date = batch_overrides.get('hist_end_date', datetime.now().strftime('%Y-%m-%d'))

            # Daily market data
            if config.yf_daily_data:
                print("\n📅 Downloading daily (1d) market data...")
                daily_params = {
                    'interval': '1d',
                    'start_date': '2020-01-01',
                    'end_date': hist_end_date,
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
                    'end_date': hist_end_date,
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
                    'end_date': hist_end_date,
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
    
    # ============ FAST BATCH DOWNLOADER ============
    if config.yf_batch_data:
        print("\n" + "="*60)
        print("FAST BATCH DOWNLOAD (yf.download)")
        print("="*60)

        # Determine universe file
        # Priority: batch_ticker_choice (CLI) > batch_universe (CSV/CLI) > slow-pipeline combined_file
        if config.yf_batch_ticker_choice:
            batch_choice = config.yf_batch_ticker_choice
            print(f"  Generating ticker files for batch ticker_choice: {batch_choice}")
            generate_all_ticker_files(unified_config, batch_choice)
            batch_ticker_file = os.path.join(PARAMS_DIR["TICKERS_DIR"], f"combined_tickers_{batch_choice}.csv")
        elif config.yf_batch_universe:
            batch_ticker_file = os.path.join(config.user_input_path, config.yf_batch_universe)
        else:
            batch_ticker_file = combined_file  # reuse slow-pipeline universe
        print(f"  Universe: {batch_ticker_file}")

        # Build interval config from CSV settings
        interval_cfg = {}
        if config.yf_batch_daily:
            interval_cfg["1d"] = _parse_interval_cfg(
                config.yf_batch_daily_start_date,
                config.yf_batch_daily_end_date,
                config.yf_batch_daily_period,
            )
        if config.yf_batch_weekly:
            interval_cfg["1wk"] = _parse_interval_cfg(
                config.yf_batch_weekly_start_date,
                config.yf_batch_weekly_end_date,
                config.yf_batch_weekly_period,
            )
        if config.yf_batch_monthly:
            interval_cfg["1mo"] = _parse_interval_cfg(
                config.yf_batch_monthly_start_date,
                config.yf_batch_monthly_end_date,
                config.yf_batch_monthly_period,
            )

        if not interval_cfg:
            print("  No batch intervals enabled — set YF_batch_daily/weekly/monthly to TRUE")
        else:
            batch_params = {
                "ticker_file":    batch_ticker_file,
                "output_dir":     config.yf_batch_output_path,
                "failed_file":    os.path.join(PARAMS_DIR["TICKERS_DIR"], "problematic_tickers_batch.csv"),
                "use_failed_file": config.yf_batch_use_failed_file,
                "interval_cfg":   interval_cfg,
                **batch_overrides,  # CLI --batch-start/end/period overrides
            }
            run_batch_data_retrieval(batch_params)
    else:
        print("\n" + "="*60)
        print("FAST BATCH DOWNLOAD DISABLED")
        print("="*60)
        print("  To enable: Set YF_batch_data = TRUE in user_input/user_data.csv")
        print("  Or use CLI: python main.py --batch-data --batch-daily")

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
