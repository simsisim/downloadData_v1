"""
CANSLIM O'Neil fundamental screen — a pure DataFrame -> DataFrame transform.

Scope (see docus/CANSLIM_METHODOLOGY_AND_IMPLEMENTATIONS.md for the full rationale):
  C, A  -> HARD gates (the letters O'Neil defines with numbers, and where the
           fundamental data is complete)
  N, S, I -> scored SUPPORT flags. The screen requires C AND A AND
           >= `min_support` of {N, S, I}.
  L (relative strength), M (market direction) -> OUT of scope here; they need
           price / index data. Intersect this screen's output with a price-based
           leader list (e.g. dashboard-screener/src/leaders/minervini.py) for L,
           and only consume the list while the market is in a confirmed uptrend
           for M.

Design: no thresholds are baked upstream. Every value below is derived from the
raw extracted fields already in financial_data_<choice>.csv / the fin_data.db
`financials` table. Re-run `apply_screen()` with a different preset to re-screen
in seconds — no re-fetch, no recompute of the snapshot.

N/A policy (confirmed 2026-08-29):
  - a HARD-gate input that is N/A  -> that gate is False -> ticker excluded
    (a screen must never pass a stock it cannot verify)
  - a SUPPORT-flag input that is N/A -> that flag is False, but the ticker can
    still pass via the other support letters (needs >= K of 3, not all 3)
"""
from __future__ import annotations

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# Presets. `classic` = William O'Neil, "How to Make Money in Stocks" canonical
# values (25% C, 25% A, 17% ROE, ~1.2x cash-flow-vs-EPS, within 15% of the
# 52-week high, institutions present but not over-owned). `aggressive` /
# `relaxed` are for A/B-ing how strict the net is. Every key is overridable
# per-run from user_data.csv.
# ---------------------------------------------------------------------------
PRESETS: dict[str, dict] = {
    "classic": {
        "c_min_eps_yoy": 0.25,          # C: latest quarter diluted EPS YoY
        "c_min_sales_yoy": 0.25,        # C: latest quarter revenue YoY
        "c_require_sales": True,        # C: sales YoY is a hard part of C
        "c_min_base_eps": 0.05,        # C: year-ago quarter EPS floor (kills
                                       #    near-zero-base % artifacts)
        "a_min_cagr": 0.25,            # A: 3-year diluted EPS CAGR
        "a_require_each_year_up": True, # A: EPS up every year y4->y1
        "a_min_roe": 0.17,            # A: latest fiscal-year ROE
        "a_min_cashflow_ratio": 1.2,   # A (quality flag): op-CF-per-share / EPS
        "a_min_sales_cagr": 0.20,      # A (quality flag): 3-year revenue CAGR
        "n_min_pct_from_high": -0.15,   # N: within 15% of the 52-week high
        "s_max_debt_equity": 150.0,     # S: debtToEquity (yfinance ~*100 units)
        "i_min_inst": 0.15,           # I: institutional ownership floor
        "i_max_inst": 0.90,           # I: over-ownership ceiling
        "min_support": 2,             # screen: >= N of {N, S, I} must pass
    },
    "aggressive": {
        "c_min_eps_yoy": 0.40,
        "c_min_sales_yoy": 0.25,
        "c_require_sales": True,
        "c_min_base_eps": 0.05,
        "a_min_cagr": 0.30,
        "a_require_each_year_up": True,
        "a_min_roe": 0.20,
        "a_min_cashflow_ratio": 1.2,
        "a_min_sales_cagr": 0.25,
        "n_min_pct_from_high": -0.10,
        "s_max_debt_equity": 100.0,
        "i_min_inst": 0.20,
        "i_max_inst": 0.85,
        "min_support": 3,
    },
    "relaxed": {
        "c_min_eps_yoy": 0.20,
        "c_min_sales_yoy": 0.15,
        "c_require_sales": False,
        "c_min_base_eps": 0.02,
        "a_min_cagr": 0.18,
        "a_require_each_year_up": False,
        "a_min_roe": 0.12,
        "a_min_cashflow_ratio": 1.0,
        "a_min_sales_cagr": 0.10,
        "n_min_pct_from_high": -0.25,
        "s_max_debt_equity": 300.0,
        "i_min_inst": 0.05,
        "i_max_inst": 0.98,
        "min_support": 1,
    },
}

