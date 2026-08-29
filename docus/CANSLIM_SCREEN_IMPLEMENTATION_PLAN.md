# CANSLIM O'Neil screen — implementation plan

Status: DRAFT for review. Started 2026-08-29.
Companion to `CANSLIM_METHODOLOGY_AND_IMPLEMENTATIONS.md` (the *why*); this is
the *what and how*. Nothing here is built yet.

---

## 1. Goal

A **fundamental-only** CANSLIM screen inside `downloadData_v1` that:

1. computes **every** CANSLIM metric for **every** ticker (no thresholds baked in),
2. persists them (SQLite + CSV exports), accumulating a dated history,
3. filters them with a **named O'Neil preset** into a ready-made leader list,
4. leaves the raw metric table exposed so the user (or `dashboard-screener`, or
   a notebook) can filter with their own thresholds,
5. hands **L** and **M** off to an intersection step in another repo.

Design rule: **values at fetch time, pass/fail at filter time.** Re-screening
with new thresholds is then a seconds-long re-run of the filter step — no
re-fetch, no recompute of values.

---

## 2. Scope — which letters

| letter | in this screen? | how |
|---|---|---|
| **C** — current quarterly EPS + sales | ✅ **hard gate** | `q1_eps` vs `q5_eps`, `q1_revenue` vs `q5_revenue`, acceleration flag |
| **A** — annual EPS growth + quality | ✅ **hard gate** | 3-yr EPS CAGR, year-over-year consistency, ROE; cash-flow-vs-EPS as a quality flag |
| **N** — near new high | ✅ **support flag** | `fiftyTwoWeekHighChangePercent` (already in snapshot). New products/mgmt = not screenable. |
| **S** — supply | ✅ **support flag** | share-count trend, `debtToEquity`, buyback $. Volume/demand = not fundamental. |
| **I** — institutional sponsorship | ✅ **support flag (weak)** | ownership *level* + over-ownership ceiling. Rising holder *count* = unavailable (snapshot only); `institutional_holders_avg_pct_change` used as a thin tiebreak. |
| **L** — leader / relative strength | ❌ **out** | needs cross-sectional RS from price history → intersect with `dashboard-screener/minervini.py` (`rs_pct >= 70`) or an RS Rating ≥ 80 elsewhere |
| **M** — market direction | ❌ **out** | index-level timing overlay, applied when the screen is *consumed*, not per-ticker |

**Screen pass rule:** `C_pass AND A_pass AND (N_pass + S_pass + I_pass) >= canslim_min_support` (default 2).
Also emit `canslim_score` = count of C/A/N/S/I passing (0–5), for ranking/reference.

---

## 3. Metric definitions

All field names are `downloadData_v1`'s existing schema unless marked **NEW**.
`q1` = most recent quarter, `q5` = same quarter one year earlier, `y1` = latest
fiscal year, `y4` = 3 years before that.

### 3.1 Values computed at fetch time (`get_financial_data.py`)

Threshold-free. Written to the per-ticker JSON, the full CSV, and SQLite.

