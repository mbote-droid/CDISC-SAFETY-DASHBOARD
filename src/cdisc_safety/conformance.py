"""Conformance checks on derived SDTM datasets.

A focused subset of the kind of rules applied by tools such as Pinnacle 21:
structure, keys, referential integrity, controlled terminology, ISO 8601 dates
and SAS v5 transport limits. Findings are reported, never raised.
"""

from __future__ import annotations

import pandas as pd

from cdisc_safety.findings import Findings
from cdisc_safety.sdtm import AE_VARS, DM_VARS, LB_VARS
from cdisc_safety.terminology import AESEV_CT, LABELS, NY_CT, SEX_CT

ISO_DATE = r"\d{4}-\d{2}-\d{2}"
SPEC = {"DM": DM_VARS, "AE": AE_VARS, "LB": LB_VARS}


def _ids(df: pd.DataFrame, mask: pd.Series) -> pd.Series:
    return df.loc[mask, "USUBJID"] if "USUBJID" in df.columns else pd.Series(dtype=str)


def check_sdtm(domains: dict[str, pd.DataFrame], findings: Findings) -> None:
    """Run conformance rules over SDTM datasets and record findings."""
    dm = domains.get("DM", pd.DataFrame())
    subjects = set(dm["USUBJID"]) if "USUBJID" in dm.columns else set()

    for name, df in domains.items():
        expected = SPEC.get(name, [])
        missing = [v for v in expected if v not in df.columns]
        if missing:
            findings.add("SD0001", name, "ERROR", f"Required variables missing: {', '.join(missing)}", count=len(missing))
        long_names = [c for c in df.columns if len(c) > 8]
        findings.add("SD0002", name, "ERROR", "Variable name longer than 8 characters", long_names)
        long_labels = [c for c in df.columns if len(LABELS.get(c, "")) > 40]
        findings.add("SD0003", name, "ERROR", "Variable label longer than 40 characters", long_labels)
        for key in ("STUDYID", "DOMAIN", "USUBJID"):
            if key in df.columns:
                blank = df[key].astype(str).eq("") | df[key].isna()
                findings.add("SD0004", name, "ERROR", f"{key} is null", _ids(df, blank))
        if name != "DM" and "USUBJID" in df.columns:
            orphan = ~df["USUBJID"].isin(subjects)
            findings.add("SD0005", name, "ERROR", "USUBJID not found in DM", _ids(df, orphan))
        seq = f"{name}SEQ"
        if seq in df.columns:
            dup = df.duplicated(["USUBJID", seq])
            findings.add("SD0006", name, "ERROR", f"{seq} not unique within subject", _ids(df, dup))
        for col in [c for c in df.columns if c.endswith("DTC")]:
            values = df[col].astype(str)
            bad = values.ne("") & ~values.str.fullmatch(ISO_DATE)
            findings.add("SD0007", name, "ERROR", f"{col} is not ISO 8601", _ids(df, bad))
        for col in [c for c in df.columns if c.endswith("DY")]:
            zero = pd.to_numeric(df[col], errors="coerce").eq(0)
            findings.add("SD0008", name, "ERROR", f"{col} equals 0 (SDTM study days have no day 0)", _ids(df, zero))

    if not dm.empty:
        dup = dm["USUBJID"].duplicated()
        findings.add("DM0001", "DM", "ERROR", "USUBJID not unique in DM", _ids(dm, dup))
        findings.add("DM0002", "DM", "ERROR", "SEX not in controlled terminology", _ids(dm, ~dm["SEX"].isin(SEX_CT)))
        death = dm["DTHFL"].eq("Y") & dm["DTHDTC"].eq("")
        findings.add("DM0003", "DM", "WARNING", "DTHFL is Y but DTHDTC is missing", _ids(dm, death))

    ae = domains.get("AE", pd.DataFrame())
    if not ae.empty:
        findings.add("AE0001", "AE", "ERROR", "AESEV not in controlled terminology", _ids(ae, ~ae["AESEV"].isin(AESEV_CT)))
        findings.add("AE0002", "AE", "ERROR", "AESER not Y/N", _ids(ae, ~ae["AESER"].isin(NY_CT)))
        st = pd.to_datetime(ae["AESTDTC"], errors="coerce")
        en = pd.to_datetime(ae["AEENDTC"], errors="coerce")
        findings.add("AE0003", "AE", "ERROR", "AEENDTC before AESTDTC", _ids(ae, en.notna() & (en < st)))
        fatal_not_ser = ae["AEOUT"].eq("FATAL") & ae["AESER"].ne("Y")
        findings.add("AE0004", "AE", "WARNING", "Fatal outcome but AESER is not Y", _ids(ae, fatal_not_ser))
        grade_sev = pd.to_numeric(ae["AETOXGR"], errors="coerce").ge(3) & ae["AESEV"].eq("MILD")
        findings.add("AE0005", "AE", "WARNING", "Grade >=3 reported as MILD", _ids(ae, grade_sev))

    lb = domains.get("LB", pd.DataFrame())
    if not lb.empty:
        no_base = set(lb["USUBJID"]) - set(lb.loc[lb["LBBLFL"].eq("Y"), "USUBJID"])
        findings.add("LB0001", "LB", "WARNING", "Subject has no baseline lab record", sorted(no_base))
        bad_ind = ~lb["LBNRIND"].isin(["LOW", "NORMAL", "HIGH", ""])
        findings.add("LB0002", "LB", "ERROR", "LBNRIND not in controlled terminology", _ids(lb, bad_ind))