# Raw columns apply_screen() reads. Missing ones are tolerated (treated as all
# N/A) but logged by check_inputs().
REQUIRED_INPUT_COLUMNS = [
    "ticker",
    "q1_eps", "q5_eps", "q1_date", "q5_date", "q1_net_income",
    "earningsQuarterlyGrowth", "q1_revenue", "q5_revenue",
    "q1_eps_growth_yoy", "q2_eps_growth_yoy", "q3_eps_growth_yoy",
    "eps_growth_accelerating",
    "y1_eps", "y2_eps", "y3_eps", "y4_eps", "y1_net_income", "y4_net_income",
    "y1_revenue", "y4_revenue", "y1_roe", "y1_cashflow_vs_eps_ratio",
    "fiftyTwoWeekHighChangePercent", "supply_trend", "debtToEquity",
    "heldPercentInstitutions",
]

# The value/flag columns apply_screen() adds. `canslim_metrics_<choice>.csv`
# is (ticker + VALUE_COLUMNS + score/support/screen_pass).
VALUE_COLUMNS = [
    "canslim_c_eps_yoy", "canslim_c_eps_yoy_src", "canslim_c_sales_yoy",
    "canslim_c_accelerating",
    "canslim_a_eps_cagr_3y", "canslim_a_each_year_up", "canslim_a_roe",
    "canslim_a_cashflow_ratio", "canslim_a_sales_cagr_3y",
    "canslim_n_pct_from_high", "canslim_s_supply_trend", "canslim_s_debt_equity",
    "canslim_i_inst_pct",
]


def _as_bool(v) -> bool:
    if isinstance(v, bool):
        return v
    return str(v).strip().lower() in ("1", "true", "yes", "y", "t")


def resolve_thresholds(preset: str = "classic", overrides: dict | None = None) -> dict:
    """
    Start from a named preset, apply per-key overrides (blank / None ignored so
    an empty user_data.csv cell means "use the preset value"). Override values
    are coerced to the preset value's type.
    """
    if preset not in PRESETS:
        raise ValueError(f"unknown preset {preset!r}; choose from {list(PRESETS)}")
    t = dict(PRESETS[preset])
    for key, val in (overrides or {}).items():
        if val is None or (isinstance(val, str) and val.strip() == ""):
            continue
        if key not in t:
            raise ValueError(f"unknown threshold override {key!r}")
        default = t[key]
        if isinstance(default, bool):
            t[key] = _as_bool(val)
        elif isinstance(default, int):
            t[key] = int(float(val))
        else:
            t[key] = float(val)
    return t


def check_inputs(df: pd.DataFrame) -> list[str]:
    """Return the REQUIRED_INPUT_COLUMNS missing from df (for logging)."""
    return [c for c in REQUIRED_INPUT_COLUMNS if c not in df.columns]


def _num(df: pd.DataFrame, col: str) -> pd.Series:
    """Numeric view of a column, or an all-NaN Series if the column is absent."""
    if col not in df.columns:
        return pd.Series(np.nan, index=df.index, dtype="float64")
    return pd.to_numeric(df[col], errors="coerce")


def _yoy(latest: pd.Series, prior: pd.Series) -> pd.Series:
    """
    YoY growth as a fraction (0.25 = +25%). NaN unless BOTH periods are > 0 —
    a percentage across zero / a negative base is not meaningful (O'Neil's own
    convention for a clean C or A pass).
    """
    out = (latest / prior.replace(0, np.nan)) - 1.0
    out[~((latest > 0) & (prior > 0))] = np.nan
    return out


def _cagr(latest: pd.Series, base: pd.Series, n_years: int) -> pd.Series:
    """n-year CAGR as a fraction. NaN unless both endpoints are > 0."""
    out = (latest / base.replace(0, np.nan)) ** (1.0 / n_years) - 1.0
    out[~((latest > 0) & (base > 0))] = np.nan
    return out


def _tribool(cond: pd.Series, valid: pd.Series | None = None) -> pd.Series:
    """
    A nullable-boolean Series: `cond` where `valid` (default: cond.notna()),
    <NA> elsewhere. Keeps three-state logic (pass / fail / unknown) without the
    object-dtype .fillna downcast warnings.
    """
    b = cond.astype("boolean")
    if valid is not None:
        b = b.where(valid.astype("boolean").fillna(False), other=pd.NA)
    return b