| NEW column | definition | source |
|---|---|---|
| `canslim_c_eps_yoy` | `(q1_eps - q5_eps) / q5_eps`; `N/A` unless both > 0 and `q5_eps >= 0` | already have `q1_eps_growth_yoy` — alias/reuse |
| `canslim_c_eps_yoy_src` | `"statement"` if from q1/q5, `"yf_fallback"` if from `earningsQuarterlyGrowth`, `"na"` | — |
| `canslim_c_sales_yoy` | `(q1_revenue - q5_revenue) / q5_revenue`; `N/A` unless both > 0 | **NEW** (needs corrected revenue — §6) |
| `canslim_c_accelerating` | `qh1_eps_growth_yoy > qh2_eps_growth_yoy > qh3_eps_growth_yoy` (existing `eps_growth_accelerating`), OR fallback `q1_eps_growth_yoy > q2_eps_growth_yoy > q3_eps_growth_yoy` | reuse + extend `_calculate_eps_growth` |
| `canslim_c_q1_date`, `canslim_c_q5_date` | `q1_date`, `q5_date` (for the ordering guard) | — |
| `canslim_a_eps_cagr_3y` | `(y1_eps / y4_eps) ** (1/3) - 1`; `N/A` unless both > 0 | **NEW** helper (have the inputs) |
| `canslim_a_ni_cagr_3y` | same on `y1_net_income` / `y4_net_income` (fallback for `a_eps_cagr_3y`) | **NEW** |
| `canslim_a_each_year_up` | `y1_eps > y2_eps AND y2_eps > y3_eps AND y3_eps > y4_eps` (diluted; `N/A` if any missing) | **NEW** |
| `canslim_a_roe` | `y1_roe` (net income / stockholders equity) | already have `y1_roe` |
| `canslim_a_cashflow_ratio` | `y1_cashflow_vs_eps_ratio` (op-cash-flow-per-share ÷ diluted EPS) | already have |
| `canslim_a_sales_cagr_3y` | `(y1_revenue / y4_revenue) ** (1/3) - 1` | **NEW** (needs corrected revenue) |
| `canslim_n_pct_from_high` | `fiftyTwoWeekHighChangePercent` (e.g. `-0.08` = 8% below the 52-wk high) | already in `info` |
| `canslim_s_supply_trend` | `supply_trend` (`shrinking` / `stable` / `diluting`) | already have |
| `canslim_s_debt_equity` | `debtToEquity` (yfinance units — see §7 note) | already in `info` |
| `canslim_s_buyback_active` | `buyback_active` (any `y*_buyback < 0`) | already have |
| `canslim_i_inst_pct` | `heldPercentInstitutions` | already in `info` |
| `canslim_i_holders_direction` | `institutional_holders_avg_pct_change` (mean position Δ of top-10 holders; weak proxy for "sponsorship rising") | already have (needs `collect_sponsorship_detail`) |
| `canslim_years_public` | `yearsSincePublic` (for the optional "young leader" tiebreak) | already have |

### 3.2 Pass/fail computed at filter time (`canslim_screen.py`)

Pure function of the §3.1 values + a threshold dict.

```
# --- C (hard) ---
c_eps_ok    = canslim_c_eps_yoy   >= t.c_min_eps_yoy          (and q1_date > q5_date)
c_sales_ok  = canslim_c_sales_yoy >= t.c_min_sales_yoy        (only if t.c_require_sales)
C_pass      = c_eps_ok AND (c_sales_ok OR NOT t.c_require_sales)

# --- A (hard) ---
a_growth_ok = coalesce(canslim_a_eps_cagr_3y, canslim_a_ni_cagr_3y) >= t.a_min_cagr
a_stable_ok = canslim_a_each_year_up is True                  (only if t.a_require_each_year_up)
a_roe_ok    = canslim_a_roe >= t.a_min_roe
A_pass      = a_growth_ok AND a_roe_ok AND (a_stable_ok OR NOT t.a_require_each_year_up)

# --- support flags ---
N_pass = canslim_n_pct_from_high >= t.n_min_pct_from_high         # e.g. -0.15
S_pass = canslim_s_supply_trend in ('shrinking','stable')
         AND (canslim_s_debt_equity is N/A OR canslim_s_debt_equity <= t.s_max_debt_equity)
I_pass = t.i_min_inst <= canslim_i_inst_pct <= t.i_max_inst

# --- quality flags (reported, not gating) ---
A_cashflow_ok = canslim_a_cashflow_ratio >= t.a_min_cashflow_ratio   # 1.2
A_sales_ok    = canslim_a_sales_cagr_3y  >= t.a_min_sales_cagr

# --- composite + screen ---
canslim_score       = C_pass + A_pass + N_pass + S_pass + I_pass      # 0-5
support_count       = N_pass + S_pass + I_pass                        # 0-3
canslim_screen_pass = C_pass AND A_pass AND support_count >= t.min_support
canslim_rank        = row_number over screen_pass, ordered by canslim_c_eps_yoy desc
                      (O'Neil "bigger is better")
```

### 3.3 N/A policy (confirm — §10)

- **Hard gate (C, A) input is `N/A` → the gate is `False` → ticker excluded.**
  A screen must not pass a stock it can't verify. (This is how
  `dashboard-screener` behaves; `downloadData_v1`'s current composite instead
  shrinks the denominator — we do **not** carry that in.)
- **Support flag input is `N/A` → that flag is `False`** but doesn't
  disqualify (screen needs ≥K of 3, not all 3).
- Every `canslim_*_pass` column also gets a sibling `canslim_*_reason` string
  (`"ok"`, `"below_threshold"`, `"na:q5_eps"`, `"na:no_revenue"`, …) so a
  rejected name is explainable.

---

## 4. Presets

Shipped in code (`canslim_screen.PRESETS`), selected by name, individually
overridable.

