"""ADaM analysis datasets ADSL, ADAE and ADLB (ADaMIG 1.3 style)."""

from __future__ import annotations

import numpy as np
import pandas as pd

from cdisc_safety.terminology import AGE_GROUPS, ARM_BY_CODE

TEAE_WINDOW_DAYS = 30  # events starting up to 30 days after last dose are treatment-emergent

ADSL_VARS = [
    "STUDYID",
    "USUBJID",
    "SUBJID",
    "SITEID",
    "COUNTRY",
    "AGE",
    "AGEU",
    "AGEGR1",
    "AGEGR1N",
    "SEX",
    "RACE",
    "ETHNIC",
    "ARMCD",
    "ARM",
    "TRT01P",
    "TRT01PN",
    "TRT01A",
    "TRT01AN",
    "TRTSDT",
    "TRTEDT",
    "TRTDURD",
    "SAFFL",
    "ITTFL",
    "EOSSTT",
    "DCSREAS",
    "DTHFL",
]
ADAE_VARS = [
    "STUDYID",
    "USUBJID",
    "SITEID",
    "AGE",
    "SEX",
    "RACE",
    "TRTA",
    "TRTAN",
    "SAFFL",
    "TRTSDT",
    "TRTEDT",
    "AESEQ",
    "AETERM",
    "AEDECOD",
    "AEBODSYS",
    "AESEV",
    "AESER",
    "AEREL",
    "AEACN",
    "AEOUT",
    "AETOXGR",
    "ATOXGR",
    "ASTDT",
    "AENDT",
    "ASTDY",
    "TRTEMFL",
    "AOCCFL",
    "AOCCSFL",
    "AOCCPFL",
]
ADLB_VARS = [
    "STUDYID",
    "USUBJID",
    "TRTA",
    "TRTAN",
    "SAFFL",
    "PARAMCD",
    "PARAM",
    "AVISIT",
    "AVISITN",
    "ADT",
    "ADY",
    "AVAL",
    "BASE",
    "CHG",
    "PCHG",
    "ANRLO",
    "ANRHI",
    "ANRIND",
    "BNRIND",
    "ABLFL",
    "R2ANRHI",
]


def _age_group(age: pd.Series) -> tuple[pd.Series, pd.Series]:
    labels = pd.Series("", index=age.index)
    codes = pd.Series(pd.NA, index=age.index, dtype="Int64")
    for label, code, lo, hi in AGE_GROUPS:
        mask = (age >= lo) & (age < hi)
        labels[mask] = label
        codes[mask] = code
    return labels, codes


def build_adsl(dm_sdtm: pd.DataFrame, dm_clean: pd.DataFrame) -> pd.DataFrame:
    """Derive the subject-level analysis dataset."""
    out = dm_sdtm.copy()
    extra = dm_clean.set_index("SUBJID")
    out["TRTSDT"] = pd.to_datetime(out["RFSTDTC"], errors="coerce")
    out["TRTEDT"] = pd.to_datetime(out["RFENDTC"], errors="coerce")
    out["TRTDURD"] = ((out["TRTEDT"] - out["TRTSDT"]).dt.days + 1).astype("Int64")
    out["AGEGR1"], out["AGEGR1N"] = _age_group(out["AGE"])
    out["TRT01P"] = out["ARM"]
    out["TRT01PN"] = out["ARMCD"].map(lambda c: ARM_BY_CODE[c].trtn).astype(int)
    out["TRT01A"] = out["ACTARM"]
    out["TRT01AN"] = out["ACTARMCD"].map(lambda c: ARM_BY_CODE[c].trtn).astype(int)
    out["SAFFL"] = np.where(out["TRTSDT"].notna(), "Y", "N")
    out["ITTFL"] = np.where(out["ARMCD"].ne(""), "Y", "N")
    reason = out["SUBJID"].map(extra["DCSREAS"]).fillna("").astype(str)
    out["DCSREAS"] = reason
    out["EOSSTT"] = np.where(reason.eq(""), "COMPLETED", "DISCONTINUED")
    return out[ADSL_VARS].reset_index(drop=True)


