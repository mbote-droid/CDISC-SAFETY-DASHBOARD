from __future__ import annotations

import pandas as pd
import pytest

from cdisc_safety import cleaning
from cdisc_safety.findings import Findings


def _dm(**overrides) -> pd.DataFrame:
    base = {
        "SUBJID": ["101-0001", "101-0002", "101-0003"],
        "SITEID": ["101"] * 3,
        "AGE": ["40", "50", "60"],
        "SEX": ["M", "F", "M"],
        "RACE": ["WHITE", "ASIAN", "BLACK OR AFRICAN AMERICAN"],
        "ARMCD": ["PBO", "DRGA50", "DRGA100"],
        "ARM": ["Placebo", "Drug A 50 mg", "Drug A 100 mg"],
        "TRTSDT": ["2025-01-01"] * 3,
        "TRTEDT": ["2025-03-25"] * 3,
    }
    base.update(overrides)
    return pd.DataFrame(base)


def rules(findings: Findings) -> set[str]:
    return {f.rule_id for f in findings.items}


def test_clean_dm_happy_path():
    f = Findings()
    clean, q = cleaning.clean_dm(_dm(), f)
    assert len(clean) == 3 and q.empty and not f.items
    assert clean["AGE"].dtype.kind == "i"
    assert {"ETHNIC", "COUNTRY", "DCSREAS", "DTHDT"} <= set(clean.columns)


@pytest.mark.parametrize(
    ("override", "rule", "quarantined"),
    [
        ({"SUBJID": ["", "101-0002", "101-0003"]}, "DM-R01", 1),
        ({"SUBJID": ["101-0001", "101-0001", "101-0003"]}, "DM-R02", 1),
        ({"AGE": ["abc", "50", "200"]}, "DM-R03", 2),
        ({"SEX": ["Q", "F", "M"]}, "DM-R06", 1),
        ({"ARMCD": ["XXX", "DRGA50", "DRGA100"]}, "DM-R08", 1),
        ({"TRTSDT": ["01/01/2025", "2025-01-01", "2025-01-01"]}, "DM-R09", 1),
    ],
)
def test_clean_dm_quarantines(override, rule, quarantined):
    f = Findings()
    clean, q = cleaning.clean_dm(_dm(**override), f)
    assert rule in rules(f)
    assert len(q) == quarantined
    assert len(clean) == 3 - quarantined
    assert q["QREASON"].ne("").all()


def test_clean_dm_warnings_keep_records():
    f = Findings()
    dm = _dm(
        AGE=["16", "50", "60"],
        SEX=["Male", "female", "M"],
        RACE=["martian", "", "ASIAN"],
        TRTEDT=["", "2024-01-01", "2025-03-25"],
    )
    clean, q = cleaning.clean_dm(dm, f)
    assert q.empty and len(clean) == 3
    assert {"DM-R04", "DM-R05", "DM-R07", "DM-R10"} <= rules(f)
    assert clean["SEX"].tolist() == ["M", "F", "M"]
    assert clean.loc[0, "RACE"] == "UNKNOWN" and clean.loc[1, "RACE"] == "NOT REPORTED"
    assert (clean["TRTEDT"] >= clean["TRTSDT"]).all()


def _ae(**overrides) -> pd.DataFrame:
    base = {
        "SUBJID": ["101-0001", "101-0002"],
        "AEDECOD": ["Nausea", "Headache"],
        "AEBODSYS": ["Gastrointestinal disorders", "Nervous system disorders"],
        "AESTDT": ["2025-01-10", "2025-01-12"],
        "AEENDT": ["2025-01-15", ""],
        "AETOXGR": ["1", "3"],
        "AESER": ["N", "Yes"],
    }
    base.update(overrides)
    return pd.DataFrame(base)


def test_clean_ae_defaults_and_derivations():
    f = Findings()
    clean, q = cleaning.clean_ae(_ae(), {"101-0001", "101-0002"}, f)
    assert q.empty
    assert clean["AESER"].tolist() == ["N", "Y"]
    assert clean["AESEV"].tolist() == ["MILD", "SEVERE"]
    assert clean["AETERM"].tolist() == ["Nausea", "Headache"]
    assert pd.isna(clean.loc[1, "AEENDT"])


def test_clean_ae_rules():
    f = Findings()
    ae = _ae(SUBJID=["101-0001", "999"], AEENDT=["2024-01-01", "x"], AETOXGR=["9", "2"], AESER=["maybe", "N"])
    clean, q = cleaning.clean_ae(ae, {"101-0001"}, f)
    assert {"AE-R01", "AE-R04", "AE-R05", "AE-R06"} <= rules(f)
    assert len(q) == 1 and len(clean) == 1
    assert pd.isna(clean.loc[0, "AEENDT"]) and pd.isna(clean.loc[0, "AETOXGR"])

    f2 = Findings()
    _, q2 = cleaning.clean_ae(_ae(AESTDT=["bad", "2025-01-12"], AEENDT=["", "nope"]), {"101-0001", "101-0002"}, f2)
    assert {"AE-R02", "AE-R03"} <= rules(f2) and len(q2) == 1


def _lb(**overrides) -> pd.DataFrame:
    base = {
        "SUBJID": ["101-0001", "101-0001"],
        "VISITNUM": ["1", "2"],
        "VISIT": ["SCREENING", "WEEK 4"],
        "LBDT": ["2024-12-25", "2025-01-29"],
        "LBTESTCD": ["ALT", "ALT"],
        "LBORRES": ["30", "<5"],
        "LBORNRLO": ["7", "7"],
        "LBORNRHI": ["56", "56"],
    }
    base.update(overrides)
    return pd.DataFrame(base)


def test_clean_lb_rules():
    f = Findings()
    clean, q = cleaning.clean_lb(_lb(), {"101-0001"}, f)
    assert q.empty and "LB-R04" in rules(f)
    assert clean["LBSTRESN"].isna().sum() == 1
    f2 = Findings()
    lb = _lb(
        SUBJID=["101-0001", "nobody"],
        LBDT=["2024-12-25", "2025-01-29"],
        VISITNUM=["x", "2"],
        LBORNRLO=["60", "7"],
        LBORNRHI=["56", "56"],
    )
    clean2, q2 = cleaning.clean_lb(lb, {"101-0001"}, f2)
    assert {"LB-R01", "LB-R03"} <= rules(f2)
    assert len(q2) == 2 and clean2.empty
    f3 = Findings()
    clean3, _ = cleaning.clean_lb(_lb(LBDT=["bad", "2025-01-29"], LBORNRLO=["7", "60"]), {"101-0001"}, f3)
    assert {"LB-R02", "LB-R05"} <= rules(f3)
    assert len(clean3) == 1


def test_findings_validation_and_frame():
    f = Findings()
    with pytest.raises(ValueError):
        f.add("X", "DM", "FATAL", "bad")
    f.add("X", "DM", "ERROR", "nothing", ids=[])
    assert f.items == []
    assert list(f.to_frame().columns) == ["rule_id", "domain", "severity", "message", "count", "examples"]
    f.add("B", "DM", "WARNING", "w", ids=["s1"])
    f.add("A", "DM", "ERROR", "e", ids=["s2", "s3"])
    df = f.to_frame()
    assert df.iloc[0]["severity"] == "ERROR" and df.iloc[0]["count"] == 2
    assert f.count("ERROR") == 1 and f.count("NOTE") == 0
