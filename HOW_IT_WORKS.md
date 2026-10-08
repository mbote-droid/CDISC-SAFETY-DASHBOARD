# How it works

## 1. Input (`io.py`)

Raw files are read as text (CSV with auto-detected delimiter, UTF-8 with Latin-1 fallback, or Parquet). Column
names are normalised to upper case. A file is rejected outright only if it cannot be used at all: empty, larger
than 200 MB, unparseable, or missing a required column. A rejected AE or LB file becomes a `PIPE-03` finding and
the run continues; a rejected DM file stops the run, because every other domain depends on it.

## 2. Cleaning and quarantine (`cleaning.py`)

Every rule records a finding with a rule ID, severity, record count and example subjects. Records that cannot be
used safely are moved to `reports/quarantine_<domain>.csv` with the reason.

| Rule | Severity | Action |
|---|---|---|
| DM-R01 missing SUBJID | ERROR | quarantine |
| DM-R02 duplicate subject | ERROR | keep first, quarantine later copies |
| DM-R03 AGE missing/non-numeric/outside 0-120 | ERROR | quarantine |
| DM-R04 AGE outside protocol range 18-85 | WARNING | keep |
| DM-R05 SEX synonym (Male, female) | WARNING | map to CDISC terminology |
| DM-R06 SEX not mappable | ERROR | quarantine |
| DM-R07 RACE not in terminology | WARNING | set to UNKNOWN |
| DM-R08 ARMCD not a planned arm | ERROR | quarantine |
| DM-R09 first-dose date invalid | ERROR | quarantine |
| DM-R10 last-dose date invalid or before first dose | WARNING | set to first-dose date |
| AE-R01 / LB-R01 subject not in DM | ERROR | quarantine |
| AE-R02 AE start date invalid | ERROR | quarantine |
| AE-R03 AE end date invalid | WARNING | set missing (ongoing) |
| AE-R04 AE end before start | WARNING | end date set missing |
| AE-R05 toxicity grade not 1-5 | WARNING | set missing |
| AE-R06 AESER not Y/N (Yes/No/1/0 mapped) | WARNING | treated as N |
| LB-R02 collection date invalid | ERROR | quarantine |
| LB-R03 visit number not numeric | ERROR | quarantine |
| LB-R04 non-numeric result such as `<5` | WARNING | kept as text, excluded from analysis |
| LB-R05 reference range missing or low ≥ high | WARNING | range set missing |

## 3. SDTM (`sdtm.py`)

* `USUBJID = STUDYID-SUBJID`; `--SEQ` numbered per subject in date order.
* Study day: `date − RFSTDTC + 1` on or after the reference date, `date − RFSTDTC` before it (no day 0).
* LB: `LBNRIND` from the reference range; `LBBLFL = Y` on the last non-missing result on or before first dose.

## 4. Conformance (`conformance.py`)

Checks on the derived SDTM: required variables (SD0001), variable names ≤ 8 and labels ≤ 40 characters for SAS v5
transport (SD0002/3), null keys (SD0004), referential integrity to DM (SD0005), unique `--SEQ` (SD0006), ISO 8601
dates (SD0007), no study day 0 (SD0008), unique subjects, controlled terminology for SEX, AESEV, AESER and LBNRIND,
death flag consistency, fatal events marked serious, grade/severity consistency and missing baselines.

## 5. ADaM (`adam.py`)

* **ADSL**: TRT01P/A with numeric codes, TRTSDT/TRTEDT, TRTDURD, AGEGR1, SAFFL (received study drug), ITTFL,
  EOSSTT and DCSREAS.
* **ADAE**: `TRTEMFL = Y` when the event starts on or after first dose and no later than 30 days after last dose.
  `AOCCFL`, `AOCCSFL` and `AOCCPFL` flag the first treatment-emergent occurrence per subject, per SOC and per PT.
* **ADLB**: PARAM, AVISIT, AVAL, BASE, CHG, PCHG, ANRIND/BNRIND and `R2ANRHI` (value ÷ upper limit of normal).

## 6. Safety tables (`tables.py`, `stats.py`)

All counts are **subjects**, not events, in the safety population.

* TEAE overview: any TEAE, serious, grade ≥ 3, treatment-related, leading to discontinuation, fatal.
* SOC/PT incidence sorted by overall frequency.
* Risk difference (active − placebo) per preferred term with Newcombe's hybrid score interval (method 10), built
  on Wilson score intervals. Both are verified against published values in the tests.
* Lab shift from baseline indicator to worst post-baseline indicator (HIGH > LOW > NORMAL).
* eDISH: peak post-baseline ALT/AST and bilirubin as multiples of ULN; potential Hy's law when ALT or AST ≥ 3×ULN
  and bilirubin ≥ 2×ULN.
* Mean change from baseline with standard error per visit.

## 7. Outputs and traceability (`export.py`, `pipeline.py`)

Datasets are written as SAS XPT v5 (labels, `DATE9.` formats), Parquet and CSV. A failing format is logged and
does not stop the others. `manifest.json` records the run ID, tool and library versions, timestamps, status,
record counts, quarantine counts, findings by severity and the SHA-256 of every input and output, so a run can be
audited and reproduced.

## 8. Fault tolerance summary

| Situation | Behaviour |
|---|---|
| DM missing, empty or unusable | Run status `FAILED` with a clear message |
| Every DM record invalid | `FAILED`, all records in quarantine |
| AE or LB missing | Empty domain, `PIPE-02` note |
| AE or LB file unreadable | Empty domain, `PIPE-03` error finding |
| Unexpected error in any stage | Stage skipped, `PIPE-01` error finding, other stages continue |
| Bad records | Quarantined with reason; status `PASSED WITH FINDINGS` |
| Dashboard view fails | That tab shows an error; other tabs keep working |
