import logging
import os

import matplotlib
matplotlib.use('Agg')  # headless-safe backend - this runs in a batch pipeline, not a GUI
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import pandas as pd

from src.config import PARAMS_DIR

logger = logging.getLogger(__name__)

# Chart chrome (docus/dataviz palette reference instance, light surface)
SURFACE = '#fcfcfb'
INK_PRIMARY = '#0b0b0b'
INK_SECONDARY = '#52514e'
INK_MUTED = '#898781'
GRIDLINE = '#e1e0d9'
AXIS_LINE = '#c3c2b7'
STATUS_GOOD = '#0ca30c'

# Categorical palette, slots 1-5 (validated: worst adjacent CVD dE 9.1, worst
# adjacent normal-vision dE 19.6 - see docus dataviz skill palette reference).
# Target ticker always takes slot 1; peers take slots 2-5 in the fixed order.
CATEGORICAL_TARGET = '#2a78d6'
CATEGORICAL_PEERS = ['#eb6834', '#1baf7a', '#eda100', '#e87ba4']


def _get_quarterly_eps_series(row, quarters_to_show):
    """
    Build a chronological (offset, eps) series from a row's qh{i}_eps fields.
    offset 0 = most recent reported quarter, -1 = one quarter back, etc.
    (deep-history 'qh' series - see get_financial_data.py's
    _extract_earnings_history - not the ~5-quarter-capped 'q' series.)
    """
    points = []
    for i in range(1, quarters_to_show + 1):
        eps = row.get(f'qh{i}_eps', 'N/A')
        if isinstance(eps, (int, float)) and pd.notna(eps):
            points.append((-(i - 1), eps))
    points.sort(key=lambda p: p[0])
    return points


def _select_peers(financial_df, ticker, target_row, max_peers):
    """
    Same-industry peers, falling back to same-sector if too few. Ranked by
    market cap (largest first) since bigger peers are more meaningful
    comparators for "is the whole group accelerating, or just this one stock".
    """
    pool = financial_df[financial_df['ticker'] != ticker].copy()

    industry = target_row.get('industry', 'N/A')
    sector = target_row.get('sector', 'N/A')

    peers = pool[pool['industry'] == industry] if industry != 'N/A' else pool.iloc[0:0]
    group_label = f"industry: {industry}"
    if len(peers) < 2 and sector != 'N/A':
        peers = pool[pool['sector'] == sector]
        group_label = f"sector: {sector}"

    if peers.empty:
        return peers, group_label

    peers = peers.copy()
    peers['marketCap'] = pd.to_numeric(peers['marketCap'], errors='coerce')
    peers = peers.sort_values('marketCap', ascending=False, na_position='last')
    return peers.head(max_peers), group_label


