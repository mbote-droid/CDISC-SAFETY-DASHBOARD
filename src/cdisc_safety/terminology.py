"""Controlled terminology, study design constants and variable labels.

Terms follow CDISC Controlled Terminology conventions. Adverse-event terms use
MedDRA-style system organ class (SOC) and preferred term (PT) names; the data
built from them is synthetic and not coded against a licensed MedDRA release.
"""

from __future__ import annotations

from dataclasses import dataclass

STUDYID = "SYN-SAFETY-001"

SEX_CT = ("M", "F", "U", "UNDIFFERENTIATED")
AESEV_CT = ("MILD", "MODERATE", "SEVERE")
NY_CT = ("Y", "N")
AEREL_CT = ("NOT RELATED", "UNLIKELY RELATED", "POSSIBLY RELATED", "PROBABLY RELATED", "RELATED")
AEACN_CT = ("DOSE NOT CHANGED", "DOSE REDUCED", "DRUG INTERRUPTED", "DRUG WITHDRAWN", "NOT APPLICABLE")
AEOUT_CT = (
    "RECOVERED/RESOLVED",
    "RECOVERING/RESOLVING",
    "NOT RECOVERED/NOT RESOLVED",
    "RECOVERED/RESOLVED WITH SEQUELAE",
    "FATAL",
    "UNKNOWN",
)
RACE_CT = (
    "WHITE",
    "BLACK OR AFRICAN AMERICAN",
    "ASIAN",
    "AMERICAN INDIAN OR ALASKA NATIVE",
    "NATIVE HAWAIIAN OR OTHER PACIFIC ISLANDER",
    "MULTIPLE",
    "NOT REPORTED",
    "UNKNOWN",
)
ETHNIC_CT = ("HISPANIC OR LATINO", "NOT HISPANIC OR LATINO", "NOT REPORTED", "UNKNOWN")
RELATED_TERMS = ("POSSIBLY RELATED", "PROBABLY RELATED", "RELATED")


@dataclass(frozen=True)
class Arm:
    """A planned treatment arm."""

    armcd: str
    arm: str
    trtn: int
    dose_level: int


ARMS: tuple[Arm, ...] = (
    Arm("PBO", "Placebo", 0, 0),
    Arm("DRGA50", "Drug A 50 mg", 1, 1),
    Arm("DRGA100", "Drug A 100 mg", 2, 2),
)
ARM_BY_CODE = {a.armcd: a for a in ARMS}
CONTROL_ARM = "Placebo"


@dataclass(frozen=True)
class AETerm:
    """A synthetic adverse-event term with a baseline rate and dose effect."""

    soc: str
    pt: str
    verbatims: tuple[str, ...]
    base_rate: float
    dose_mult: float


AE_TERMS: tuple[AETerm, ...] = (
    AETerm("Gastrointestinal disorders", "Nausea", ("nausea", "feeling sick", "NAUSEA"), 0.10, 1.8),
    AETerm("Gastrointestinal disorders", "Diarrhoea", ("diarrhea", "loose stools"), 0.08, 1.5),
    AETerm("Gastrointestinal disorders", "Vomiting", ("vomiting", "threw up"), 0.05, 1.6),
    AETerm("Gastrointestinal disorders", "Abdominal pain", ("abdominal pain", "stomach ache"), 0.04, 1.1),
    AETerm("Nervous system disorders", "Headache", ("headache", "head ache"), 0.12, 1.1),
    AETerm("Nervous system disorders", "Dizziness", ("dizziness", "feeling dizzy"), 0.06, 1.3),
    AETerm("General disorders and administration site conditions", "Fatigue", ("fatigue", "tiredness"), 0.10, 1.4),
    AETerm("General disorders and administration site conditions", "Pyrexia", ("fever", "pyrexia"), 0.05, 1.0),
    AETerm("Skin and subcutaneous tissue disorders", "Rash", ("rash", "skin rash"), 0.04, 2.0),
    AETerm("Skin and subcutaneous tissue disorders", "Pruritus", ("itching", "pruritus"), 0.03, 1.5),
    AETerm("Infections and infestations", "Nasopharyngitis", ("common cold", "nasopharyngitis"), 0.08, 1.0),
    AETerm(
        "Infections and infestations",
        "Upper respiratory tract infection",
        ("URTI", "upper respiratory infection"),
        0.05,
        1.0,
    ),
    AETerm("Investigations", "Alanine aminotransferase increased", ("ALT increased", "raised ALT"), 0.02, 2.5),
    AETerm("Blood and lymphatic system disorders", "Neutropenia", ("neutropenia", "low neutrophils"), 0.02, 2.5),
    AETerm("Blood and lymphatic system disorders", "Anaemia", ("anemia", "low haemoglobin"), 0.03, 1.3),
    AETerm("Metabolism and nutrition disorders", "Decreased appetite", ("poor appetite",), 0.04, 1.5),
    AETerm("Musculoskeletal and connective tissue disorders", "Arthralgia", ("joint pain",), 0.04, 1.0),
    AETerm("Cardiac disorders", "Palpitations", ("palpitations",), 0.02, 1.2),
    AETerm("Psychiatric disorders", "Insomnia", ("insomnia", "can't sleep"), 0.04, 1.1),
)


@dataclass(frozen=True)
class LabTest:
    """A laboratory parameter with its reference range in SI units."""

    testcd: str
    test: str
    unit: str
    low: float
    high: float


