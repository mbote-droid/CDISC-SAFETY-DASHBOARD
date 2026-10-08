# CDISC Safety Dashboard

[![CI](https://github.com/mbote-droid/CDISC-SAFETY-DASHBOARD/actions/workflows/ci.yml/badge.svg)](https://github.com/mbote-droid/CDISC-SAFETY-DASHBOARD/actions/workflows/ci.yml)
[![CD](https://github.com/mbote-droid/CDISC-SAFETY-DASHBOARD/actions/workflows/cd.yml/badge.svg)](https://github.com/mbote-droid/CDISC-SAFETY-DASHBOARD/actions/workflows/cd.yml)
[![Python](https://img.shields.io/badge/Python-3.11%20%7C%203.12%20%7C%203.13-blue?logo=python&logoColor=white)](https://www.python.org)
[![Coverage](https://img.shields.io/badge/coverage-98%25-brightgreen)](#testing-and-quality)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

An end-to-end clinical trial safety pipeline and interactive dashboard. It turns raw, messy EDC-style exports into
**CDISC SDTM** (DM, AE, LB) and **ADaM** (ADSL, ADAE, ADLB) datasets, runs data-quality and conformance checks,
and produces the safety tables and figures a medical monitor or biostatistician reviews: TEAE summaries, SOC/PT
incidence, risk differences with confidence intervals, lab shift tables and an eDISH plot for Hy's law.

> **Synthetic data only.** The built-in study is simulated. This is a portfolio and teaching tool, not a validated
> system for regulatory submissions or clinical decisions.

## What it does

```
raw CSV/Parquet ──► cleaning & quarantine ──► SDTM DM / AE / LB ──► conformance checks
                                                       │
                                                       ▼
            safety tables & figures ◄── ADaM ADSL / ADAE / ADLB ──► XPT v5, Parquet, CSV, define metadata, manifest
```

| Area | Features |
|---|---|
| **Data ingestion** | CSV or Parquet; UTF-8/Latin-1; auto-detected delimiters; 200 MB limit; every value read as text so type problems become findings, not crashes |
| **Cleaning** | 20+ row-level rules; unusable records quarantined with a reason; terminology mapping (e.g. `Male` → `M`); nothing is silently dropped |
| **SDTM** | DM, AE, LB with USUBJID, `--SEQ`, ISO 8601 dates, study days (no day 0), reference-range indicators, baseline flags |
| **ADaM** | ADSL (populations, treatment dates, duration, age groups, disposition), ADAE (treatment-emergent flag with 30-day window, first-occurrence flags), ADLB (baseline, change, % change, ratio to ULN) |
| **Conformance** | Pinnacle 21-style rules: required variables, keys, referential integrity, controlled terminology, ISO 8601, SAS v5 name/label limits |
| **Safety analytics** | TEAE overview; SOC/PT incidence; risk difference vs placebo with **Newcombe hybrid-score 95% CIs**; lab shift tables; mean change from baseline; eDISH / potential **Hy's law** screen |
| **Outputs** | SAS **XPT v5** (FDA transport format), Parquet, CSV, define-style JSON metadata, findings report, quarantine files and a **manifest with SHA-256 checksums** of every input and output |
| **Dashboard** | Streamlit app with demo or upload mode, interactive Altair charts, searchable tables and one-click ZIP download |
| **Fault tolerance** | Stage isolation (one failing domain never loses the others); DM-only runs work; failures reported as findings; the UI never shows a stack trace |

## Quick start

```bash
git clone https://github.com/mbote-droid/CDISC-SAFETY-DASHBOARD.git
cd CDISC-SAFETY-DASHBOARD
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -e ".[app,dev]"

streamlit run app/streamlit_app.py # dashboard at http://localhost:8501
```

Command line:

```bash
cdisc-safety demo --out outputs                        # synthetic study end to end
cdisc-safety generate --out data/raw --inject-errors   # raw files with realistic data-entry faults
cdisc-safety run --raw data/raw --out outputs          # run on your own dm_raw/ae_raw/lb_raw files
cdisc-safety run --raw data/raw --out outputs --strict # exit code 2 if any ERROR finding fires (for pipelines)
```

Docker:

```bash
docker compose up --build          # http://localhost:8501
```

## Input format

| File | Required columns | Optional columns |
|---|---|---|
| `dm_raw` | SUBJID, SITEID, AGE, SEX, RACE, ARMCD, ARM, TRTSDT, TRTEDT | ETHNIC, COUNTRY, RANDDT, DCSREAS, DTHDT |
| `ae_raw` | SUBJID, AEDECOD, AEBODSYS, AESTDT, AETOXGR, AESER | AETERM, AEENDT, AESEV, AEREL, AEACN, AEOUT |
| `lb_raw` | SUBJID, VISITNUM, VISIT, LBDT, LBTESTCD, LBORRES, LBORNRLO, LBORNRHI | LBTEST, LBORRESU |

Dates are ISO 8601 (`YYYY-MM-DD`). Planned arms are `PBO`, `DRGA50` and `DRGA100`. The dashboard's demo mode can
download a ready-made template.

## Outputs

```
outputs/
├── sdtm/      dm, ae, lb        (.xpt, .parquet, .csv)
├── adam/      adsl, adae, adlb  (.xpt, .parquet, .csv)
├── tables/    demographics, teae_overview, teae_soc_pt, risk_differences, lab_shift, hys_law, lab_mean_change
├── reports/   findings.csv, quarantine_*.csv
├── define/    datasets.json     (dataset and variable metadata)
└── manifest.json                (run ID, versions, status, record counts, SHA-256 of every input and output)
```

## Testing and quality

* **70 tests**, **98% branch coverage** (CI fails below 90%): unit tests for every module, end-to-end runs,
  fault-injection runs, stage-failure isolation, XPT round-trips, checksum verification, reproducibility,
  CLI exit codes and headless dashboard tests with Streamlit's `AppTest`.
* Statistical methods are checked against published values (Wilson interval; Newcombe 1998 worked example).
* CI on Python 3.11, 3.12 and 3.13: ruff lint and format, pytest, bandit, pip-audit, CLI smoke test,
  and a Docker build with a container health check. CD publishes the image to GitHub Container Registry.
* Performance: 1,500 subjects (about 35,000 lab records) processed in under 1 second; 5,000 subjects in about 3 seconds.

## Deployment

The container honours `$PORT`, so the same image runs on Streamlit Community Cloud, Hugging Face Spaces,
Google Cloud Run, Render or Fly.io. See [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md).

## Documentation

* [HOW_IT_WORKS.md](HOW_IT_WORKS.md): pipeline stages, derivation rules and data-quality rules
* [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md): hosting options with step-by-step instructions
* [SECURITY.md](SECURITY.md): security model and reporting

## Citation

If you use this software, please cite it using the metadata in [CITATION.cff](CITATION.cff).

## License

MIT © Samuel Mbote