def apply_screen(
    df: pd.DataFrame,
    thresholds: dict | None = None,
    preset: str = "classic",
    overrides: dict | None = None,
) -> pd.DataFrame:
    """
    Compute the CANSLIM values, the per-letter pass/fail, the composite score
    and the screen membership for every row of `df`.

    Returns a new DataFrame aligned to df.index with:
      - VALUE_COLUMNS (threshold-free metrics)
      - canslim_C_pass .. canslim_I_pass (bool)
      - canslim_A_cashflow_ok, canslim_A_sales_ok (bool quality flags)
      - canslim_score (0-5), canslim_support_count (0-3)
      - canslim_screen_pass (bool), canslim_rank (Int64, only for passers)
      - canslim_c_reason, canslim_a_reason (short strings, for triage)
      - canslim_preset (the preset name used)
    """
    t = thresholds or resolve_thresholds(preset, overrides)
    idx = df.index

    # ================= C — current quarterly EPS + sales =================
    q1e, q5e = _num(df, "q1_eps"), _num(df, "q5_eps")
    c_eps_yoy = _yoy(q1e, q5e)

    # base-EPS floor: a $0.001 -> $0.30 jump is +30,000%, not O'Neil's
    # "meaningful improvement"
    below_base = q5e < t["c_min_base_eps"]
    c_eps_yoy = c_eps_yoy.mask(below_base.fillna(False))

    # fiscal-alignment guard: q1 must be a MORE RECENT quarter than q5
    d1 = pd.to_datetime(df["q1_date"], errors="coerce") if "q1_date" in df else pd.Series(pd.NaT, index=idx)
    d5 = pd.to_datetime(df["q5_date"], errors="coerce") if "q5_date" in df else pd.Series(pd.NaT, index=idx)
    bad_order = d1.notna() & d5.notna() & (d1 <= d5)
    c_eps_yoy = c_eps_yoy.mask(bad_order)

    # fallback to yfinance's own prior-quarter YoY field when the statement
    # pair is unusable
    eqg = _num(df, "earningsQuarterlyGrowth")
    c_eps_src = pd.Series(
        np.where(c_eps_yoy.notna(), "statement",
                 np.where(eqg.notna(), "yf_fallback", "na")),
        index=idx, dtype="object",
    )
    c_eps_yoy = c_eps_yoy.fillna(eqg)

    # sales YoY — guard against the stale-revenue extraction bug: if the stored
    # "revenue" is below net income the row is pre-fix COGS, not revenue
    q1r, q5r = _num(df, "q1_revenue"), _num(df, "q5_revenue")
    q1ni = _num(df, "q1_net_income")
    rev_suspect = q1r.notna() & q1ni.notna() & (q1r < q1ni)
    c_sales_yoy = _yoy(q1r, q5r).mask(rev_suspect)

    c_accel = _acceleration_flag(df)

    c_eps_ok = c_eps_yoy >= t["c_min_eps_yoy"]
    c_sales_ok = c_sales_yoy >= t["c_min_sales_yoy"]
    if t["c_require_sales"]:
        C_pass = c_eps_ok.fillna(False) & c_sales_ok.fillna(False)
    else:
        C_pass = c_eps_ok.fillna(False)

    c_reason = pd.Series("ok", index=idx, dtype="object")
    c_reason = c_reason.mask(~c_eps_ok.fillna(False) & c_eps_yoy.notna(), "eps_below_threshold")
    c_reason = c_reason.mask(c_eps_yoy.isna(), "eps_na")
    c_reason = c_reason.mask(bad_order, "bad_quarter_order")
    if t["c_require_sales"]:
        c_reason = c_reason.mask(C_pass.eq(False) & c_eps_ok.fillna(False) & rev_suspect, "revenue_suspect")
        c_reason = c_reason.mask(C_pass.eq(False) & c_eps_ok.fillna(False) & c_sales_yoy.isna() & ~rev_suspect, "sales_na")
        c_reason = c_reason.mask(C_pass.eq(False) & c_eps_ok.fillna(False) & (c_sales_yoy < t["c_min_sales_yoy"]), "sales_below_threshold")
    c_reason = c_reason.mask(C_pass, "ok")

    # ================= A — annual EPS growth + quality =================
    a_eps_cagr = _cagr(_num(df, "y1_eps"), _num(df, "y4_eps"), 3)
    a_ni_cagr = _cagr(_num(df, "y1_net_income"), _num(df, "y4_net_income"), 3)
    a_cagr = a_eps_cagr.fillna(a_ni_cagr)

    y1, y2, y3, y4 = (_num(df, f"y{i}_eps") for i in (1, 2, 3, 4))
    have_all_years = y1.notna() & y2.notna() & y3.notna() & y4.notna()
    a_each_up = _tribool((y1 > y2) & (y2 > y3) & (y3 > y4), have_all_years)

    a_roe = _num(df, "y1_roe")
    a_cfr = _num(df, "y1_cashflow_vs_eps_ratio")
    a_sales_cagr = _cagr(_num(df, "y1_revenue"), _num(df, "y4_revenue"), 3)

    a_growth_ok = a_cagr >= t["a_min_cagr"]
    a_roe_ok = a_roe >= t["a_min_roe"]
    A_pass = a_growth_ok.fillna(False) & a_roe_ok.fillna(False)
    if t["a_require_each_year_up"]:
        A_pass = A_pass & a_each_up.fillna(False).astype(bool)

    a_reason = pd.Series("ok", index=idx, dtype="object")
    a_growth_ok_f = a_growth_ok.fillna(False)
    a_roe_ok_f = a_roe_ok.fillna(False)
    a_each_up_isna = a_each_up.isna()
    a_each_up_false = a_each_up.fillna(False).astype(bool).eq(False) & ~a_each_up_isna
    a_reason = a_reason.mask(a_cagr.isna(), "growth_na")
    a_reason = a_reason.mask(a_cagr.notna() & ~a_growth_ok_f, "growth_below_threshold")
    a_reason = a_reason.mask(A_pass.eq(False) & a_growth_ok_f & a_roe.isna(), "roe_na")
    a_reason = a_reason.mask(A_pass.eq(False) & a_growth_ok_f & a_roe.notna() & ~a_roe_ok_f, "roe_below_threshold")
    if t["a_require_each_year_up"]:
        a_reason = a_reason.mask(A_pass.eq(False) & a_growth_ok_f & a_roe_ok_f & a_each_up_isna, "consistency_na")
        a_reason = a_reason.mask(A_pass.eq(False) & a_growth_ok_f & a_roe_ok_f & a_each_up_false, "not_each_year_up")
    a_reason = a_reason.mask(A_pass, "ok")

    a_cashflow_ok = (a_cfr >= t["a_min_cashflow_ratio"]).fillna(False)
    a_sales_ok = (a_sales_cagr >= t["a_min_sales_cagr"]).fillna(False)

    # ================= N — near a new price high =================
    n_pct = _num(df, "fiftyTwoWeekHighChangePercent")
    N_pass = (n_pct >= t["n_min_pct_from_high"]).fillna(False)

    # ================= S — supply (share count + debt) =================
    if "supply_trend" in df.columns:
        supply_trend = df["supply_trend"].astype("object")
    else:
        supply_trend = pd.Series(np.nan, index=idx, dtype="object")
    de = _num(df, "debtToEquity")
    s_supply_ok = supply_trend.isin(["shrinking", "stable"])
    s_debt_ok = de.isna() | (de <= t["s_max_debt_equity"])   # debt-free (N/A) is fine
    S_pass = (s_supply_ok & s_debt_ok).fillna(False)

    # ================= I — institutional sponsorship (level) =================
    inst = _num(df, "heldPercentInstitutions")
    I_pass = ((inst >= t["i_min_inst"]) & (inst <= t["i_max_inst"])).fillna(False)

    # ================= composite + screen =================
    score = (C_pass.astype(int) + A_pass.astype(int) + N_pass.astype(int)
             + S_pass.astype(int) + I_pass.astype(int))
    support = N_pass.astype(int) + S_pass.astype(int) + I_pass.astype(int)
    screen_pass = C_pass & A_pass & (support >= t["min_support"])

    out = pd.DataFrame(index=idx)
    out["ticker"] = df["ticker"] if "ticker" in df.columns else idx
    out["canslim_c_eps_yoy"] = c_eps_yoy.round(4)
    out["canslim_c_eps_yoy_src"] = c_eps_src
    out["canslim_c_sales_yoy"] = c_sales_yoy.round(4)
    out["canslim_c_accelerating"] = c_accel
    out["canslim_a_eps_cagr_3y"] = a_cagr.round(4)
    out["canslim_a_each_year_up"] = a_each_up
    out["canslim_a_roe"] = a_roe.round(4)
    out["canslim_a_cashflow_ratio"] = a_cfr.round(3)
    out["canslim_a_sales_cagr_3y"] = a_sales_cagr.round(4)
    out["canslim_n_pct_from_high"] = n_pct.round(4)
    out["canslim_s_supply_trend"] = supply_trend
    out["canslim_s_debt_equity"] = de.round(1)
    out["canslim_i_inst_pct"] = inst.round(4)
    out["canslim_C_pass"] = C_pass
    out["canslim_A_pass"] = A_pass
    out["canslim_N_pass"] = N_pass
    out["canslim_S_pass"] = S_pass
    out["canslim_I_pass"] = I_pass
    out["canslim_A_cashflow_ok"] = a_cashflow_ok
    out["canslim_A_sales_ok"] = a_sales_ok
    out["canslim_score"] = score.astype("int64")
    out["canslim_support_count"] = support.astype("int64")
    out["canslim_screen_pass"] = screen_pass
    out["canslim_c_reason"] = c_reason
    out["canslim_a_reason"] = a_reason
    out["canslim_preset"] = preset

    out["canslim_rank"] = pd.Series(pd.NA, index=idx, dtype="Int64")
    if screen_pass.any():
        rank = (out.loc[screen_pass, "canslim_c_eps_yoy"]
                .rank(ascending=False, method="first"))
        out.loc[screen_pass, "canslim_rank"] = rank.astype("Int64")
    return out