def plot_eps_trend(ticker, financial_df, output_dir=None, quarters_to_show=8, max_peers=4):
    """
    O'Neil/IBD-style quarterly EPS trend chart: the target ticker plotted
    against up to `max_peers` same-industry (or same-sector, if too few
    industry peers exist) peers.

    Quarters are aligned by POSITION (T, T-1, T-2, ...), not by exact
    calendar date - different companies report on different fiscal
    calendars, so lining up "quarters back from each company's own most
    recent report" is what makes the comparison meaningful, at the cost of
    the x-axis not being a literal timeline.

    Y-axis is log-scaled when every plotted EPS value is positive - on a log
    scale, a constant growth RATE draws as a straight line, so acceleration
    (steepening) or deceleration (flattening/rolling over) is visible as
    curvature. Falls back to a linear scale (labeled as such) when any
    plotted quarter was a loss, since log of a non-positive value is undefined.

    Returns the saved PNG path, or None if the ticker has no usable EPS data.
    """
    output_dir = output_dir or PARAMS_DIR['CHARTS_DIR']
    os.makedirs(output_dir, exist_ok=True)

    matches = financial_df[financial_df['ticker'] == ticker]
    if matches.empty:
        logger.warning(f"plot_eps_trend: {ticker} not found in financial_df")
        return None
    target_row = matches.iloc[0]

    target_points = _get_quarterly_eps_series(target_row, quarters_to_show)
    if len(target_points) < 2:
        logger.warning(f"plot_eps_trend: {ticker} has fewer than 2 usable quarterly EPS points")
        return None

    peer_rows, group_label = _select_peers(financial_df, ticker, target_row, max_peers)
    peer_series = {}
    for _, prow in peer_rows.iterrows():
        pts = _get_quarterly_eps_series(prow, quarters_to_show)
        if len(pts) >= 2:
            peer_series[prow['ticker']] = pts

    all_eps_values = [v for _, v in target_points]
    for pts in peer_series.values():
        all_eps_values.extend(v for _, v in pts)
    use_log = len(all_eps_values) > 0 and all(v > 0 for v in all_eps_values)

    fig, ax = plt.subplots(figsize=(9, 5.5), facecolor=SURFACE)
    ax.set_facecolor(SURFACE)

    # Recessive gridlines behind the data
    ax.grid(True, axis='y', color=GRIDLINE, linewidth=0.8, zorder=0)
    for spine in ('top', 'right'):
        ax.spines[spine].set_visible(False)
    for spine in ('left', 'bottom'):
        ax.spines[spine].set_color(AXIS_LINE)
    ax.tick_params(colors=INK_MUTED, labelsize=9)

    def _plot_series(points, color, linewidth, label, is_target):
        xs = [p[0] for p in points]
        ys = [p[1] for p in points]
        ax.plot(xs, ys, color=color, linewidth=linewidth, marker='o', label=label,
                markersize=7 if is_target else 5.5, zorder=3 if is_target else 2)
        # Direct label at the most recent point - text wears ink, not the
        # series color, so identity is never color-alone (dataviz relief rule).
        ax.annotate(label, xy=(xs[-1], ys[-1]), xytext=(6, 0),
                    textcoords='offset points', va='center',
                    fontsize=9, color=INK_PRIMARY if is_target else INK_SECONDARY,
                    fontweight='bold' if is_target else 'normal')
        return xs[-1], ys[-1]

    _plot_series(target_points, CATEGORICAL_TARGET, 2.5, ticker, is_target=True)
    for idx, (peer_ticker, pts) in enumerate(peer_series.items()):
        color = CATEGORICAL_PEERS[idx % len(CATEGORICAL_PEERS)]
        _plot_series(pts, color, 1.5, peer_ticker, is_target=False)

    # Flag if the target's latest EPS is at/near the high of the plotted window.
    # Placed as figure-level text (outside the axes bounding box entirely), not
    # inline near the data or inside the axes - every series' direct label
    # clusters at the right edge (all "most recent" points share an x), and an
    # in-axes corner risks colliding with wherever legend(loc='best') lands.
    target_max = max(v for _, v in target_points)
    latest_offset, latest_eps = target_points[-1]
    near_high = latest_eps >= 0.95 * target_max
    if near_high:
        fig.text(0.99, 0.985, f'{ticker}: near/at {quarters_to_show}Q high',
                  fontsize=9, color=STATUS_GOOD, fontweight='bold', va='top', ha='right')

    if use_log:
        ax.set_yscale('log')
        ax.yaxis.set_major_formatter(mticker.FormatStrFormatter('%.2f'))
        scale_note = 'log scale - a straight line = constant growth rate'
    else:
        scale_note = 'linear scale - includes a loss quarter, log scale not meaningful'

    ax.set_title(f'{ticker} Quarterly EPS Trend vs. Peers ({group_label})',
                 fontsize=13, color=INK_PRIMARY, fontweight='bold', pad=14)
    ax.set_xlabel('Quarters back from most recent report (aligned by position, not calendar date)',
                  fontsize=9, color=INK_MUTED)
    ax.set_ylabel(f'Reported diluted EPS ({scale_note})', fontsize=9, color=INK_MUTED)

    n_series = 1 + len(peer_series)
    if n_series >= 2:
        ax.legend(loc='best', frameon=False, fontsize=8, labelcolor=INK_SECONDARY)

    fig.tight_layout()
    output_path = os.path.join(output_dir, f'{ticker}_eps_trend.png')
    fig.savefig(output_path, dpi=150, facecolor=SURFACE)
    plt.close(fig)
    logger.info(f"Saved EPS trend chart for {ticker} to {output_path}")
    return output_path


def generate_eps_trend_charts(financial_data_csv_path, tickers, output_dir=None,
                               quarters_to_show=8, max_peers=4):
    """
    Generate EPS trend charts for an explicit list of tickers (no implicit
    "all tickers" default - charting an entire universe unattended would be
    slow and disk-heavy; callers decide which tickers matter).
    """
    financial_df = pd.read_csv(financial_data_csv_path)
    saved_paths = []
    for ticker in tickers:
        path = plot_eps_trend(ticker, financial_df, output_dir=output_dir,
                               quarters_to_show=quarters_to_show, max_peers=max_peers)
        if path:
            saved_paths.append(path)
    return saved_paths
