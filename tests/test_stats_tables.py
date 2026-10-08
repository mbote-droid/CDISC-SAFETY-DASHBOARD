from __future__ import annotations

import math

import pandas as pd
import pytest

from cdisc_safety import tables
from cdisc_safety.stats import newcombe_diff, wilson


def test_wilson_known_values():
    lo, hi = wilson(0, 10)
    assert lo == 0.0 and hi == pytest.approx(0.2775, abs=1e-4)
    lo, hi = wilson(81, 263)
    assert lo == pytest.approx(0.2553, abs=1e-4) and hi == pytest.approx(0.3662, abs=1e-4)
    assert all(math.isnan(v) for v in wilson(0, 0))
    with pytest.raises(ValueError):
        wilson(5, 3)


def test_newcombe_matches_published_example():
    # Newcombe (1998), Table II example (56/70 vs 48/80): diff 0.2, 95% CI 0.0524 to 0.3339
    d, lo, hi = newcombe_diff(56, 70, 48, 80)
    assert d == pytest.approx(0.2)
    assert lo == pytest.approx(0.0524, abs=1e-4) and hi == pytest.approx(0.3339, abs=1e-4)
    assert all(math.isnan(v) for v in newcombe_diff(1, 0, 1, 1))


def test_fmt_np():
    assert tables.fmt_np(3, 12) == "3 (25.0%)"
    assert tables.fmt_np(0, 0) == "0"


def test_teae_overview_counts_match_adae(result):
    ov = result.tables["teae_overview"]
    adae = result.adam["ADAE"]
    any_teae = adae[adae["TRTEMFL"].eq("Y")]["USUBJID"].nunique()
    assert ov.loc[ov["Category"].eq("Any TEAE"), "_n_Total"].iloc[0] == any_teae
    serious = adae[adae["TRTEMFL"].eq("Y") & adae["AESER"].eq("Y")]["USUBJID"].nunique()
    assert ov.loc[ov["Category"].eq("Any serious TEAE"), "_n_Total"].iloc[0] == serious


def test_soc_pt_sorted_and_consistent(result):
    t = result.tables["teae_soc_pt"]
    socs = t[t["PT"].eq("")]
    assert socs["_total"].is_monotonic_decreasing
    for soc in socs["SOC"]:
        block = t[t["SOC"].eq(soc)]
        assert block.iloc[0]["PT"] == ""
        assert block["_total"].iloc[1:].max() <= block["_total"].iloc[0]


def test_dose_response_signal_for_nausea(result):
    rd = result.tables["risk_differences"]
    nausea = rd[rd["PT"].eq("Nausea")].set_index("Arm")
    assert nausea.loc["Drug A 100 mg", "Diff"] > 0
    assert (rd["Lower"] <= rd["Diff"]).all() and (rd["Diff"] <= rd["Upper"]).all()


def test_hys_law_case_detected(result):
    hys = result.tables["hys_law"]
    flagged = hys[hys["Potential Hy's law"]]
    assert len(flagged) >= 1
    assert set(flagged["TRTA"]) == {"Drug A 100 mg"}


def test_shift_and_mean_change(result):
    shift = result.tables["lab_shift"]
    assert set(shift["Worst post-baseline"]) <= {"LOW", "NORMAL", "HIGH"}
    n_sub = result.adam["ADLB"]["USUBJID"].nunique()
    per_param = shift.groupby(["PARAMCD"])["Subjects"].sum()
    assert (per_param <= n_sub).all()
    change = result.tables["lab_mean_change"]
    assert (change["n"] > 0).all() and set(change["AVISITN"]) <= {2, 3, 4}


def test_demographics_rows(result):
    demo = result.tables["demographics"]
    assert demo.iloc[0]["Characteristic"] == "N"
    assert demo.iloc[0]["Total"] == str(result.adam["ADSL"].shape[0])
    groups = demo[demo["Characteristic"].str.startswith("Age group")]["Characteristic"].tolist()
    assert groups == sorted(groups, key=lambda s: ["<45", "45-64", ">=65"].index(s.split(": ")[1]))


def test_tables_handle_empty_inputs(result):
    adsl = result.adam["ADSL"]
    empty_ae = pd.DataFrame(columns=result.adam["ADAE"].columns)
    empty_lb = pd.DataFrame(columns=result.adam["ADLB"].columns)
    assert tables.teae_by_soc_pt(adsl, empty_ae).empty
    assert tables.risk_differences(adsl, empty_ae).empty
    assert tables.lab_shift(empty_lb).empty
    assert tables.hys_law(empty_lb).empty
    assert tables.lab_mean_change(empty_lb).empty
    ov = tables.teae_overview(adsl, empty_ae)
    assert (ov["_n_Total"] == 0).all()