def _acceleration_flag(df: pd.DataFrame) -> pd.Series:
    """
    C acceleration (nullable boolean): is YoY EPS growth rising over the last 3
    comparable quarters? Prefer the deep-history flag already computed by
    get_financial_data.py (`eps_growth_accelerating`, qh-based); fall back to
    the statement q1..q3 YoY series. Reported, not gated.
    """
    idx = df.index

    def _parse(v):
        if v is True or (isinstance(v, str) and v.strip().lower() == "true"):
            return True
        if v is False or (isinstance(v, str) and v.strip().lower() == "false"):
            return False
        return pd.NA

    if "eps_growth_accelerating" in df.columns:
        acc = pd.array([_parse(v) for v in df["eps_growth_accelerating"]], dtype="boolean")
        acc = pd.Series(acc, index=idx)
    else:
        acc = pd.Series(pd.NA, index=idx, dtype="boolean")

    g1, g2, g3 = (_num(df, f"q{i}_eps_growth_yoy") for i in (1, 2, 3))
    stmt = _tribool((g1 > g2) & (g2 > g3), g1.notna() & g2.notna() & g3.notna())
    return acc.fillna(stmt)


def screened(screen_df: pd.DataFrame) -> pd.DataFrame:
    """The passing rows, ordered by canslim_rank."""
    passed = screen_df[screen_df["canslim_screen_pass"] == True].copy()  # noqa: E712
    return passed.sort_values("canslim_rank", na_position="last")


