"""Deterministic synthetic raw clinical trial data (an EDC-style export).

The generator produces three raw tables (demographics, adverse events and
laboratory results) for a three-arm, 12-week, placebo-controlled study. Adverse
event rates rise with dose, liver enzymes rise slightly on treatment and one
high-dose subject meets Hy's law criteria, so every dashboard view has a real
signal to show. All data is synthetic; no real person is represented.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

from cdisc_safety.terminology import AE_TERMS, ARMS, LAB_TESTS, VISITS

PLANNED_DAYS = 84
FOLLOW_UP_DAYS = 30
COUNTRIES = (("KEN", 0.30), ("USA", 0.30), ("GBR", 0.20), ("ZAF", 0.20))
RACES = (
    ("BLACK OR AFRICAN AMERICAN", 0.40),
    ("WHITE", 0.40),
    ("ASIAN", 0.12),
    ("AMERICAN INDIAN OR ALASKA NATIVE", 0.03),
    ("MULTIPLE", 0.05),
)
GRADE_P = (0.60, 0.28, 0.10, 0.015, 0.005)


@dataclass(frozen=True)
class RawData:
    """Raw tables as exported from an electronic data capture system."""

    dm: pd.DataFrame
    ae: pd.DataFrame
    lb: pd.DataFrame


def _choice(rng: np.random.Generator, options: tuple[tuple[str, float], ...]) -> str:
    labels = [o[0] for o in options]
    probs = np.array([o[1] for o in options], dtype=float)
    return str(rng.choice(labels, p=probs / probs.sum()))


def _iso(d: date | None) -> str:
    return d.isoformat() if d is not None else ""


def _generate_subjects(rng: np.random.Generator, n_subjects: int) -> list[dict]:
    start = date(2025, 1, 6)
    subjects = []
    for i in range(n_subjects):
        arm = ARMS[i % len(ARMS)]
        site = f"{101 + (i % 6)}"
        rand_dt = start + timedelta(days=int(rng.integers(0, 260)))
        trt_start = rand_dt + timedelta(days=int(rng.integers(0, 4)))
        subjects.append(
            {
                "SUBJID": f"{site}-{i + 1:04d}",
                "SITEID": site,
                "AGE": int(np.clip(rng.normal(54, 12), 18, 85)),
                "SEX": "F" if rng.random() < 0.52 else "M",
                "RACE": _choice(rng, RACES),
                "ETHNIC": "HISPANIC OR LATINO" if rng.random() < 0.08 else "NOT HISPANIC OR LATINO",
                "COUNTRY": _choice(rng, COUNTRIES),
                "ARMCD": arm.armcd,
                "ARM": arm.arm,
                "DOSE_LEVEL": arm.dose_level,
                "RANDDT": rand_dt,
                "TRTSDT": trt_start,
                "TRTEDT": trt_start + timedelta(days=PLANNED_DAYS - 1),
                "DCSREAS": "",
                "DTHDT": None,
            }
        )
    return subjects


def _generate_aes(rng: np.random.Generator, subjects: list[dict]) -> list[dict]:
    rows: list[dict] = []
    for s in subjects:
        for term in AE_TERMS:
            rate = min(term.base_rate * term.dose_mult ** s["DOSE_LEVEL"], 0.6)
            if rng.random() >= rate:
                continue
            grade = int(rng.choice([1, 2, 3, 4, 5], p=GRADE_P))
            if rng.random() < 0.04:
                onset = int(rng.integers(-10, 0))  # started before first dose: not treatment-emergent
                grade = min(grade, 2)  # pre-treatment events are mild and never alter dosing
            else:
                onset = int(rng.integers(0, PLANNED_DAYS + 10))
            st = s["TRTSDT"] + timedelta(days=onset)
            ongoing = rng.random() < 0.1 and grade < 5
            en = None if ongoing else st + timedelta(days=int(rng.integers(1, 21)))
            withdrawn = grade >= 3 and rng.random() < 0.3 and onset >= 0
            if grade == 5:
                outcome, en = "FATAL", st
            elif ongoing:
                outcome = "NOT RECOVERED/NOT RESOLVED"
            else:
                outcome = "RECOVERED/RESOLVED"
            if s["DOSE_LEVEL"] == 0:
                rel = str(rng.choice(["NOT RELATED", "UNLIKELY RELATED", "POSSIBLY RELATED"], p=[0.6, 0.3, 0.1]))
            else:
                rel = str(
                    rng.choice(
                        ["NOT RELATED", "UNLIKELY RELATED", "POSSIBLY RELATED", "PROBABLY RELATED"],
                        p=[0.3, 0.2, 0.35, 0.15],
                    )
                )
            rows.append(
                {
                    "SUBJID": s["SUBJID"],
                    "AETERM": str(rng.choice(term.verbatims)),
                    "AEDECOD": term.pt,
                    "AEBODSYS": term.soc,
                    "AESTDT": st,
                    "AEENDT": en,
                    "AETOXGR": grade,
                    "AESEV": "MILD" if grade == 1 else "MODERATE" if grade == 2 else "SEVERE",
                    "AESER": "Y" if grade >= 4 or (grade == 3 and rng.random() < 0.25) else "N",
                    "AEREL": rel,
                    "AEACN": "DRUG WITHDRAWN" if withdrawn else "DOSE NOT CHANGED",
                    "AEOUT": outcome,
                }
            )
            if withdrawn and st <= s["TRTEDT"]:
                s["TRTEDT"] = st
                s["DCSREAS"] = "ADVERSE EVENT"
            if grade == 5:
                s["DTHDT"] = st
                s["TRTEDT"] = min(s["TRTEDT"], st)
                s["DCSREAS"] = "DEATH"
    for s in subjects:
        if not s["DCSREAS"] and rng.random() < 0.06:
            s["TRTEDT"] = s["TRTSDT"] + timedelta(days=int(rng.integers(14, PLANNED_DAYS - 1)))
            s["DCSREAS"] = "WITHDRAWAL BY SUBJECT"
    return rows


def _lab_value(rng: np.random.Generator, test, dose_level: int, visitnum: int) -> float:
    mid = (test.low + test.high) / 2
    sd = (test.high - test.low) / 5
    on_treatment = visitnum > 1
    shift = 0.0
    if on_treatment and test.testcd in ("ALT", "AST"):
        shift = 4.0 * dose_level
    if on_treatment and test.testcd == "NEUT":
        shift = -0.45 * dose_level
    if test.testcd in ("ALT", "AST", "BILI"):
        return float(round(max(rng.lognormal(np.log(mid * 0.7 + shift), 0.35), 1.0), 1))
    return float(round(max(rng.normal(mid + shift, sd), 0.1), 1))


def _generate_labs(rng: np.random.Generator, subjects: list[dict]) -> list[dict]:
    rows: list[dict] = []
    hys_case = next((s["SUBJID"] for s in subjects if s["DOSE_LEVEL"] == 2 and not s["DCSREAS"]), None)
    for s in subjects:
        last_day = (s["TRTEDT"] - s["TRTSDT"]).days + FOLLOW_UP_DAYS
        for visitnum, visit, day in VISITS:
            if day > last_day:
                continue
            lbdt = s["TRTSDT"] + timedelta(days=day + int(rng.integers(-2, 3)))
            for test in LAB_TESTS:
                value = _lab_value(rng, test, s["DOSE_LEVEL"], visitnum)
                if s["SUBJID"] == hys_case and visitnum == 3:
                    value = {"ALT": 5.2 * test.high, "AST": 4.1 * test.high, "BILI": 2.6 * test.high}.get(test.testcd, value)
                rows.append(
                    {
                        "SUBJID": s["SUBJID"],
                        "VISITNUM": visitnum,
                        "VISIT": visit,
                        "LBDT": lbdt,
                        "LBTESTCD": test.testcd,
                        "LBTEST": test.test,
                        "LBORRES": f"{round(value, 1)}",
                        "LBORRESU": test.unit,
                        "LBORNRLO": test.low,
                        "LBORNRHI": test.high,
                    }
                )
    return rows


def generate(n_subjects: int = 300, seed: int = 42, inject_errors: bool = False) -> RawData:
    """Generate a reproducible raw dataset; ``inject_errors`` adds realistic data-entry faults."""
    if n_subjects < 3:
        raise ValueError("n_subjects must be at least 3 (one per arm)")
    rng = np.random.default_rng(seed)
    subjects = _generate_subjects(rng, n_subjects)
    ae_rows = _generate_aes(rng, subjects)
    lb_rows = _generate_labs(rng, subjects)

    dm = pd.DataFrame(
        [
            {
                **{k: v for k, v in s.items() if k not in ("DOSE_LEVEL",)},
                "RANDDT": _iso(s["RANDDT"]),
                "TRTSDT": _iso(s["TRTSDT"]),
                "TRTEDT": _iso(s["TRTEDT"]),
                "DTHDT": _iso(s["DTHDT"]),
            }
            for s in subjects
        ]
    )
    ae = pd.DataFrame(ae_rows)
    if not ae.empty:
        ae["AESTDT"] = ae["AESTDT"].map(_iso)
        ae["AEENDT"] = ae["AEENDT"].map(_iso)
    lb = pd.DataFrame(lb_rows)
    lb["LBDT"] = lb["LBDT"].map(_iso)

    if inject_errors:
        dm, ae, lb = _inject_errors(dm, ae, lb)
    return RawData(dm=dm, ae=ae, lb=lb)


def _inject_errors(dm: pd.DataFrame, ae: pd.DataFrame, lb: pd.DataFrame):
    """Introduce the faults a data manager meets in real EDC exports."""
    dm = dm.copy()
    ae = ae.copy()
    lb = lb.copy()
    dm.loc[0, "AGE"] = 150  # impossible age (subject is quarantined with its records)
    dm.loc[1, "SEX"] = "Male"  # non-standard terminology
    dm = pd.concat([dm, dm.iloc[[2]]], ignore_index=True)  # duplicate subject
    affected = set(dm["SUBJID"].iloc[:3])
    ae_ok = ae.index[~ae["SUBJID"].isin(affected)]
    if len(ae_ok) >= 2:
        ae.loc[ae_ok[0], "AEENDT"] = "2020-01-01"  # ends before it starts
        ae.loc[ae_ok[1], "AESTDT"] = "2025-13-45"  # invalid date
    if len(ae):
        orphan = {**ae.iloc[-1].to_dict(), "SUBJID": "999-9999"}  # subject not in DM
        ae = pd.concat([ae, pd.DataFrame([orphan])], ignore_index=True)
    lb_ok = lb.index[~lb["SUBJID"].isin(affected)]
    if len(lb_ok):
        lb.loc[lb_ok[0], "LBORRES"] = "<5"  # non-numeric result
    return dm, ae, lb


def write_raw(raw: RawData, out_dir: str | Path) -> dict[str, Path]:
    """Write raw tables as CSV files and return their paths."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    paths = {}
    for name, df in (("dm", raw.dm), ("ae", raw.ae), ("lb", raw.lb)):
        path = out / f"{name}_raw.csv"
        df.to_csv(path, index=False)
        paths[name] = path
    return paths
