"""Row-level cleaning of raw tables.

Each function returns ``(clean, quarantine)``. Records that cannot be mapped
safely are moved to quarantine with a reason instead of stopping the run, and
every decision is recorded as a finding so nothing is silently dropped.
"""

from __future__ import annotations

import pandas as pd

from cdisc_safety.findings import Findings
from cdisc_safety.terminology import AESEV_CT, ARM_BY_CODE, RACE_CT

SEX_SYNONYMS = {
    "M": "M",
    "MALE": "M",
    "F": "F",
    "FEMALE": "F",
    "U": "U",
    "UNKNOWN": "U",
    "UNDIFFERENTIATED": "UNDIFFERENTIATED",
}
YN_SYNONYMS = {"Y": "Y", "YES": "Y", "1": "Y", "TRUE": "Y", "N": "N", "NO": "N", "0": "N", "FALSE": "N"}


def parse_dates(series: pd.Series) -> pd.Series:
    """Parse ISO 8601 dates (YYYY-MM-DD); anything else becomes NaT."""
    return pd.to_datetime(
        series.where(series.astype(str).str.fullmatch(r"\d{4}-\d{2}-\d{2}")), format="%Y-%m-%d", errors="coerce"
    )


def _quarantine(df: pd.DataFrame, mask: pd.Series, reason: str, parts: list[pd.DataFrame]) -> pd.DataFrame:
    if mask.any():
        q = df[mask].copy()
        q["QREASON"] = reason
        parts.append(q)
    return df[~mask]


def _concat(parts: list[pd.DataFrame]) -> pd.DataFrame:
    return pd.concat(parts, ignore_index=True) if parts else pd.DataFrame(columns=["QREASON"])


def clean_dm(raw: pd.DataFrame, findings: Findings) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Clean demographics: one row per subject with valid age, sex, arm and dates."""
    df = raw.copy()
    q: list[pd.DataFrame] = []

    blank = df["SUBJID"].eq("")
    findings.add("DM-R01", "DM", "ERROR", "Subject identifier is missing; record quarantined", count=int(blank.sum()))
    df = _quarantine(df, blank, "missing SUBJID", q)

    dup = df["SUBJID"].duplicated(keep="first")
    findings.add("DM-R02", "DM", "ERROR", "Duplicate subject record; later copy quarantined", df.loc[dup, "SUBJID"])
    df = _quarantine(df, dup, "duplicate SUBJID", q)

    age = pd.to_numeric(df["AGE"], errors="coerce")
    bad_age = age.isna() | (age < 0) | (age > 120)
    findings.add("DM-R03", "DM", "ERROR", "AGE missing, non-numeric or outside 0-120", df.loc[bad_age, "SUBJID"])
    df = _quarantine(df, bad_age, "invalid AGE", q)
    df["AGE"] = pd.to_numeric(df["AGE"]).astype(int)
    outside = (df["AGE"] < 18) | (df["AGE"] > 85)
    findings.add("DM-R04", "DM", "WARNING", "AGE outside protocol range 18-85", df.loc[outside, "SUBJID"])

    sex_up = df["SEX"].str.upper()
    mapped = sex_up.map(SEX_SYNONYMS)
    remapped = mapped.notna() & (mapped != df["SEX"])
    findings.add("DM-R05", "DM", "WARNING", "SEX mapped to CDISC terminology (e.g. Male -> M)", df.loc[remapped, "SUBJID"])
    bad_sex = mapped.isna()
    findings.add("DM-R06", "DM", "ERROR", "SEX not mappable to CDISC terminology", df.loc[bad_sex, "SUBJID"])
    df["SEX"] = mapped
    df = _quarantine(df, bad_sex, "invalid SEX", q)

    df["RACE"] = df["RACE"].str.upper().replace("", "NOT REPORTED")
    bad_race = ~df["RACE"].isin(RACE_CT)
    findings.add("DM-R07", "DM", "WARNING", "RACE not in CDISC terminology; set to UNKNOWN", df.loc[bad_race, "SUBJID"])
    df.loc[bad_race, "RACE"] = "UNKNOWN"
    if "ETHNIC" not in df.columns:
        df["ETHNIC"] = "NOT REPORTED"
    if "COUNTRY" not in df.columns:
        df["COUNTRY"] = ""

    bad_arm = ~df["ARMCD"].isin(ARM_BY_CODE)
    findings.add("DM-R08", "DM", "ERROR", "ARMCD is not a planned arm", df.loc[bad_arm, "SUBJID"])
    df = _quarantine(df, bad_arm, "invalid ARMCD", q)

    df["TRTSDT"] = parse_dates(df["TRTSDT"])
    df["TRTEDT"] = parse_dates(df["TRTEDT"])
    bad_start = df["TRTSDT"].isna()
    findings.add("DM-R09", "DM", "ERROR", "First-dose date missing or not ISO 8601", df.loc[bad_start, "SUBJID"])
    df = _quarantine(df, bad_start, "invalid TRTSDT", q)
    bad_end = df["TRTEDT"].isna() | (df["TRTEDT"] < df["TRTSDT"])
    findings.add("DM-R10", "DM", "WARNING", "Last-dose date missing/invalid; set to first-dose date", df.loc[bad_end, "SUBJID"])
    df.loc[bad_end, "TRTEDT"] = df.loc[bad_end, "TRTSDT"]

    for col in ("RANDDT", "DTHDT"):
        df[col] = parse_dates(df[col]) if col in df.columns else pd.NaT
    if "DCSREAS" not in df.columns:
        df["DCSREAS"] = ""
    return df.reset_index(drop=True), _concat(q)


def clean_ae(raw: pd.DataFrame, subjects: set[str], findings: Findings) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Clean adverse events: known subject, valid start date, standard terminology."""
    df = raw.copy()
    q: list[pd.DataFrame] = []
    for col, default in (("AETERM", ""), ("AEENDT", ""), ("AESEV", ""), ("AEREL", ""), ("AEACN", ""), ("AEOUT", "")):
        if col not in df.columns:
            df[col] = default

    orphan = ~df["SUBJID"].isin(subjects)
    findings.add(
        "AE-R01", "AE", "ERROR", "Adverse event for a subject not in (or removed from) DM; quarantined", df.loc[orphan, "SUBJID"]
    )
    df = _quarantine(df, orphan, "subject not in DM", q)

    df["AESTDT"] = parse_dates(df["AESTDT"])
    bad_start = df["AESTDT"].isna()
    findings.add("AE-R02", "AE", "ERROR", "AE start date missing or not ISO 8601; quarantined", df.loc[bad_start, "SUBJID"])
    df = _quarantine(df, bad_start, "invalid AESTDT", q)

    raw_end = df["AEENDT"].astype(str)
    df["AEENDT"] = parse_dates(df["AEENDT"])
    bad_end = raw_end.ne("") & df["AEENDT"].isna()
    findings.add("AE-R03", "AE", "WARNING", "AE end date not ISO 8601; set to missing (ongoing)", df.loc[bad_end, "SUBJID"])
    reversed_ = df["AEENDT"].notna() & (df["AEENDT"] < df["AESTDT"])
    findings.add("AE-R04", "AE", "WARNING", "AE end date before start date; end date set to missing", df.loc[reversed_, "SUBJID"])
    df.loc[reversed_, "AEENDT"] = pd.NaT

    grade = pd.to_numeric(df["AETOXGR"], errors="coerce")
    bad_grade = grade.isna() | ~grade.isin([1, 2, 3, 4, 5])
    findings.add("AE-R05", "AE", "WARNING", "Toxicity grade not 1-5; set to missing", df.loc[bad_grade, "SUBJID"])
    df["AETOXGR"] = grade.where(~bad_grade).astype("Int64")

    ser = df["AESER"].str.upper().map(YN_SYNONYMS)
    findings.add("AE-R06", "AE", "WARNING", "AESER not Y/N; treated as N", df.loc[ser.isna(), "SUBJID"])
    df["AESER"] = ser.fillna("N")

    sev = df["AESEV"].str.upper()
    derived = df["AETOXGR"].map(lambda g: pd.NA if pd.isna(g) else "MILD" if g == 1 else "MODERATE" if g == 2 else "SEVERE")
    df["AESEV"] = sev.where(sev.isin(AESEV_CT), derived)
    if "AETERM" in df.columns:
        df["AETERM"] = df["AETERM"].where(df["AETERM"].ne(""), df["AEDECOD"])
    return df.reset_index(drop=True), _concat(q)


