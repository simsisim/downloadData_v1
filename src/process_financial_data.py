import logging
import os

import pandas as pd

from src import canslim_screen, fin_data_store
from src.visualize_financial_data import generate_eps_trend_charts

logger = logging.getLogger(__name__)

# The canslim_* override knobs on UserConfiguration -> resolve_thresholds keys.
_OVERRIDE_ATTRS = {
    "canslim_c_min_eps_yoy": "c_min_eps_yoy",
    "canslim_c_min_sales_yoy": "c_min_sales_yoy",
    "canslim_c_require_sales": "c_require_sales",
    "canslim_a_min_cagr": "a_min_cagr",
    "canslim_a_require_each_year_up": "a_require_each_year_up",
    "canslim_a_min_roe": "a_min_roe",
    "canslim_a_min_cashflow_ratio": "a_min_cashflow_ratio",
    "canslim_n_min_pct_from_high": "n_min_pct_from_high",
    "canslim_s_max_debt_equity": "s_max_debt_equity",
    "canslim_i_min_inst": "i_min_inst",
    "canslim_i_max_inst": "i_max_inst",
    "canslim_min_support": "min_support",
}


def _collect_overrides(config):
    out = {}
    for attr, key in _OVERRIDE_ATTRS.items():
        val = getattr(config, attr, None)
        if val is not None:
            out[key] = val
    return out


def _select_top_tickers(financial_df, top_n):
    """
    Rank for charting. Prefer canslim_rank (screen survivors first, by C
    magnitude); fall back to cansi_criteria_met, then market cap, so an older
    CSV without those columns still charts something rather than failing.
    """
    if 'canslim_rank' in financial_df.columns and financial_df['canslim_rank'].notna().any():
        ranked = financial_df.sort_values('canslim_rank', ascending=True, na_position='last')
    elif 'cansi_criteria_met' in financial_df.columns:
        ranked = financial_df.sort_values('cansi_criteria_met', ascending=False, na_position='last')
    else:
        logger.warning("no canslim_rank / cansi_criteria_met column - falling back to market cap ranking")
        ranked = financial_df.copy()
        ranked['marketCap'] = pd.to_numeric(ranked['marketCap'], errors='coerce')
        ranked = ranked.sort_values('marketCap', ascending=False, na_position='last')
    return ranked['ticker'].head(top_n).tolist()


def _run_canslim_screen(financial_df, financial_data_csv_path, config):
    """
    Apply the O'Neil preset to the run's data, write canslim_metrics_<choice>.csv
    and canslim_screened_<choice>.csv, persist the screen into fin_data.db, and
    return financial_df with the canslim_* columns merged in (for charting).
    """
    preset = getattr(config, 'canslim_preset', 'classic')
    overrides = _collect_overrides(config)

    missing = canslim_screen.check_inputs(financial_df)
    if missing:
        logger.warning("CANSLIM screen: %d expected input column(s) missing: %s",
                       len(missing), missing)

    scr = canslim_screen.apply_screen(financial_df, preset=preset, overrides=overrides)
    passers = canslim_screen.screened(scr)

    base = financial_data_csv_path.replace('financial_data_', 'canslim_metrics_')
    metrics_path = base
    screened_path = financial_data_csv_path.replace('financial_data_', 'canslim_screened_')

    canslim_screen.metrics_frame(scr).to_csv(metrics_path, index=False)
    passers.to_csv(screened_path, index=False)
    print(f"🧮 CANSLIM screen ({preset}): {len(passers)}/{len(scr)} pass "
          f"— C={int(scr['canslim_C_pass'].sum())} A={int(scr['canslim_A_pass'].sum())} "
          f"N={int(scr['canslim_N_pass'].sum())} S={int(scr['canslim_S_pass'].sum())} "
          f"I={int(scr['canslim_I_pass'].sum())}")
    print(f"   → {os.path.basename(metrics_path)}, {os.path.basename(screened_path)}")

    snap = _infer_snapshot_date(financial_df)
    try:
        conn = fin_data_store.open_db()
        try:
            fin_data_store.write_screen(scr, snap, preset, conn=conn)
        finally:
            conn.close()
        print(f"   → fin_data.db canslim_screen (snapshot {snap}, preset {preset})")
    except Exception as e:
        logger.warning("could not persist CANSLIM screen to fin_data.db: %s", e)

    merge_cols = [c for c in scr.columns if c.startswith('canslim_')]
    return financial_df.merge(scr[['ticker'] + merge_cols], on='ticker', how='left')


def _infer_snapshot_date(df):
    if 'last_updated' in df.columns:
        ts = pd.to_datetime(df['last_updated'], errors='coerce').max()
        if pd.notna(ts):
            return ts.date().isoformat()
    return pd.Timestamp.today().date().isoformat()


def run_financial_data_processing(financial_data_csv_path, config):
    """
    Process already-downloaded financial data: the CANSLIM O'Neil screen +
    EPS-trend charts. Independent of the download stage - no yfinance calls,
    works entirely off financial_data_csv_path.
    """
    financial_df = pd.read_csv(financial_data_csv_path, low_memory=False)
    print(f"📄 Loaded {len(financial_df)} tickers from {financial_data_csv_path}")

    if getattr(config, 'canslim_screen_enabled', True):
        financial_df = _run_canslim_screen(financial_df, financial_data_csv_path, config)
    else:
        print("⏭️  CANSLIM screen disabled (canslim_screen_enabled = FALSE)")

    top_tickers = _select_top_tickers(financial_df, config.fin_data_chart_top_n)
    print(f"📈 Charting top {len(top_tickers)} tickers: {', '.join(top_tickers)}")

    saved_paths = generate_eps_trend_charts(
        financial_data_csv_path,
        tickers=top_tickers,
        quarters_to_show=config.fin_data_chart_quarters,
        max_peers=config.fin_data_chart_max_peers,
    )
    print(f"✅ Generated {len(saved_paths)} EPS trend chart(s)")

    return saved_paths