def build_adae(ae_sdtm: pd.DataFrame, adsl: pd.DataFrame) -> pd.DataFrame:
    """Derive the adverse-event analysis dataset with treatment-emergent and first-occurrence flags."""
    if ae_sdtm.empty:
        return pd.DataFrame(columns=ADAE_VARS)
    keys = adsl[["USUBJID", "SITEID", "AGE", "SEX", "RACE", "TRT01A", "TRT01AN", "SAFFL", "TRTSDT", "TRTEDT"]]
    out = ae_sdtm.merge(keys, on="USUBJID", how="inner", validate="many_to_one")
    out = out.rename(columns={"TRT01A": "TRTA", "TRT01AN": "TRTAN"})
    out["ASTDT"] = pd.to_datetime(out["AESTDTC"], errors="coerce")
    out["AENDT"] = pd.to_datetime(out["AEENDTC"], errors="coerce")
    delta = (out["ASTDT"] - out["TRTSDT"]).dt.days
    out["ASTDY"] = pd.Series(np.where(delta >= 0, delta + 1, delta), index=out.index).astype("Int64")
    window_end = out["TRTEDT"] + pd.Timedelta(days=TEAE_WINDOW_DAYS)
    out["TRTEMFL"] = np.where((out["ASTDT"] >= out["TRTSDT"]) & (out["ASTDT"] <= window_end), "Y", "")
    out["ATOXGR"] = out["AETOXGR"]
    out = out.sort_values(["USUBJID", "ASTDT", "AESEQ"], kind="stable")
    teae = out["TRTEMFL"].eq("Y")
    for flag, keys_ in (("AOCCFL", ["USUBJID"]), ("AOCCSFL", ["USUBJID", "AEBODSYS"]), ("AOCCPFL", ["USUBJID", "AEDECOD"])):
        first = ~out[teae].duplicated(keys_, keep="first")
        out[flag] = ""
        out.loc[first[first].index, flag] = "Y"
    return out[ADAE_VARS].reset_index(drop=True)


def build_adlb(lb_sdtm: pd.DataFrame, adsl: pd.DataFrame) -> pd.DataFrame:
    """Derive the laboratory analysis dataset with baseline, change and ratio to the upper limit."""
    if lb_sdtm.empty:
        return pd.DataFrame(columns=ADLB_VARS)
    keys = adsl[["USUBJID", "TRT01A", "TRT01AN", "SAFFL"]].rename(columns={"TRT01A": "TRTA", "TRT01AN": "TRTAN"})
    out = lb_sdtm.merge(keys, on="USUBJID", how="inner", validate="many_to_one")
    out["PARAMCD"] = out["LBTESTCD"]
    out["PARAM"] = out["LBTEST"].where(out["LBTEST"].ne(""), out["LBTESTCD"]) + " (" + out["LBSTRESU"] + ")"
    out["AVISIT"] = out["VISIT"]
    out["AVISITN"] = out["VISITNUM"]
    out["ADT"] = pd.to_datetime(out["LBDTC"], errors="coerce")
    out["ADY"] = out["LBDY"]
    out["AVAL"] = out["LBSTRESN"]
    out["ANRLO"] = out["LBORNRLO"]
    out["ANRHI"] = out["LBORNRHI"]
    out["ANRIND"] = out["LBNRIND"]
    out["ABLFL"] = out["LBBLFL"]
    base = out[out["ABLFL"].eq("Y")].set_index(["USUBJID", "PARAMCD"])
    base = base[~base.index.duplicated(keep="first")]
    idx = pd.MultiIndex.from_frame(out[["USUBJID", "PARAMCD"]])
    out["BASE"] = base["AVAL"].reindex(idx).to_numpy()
    out["BNRIND"] = base["ANRIND"].reindex(idx).fillna("").to_numpy()
    out["CHG"] = out["AVAL"] - out["BASE"]
    out["PCHG"] = np.where(out["BASE"].abs() > 0, 100 * out["CHG"] / out["BASE"], np.nan)
    out["R2ANRHI"] = np.where(out["ANRHI"] > 0, out["AVAL"] / out["ANRHI"], np.nan)
    return out[ADLB_VARS].sort_values(["USUBJID", "PARAMCD", "AVISITN"]).reset_index(drop=True)
