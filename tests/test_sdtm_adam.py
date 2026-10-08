from __future__ import annotations

import pandas as pd

from cdisc_safety import adam, sdtm
from cdisc_safety.terminology import STUDYID


def test_study_day_has_no_day_zero():
    ref = pd.Series(pd.to_datetime(["2025-01-10"] * 4))
    dt = pd.Series(pd.to_datetime(["2025-01-08", "2025-01-09", "2025-01-10", "2025-01-11"]))
    assert sdtm.study_day(dt, ref).tolist() == [-2, -1, 1, 2]
    assert sdtm.study_day(pd.Series([pd.NaT]), pd.Series(pd.to_datetime(["2025-01-10"]))).isna().all()


def test_dm_structure(result):
    dm = result.sdtm["DM"]
    assert list(dm.columns) == sdtm.DM_VARS
    assert dm["USUBJID"].is_unique
    assert dm["USUBJID"].str.startswith(STUDYID + "-").all()
    assert set(dm["DOMAIN"]) == {"DM"}


def test_ae_sequence_and_days(result):
    ae = result.sdtm["AE"]
    assert list(ae.columns) == sdtm.AE_VARS
    assert not ae.duplicated(["USUBJID", "AESEQ"]).any()
    assert ae.groupby("USUBJID")["AESEQ"].apply(lambda s: list(s) == list(range(1, len(s) + 1))).all()
    assert (ae["AESTDY"].dropna() != 0).all()


def test_lb_baseline_one_per_subject_test(result):
    lb = result.sdtm["LB"]
    base = lb[lb["LBBLFL"].eq("Y")]
    assert not base.duplicated(["USUBJID", "LBTESTCD"]).any()
    assert (base["LBDY"] <= 1).all()
    assert set(lb["LBNRIND"]) <= {"LOW", "NORMAL", "HIGH", ""}


def test_empty_domains_keep_structure(result):
    assert list(sdtm.build_ae(pd.DataFrame(), result.sdtm["DM"]).columns) == sdtm.AE_VARS
    assert list(sdtm.build_lb(pd.DataFrame(), result.sdtm["DM"]).columns) == sdtm.LB_VARS
    assert list(adam.build_adae(pd.DataFrame(), result.adam["ADSL"]).columns) == adam.ADAE_VARS
    assert list(adam.build_adlb(pd.DataFrame(), result.adam["ADSL"]).columns) == adam.ADLB_VARS


def test_adsl(result):
    adsl = result.adam["ADSL"]
    assert list(adsl.columns) == adam.ADSL_VARS
    assert set(adsl["SAFFL"]) == {"Y"}
    assert (adsl["TRTDURD"] >= 1).all()
    assert set(adsl["AGEGR1"]) <= {"<45", "45-64", ">=65"}
    assert set(adsl.loc[adsl["DCSREAS"].ne(""), "EOSSTT"]) <= {"DISCONTINUED"}
    assert adsl["TRT01PN"].isin([0, 1, 2]).all()


def test_adae_treatment_emergent_flag(result):
    adae = result.adam["ADAE"]
    window = adae["TRTEDT"] + pd.Timedelta(days=adam.TEAE_WINDOW_DAYS)
    expected = (adae["ASTDT"] >= adae["TRTSDT"]) & (adae["ASTDT"] <= window)
    assert adae["TRTEMFL"].eq("Y").eq(expected).all()
    assert adae["TRTEMFL"].eq("").any(), "synthetic data should include some pre-treatment events"


def test_adae_first_occurrence_flags(result):
    adae = result.adam["ADAE"]
    teae = adae[adae["TRTEMFL"].eq("Y")]
    assert teae.groupby("USUBJID")["AOCCFL"].apply(lambda s: (s == "Y").sum()).eq(1).all()
    assert teae.groupby(["USUBJID", "AEDECOD"])["AOCCPFL"].apply(lambda s: (s == "Y").sum()).eq(1).all()
    assert adae.loc[adae["TRTEMFL"].ne("Y"), ["AOCCFL", "AOCCSFL", "AOCCPFL"]].eq("").all().all()


def test_adlb_change_from_baseline(result):
    adlb = result.adam["ADLB"]
    rows = adlb.dropna(subset=["AVAL", "BASE"])
    assert ((rows["AVAL"] - rows["BASE"] - rows["CHG"]).abs() < 1e-9).all()
    base = adlb[adlb["ABLFL"].eq("Y")]
    assert (base["CHG"].abs() < 1e-9).all()
    ratio = adlb.dropna(subset=["AVAL", "ANRHI"])
    assert ((ratio["AVAL"] / ratio["ANRHI"] - ratio["R2ANRHI"]).abs() < 1e-9).all()
