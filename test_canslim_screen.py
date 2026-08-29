"""
Unit tests for src/canslim_screen.py — synthetic rows, no network, no CSV.

Run: python -m pytest test_canslim_screen.py -q
"""
import numpy as np
import pandas as pd
import pytest

from src import canslim_screen as cs


# --------------------------------------------------------------------------
# Row builders
# --------------------------------------------------------------------------
def _base_row():
    """A row that PASSES classic on every letter. Tests mutate one field."""
    return {
        "ticker": "TEST",
        # C: q1_eps 1.00 vs q5_eps 0.50 -> +100% YoY, base ok, order ok
        "q1_eps": 1.00, "q5_eps": 0.50,
        "q1_date": "2026-06-30", "q5_date": "2025-06-30",
        "q1_net_income": 20.0,          # < q1_revenue (realistic margin)
        "earningsQuarterlyGrowth": 0.90,
        # C sales: q1_revenue 130 vs q5_revenue 100 -> +30%
        "q1_revenue": 130.0, "q5_revenue": 100.0,
        "q1_eps_growth_yoy": 1.0, "q2_eps_growth_yoy": 0.7, "q3_eps_growth_yoy": 0.5,
        "eps_growth_accelerating": True,
        # A: EPS 2.0 / 1.5 / 1.2 / 1.0 -> CAGR (2/1)^(1/3)-1 = 26%, each year up
        "y1_eps": 2.0, "y2_eps": 1.5, "y3_eps": 1.2, "y4_eps": 1.0,
        "y1_net_income": 40.0, "y4_net_income": 20.0,
        "y1_revenue": 200.0, "y4_revenue": 100.0,
        "y1_roe": 0.25,
        "y1_cashflow_vs_eps_ratio": 1.4,
        # N: 8% below the 52-wk high
        "fiftyTwoWeekHighChangePercent": -0.08,
        # S: shrinking share count, low debt
        "supply_trend": "shrinking", "debtToEquity": 40.0,
        # I: 60% institutional
        "heldPercentInstitutions": 0.60,
    }


def _screen_one(row, preset="classic", overrides=None):
    df = pd.DataFrame([row])
    return cs.apply_screen(df, preset=preset, overrides=overrides).iloc[0]


# --------------------------------------------------------------------------
# Preset / threshold resolution
# --------------------------------------------------------------------------
def test_presets_exist():
    assert set(cs.PRESETS) == {"classic", "aggressive", "relaxed"}


def test_resolve_unknown_preset():
    with pytest.raises(ValueError):
        cs.resolve_thresholds("nope")


def test_resolve_overrides_typed_and_blanks_ignored():
    t = cs.resolve_thresholds("classic", {
        "c_min_eps_yoy": "0.40",       # str -> float
        "a_require_each_year_up": "false",  # str -> bool
        "min_support": "3",            # str -> int
        "a_min_roe": "",              # blank -> keep preset
        "n_min_pct_from_high": None,   # None -> keep preset
    })
    assert t["c_min_eps_yoy"] == 0.40
    assert t["a_require_each_year_up"] is False
    assert t["min_support"] == 3 and isinstance(t["min_support"], int)
    assert t["a_min_roe"] == cs.PRESETS["classic"]["a_min_roe"]
    assert t["n_min_pct_from_high"] == cs.PRESETS["classic"]["n_min_pct_from_high"]


def test_resolve_unknown_override_key():
    with pytest.raises(ValueError):
        cs.resolve_thresholds("classic", {"bogus": 1})


# --------------------------------------------------------------------------
# Happy path
# --------------------------------------------------------------------------
def test_base_row_passes_classic():
    r = _screen_one(_base_row())
    assert bool(r["canslim_C_pass"]) and bool(r["canslim_A_pass"])
    assert bool(r["canslim_N_pass"]) and bool(r["canslim_S_pass"]) and bool(r["canslim_I_pass"])
    assert r["canslim_score"] == 5
    assert bool(r["canslim_screen_pass"]) is True
    assert r["canslim_rank"] == 1
    assert r["canslim_c_reason"] == "ok" and r["canslim_a_reason"] == "ok"


# --------------------------------------------------------------------------
# C
# --------------------------------------------------------------------------
def test_c_eps_below_threshold_fails():
    row = _base_row()
    row["q1_eps"], row["q5_eps"] = 0.55, 0.50   # +10% YoY
    row["earningsQuarterlyGrowth"] = 0.10
    r = _screen_one(row)
    assert not bool(r["canslim_C_pass"])
    assert r["canslim_c_reason"] == "eps_below_threshold"


def test_c_base_eps_floor_blocks_near_zero_base():
    row = _base_row()
    row["q1_eps"], row["q5_eps"] = 5.00, 0.01   # +49,900% but base < $0.05
    row["earningsQuarterlyGrowth"] = np.nan
    r = _screen_one(row)
    assert pd.isna(r["canslim_c_eps_yoy"])
    assert r["canslim_c_reason"] == "eps_na"
    assert not bool(r["canslim_C_pass"])


