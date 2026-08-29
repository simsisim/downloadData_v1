# CANSLIM — methodology, the two implementations, and what to actually scan for

Status: living doc. Started 2026-08-29.
Scope: compares the CANSLIM logic in **this repo** (`downloadData_v1`) with the
one in **`dashboard-screener/src/leaders/canslim.py`**, measures both against
O'Neil's canonical method, and specifies a screen to build.

---

## 1. O'Neil's canonical CANSLIM (reference)

Source: William J. O'Neil, *How to Make Money in Stocks*. Thresholds below are
the ones O'Neil states explicitly; "bonus" items are things he emphasises but
without a hard number.

| Letter | Core rule | Threshold | Data needed |
|---|---|---|---|
| **C** — Current quarterly earnings | Most recent quarter EPS up big vs the **same quarter last year**. Bigger is better (his winners averaged +70% before the move). Growth should be **accelerating** over the last 2–3 quarters. **Sales** also up in the latest quarter. Watch for one-time gains. | EPS YoY **≥ +25%** (he often says 20–25%); sales YoY **≥ +25%** or sales-growth accelerating 3 quarters | quarterly EPS (diluted), quarterly revenue |
| **A** — Annual earnings growth | Annual EPS up each year for the **last 3 years**, at a strong rate; consistent, not erratic. Backed by high return on equity and by cash flow that exceeds reported EPS. | annual EPS growth **≥ +25%/yr** for 3 yr (each year up); **ROE ≥ 17%**; cash flow/sh ≥ ~1.2× EPS (bonus); annual sales growth strong (bonus) | 3–5 yr annual EPS, net income, equity, operating cash flow, revenue |
| **N** — New | New product / service / management / industry condition, **and** the stock is emerging from a proper base at or near a **new price high**. | within ~15% of the 52-week high | 52-week high/low, price (news/products = manual) |
| **S** — Supply & demand | Reasonable or shrinking share supply; heavy volume on up-days (demand); company buying back stock; low debt. | share count flat/shrinking; D/E low or falling; buybacks a plus; volume surge on breakouts | shares outstanding history, debt/equity, buyback $, **volume (price data)** |
| **L** — Leader or laggard | Buy the #1–2 relative-strength name in a strong group; avoid laggards/sympathy plays. | **RS Rating ≥ 80** (ideally 80–90+) | price history (cross-sectional relative strength) — **not fundamental** |
| **I** — Institutional sponsorship | Owned by institutions and the **number of institutional owners is rising** over recent quarters; a few high-quality funds. Not *over*-owned (that's late). | rising holder count; some but not extreme ownership | quarter-over-quarter institutional holder counts |
| **M** — Market direction | 3 of 4 stocks follow the market. Only buy in a **confirmed uptrend**; step aside on a correction (distribution-day count on the indexes). | index-level, distribution-day method | index price/volume — **not per-stock, not fundamental** |

### What is screenable from *fundamental* data alone

- **Fully:** C (EPS + sales), A (growth + ROE + cash-flow quality)
- **Partly:** N (near-new-high yes; new products no), S (share count / debt / buyback yes; volume no), I (ownership *level* yes; holder-count *trend* no — only a snapshot is available)
- **Not at all:** L (needs cross-sectional RS from prices), M (needs index timing)

So a "CANSLIM fundamental screen" can honestly deliver **C, A, and the fundamental parts of N/S/I**. L and M must come from a price-based module (in the dashboard-screener project that's `minervini.py` / `scooter.py` + a market-timing overlay).

---

## 2. Implementation A — `downloadData_v1` (this repo)

### Where
- **Calculation:** `src/get_financial_data.py`, the `_calculate_*` methods, run **at fetch time** for every ticker. Results are written as columns into `data/fin_data/tickers/<TICKER>.json` and the combined `data/fin_data/financial_data_<choice>.csv`.
- **"Filtering":** `src/process_financial_data.py` — **does not screen.** It sorts by `cansi_criteria_met` (desc) and generates EPS-trend charts for the top `fin_data_chart_top_n`. The actual screen is an explicit `# TODO` stub (≈ lines 48–51). There is **no pass/fail membership column and no screened-CSV output.**
- **Thresholds:** hard-coded in `get_financial_data.py` (no config knobs).

### Exact criteria as computed

| Letter | Column(s) | Rule in code | Method |
|---|---|---|---|
| **C** | `eps_growth_accelerating` | `qh1_eps_growth_yoy > qh2_eps_growth_yoy > qh3_eps_growth_yoy` (YoY growth rising over 3 quarters, from the deep `get_earnings_dates` history) | `_calculate_eps_growth` |
| **A** | `roe_meets_threshold` **and** `cashflow_quality_pass` | `y1_roe >= 0.17` **and** `y1_cashflow_vs_eps_ratio >= 1.2` (op-cash-flow-per-share ÷ diluted EPS) | `_calculate_annual_quality` |
| **N** | `near_new_high` | `fiftyTwoWeekHighChangePercent >= -0.15` | `_calculate_n_flags` (also `recent_ipo` = `yearsSincePublic <= 10`, not used in score) |
| **S** | `supply_trend` | oldest→newest `y*_shares_outstanding` change: `<= -2%` → *shrinking*, `>= +2%` → *diluting*, else *stable* | `_calculate_supply_trend` (also `buyback_active` = any `y*_buyback < 0`, not used in score) |
| **I** | `sponsorship_level` | `heldPercentInstitutions > 0.70` → *over_owned*; `0.20–0.70` → *healthy*; `< 0.20` → *low* | `_calculate_sponsorship_level` |

### Composite — `_calculate_cansi_score`

```
C pass = eps_growth_accelerating is True
A pass = roe_meets_threshold is True AND cashflow_quality_pass is True
N pass = near_new_high is True
S pass = supply_trend in ('shrinking', 'stable')
I pass = sponsorship_level == 'healthy'
```
`cansi_criteria_met` = count of letters passing; `cansi_criteria_available` =
count of letters with non-`N/A` inputs (N/A letters are excluded from the
denominator, not counted as fails); `cansi_letters_passed` = e.g. `"CNS"`.
**No membership threshold is applied anywhere.**

Also computed but unused by the score (available for a future screen): per-quarter
and per-year YoY EPS growth (`q*_eps_growth_yoy`, `qh*_eps_growth_yoy`,
`y*_eps_growth_yoy`), per-year ROE (`y*_roe`), cash-flow-per-share
(`y*_cashflow_per_share`, `y*_cashflow_vs_eps_ratio`).

### Gaps vs O'Neil
- **C has no magnitude gate.** It checks only that growth is *accelerating*, never that the latest quarter is ≥ +25% YoY. A stock going +3% → +5% → +8% passes C; a stock at a steady +60% fails. This is the single biggest deviation — O'Neil's C is fundamentally "≥ 25%, bigger is better."
- **C ignores sales.** `q*_revenue` is collected but not used (and was buggy until 2026-08-29 — see §5).
- **A is a quality screen, not a growth screen.** It never checks annual EPS growth ≥ 25%/yr or the "up every year for 3 years" consistency. It checks ROE and cash-flow quality — which O'Neil *also* wants, but as support for A, not as A itself.
- **A ignores sales.**
- **L and M** absent (expected — no price data in this repo).
- One-time-gain screening: none.

### Strengths vs O'Neil
- Keeps the O'Neil support metrics the other implementation drops: **ROE ≥ 17%**, **cash flow ≥ 1.2× EPS**, **share-count trend**, **buyback evidence**, **near-new-high**.
- **I has an over-ownership ceiling** (>70% institutional → fail), which is O'Neil's actual caution.
- `institutional_holders_avg_pct_change` / `mutualfund_holders_avg_pct_change` are collected (mean position change of the top-10 holders) — a partial proxy for O'Neil's "sponsorship increasing," though not the holder-*count* trend.

---

## 3. Implementation B — `dashboard-screener/src/leaders/canslim.py`

### Where
- Reads the **frozen snapshot** `downloadData_v1/data/fin_data/financial_data_0_8.csv` (2026-08-21, 3,813 tickers) via `src/data_loader.load_financial_data()`. No network.
- **Re-derives C/A/I from the raw columns** (`q1_eps`, `q5_eps`, `q1_date`, `q5_date`, `earningsQuarterlyGrowth`, `y1_eps`, `y4_eps`, `y1_net_income`, `y4_net_income`, `heldPercentInstitutions`). **It does not read any of downloadData_v1's `cansi_*` / `*_accelerating` / `*_meets_threshold` columns** — completely independent logic.
- Thresholds in `dashboard-screener/config.py` (`CANSLIM_*`).
- Deliberately **C-A-I only** — per the project's `intro.md`: *"only focus on CA**I** — the only ones that can be filtered using financial data."* N/S handled elsewhere or skipped; L via `minervini.py` (IBD RS percentile) / `scooter.py` (SCTR); M not in v1.

### Exact criteria

| Letter | Rule | Threshold (`config.py`) |
|---|---|---|
| **C** | `c_yoy = q1_eps / q5_eps - 1` (latest quarter diluted EPS vs same quarter a year earlier). Requires EPS **positive in both** periods and year-ago EPS ≥ base floor. Runtime check `q1_date > q5_date`. Falls back to `earningsQuarterlyGrowth` when `c_yoy` is NaN. **Pass = `c_yoy >= 0.25`.** A separate `C_accelerating` flag (`c_yoy > earningsQuarterlyGrowth`) is reported but **does not gate**. | `CANSLIM_C_MIN_YOY = 0.25`, `CANSLIM_C_MIN_BASE_EPS = 0.05` |
| **A** | `a_cagr` = 3-yr CAGR of `y1_eps` vs `y4_eps` (both positive); net-income CAGR (`y1_net_income` vs `y4_net_income`) as fallback. **Pass = `a_cagr >= 0.25`.** | `CANSLIM_A_MIN_CAGR = 0.25` |
| **I** | `heldPercentInstitutions`. **Pass = `inst >= 0.20`** — floor only, **no ceiling.** Plus a non-gating `accumulation_flag` (shares outstanding flat/shrinking over the last ~90 days, from market-data share files). | `CANSLIM_I_MIN_INST = 0.20` |

### Composite
`canslim_score = C_pass + A_pass + I_pass` (0–3).
`in_canslim = canslim_score >= CANSLIM_MIN_SCORE` where `CANSLIM_MIN_SCORE = 3`
→ **must pass C and A and I.** `leaders()` → `leaders_canslim.csv` (141 tickers on
the 2026-08-24 run).

### Gaps vs O'Neil
- **C ignores sales** (EPS only).
- **C acceleration is not required** (reported, not gated). Defensible — O'Neil's hard gate is the level; acceleration is the tie-breaker.
- **A uses CAGR, which hides a down year.** `y1 > y4` at 25%/yr can include a middle year that fell. O'Neil wants each year up.
- **A drops ROE and the cash-flow-vs-EPS quality check.**
- **I is a bare floor and backwards from O'Neil.** O'Neil's I signal is the *rising number of holders* and a warning against *over*-ownership; a `>= 20%` floor is neither. (Median institutional ownership in this universe is ~82%, so the floor is close to a no-op — noted in their own comments; it was raised 5% → 20% during their testing.)
- **N, S** not done here.
- **L, M** handled by other modules / not in v1.

### Strengths vs O'Neil
- **C uses the canonical +25% YoY level gate** on the correct quarter pair, with a sane base-EPS floor and a positive-both-periods rule.
- **A uses the canonical +25%/yr growth over 3 years.**
- Requires **all three** letters to pass (a real screen, not a rank).
- Cross-checked against price-based leader modules in the same project.

---

## 4. Side-by-side, and which is closer to O'Neil

| | downloadData_v1 `_calculate_cansi_score` | dashboard-screener `canslim.py` | Closer to O'Neil |
|---|---|---|---|
| **C — EPS** | growth *accelerating* over 3 qtrs; no level gate | latest qtr EPS **≥ +25% YoY** (canonical); acceleration reported only | **dashboard-screener** (level is O'Neil's C) |
| **C — sales** | not used | not used | neither |
| **A — growth** | not checked | 3-yr EPS **CAGR ≥ 25%/yr** (canonical) | **dashboard-screener** |
| **A — consistency** | not checked | not checked (CAGR masks a down year) | neither |
| **A — ROE** | **≥ 17%** (canonical) | not checked | **downloadData_v1** |
| **A — cash flow ≥ 1.2× EPS** | **checked** (canonical) | not checked | **downloadData_v1** |
| **N — near new high** | within 15% of 52-wk high (canonical) | not done | **downloadData_v1** |
| **S — share supply / buyback / debt** | share-count trend + buyback flag | not done | **downloadData_v1** |
| **I — level** | 20–70% band | ≥ 20% floor | roughly equal |
| **I — over-ownership ceiling** | **yes, >70% fails** (canonical caution) | no ceiling | **downloadData_v1** |
| **I — holder-count trend** | not available (snapshot); weak `avg_pct_change` proxy | not available | neither |
| **L — relative strength** | absent | via `minervini.py` (RS pct ≥ 70) | **dashboard-screener ecosystem** |
| **M — market timing** | absent | absent (v1) | neither |
| **Is it a screen?** | no — rank only, no threshold | **yes** — `score >= 3` (C and A and I) | **dashboard-screener** |

### Verdict

**Neither is a faithful full CANSLIM**, and they're not even close to each other:

- On the **two letters that O'Neil defines with hard numbers — C and A —
  `dashboard-screener/canslim.py` is materially closer.** It uses the actual
  +25% YoY (C) and +25%/yr-for-3-yr (A) thresholds and gates a real
  pass/fail list on them. downloadData_v1's C tests only *acceleration* (a
  stock can pass C at +8% YoY) and its "A" doesn't test earnings growth at all.
- **downloadData_v1 carries more of O'Neil's supporting checks** (ROE 17%,
  cash-flow quality, near-new-high, share supply, over-ownership ceiling) but
  never assembles them into a screen and gets the C definition wrong.
- **Both miss sales growth** (a real part of C and A) and, on their own,
  **L and M**.

So: closest-to-O'Neil for a *fundamental screen today* = **dashboard-screener's
C-A-I**, with downloadData_v1's ROE / cash-flow / near-high / supply / ceiling
checks as the missing "quality and N/S" layer.

---

## 5. Known data issues (affect either implementation)

| Issue | Status | Effect |
|---|---|---|
| **Revenue extraction bug** — `q*_revenue` / `y*_revenue` matched `Reconciled Cost Of Revenue` (substring `"Revenue"` + `.iloc[0]`), i.e. stored COGS as revenue. Net income > "revenue" in every row. | **Fixed 2026-08-29** (`_get_row_first_of`, exact-name match). Corrected values reach the cache only on a **full** fetch — force-refresh run scheduled 22:00 2026-08-29. Until then most cached tickers still hold the bad values. | Any sales-growth screen is impossible/wrong until the force-refresh lands. Neither current screen uses revenue, so present output is unaffected. |
| **Net-income / operating-income** had the same substring pattern (`Net Income From Continuing Operation Net Minority Interest`, `Total Operating Income As Reported` sort first). | Fixed in the same change. | For minority-interest / discontinued-ops names the old `y*_net_income` could be off → nudges dashboard-screener's A-CAGR *net-income fallback* (EPS is primary and was always exact-matched, so small). |
| **Snapshot staleness** — `financial_data_0_8.csv` is 2026-08-21; dashboard-screener reads it directly. | The 2026-08-29 run writes `financial_data_0_5.csv` (current `ticker_choice`), not `_0_8`. dashboard-screener's `config.FIN_DATA_CSV` path may need pointing at the new file. | dashboard-screener screens on 8-day-old (soon stale) fundamentals until repointed. |
| **`heldPercentInstitutions` > 1.0** for some tickers (yfinance sums holder categories). | Known yfinance quirk, passed through. | Inflates I; a ceiling test should allow for it (e.g. cap the comparison, or use `< 0.90` rather than a hard `<= 0.70`). |
| **`debtToEquity` unit** — yfinance returns it as a percent-like number (NVDA ≈ 6.6, some names ≈ 50, ≈ 200). | As-is. | A D/E screen must treat it as percent (e.g. `< 100` ≈ "under 1.0×"), not as a ratio. |
| **`_safe_growth_rate` returns N/A when prior ≤ 0** — loss→profit turnarounds get no growth number. | Intentional (a % across zero is meaningless). | Both implementations silently drop turnaround names from C/A rather than pass or fail them. |
| **qh acceleration needs `qh1..qh3` YoY**, which needs `qh1..qh7` reported. Thin-history / recent IPOs → `eps_growth_accelerating = N/A` → C excluded from downloadData_v1's denominator (not failed). | As-is. | downloadData_v1's `cansi_criteria_met` is over a variable denominator; comparing counts across tickers is not apples-to-apples. |

---

## 6. What to scan for — recommended O'Neil fundamental screen

Target: stocks with genuine CANSLIM *fundamental* characteristics. L and M are
out of scope for a fin-data screen (get them from a price module + market
overlay). All field names below are downloadData_v1's schema; "✅ now" =
already in the data, "⏳ after force-refresh" = needs the 2026-08-29 run,
"❌" = not available.

### C — Current quarterly earnings & sales
- `q1_eps` YoY vs `q5_eps` **≥ +0.25**, both positive, `q5_eps ≥ 0.05`, `q1_date > q5_date`. Fallback `earningsQuarterlyGrowth`. — ✅ now (`q1_eps_growth_yoy` already computed)
- `q1_revenue` YoY vs `q5_revenue` **≥ +0.25** (or sales-growth accelerating: `q1` vs `q2` vs `q3` YoY rising). — ⏳ after force-refresh
- *Bonus, softer:* `qh1_eps_growth_yoy > qh2_eps_growth_yoy > qh3_eps_growth_yoy` (acceleration) — ✅ now (`eps_growth_accelerating`)
- *Bonus:* the bigger the better — rank survivors by `q1_eps_growth_yoy` descending.

### A — Annual earnings growth & quality
- Annual diluted EPS: `y1_eps > y2_eps > y3_eps` **and** 3-yr CAGR `(y1_eps/y4_eps)**(1/3) - 1 ≥ 0.25` (net-income fallback `y1_net_income/y4_net_income`). — ✅ now (`y*_eps` present; CAGR is trivial to compute)
- `y1_roe ≥ 0.17` — ✅ now (`roe_meets_threshold`)
- `y1_cashflow_vs_eps_ratio ≥ 1.2` — ✅ now (`cashflow_quality_pass`)
- *Bonus:* `y1_revenue` vs `y3_revenue` sales growth strong — ⏳ after force-refresh

### N — New high (fundamental part only)
- `fiftyTwoWeekHighChangePercent ≥ -0.15` (within 15% of the 52-wk high) — ✅ now (`near_new_high`)
- New products / management → not screenable, manual review of survivors.

### S — Supply & demand (fundamental part only)
- `supply_trend in ('shrinking','stable')` — ✅ now
- `debtToEquity` low or falling: `debtToEquity < 100` (≈ under 1.0×) or `y1_long_term_debt < y3_long_term_debt` — ✅ now
- *Bonus:* `buyback_active is True` — ✅ now
- Volume surge on breakout → price data, not here.

### I — Institutional sponsorship (level + weak trend proxy)
- `0.20 ≤ heldPercentInstitutions ≤ 0.90` (present, not over-owned; upper bound loosened from 0.70 because of the >1.0 quirk and this universe's ~82% median) — ✅ now
- *Weak trend proxy:* `institutional_holders_avg_pct_change ≥ 0` (top-10 holders adding, not trimming) — ✅ now, use as a tiebreak not a gate
- Rising holder *count* quarter over quarter → ❌ not available (snapshot only).

### L — Leader / relative strength
- **Not in fin_data.** Require the survivor to also pass a price-based RS screen
  (RS Rating ≥ 80, or `dashboard-screener/minervini.py` `rs_pct ≥ 70`, or SCTR
  ≥ 90). Intersect the two lists.

### M — Market direction
- **Not per-stock.** Only take signals when the general market (index
  distribution-day / trend) is in a confirmed uptrend. Separate overlay.

### Suggested pass rule
- **Hard screen:** C (EPS ≥ 25% **and** sales ≥ 25%) **and** A (CAGR ≥ 25% **and**
  each year up **and** ROE ≥ 17%). These are the non-negotiable O'Neil numbers.
- **Then require ≥ 2 of:** cash-flow quality, near-new-high, healthy supply,
  healthy (non-over-owned) sponsorship.
- **Then intersect with a price RS leader list** for the L.
- **Rank the final list** by `q1_eps_growth_yoy` (C magnitude — "bigger is better").
- Make every threshold a config knob (`canslim_c_min_yoy`, `canslim_a_min_cagr`,
  `canslim_roe_min`, `canslim_sales_min_yoy`, `canslim_min_support_letters`, …).

---

## 7. Open work items (this repo)

1. **Force-refresh run** (scheduled 22:00 2026-08-29) → correct `q*_revenue` /
   `y*_revenue` / net-income universe-wide; populate `next_earnings_date`.
2. **Rewrite `_calculate_growth_trends`** (currently commented out) → quarterly &
   annual sales-growth + acceleration from the corrected revenue.
3. **Add the C magnitude gate and the A growth+consistency gate** — either fix
   `_calculate_cansi_score` to match O'Neil, or add a parallel
   `canslim_oneill_*` set of columns so the existing `cansi_*` composite is left
   intact for whoever depends on it.
4. **Config knobs** for every threshold (`user_input/user_data.csv` +
   `src/user_defined_data.py`).
5. **Wire `process_financial_data.py`'s screening stub** → write
   `data/fin_data/canslim_screened_<choice>.csv` (survivors, ranked), which is
   what a downstream consumer / dashboard-screener would read.
6. **Decide the source of truth.** Options: (a) this repo computes the O'Neil
   screen and writes the screened CSV; (b) this repo only fixes/serves clean raw
   data and `dashboard-screener/canslim.py` owns the screen (then extend *that*
   file with sales + ROE + consistency). (b) keeps one screen implementation;
   (a) keeps the dashboard-screener free of fundamental logic.
7. **Repoint `dashboard-screener/config.FIN_DATA_CSV`** from `financial_data_0_8.csv`
   to the current `financial_data_0_5.csv` once the run completes.

---

## Using the screen with L and M

`canslim_screened_<choice>.csv` is C-A-N-S-I only. To approximate full CANSLIM:

**L — relative strength.** Intersect the survivors with a price-based leader
list:
- `dashboard-screener/src/leaders/minervini.py` → `in_minervini` (its criterion
  8 is IBD RS percentile ≥ 70), or its `rs_pct` column directly, or
- any RS Rating ≥ 80 source.
```python
canslim = pd.read_csv("data/fin_data/canslim_screened_0_5.csv")
leaders = minervini_df[minervini_df["in_minervini"]]        # or rs_pct >= 70
final = canslim[canslim["ticker"].isin(leaders["ticker"])]
```

**M — market direction.** Not per-ticker. Gate the *use* of the list: only act
on it while the general market (S&P 500 / Nasdaq Composite) is in a confirmed
uptrend — e.g. index above its 50-day and 200-day MA and distribution-day count
low. If the market is in a correction, the screen still runs but you sit out.

**N (qualitative) and S (volume/demand).** The screen covers near-new-high (N)
and share-supply/debt (S). New products/management (N) and up-day volume surges
(S) are manual / price-data checks on the shortlist.

## 8. File map

| Concern | File |
|---|---|
| Fundamental data fetch + `_calculate_*` (this repo) | `downloadData_v1/src/get_financial_data.py` |
| "Processing" (charts + screening stub) | `downloadData_v1/src/process_financial_data.py` |
| Per-ticker cache | `downloadData_v1/data/fin_data/tickers/<TICKER>.json` |
| Combined CSV consumed downstream | `downloadData_v1/data/fin_data/financial_data_<choice>.csv` |
| Raw-field requirements / extraction notes | `downloadData_v1/docus/CANSI_RAW_DATA_REQUIREMENTS.md` |
| CANSLIM C-A-I screen (other repo) | `dashboard-screener/src/leaders/canslim.py` |
| Its thresholds | `dashboard-screener/config.py` (`CANSLIM_*`) |
| Its data loader | `dashboard-screener/src/data_loader.py` (`load_financial_data`) |
| Price-based leader (covers L) | `dashboard-screener/src/leaders/minervini.py`, `scooter.py` |
| Its plan / provenance | `dashboard-screener/IMPLEMENTATION_PLAN.md`, `intro.md` |