| knob | `classic` (O'Neil canonical) | `aggressive` | `relaxed` |
|---|---|---|---|
| `c_min_eps_yoy` | 0.25 | 0.40 | 0.20 |
| `c_min_sales_yoy` | 0.25 | 0.25 | 0.15 |
| `c_require_sales` | true | true | false |
| `c_min_base_eps` | 0.05 | 0.05 | 0.02 |
| `a_min_cagr` | 0.25 | 0.30 | 0.18 |
| `a_require_each_year_up` | true | true | false |
| `a_min_roe` | 0.17 | 0.20 | 0.12 |
| `a_min_cashflow_ratio` | 1.2 | 1.2 | 1.0 |
| `a_min_sales_cagr` | 0.20 | 0.25 | 0.10 |
| `n_min_pct_from_high` | −0.15 | −0.10 | −0.25 |
| `s_max_debt_equity` | 150 | 100 | 300 |
| `i_min_inst` | 0.15 | 0.20 | 0.05 |
| `i_max_inst` | 0.90 | 0.85 | 0.98 |
| `min_support` | 2 | 3 | 1 |

`classic` = the "how O'Neil describes it" default. Every value is a citation to
*How to Make Money in Stocks* (25% C, 25% A, 17% ROE, ~1.2× cash-flow,
15% off-high, "not over-owned"). The others are for A/B-ing strictness.

---

## 5. Config surface

`user_input/user_data.csv` (+ typed in `src/user_defined_data.py`):

```
canslim_screen_enabled,TRUE,Run the CANSLIM O'Neil screen during fin-data processing
canslim_preset,classic,Threshold preset: classic | aggressive | relaxed
# optional per-knob overrides (blank = use preset value):
canslim_c_min_eps_yoy,,
canslim_c_min_sales_yoy,,
canslim_c_require_sales,,
canslim_a_min_cagr,,
canslim_a_require_each_year_up,,
canslim_a_min_roe,,
canslim_a_min_cashflow_ratio,,
canslim_n_min_pct_from_high,,
canslim_s_max_debt_equity,,
canslim_i_min_inst,,
canslim_i_max_inst,,
canslim_min_support,,
```

---

## 6. Dependency on tonight's force-refresh

| can build/test NOW (no revenue) | blocked until corrected revenue (force-refresh, 22:00 2026-08-29) |
|---|---|
| `canslim_screen.py` skeleton + all EPS/ROE/consistency/near-high/supply/sponsorship logic | `canslim_c_sales_yoy`, `canslim_a_sales_cagr_3y` |
| SQLite store + backfill from `financial_data_0_8.csv` (snapshot 2026-08-21) | wiring sales into `C_pass` / `A_sales_ok` |
| preset machinery, config knobs | final preset tuning, validation vs `dashboard-screener` |
| unit tests on synthetic rows | integration run on real corrected data |

So: build the revenue-free 90% now; add ~20 lines of sales logic + tune after
the run.

---

## 7. Storage — SQLite + CSV exports

New file `src/fin_data_store.py`. DB at `data/fin_data/fin_data.db`.

```
table financials
  ticker TEXT, snapshot_date TEXT (YYYY-MM-DD), <~360 raw+derived columns>
  PRIMARY KEY (ticker, snapshot_date)

table canslim_screen
  ticker TEXT, snapshot_date TEXT, preset TEXT,
  canslim_c_eps_yoy, canslim_c_sales_yoy, ... (all §3.1 values),
  C_pass, A_pass, N_pass, S_pass, I_pass,
  A_cashflow_ok, A_sales_ok,
  canslim_score, support_count, canslim_screen_pass, canslim_rank,
  <*_reason strings>
  PRIMARY KEY (ticker, snapshot_date, preset)
```

**Write path** (end of `generate_financial_data_file`, after the list is built):
1. `snapshot_date = today`.
2. `DELETE FROM financials WHERE snapshot_date = ?` then append (idempotent re-run).
3. Same for `canslim_screen` (per preset).

**Backfill** (one-time): load every existing `financial_data_<choice>.csv`,
tag `snapshot_date` from the file's max `last_updated` (or `2026-08-21` for
`_0_8`), insert. Gives ≥2 historical points immediately → the start of the
holder-count history O'Neil's "I" needs.

**CSV exports** (per run, latest snapshot only — backward compat + easy opening):