def test_c_extreme_yoy_rejected():
    row = _base_row()
    row["q1_eps"], row["q5_eps"] = 60.0, 0.10   # +59,900% -> near-zero-base artifact
    row["earningsQuarterlyGrowth"] = np.nan
    r = _screen_one(row)
    assert pd.isna(r["canslim_c_eps_yoy"])
    assert r["canslim_c_reason"] == "eps_yoy_extreme"
    assert not bool(r["canslim_C_pass"])


def test_c_bad_quarter_order_rejected():
    row = _base_row()
    row["q1_date"], row["q5_date"] = "2025-06-30", "2026-06-30"  # q1 older than q5
    row["earningsQuarterlyGrowth"] = np.nan
    r = _screen_one(row)
    assert r["canslim_c_reason"] == "bad_quarter_order"
    assert not bool(r["canslim_C_pass"])


def test_c_falls_back_to_earnings_quarterly_growth():
    row = _base_row()
    row["q5_eps"] = -0.10           # negative base -> statement YoY unusable
    row["earningsQuarterlyGrowth"] = 0.40
    r = _screen_one(row)
    assert r["canslim_c_eps_yoy_src"] == "yf_fallback"
    assert r["canslim_c_eps_yoy"] == pytest.approx(0.40)
    assert bool(r["canslim_C_pass"])


def test_c_sales_hard_gate_in_classic():
    row = _base_row()
    row["q1_revenue"], row["q5_revenue"] = 105.0, 100.0   # +5% sales
    r = _screen_one(row)
    assert not bool(r["canslim_C_pass"])
    assert r["canslim_c_reason"] == "sales_below_threshold"


def test_c_sales_not_required_in_relaxed():
    row = _base_row()
    row["q1_revenue"], row["q5_revenue"] = 105.0, 100.0
    r = _screen_one(row, preset="relaxed")
    assert bool(r["canslim_C_pass"])   # relaxed: c_require_sales = False


def test_c_revenue_suspect_when_revenue_below_net_income():
    row = _base_row()
    row["q1_revenue"] = 15.0           # < q1_net_income 20 -> pre-fix COGS row
    r = _screen_one(row)
    assert pd.isna(r["canslim_c_sales_yoy"])
    assert r["canslim_c_reason"] == "revenue_suspect"
    assert not bool(r["canslim_C_pass"])


# --------------------------------------------------------------------------
# A
# --------------------------------------------------------------------------
def test_a_cagr_below_threshold():
    row = _base_row()
    row["y1_eps"], row["y4_eps"] = 1.10, 1.00   # ~3.2%/yr
    row["y1_net_income"], row["y4_net_income"] = 110.0, 100.0
    r = _screen_one(row)
    assert not bool(r["canslim_A_pass"])
    assert r["canslim_a_reason"] == "growth_below_threshold"


def test_a_net_income_cagr_fallback():
    row = _base_row()
    row["y1_net_income"], row["y4_net_income"] = 2_000.0, 1_000.0  # +26%/yr
    row["y1_eps"] = np.nan
    row["y4_eps"] = np.nan                        # EPS CAGR unusable -> NI fallback
    r = _screen_one(row)
    expected = (2_000 / 1_000) ** (1 / 3) - 1
    assert r["canslim_a_eps_cagr_3y"] == pytest.approx(expected, abs=1e-4)


def test_a_roe_below_threshold():
    row = _base_row()
    row["y1_roe"] = 0.10
    r = _screen_one(row)
    assert not bool(r["canslim_A_pass"])
    assert r["canslim_a_reason"] == "roe_below_threshold"


def test_a_each_year_up_required_in_classic():
    row = _base_row()
    row["y2_eps"], row["y3_eps"] = 1.0, 1.3      # y2 < y3 -> not monotonic
    r = _screen_one(row)
    assert not bool(r["canslim_A_pass"])
    assert r["canslim_a_reason"] == "not_each_year_up"


def test_a_each_year_up_not_required_in_relaxed():
    row = _base_row()
    row["y2_eps"], row["y3_eps"] = 1.0, 1.3
    r = _screen_one(row, preset="relaxed")
    # relaxed a_min_cagr 0.18, a_min_roe 0.12, no consistency
    assert bool(r["canslim_A_pass"])


def test_a_roe_falls_back_to_info_return_on_equity():
    row = _base_row()
    row["y1_roe"] = np.nan
    row["returnOnEquity"] = 0.22
    r = _screen_one(row)
    assert bool(r["canslim_A_pass"])


def test_a_roe_waived_for_buyback_negative_equity():
    row = _base_row()
    row["y1_roe"] = np.nan
    row["returnOnEquity"] = np.nan
    row["y1_net_income"] = 5_000.0            # profitable
    row["y1_stockholders_equity"] = -2_000.0  # negative book equity from buybacks
    r = _screen_one(row)
    assert bool(r["canslim_A_pass"])          # ROE sub-check waived
    assert r["canslim_a_reason"] == "ok"