def metrics_frame(screen_df: pd.DataFrame) -> pd.DataFrame:
    """The clean value/flag table for hand-filtering (canslim_metrics_<choice>.csv)."""
    cols = (["ticker"] + VALUE_COLUMNS
            + ["canslim_C_pass", "canslim_A_pass", "canslim_N_pass",
               "canslim_S_pass", "canslim_I_pass", "canslim_score",
               "canslim_support_count", "canslim_screen_pass",
               "canslim_c_reason", "canslim_a_reason", "canslim_preset"])
    return screen_df[[c for c in cols if c in screen_df.columns]].copy()


# --------------------------------------------------------------------------
# CLI: re-screen straight from the SQLite snapshot without a fetch run.
#   python -m src.canslim_screen --preset aggressive
# --------------------------------------------------------------------------
def _main(argv=None):
    import argparse
    from src import fin_data_store

    p = argparse.ArgumentParser(description="Re-run the CANSLIM screen from fin_data.db")
    p.add_argument("--preset", default="classic", choices=list(PRESETS))
    p.add_argument("--snapshot-date", default=None,
                   help="YYYY-MM-DD; default = latest snapshot in the DB")
    p.add_argument("--out", default=None, help="write screened CSV here")
    args = p.parse_args(argv)

    conn = fin_data_store.open_db()
    try:
        df = fin_data_store.latest_snapshot(conn) if not args.snapshot_date \
            else fin_data_store.snapshot(conn, args.snapshot_date)
    finally:
        conn.close()
    if df is None or df.empty:
        print("No snapshot in fin_data.db — run --fin-data first (or backfill).")
        return

    missing = check_inputs(df)
    if missing:
        print(f"⚠️  snapshot is missing {len(missing)} expected column(s): {missing}")

    scr = apply_screen(df, preset=args.preset)
    passers = screened(scr)
    print(f"{args.preset}: {len(passers)}/{len(scr)} tickers pass "
          f"(C {int(scr['canslim_C_pass'].sum())}, A {int(scr['canslim_A_pass'].sum())}, "
          f"N {int(scr['canslim_N_pass'].sum())}, S {int(scr['canslim_S_pass'].sum())}, "
          f"I {int(scr['canslim_I_pass'].sum())})")
    print(passers[["ticker", "canslim_c_eps_yoy", "canslim_a_eps_cagr_3y",
                   "canslim_a_roe", "canslim_score"]].head(25).to_string(index=False))
    if args.out:
        passers.to_csv(args.out, index=False)
        print(f"wrote {args.out}")


if __name__ == "__main__":
    _main()
