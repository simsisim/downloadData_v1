# CANSI Raw Data Requirements (William O'Neil's CANSLIM)

Scope: **C, A, N, S, I** only. **L (Leader/Laggard)** and **M (Market Direction)** are deliberately excluded from this pass — L is a relative-strength/peer-comparison concern, M is a macro/index-level concern, both out of scope for per-ticker fundamental collection.

All yfinance field names below were verified against a live `yf.Ticker('AAPL')` call (Jan 2026 API surface, yfinance 1.2.0). Row names inside `income_stmt` / `balance_sheet` / `cashflow` come from the actual `.index` of those DataFrames.

**Implementation status:** raw extraction AND scoring/threshold calculations for all of C/A/N/S/I are implemented in `src/get_financial_data.py`, plus a simple composite CANSI signal. What's left is a full point-weighted composite score (the old dead/commented-out `_calculate_canslim_score` code was never revived) and the letters explicitly out of scope (L, M) or unautomatable (see below).

---

## C — Current Quarterly Earnings

O'Neil's test: **YoY quarterly EPS growth**, ideally 25%+, checked for **acceleration across the last 3 quarters**, confirmed by sales growth (rules out cost-cutting driving EPS) and margin expansion. Watch for one-time items inflating a quarter.

| Raw data point | yfinance source | Field / row name | Extracted as | Status |
|---|---|---|---|---|
| Quarterly diluted EPS | `ticker.quarterly_income_stmt` | `Diluted EPS` | `q{i}_eps` (i=1..12, capped at ~5 by yfinance) | ✅ Done |
| Quarterly basic EPS | `ticker.quarterly_income_stmt` | `Basic EPS` | `q{i}_eps_basic` | ✅ Done — kept alongside diluted; undecided which basis CANSLIM scoring should standardize on |
| Quarterly revenue | `ticker.quarterly_income_stmt` | `Total Revenue` | `q{i}_revenue` | ✅ Done (pre-existing) |
| Quarterly pretax income | `ticker.quarterly_income_stmt` | `Pretax Income` | `q{i}_pretax_income` | ✅ Done |
| Quarterly operating income | `ticker.quarterly_income_stmt` | `Operating Income` | `q{i}_operating_income` | ✅ Done (pre-existing) |
| **Deep quarterly EPS history** (years, not ~5 quarters) | `ticker.get_earnings_dates(limit=N)` | `Reported EPS` column | `qh{i}_eps` (qh = quarter-history) | ✅ Done — see gotcha below |
| Analyst EPS estimate per quarter | `ticker.get_earnings_dates(limit=N)` | `EPS Estimate` column | `qh{i}_eps_estimate` | ✅ Done (free, same call) |
| Earnings surprise % (beat/miss) per quarter | `ticker.get_earnings_dates(limit=N)` | `Surprise(%)` column | `qh{i}_surprise_pct` | ✅ Done (free, same call) — not yet used in any calculation |
| Same-quarter-last-year EPS YoY growth | Derived | — | `q{i}_eps(_basic)_growth_yoy`, `qh{i}_eps_growth_yoy` | ✅ Done — `_safe_growth_rate()`, N/A when prior period ≤0 (loss→profit swings aren't a meaningful %) |
| 3-quarter acceleration flag | Derived from `qh1/qh2/qh3` growth | — | `eps_growth_accelerating` (bool or N/A) | ✅ Done |
| Unusual/one-time items flag | `ticker.quarterly_income_stmt` | `Unusual Items` (conditional row — only present when applicable) | — | ❌ Not implemented — row is inconsistent across tickers, deferred |

**Gotcha discovered during implementation:** yfinance's free `quarterly_income_stmt` feed only returns **~5 trailing quarters**, regardless of how many are requested. That's enough for exactly one YoY comparison (`q1` vs `q5`) — not the 7+ quarters O'Neil's 3-quarter acceleration test actually needs. Solved by adding `ticker.get_earnings_dates(limit=N)` as a second source: it returns years of *reported* EPS (cross-verified to match the diluted EPS from the income statement, e.g. AAPL's `q1_eps=2.01` = `qh1_eps=2.01`). The `qh{i}_` series is what the acceleration flag is actually computed from; `q{i}_eps` is kept for cross-checking against the full-statement data (revenue/pretax income from the same source/period). `earnings_history_limit` (default 12) controls how deep the `qh` series goes.

---

## A — Annual Earnings Growth

O'Neil's test: **3-5 year annual EPS growth**, ideally 25%+ average with **no down year**, ROE ≥17%, and **cash flow/share meaningfully above EPS** (his quality-of-earnings check). Falling long-term debt is a supporting positive.

| Raw data point | yfinance source | Field / row name | Extracted as | Status |
|---|---|---|---|---|
| Annual diluted EPS (3-5 yrs) | `ticker.income_stmt` | `Diluted EPS` | `y{i}_eps` (i=1..5) | ✅ Done |
| Annual basic EPS | `ticker.income_stmt` | `Basic EPS` | `y{i}_eps_basic` | ✅ Done |
| Annual revenue (3-5 yrs) | `ticker.income_stmt` | `Total Revenue` | `y{i}_revenue` | ✅ Done (pre-existing) |
| Annual pretax income | `ticker.income_stmt` | `Pretax Income` | `y{i}_pretax_income` | ✅ Done |
| Stockholders' equity (annual, 3-5 yrs) | `ticker.balance_sheet` | `Stockholders Equity` | `y{i}_stockholders_equity` | ✅ Done — real ROE-trend basis, replaces snapshot-only `returnOnEquity` |
| Net income (annual, for ROE) | `ticker.income_stmt` | `Net Income` | `y{i}_net_income` | ✅ Done (pre-existing) |
| Operating cash flow (annual, 3-5 yrs) | `ticker.cashflow` | `Operating Cash Flow` | `y{i}_operating_cashflow` | ✅ Done |
| Long-term debt (annual trend) | `ticker.balance_sheet` | `Long Term Debt` | `y{i}_long_term_debt` | ✅ Done |
| Annual YoY EPS growth | Derived (`y{i}` vs `y{i+1}`) | — | `y{i}_eps(_basic)_growth_yoy` | ✅ Done — same `_safe_growth_rate()` helper as C |
| ROE trend / cash-flow-per-share vs EPS check | Derived from the above | — | — | ❌ Not implemented yet — raw fields exist, the actual comparison/scoring logic doesn't |

---

## N — New (Products / Management / New Highs)

Weakest letter for automated collection — O'Neil's original criteria are partly qualitative (news-driven: new product, new management, new industry conditions). Two solid quantitative proxies exist and are directly available as `info` snapshot fields (no price-history join needed):

| Raw data point | yfinance source | Field name | Extracted as | Status |
|---|---|---|---|---|
| Distance from 52-week high | `ticker.info` | `fiftyTwoWeekHighChangePercent` | `fiftyTwoWeekHighChangePercent` | ✅ Done |
| Distance from all-time high | `ticker.info` | `allTimeHigh` (compare to `currentPrice`) | `allTimeHigh` | ✅ Done (raw field only; the comparison-to-current-price calc isn't built yet) |
| 52-week high value | `ticker.info` | `fiftyTwoWeekHigh` | `fiftyTwoWeekHigh` | ✅ Done (pre-existing, lives in the L block) |
| First trade / listing date (recent-IPO proxy) | `ticker.info` | `firstTradeDateMilliseconds` | `firstTradeDateMilliseconds` → derived `yearsSincePublic` | ✅ Done |
| New product / new management signal | — | — | — | ❌ Not obtainable from structured yfinance data. Would require a news/filings API (e.g. 8-K parsing). Explicitly out of scope. |

---

## S — Supply and Demand

O'Neil's test: smaller float favors bigger moves; **shrinking share count (buybacks)** is bullish, dilution is bearish; falling debt reduces overhang; volume should expand on up days and contract on down days (accumulation vs. distribution).

| Raw data point | yfinance source | Field / row name | Extracted as | Status |
|---|---|---|---|---|
| Shares outstanding (current) | `ticker.info` | `sharesOutstanding` | `sharesOutstanding` | ✅ Done (pre-existing, snapshot only) |
| Float shares | `ticker.info` | `floatShares` | `floatShares` | ✅ Done (pre-existing) |
| Ordinary shares number (annual trend) | `ticker.balance_sheet` | `Ordinary Shares Number` | `y{i}_shares_outstanding` | ✅ Done — multi-year trend, detects buyback vs. dilution |
| Treasury shares number (annual trend) | `ticker.balance_sheet` | `Treasury Shares Number` | `y{i}_treasury_shares` | ✅ Done (often `N/A` — not all issuers report treasury shares this way) |
| Repurchase of capital stock ($, annual) | `ticker.cashflow` | `Repurchase Of Capital Stock` | `y{i}_buyback` | ✅ Done — direct dollar evidence of buybacks |
| Debt-to-equity | `ticker.info` | `debtToEquity` | `debtToEquity` | ✅ Done (pre-existing, snapshot; trend lives under A's `y{i}_long_term_debt`) |
| Daily volume + price change (up/down volume ratio) | Not from `Ticker` fundamentals — needs the existing daily OHLCV pipeline (`get_marketData.py`) | — | — | ❌ Not implemented — needs a join with `data/market_data*/daily/<ticker>.csv`; cross-module dependency, deferred |

---

## I — Institutional Sponsorship

O'Neil's test: **increasing number of institutional/mutual-fund holders** quarter over quarter (count matters more than raw %), ideally quality funds; flags over-ownership (~>70%) as a ceiling risk limiting future buying power.

| Raw data point | yfinance source | Field name | Extracted as | Status |
|---|---|---|---|---|
| % held by institutions | `ticker.info` | `heldPercentInstitutions` | `heldPercentInstitutions` | ✅ Done — now correctly grouped under the I block (previously mislabeled under "N & S") |
| Total institutional holder count | `ticker.major_holders` | `institutionsCount` | `institutionsCount` | ✅ Done — gated behind `collect_sponsorship_detail` (3 extra yfinance calls/ticker) |
| % held by institutions (cross-check) | `ticker.major_holders` | `institutionsPercentHeld` | `institutionsPercentHeld` | ✅ Done (gated) |
| Top institutional holders detail | `ticker.institutional_holders` | DataFrame: `Holder`, `Shares`, `Value`, `pctChange`, `Date Reported` | `institutional_holders_count`, `institutional_holders_avg_pct_change` | ✅ Done (gated) — condensed to count + average pctChange rather than storing the full top-10 table per ticker |
| Top mutual fund holders detail | `ticker.mutualfund_holders` | Same shape as above | `mutualfund_holders_count`, `mutualfund_holders_avg_pct_change` | ✅ Done (gated) |
| Sponsorship **trend** (holder count over time) | — | — | — | ❌ Not obtainable from one collection run — a single API call only gives a snapshot; true QoQ trend requires this pipeline to run repeatedly and diff snapshots over time |

---

## Config flags introduced during implementation

- `collect_sponsorship_detail` (default `False`) — gates the 3 extra I-detail calls (`major_holders`, `institutional_holders`, `mutualfund_holders`). Off by default so large-universe runs (thousands of tickers) aren't slowed down / rate-limited by default.
- `earnings_history_limit` (default `12`) — how many periods to request from `ticker.get_earnings_dates()` for the deep quarterly `qh{i}_` series.

## Still out of scope / unautomatable from this data source

- New product / new management signal (N) — needs a news/filings API
- Up/down volume accumulation-distribution ratio (S) — needs a join with the separate daily-OHLCV pipeline, not a `Ticker.info`/statement field
- True sponsorship trend (I) — needs repeated snapshots over time, not a single collection run
- Unusual/one-time items flag (C) — row is inconsistently present across tickers in yfinance's statements

## Scoring/threshold layer (implemented)

Built on top of the raw data above, in `get_financial_data.py`:

| Letter | Calculation | Fields | Method |
|---|---|---|---|
| A | ROE per year (`net_income / stockholders_equity`), flagged against O'Neil's 17%+ bar; cash-flow-per-share vs. EPS ratio, flagged against his ~20%+ premium bar | `y{i}_roe`, `y{i}_cashflow_per_share`, `y{i}_cashflow_vs_eps_ratio`, `roe_meets_threshold`, `cashflow_quality_pass` | `_calculate_annual_quality` |
| N | Within ~15% of 52-week high; recent-IPO heuristic (≤10 years, not a hard O'Neil rule — approximation) | `near_new_high`, `recent_ipo` | `_calculate_n_flags` |
| S | Multi-year share-count trend classification (`shrinking`/`stable`/`diluting`) from `y{i}_shares_outstanding`; buyback-$ evidence flag from `y{i}_buyback` | `supply_trend`, `buyback_active` | `_calculate_supply_trend` |
| I | Ownership-level classification (`healthy` / `over_owned` >70% / `low` <20%) from `heldPercentInstitutions` — works even when `collect_sponsorship_detail` is off | `sponsorship_level` | `_calculate_sponsorship_level` |
| Composite | Count of letters whose criteria are met, out of however many have usable (non-N/A) data — **not** a full weighted CANSLIM score/rank like IBD's, just a rough combined signal | `cansi_criteria_met`, `cansi_criteria_available`, `cansi_letters_passed` | `_calculate_cansi_score` |

Thresholds used (O'Neil/IBD conventions, hardcoded — not yet config-driven): ROE ≥17%, cash-flow-per-share ≥1.2× EPS, within 15% of 52-week high, share count change ±2% classifies shrinking/diluting, institutional ownership 20-70% = healthy.

Cross-validated on AAPL: `y1_roe` (1.52) matches yfinance's own snapshot `returnOnEquity` (1.52) almost exactly; `supply_trend=shrinking` + `buyback_active=True` match AAPL's well-known aggressive buyback history.

Verified degrading gracefully on sparse tickers (e.g. SPY, which has no fundamentals): each check independently falls back to `'N/A'` rather than crashing or miscounting — the composite's `cansi_criteria_available` correctly shrinks rather than treating missing data as a fail.

**Still not built:** the old dead/commented-out `_calculate_canslim_score` / screened-file CSV logic in `get_financial_data.py` (a full point-weighted 0-100 score) has not been revived — the new composite above is a simpler pass/fail count, not a replacement for that. `main.py`'s `enable_canslim_scoring` flag remains unread by any code.
