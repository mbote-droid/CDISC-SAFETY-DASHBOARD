"""Mapping of cleaned raw data to SDTM domains DM, AE and LB (SDTMIG 3.4 style)."""

from __future__ import annotations

import numpy as np
import pandas as pd

from cdisc_safety.terminology import STUDYID

DM_VARS = [
    "STUDYID",
    "DOMAIN",
    "USUBJID",
    "SUBJID",
    "RFSTDTC",
    "RFENDTC",
    "SITEID",
    "AGE",
    "AGEU",
    "SEX",
    "RACE",
    "ETHNIC",
    "ARMCD",
    "ARM",
    "ACTARMCD",
    "ACTARM",
    "COUNTRY",
    "DTHFL",
    "DTHDTC",
]
AE_VARS = [
    "STUDYID",
    "DOMAIN",
    "USUBJID",
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
    "AESTDTC",
    "AEENDTC",
    "AESTDY",
    "AEENDY",
]
LB_VARS = [
    "STUDYID",
    "DOMAIN",
    "USUBJID",
    "LBSEQ",
    "LBTESTCD",
    "LBTEST",
    "LBORRES",
    "LBORRESU",
    "LBORNRLO",
    "LBORNRHI",
    "LBSTRESN",
    "LBSTRESU",
    "LBNRIND",
    "LBBLFL",
    "VISITNUM",
    "VISIT",
    "LBDTC",
    "LBDY",
]


def usubjid(subjid: pd.Series, studyid: str = STUDYID) -> pd.Series:
    """Build USUBJID as STUDYID-SUBJID (SUBJID already carries the site)."""
    return studyid + "-" + subjid.astype(str)


def study_day(dt: pd.Series, ref: pd.Series) -> pd.Series:
    """SDTM study day: date - reference + 1 on/after the reference date, no day 0."""
    delta = (dt - ref).dt.days
    return pd.Series(np.where(delta >= 0, delta + 1, delta), index=dt.index).where(delta.notna()).astype("Int64")


def iso(dt: pd.Series) -> pd.Series:
    """Format datetimes as ISO 8601 dates; missing values become empty strings."""
    return dt.dt.strftime("%Y-%m-%d").fillna("")


def build_dm(dm: pd.DataFrame) -> pd.DataFrame:
    """Derive the SDTM DM domain."""
    out = pd.DataFrame(
        {
            "STUDYID": STUDYID,
            "DOMAIN": "DM",
            "USUBJID": usubjid(dm["SUBJID"]),
            "SUBJID": dm["SUBJID"],
            "RFSTDTC": iso(dm["TRTSDT"]),
            "RFENDTC": iso(dm["TRTEDT"]),
            "SITEID": dm["SITEID"],
            "AGE": dm["AGE"].astype(int),
            "AGEU": "YEARS",
            "SEX": dm["SEX"],
            "RACE": dm["RACE"],
            "ETHNIC": dm["ETHNIC"].replace("", "NOT REPORTED"),
            "ARMCD": dm["ARMCD"],
            "ARM": dm["ARM"],
            "ACTARMCD": dm["ARMCD"],
            "ACTARM": dm["ARM"],
            "COUNTRY": dm["COUNTRY"],
            "DTHFL": np.where(dm["DTHDT"].notna(), "Y", ""),
            "DTHDTC": iso(dm["DTHDT"]),
        }
    )
    return out[DM_VARS].sort_values("USUBJID").reset_index(drop=True)


def _ref_dates(dm_sdtm: pd.DataFrame) -> pd.Series:
    return pd.to_datetime(dm_sdtm.set_index("USUBJID")["RFSTDTC"], errors="coerce")


def build_ae(ae: pd.DataFrame, dm_sdtm: pd.DataFrame) -> pd.DataFrame:
    """Derive the SDTM AE domain with sequence numbers and study days."""
    if ae.empty:
        return pd.DataFrame(columns=AE_VARS)
    out = ae.copy()
    out["STUDYID"] = STUDYID
    out["DOMAIN"] = "AE"
    out["USUBJID"] = usubjid(out["SUBJID"])
    out = out.sort_values(["USUBJID", "AESTDT", "AEDECOD"], kind="stable")
    out["AESEQ"] = out.groupby("USUBJID").cumcount() + 1
    ref = out["USUBJID"].map(_ref_dates(dm_sdtm))
    out["AESTDY"] = study_day(out["AESTDT"], ref)
    out["AEENDY"] = study_day(out["AEENDT"], ref)
    out["AESTDTC"] = iso(out["AESTDT"])
    out["AEENDTC"] = iso(out["AEENDT"])
    return out[AE_VARS].reset_index(drop=True)


def _nrind(value: pd.Series, low: pd.Series, high: pd.Series) -> pd.Series:
    ind = np.select([value < low, value > high], ["LOW", "HIGH"], default="NORMAL")
    return pd.Series(ind, index=value.index).where(value.notna() & low.notna() & high.notna(), "")


def build_lb(lb: pd.DataFrame, dm_sdtm: pd.DataFrame) -> pd.DataFrame:
    """Derive the SDTM LB domain with reference-range indicators and baseline flags.

    The baseline is the last non-missing result on or before the first dose.
    """
    if lb.empty:
        return pd.DataFrame(columns=LB_VARS)
    out = lb.copy()
    out["STUDYID"] = STUDYID
    out["DOMAIN"] = "LB"
    out["USUBJID"] = usubjid(out["SUBJID"])
    out = out.sort_values(["USUBJID", "LBTESTCD", "LBDT", "VISITNUM"], kind="stable")
    out["LBSEQ"] = out.groupby("USUBJID").cumcount() + 1
    ref = out["USUBJID"].map(_ref_dates(dm_sdtm))
    out["LBDY"] = study_day(out["LBDT"], ref)
    out["LBSTRESU"] = out["LBORRESU"]
    out["LBNRIND"] = _nrind(out["LBSTRESN"], out["LBORNRLO"], out["LBORNRHI"])
    eligible = out["LBSTRESN"].notna() & (out["LBDT"] <= ref)
    last_pre = out[eligible].groupby(["USUBJID", "LBTESTCD"])["LBDT"].transform("max")
    out["LBBLFL"] = ""
    out.loc[last_pre.index[out.loc[last_pre.index, "LBDT"].eq(last_pre)], "LBBLFL"] = "Y"
    # keep one baseline record per subject/test if two share the same date
    dup = out["LBBLFL"].eq("Y") & out.duplicated(["USUBJID", "LBTESTCD", "LBBLFL"], keep="first")
    out.loc[dup, "LBBLFL"] = ""
    out["LBDTC"] = iso(out["LBDT"])
    out["VISITNUM"] = out["VISITNUM"].astype(int)
    return out[LB_VARS].reset_index(drop=True)