def clean_lb(raw: pd.DataFrame, subjects: set[str], findings: Findings) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Clean laboratory results: known subject, valid date, numeric ranges."""
    df = raw.copy()
    q: list[pd.DataFrame] = []
    for col in ("LBTEST", "LBORRESU"):
        if col not in df.columns:
            df[col] = ""

    orphan = ~df["SUBJID"].isin(subjects)
    findings.add(
        "LB-R01", "LB", "ERROR", "Lab result for a subject not in (or removed from) DM; quarantined", df.loc[orphan, "SUBJID"]
    )
    df = _quarantine(df, orphan, "subject not in DM", q)

    df["LBDT"] = parse_dates(df["LBDT"])
    bad_date = df["LBDT"].isna()
    findings.add("LB-R02", "LB", "ERROR", "Collection date missing or not ISO 8601; quarantined", df.loc[bad_date, "SUBJID"])
    df = _quarantine(df, bad_date, "invalid LBDT", q)

    df["VISITNUM"] = pd.to_numeric(df["VISITNUM"], errors="coerce")
    bad_visit = df["VISITNUM"].isna()
    findings.add("LB-R03", "LB", "ERROR", "Visit number not numeric; quarantined", df.loc[bad_visit, "SUBJID"])
    df = _quarantine(df, bad_visit, "invalid VISITNUM", q)

    df["LBSTRESN"] = pd.to_numeric(df["LBORRES"], errors="coerce")
    non_num = df["LBSTRESN"].isna()
    findings.add(
        "LB-R04",
        "LB",
        "WARNING",
        "Non-numeric result (e.g. '<5'); kept as text, excluded from analysis",
        df.loc[non_num, "SUBJID"],
    )
    df["LBORNRLO"] = pd.to_numeric(df["LBORNRLO"], errors="coerce")
    df["LBORNRHI"] = pd.to_numeric(df["LBORNRHI"], errors="coerce")
    bad_range = df["LBORNRLO"].isna() | df["LBORNRHI"].isna() | (df["LBORNRLO"] >= df["LBORNRHI"])
    findings.add("LB-R05", "LB", "WARNING", "Reference range missing or low >= high", df.loc[bad_range, "SUBJID"])
    df.loc[bad_range, ["LBORNRLO", "LBORNRHI"]] = float("nan")
    return df.reset_index(drop=True), _concat(q)