def test_a_roe_not_waived_when_unprofitable():
    row = _base_row()
    row["y1_roe"] = np.nan
    row["returnOnEquity"] = np.nan
    row["y1_net_income"] = -100.0             # losing money
    row["y1_stockholders_equity"] = -2_000.0
    r = _screen_one(row)
    assert not bool(r["canslim_A_pass"])
    assert r["canslim_a_reason"] == "roe_na"


def test_a_cashflow_is_flag_not_gate():
    row = _base_row()
    row["y1_cashflow_vs_eps_ratio"] = 0.5       # fails the quality flag
    r = _screen_one(row)
    assert bool(r["canslim_A_pass"])            # still passes A (hard gate)
    assert not bool(r["canslim_A_cashflow_ok"])


# --------------------------------------------------------------------------
# N / S / I  + support logic
# --------------------------------------------------------------------------
def test_n_far_from_high_fails():
    row = _base_row()
    row["fiftyTwoWeekHighChangePercent"] = -0.30
    r = _screen_one(row)
    assert not bool(r["canslim_N_pass"])


def test_s_diluting_fails():
    row = _base_row()
    row["supply_trend"] = "diluting"
    r = _screen_one(row)
    assert not bool(r["canslim_S_pass"])


def test_s_debt_free_na_still_passes():
    row = _base_row()
    row["debtToEquity"] = np.nan               # debt-free -> not a fail
    r = _screen_one(row)
    assert bool(r["canslim_S_pass"])


def test_s_high_debt_fails():
    row = _base_row()
    row["debtToEquity"] = 250.0
    r = _screen_one(row)
    assert not bool(r["canslim_S_pass"])


def test_i_over_owned_fails_classic():
    row = _base_row()
    row["heldPercentInstitutions"] = 0.95
    r = _screen_one(row)
    assert not bool(r["canslim_I_pass"])


def test_i_too_low_fails():
    row = _base_row()
    row["heldPercentInstitutions"] = 0.05
    r = _screen_one(row)
    assert not bool(r["canslim_I_pass"])


def test_support_threshold_gates_screen():
    row = _base_row()
    # break N and S -> only I passes -> support_count 1 < min_support 2
    row["fiftyTwoWeekHighChangePercent"] = -0.40
    row["supply_trend"] = "diluting"
    r = _screen_one(row)
    assert bool(r["canslim_C_pass"]) and bool(r["canslim_A_pass"])
    assert r["canslim_support_count"] == 1
    assert not bool(r["canslim_screen_pass"])


# --------------------------------------------------------------------------
# N/A policy: N/A on a hard gate -> excluded (never passed)
# --------------------------------------------------------------------------
def test_na_on_hard_gate_excludes():
    row = _base_row()
    for k in ("q1_eps", "q5_eps", "earningsQuarterlyGrowth"):
        row[k] = np.nan
    r = _screen_one(row)
    assert pd.isna(r["canslim_c_eps_yoy"])
    assert bool(r["canslim_C_pass"]) is False
    assert bool(r["canslim_screen_pass"]) is False


def test_missing_columns_tolerated():
    # only the bare minimum columns present
    df = pd.DataFrame([{"ticker": "X", "q1_eps": 1.0, "q5_eps": 0.5,
                        "y1_eps": 2.0, "y4_eps": 1.0}])
    out = cs.apply_screen(df)
    assert len(out) == 1
    assert bool(out.iloc[0]["canslim_screen_pass"]) is False  # N/S/I all N/A


# --------------------------------------------------------------------------
# Composite / ranking over multiple rows
# --------------------------------------------------------------------------
def test_rank_orders_passers_by_c_magnitude():
    r1 = _base_row(); r1["ticker"] = "LOW";  r1["q1_eps"], r1["q5_eps"] = 0.70, 0.50   # +40%
    r2 = _base_row(); r2["ticker"] = "HIGH"; r2["q1_eps"], r2["q5_eps"] = 2.00, 0.50   # +300%
    r3 = _base_row(); r3["ticker"] = "FAIL"; r3["y1_roe"] = 0.05                       # fails A
    out = cs.apply_screen(pd.DataFrame([r1, r2, r3]))
    passers = cs.screened(out)
    assert list(passers["ticker"]) == ["HIGH", "LOW"]
    assert list(passers["canslim_rank"]) == [1, 2]
    assert "FAIL" not in set(passers["ticker"])


def test_metrics_frame_shape():
    out = cs.apply_screen(pd.DataFrame([_base_row()]))
    m = cs.metrics_frame(out)
    assert "ticker" in m.columns
    assert "canslim_screen_pass" in m.columns
    assert all(c in m.columns for c in cs.VALUE_COLUMNS)