| file | columns |
|---|---|
| `data/fin_data/financial_data_<choice>.csv` | full dump (unchanged) |
| `data/fin_data/canslim_metrics_<choice>.csv` | **NEW** — `ticker` + all §3.1 values + `canslim_score` + `canslim_screen_pass`. ~35 cols, all numeric/enum, for hand-filtering. |
| `data/fin_data/canslim_screened_<choice>.csv` | **NEW** — `canslim_screen_pass == True` rows, all §3.2 columns, ordered by `canslim_rank` |

Dated CSV snapshots are **not** needed — SQLite is the archive.

Notes / quirks to handle in code:
- `heldPercentInstitutions` can exceed 1.0 (yfinance sums holder categories) →
  `i_max_inst` default 0.90, and clamp the comparison rather than hard-reject.
- `debtToEquity` is yfinance's `(total debt / equity) * 100`-ish → threshold
  expressed in the same units (`150` ≈ 1.5×); `N/A` (debt-free) → S sub-check
  passes, not fails.
- `_safe_growth_rate` / `_safe_ratio` return `N/A` when the denominator ≤ 0 →
  loss-makers and negative-equity names drop out of C/A automatically.
- fiscal-alignment guards: keep `q1_date > q5_date` and require `y1_year >
  y4_year`; a 53-week year or a fiscal-year change → that ticker's C or A
  goes `N/A` (→ excluded) rather than silently wrong.

---

## 8. Code changes, file by file

| file | change |
|---|---|
| `src/get_financial_data.py` | (a) uncomment + rewrite `_calculate_growth_trends` → `q{i}_rev_growth_yoy` (i=1..8), `y{i}_rev_growth_yoy` (i=1..4), `rev_growth_accelerating`; (b) new `_calculate_canslim_values()` → the §3.1 `canslim_*` value columns (no thresholds); call it last in `get_comprehensive_financial_data` and in `_recompute_derived`; (c) leave `_calculate_cansi_score` and all `cansi_*` columns **untouched**. |
| `src/canslim_screen.py` | **NEW.** `PRESETS` dict; `resolve_thresholds(preset, overrides) -> dict`; `apply_screen(df, thresholds) -> df` (adds §3.2 columns, pure, vectorised pandas); `screened(df) -> df` (pass rows, ranked). No I/O. |
| `src/fin_data_store.py` | **NEW.** `open_db()`, `write_snapshot(df, snapshot_date)`, `write_screen(df, snapshot_date, preset)`, `latest_snapshot(choice) -> df`, `history(ticker) -> df`, `backfill_from_csvs()`. |
| `src/process_financial_data.py` | replace the screening `# TODO` stub: load the run's DataFrame → `canslim_screen.apply_screen` → write `canslim_metrics_<choice>.csv` + `canslim_screened_<choice>.csv` → `fin_data_store.write_screen`. Chart top N by `canslim_rank` instead of `cansi_criteria_met`. |
| `src/get_financial_data.py` `generate_financial_data_file` | after building `financial_data_list`: `fin_data_store.write_snapshot(df, today)`. |
| `src/user_defined_data.py` | add `canslim_*` fields + type map entries. |
| `user_input/user_data.csv` | add the §5 rows. |
| `main.py` | thread `canslim_*` config into `financial_config`; pass to `run_financial_data_processing`. |
| `test/test_canslim_screen.py` | **NEW.** synthetic-row unit tests (each letter: pass / below-threshold / N/A), preset resolution, screen composite, N/A policy. |
| `docus/CLI_run.md` | document the new outputs + `canslim_preset`. |

---

## 9. Milestones

**M1 — DONE 2026-08-29 (revenue-free build + unit tests):**
- `src/canslim_screen.py` — `PRESETS` (classic/aggressive/relaxed),
  `resolve_thresholds`, `apply_screen` (pure DF→DF, all C/A/N/S/I values +
  pass/fail + score + rank + `*_reason`), `screened`, `metrics_frame`, a
  `python -m src.canslim_screen --preset X` CLI that re-screens from the DB.
- `src/fin_data_store.py` — SQLite `financials` + `canslim_screen` tables
  keyed by (ticker, snapshot_date[, preset]); `write_snapshot`, `write_screen`,
  `latest_snapshot`, `history`, `backfill_from_csvs`. `.db` git-ignored.
- `src/process_financial_data.py` — screening stub replaced: runs the preset,
  writes `canslim_metrics_<choice>.csv` + `canslim_screened_<choice>.csv`,
  persists to `fin_data.db`, charts by `canslim_rank`.
- `src/get_financial_data.py` `generate_financial_data_file` — writes the run
  as a dated `financials` snapshot into `fin_data.db`.