LAB_TESTS: tuple[LabTest, ...] = (
    LabTest("ALT", "Alanine Aminotransferase", "U/L", 7.0, 56.0),
    LabTest("AST", "Aspartate Aminotransferase", "U/L", 10.0, 40.0),
    LabTest("BILI", "Bilirubin", "umol/L", 3.0, 21.0),
    LabTest("CREAT", "Creatinine", "umol/L", 60.0, 110.0),
    LabTest("HGB", "Hemoglobin", "g/L", 120.0, 170.0),
    LabTest("NEUT", "Neutrophils", "10^9/L", 1.8, 7.5),
)
LAB_BY_CODE = {t.testcd: t for t in LAB_TESTS}

VISITS: tuple[tuple[int, str, int], ...] = (
    # (VISITNUM, VISIT, planned study day relative to first dose)
    (1, "SCREENING", -7),
    (2, "WEEK 4", 28),
    (3, "WEEK 8", 56),
    (4, "WEEK 12", 84),
)

AGE_GROUPS: tuple[tuple[str, int, float, float], ...] = (
    ("<45", 1, 0, 45),
    ("45-64", 2, 45, 65),
    (">=65", 3, 65, 200),
)

# Variable labels (max 40 characters, as required for SAS v5 transport files).
LABELS: dict[str, str] = {
    "STUDYID": "Study Identifier",
    "DOMAIN": "Domain Abbreviation",
    "USUBJID": "Unique Subject Identifier",
    "SUBJID": "Subject Identifier for the Study",
    "SITEID": "Study Site Identifier",
    "RFSTDTC": "Subject Reference Start Date/Time",
    "RFENDTC": "Subject Reference End Date/Time",
    "AGE": "Age",
    "AGEU": "Age Units",
    "SEX": "Sex",
    "RACE": "Race",
    "ETHNIC": "Ethnicity",
    "ARMCD": "Planned Arm Code",
    "ARM": "Description of Planned Arm",
    "ACTARMCD": "Actual Arm Code",
    "ACTARM": "Description of Actual Arm",
    "COUNTRY": "Country",
    "DTHFL": "Subject Death Flag",
    "DTHDTC": "Date/Time of Death",
    "AESEQ": "Sequence Number",
    "AETERM": "Reported Term for the Adverse Event",
    "AEDECOD": "Dictionary-Derived Term",
    "AEBODSYS": "Body System or Organ Class",
    "AESEV": "Severity/Intensity",
    "AESER": "Serious Event",
    "AEREL": "Causality",
    "AEACN": "Action Taken with Study Treatment",
    "AEOUT": "Outcome of Adverse Event",
    "AETOXGR": "Standard Toxicity Grade",
    "AESTDTC": "Start Date/Time of Adverse Event",
    "AEENDTC": "End Date/Time of Adverse Event",
    "AESTDY": "Study Day of Start of Adverse Event",
    "AEENDY": "Study Day of End of Adverse Event",
    "LBSEQ": "Sequence Number",
    "LBTESTCD": "Lab Test or Examination Short Name",
    "LBTEST": "Lab Test or Examination Name",
    "LBORRES": "Result or Finding in Original Units",
    "LBORRESU": "Original Units",
    "LBORNRLO": "Reference Range Lower Limit in Orig Unit",
    "LBORNRHI": "Reference Range Upper Limit in Orig Unit",
    "LBSTRESN": "Numeric Result/Finding in Standard Units",
    "LBSTRESU": "Standard Units",
    "LBNRIND": "Reference Range Indicator",
    "LBBLFL": "Baseline Flag",
    "VISITNUM": "Visit Number",
    "VISIT": "Visit Name",
    "LBDTC": "Date/Time of Specimen Collection",
    "LBDY": "Study Day of Specimen Collection",
    "AGEGR1": "Pooled Age Group 1",
    "AGEGR1N": "Pooled Age Group 1 (N)",
    "TRT01P": "Planned Treatment for Period 01",
    "TRT01PN": "Planned Treatment for Period 01 (N)",
    "TRT01A": "Actual Treatment for Period 01",
    "TRT01AN": "Actual Treatment for Period 01 (N)",
    "TRTSDT": "Date of First Exposure to Treatment",
    "TRTEDT": "Date of Last Exposure to Treatment",
    "TRTDURD": "Total Treatment Duration (Days)",
    "SAFFL": "Safety Population Flag",
    "ITTFL": "Intent-To-Treat Population Flag",
    "EOSSTT": "End of Study Status",
    "DCSREAS": "Reason for Discontinuation from Study",
    "TRTA": "Actual Treatment",
    "TRTAN": "Actual Treatment (N)",
    "ASTDT": "Analysis Start Date",
    "AENDT": "Analysis End Date",
    "ASTDY": "Analysis Start Relative Day",
    "TRTEMFL": "Treatment Emergent Analysis Flag",
    "AOCCFL": "1st Occurrence within Subject Flag",
    "AOCCSFL": "1st Occurrence of SOC Flag",
    "AOCCPFL": "1st Occurrence of Preferred Term Flag",
    "ATOXGR": "Analysis Toxicity Grade",
    "PARAMCD": "Parameter Code",
    "PARAM": "Parameter",
    "AVISIT": "Analysis Visit",
    "AVISITN": "Analysis Visit (N)",
    "ADT": "Analysis Date",
    "ADY": "Analysis Relative Day",
    "AVAL": "Analysis Value",
    "BASE": "Baseline Value",
    "CHG": "Change from Baseline",
    "PCHG": "Percent Change from Baseline",
    "ANRLO": "Analysis Normal Range Lower Limit",
    "ANRHI": "Analysis Normal Range Upper Limit",
    "ANRIND": "Analysis Reference Range Indicator",
    "BNRIND": "Baseline Reference Range Indicator",
    "ABLFL": "Baseline Record Flag",
    "R2ANRHI": "Ratio to Analysis Normal Range Upper",
}
