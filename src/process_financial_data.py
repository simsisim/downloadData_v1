import logging

import pandas as pd

from src.visualize_financial_data import generate_eps_trend_charts

logger = logging.getLogger(__name__)


def _select_top_tickers(financial_df, top_n):
    """
    Rank by cansi_criteria_met (the composite CANSI signal from
    get_financial_data.py's _calculate_cansi_score) descending, so the
    processing stage self-selects the most interesting candidates by
    default. Falls back to market cap ranking if an older CSV lacks the
    cansi_criteria_met column (rather than failing outright).
    """
    if 'cansi_criteria_met' in financial_df.columns:
        ranked = financial_df.sort_values('cansi_criteria_met', ascending=False, na_position='last')
    else:
        logger.warning("cansi_criteria_met column not found - falling back to market cap ranking")
        ranked = financial_df.copy()
        ranked['marketCap'] = pd.to_numeric(ranked['marketCap'], errors='coerce')
        ranked = ranked.sort_values('marketCap', ascending=False, na_position='last')
    return ranked['ticker'].head(top_n).tolist()


def run_financial_data_processing(financial_data_csv_path, config):
    """
    Process already-downloaded financial data: charts today, filters/screening
    in the future. Independent of the download stage - takes no yfinance
    calls, works entirely off financial_data_csv_path.
    """
    financial_df = pd.read_csv(financial_data_csv_path)
    print(f"📄 Loaded {len(financial_df)} tickers from {financial_data_csv_path}")

    top_tickers = _select_top_tickers(financial_df, config.fin_data_chart_top_n)
    print(f"📈 Charting top {len(top_tickers)} tickers by CANSI score: {', '.join(top_tickers)}")

    saved_paths = generate_eps_trend_charts(
        financial_data_csv_path,
        tickers=top_tickers,
        quarters_to_show=config.fin_data_chart_quarters,
        max_peers=config.fin_data_chart_max_peers,
    )
    print(f"✅ Generated {len(saved_paths)} EPS trend chart(s)")

    # TODO: apply CANSI screening filters here and export a screened CSV
    # (e.g. filter financial_df by cansi_criteria_met/cansi_letters_passed
    # thresholds) - not implemented yet, this is the natural next call in
    # this function once screening criteria are defined.

    return saved_paths