- config: `canslim_screen_enabled`, `canslim_preset`, 11 blank-able override
  knobs (`opt_float`/`opt_int`/`opt_bool` converters) in `user_data.csv` +
  `user_defined_data.py`.
- `test_canslim_screen.py` — 29 tests green.

**Refinement vs the original plan:** there is **no** `_calculate_canslim_values()`
in `get_financial_data.py`. Every CANSLIM value is derived inside
`apply_screen()` straight from the raw extracted columns (`q1_eps`, `y1_roe`,
`fiftyTwoWeekHighChangePercent`, …), which are already threshold-free and
already at fetch time. Fewer moving parts; `cansi_*` columns untouched.

Sanity on the 2026-08-21 backfill (`classic`): 3 pass (STRL, SLDE, MRX) —
tiny because that snapshot's revenue is still the pre-fix COGS value, so the
sales gate in C rejects ~everything. A `dashboard-screener`-equivalent config
(C=EPS only, A=CAGR only, +I floor) gives 131 vs their 141 — core C/A/I logic
confirmed.

**M2 — after tonight's force-refresh:**
- confirm corrected revenue in the new snapshot (`q1_revenue > q1_net_income`, MSFT 4Q ≈ annual)
- add `canslim_c_sales_yoy` / `canslim_a_sales_cagr_3y`; wire sales into `C_pass`
- run full `--fin-data --fin-process`; produce the 3 CSVs

**M3 — validate + tune:**
- compare `canslim_screened` (`classic`) with `dashboard-screener/leaders_canslim.csv` (141 names, 2026-08-24) — expect a subset (we add sales + consistency + support); explain every drop via `*_reason`
- spot-check known names (NVDA and any classic CANSLIM winners in-universe)
- adjust preset defaults if `classic` is absurdly tight/loose
- write findings into `CANSLIM_METHODOLOGY_AND_IMPLEMENTATIONS.md`

**M4 — handoff:**
- `dashboard-screener`: repoint `config.FIN_DATA_CSV` to `financial_data_0_5.csv` (or read `fin_data.db`); optionally intersect `canslim_screened` with `minervini.py` `in_minervini` for the L.
- document the L/M intersection recipe.

---

## 10. Open confirmations

1. **N/A on a hard gate → exclude** (recommended). Confirm you don't want
   "N/A = pass" anywhere.
2. **Sales is a hard part of C in `classic`** (`c_require_sales = true`).
   Alternative: sales as a support flag only. (Screen reports both regardless,
   so you'll see the effect.)
3. **`each year up` required for A in `classic`** (`a_require_each_year_up =
   true`) — stricter than a bare CAGR. OK?
4. **Cash-flow-vs-EPS (1.2×) is a *quality flag*, not a hard A gate.** OK, or
   make it hard in `classic`?
5. **`canslim_score` counts C/A/N/S/I equally (0–5)** for ranking. Fine, or
   weight C/A heavier?
6. **SQLite lives at `data/fin_data/fin_data.db`**, committed? (recommend: DB
   file **git-ignored**, schema + backfill script committed.)
7. **Ranking key = `canslim_c_eps_yoy` desc.** O'Neil-ish. Alternative:
   composite of C-magnitude + A-magnitude.

## 11. Risks

- **Universe coverage:** ~4,000 tickers, meaningful `N/A` tail (thin history,
  delisted, foreign, recent IPO). `classic` may return a small list — that's
  correct behaviour, not a bug; `relaxed` exists for wider nets.
- **yfinance data drift:** row names / `info` keys change between yfinance
  versions. The exact-name lookups (`_get_row_first_of`) and `info.get(...,
  'N/A')` degrade to `N/A` rather than crash, but silent coverage drops are
  possible — M3 validation + the `*_reason` columns are the guardrail.
- **`dashboard-screener` coupling:** it currently hard-codes
  `financial_data_0_8.csv`. Changing the export name/schema without repointing
  it breaks that screen. M4 covers it; coordinate the switch.
- **Revenue still wrong on non-refreshed tickers** between now and the moment
  the force-refresh (or per-ticker earnings-triggered `full`) touches each one.
  `canslim_c_sales_yoy` should be `N/A` (not a wrong number) when the revenue
  fields look stale — add a guard: if `q1_revenue < q1_net_income`, treat
  revenue as unreliable → `N/A` + `reason="na:revenue_suspect"`.
- **Holder-count trend** stays unavailable until the dated snapshots
  accumulate several quarters; `canslim_i_holders_direction` is a stopgap.
