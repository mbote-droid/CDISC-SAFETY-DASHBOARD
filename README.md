# 🏥 CDISC-Compliant Clinical Trial Safety Dashboard

[![Python](https://img.shields.io/badge/Python-3.9+-blue.svg)](https://www.python.org/)
[![Docker](https://img.shields.io/badge/Docker-Supported-2496ED.svg)](https://www.docker.com/)
[![CI](https://github.com/mbote-droid/CDISC-SAFETY-DASHBOARD/actions/workflows/ci.yml/badge.svg)](https://github.com/mbote-droid/CDISC-SAFETY-DASHBOARD/actions/workflows/ci.yml)
[![CD](https://github.com/mbote-droid/CDISC-SAFETY-DASHBOARD/actions/workflows/cd.yml/badge.svg)](https://github.com/mbote-droid/CDISC-SAFETY-DASHBOARD/actions/workflows/cd.yml)

A production-ready Python pipeline and interactive dashboard that transforms raw clinical trial data into CDISC-style outputs for safety monitoring, validation, and reporting.

## 🎯 The Business Problem
Clinical trial teams must monitor safety data continuously, but raw study data is often fragmented, inconsistent, and difficult to validate at scale. Turning that data into standardized, review-ready outputs is a common bottleneck in biopharma analytics workflows.

## 💡 The Solution
This project demonstrates a practical end-to-end workflow for clinical data engineering:

1. **Automated ingestion** of raw mock clinical data without modifying source files.
2. **Strict validation** of DM-style clinical records to catch anomalies early.
3. **Transformation into SDTM/ADaM-style outputs** for downstream reporting and analysis.
4. **Interactive visualization** through a Streamlit dashboard for exploratory review.
5. **Automated quality checks** through CI, linting, and test coverage.

## ⚙️ Tech Stack
- **Data engineering and validation:** Python, Pandas, Pandera, Loguru
- **Transformation layer:** custom clinical-data transformation logic
- **Visualization:** Streamlit
- **Deployment and automation:** Docker, Docker Compose, GitHub Actions

## 📂 Project Structure

```text
CDISC-SAFETY-DASHBOARD/
├── .github/workflows/   # CI/CD automation
├── data/raw/            # Sample raw clinical data
├── project_1/           # Core pipeline, ingestion, transformation, and reporting modules
├── tests/               # Unit tests for validation and pipeline logic
├── Dockerfile           # Container build instructions
├── docker-compose.yml   # Local container orchestration
├── requirements.txt     # Python dependencies
└── README.md            # Project overview
```

## 🚀 Quickstart

### Option 1: Docker (recommended)

```bash
git clone https://github.com/mbote-droid/CDISC-SAFETY-DASHBOARD.git
cd CDISC-SAFETY-DASHBOARD
docker compose up --build
```

The app will be available at http://localhost:8501.

### Option 2: Local Python environment

```bash
python -m venv .venv
source .venv/bin/activate  # On Windows PowerShell: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m streamlit run project_1/app/app.py --server.port 8501 --server.address 0.0.0.0
```

### Option 3: Run the pipeline directly

```bash
python -c "from project_1.pipelines.ingestion_pipeline import run_pipeline; print(run_pipeline('dm.csv'))"
```

## 🧪 Validation Strategy and Dataset Design

This project's dataset design demonstrates the importance of both correctness and scale. That is why this repository uses two complementary data strategies.

### 1. Small validation dataset: the unit-test style example
A compact DM-style file with a handful of rows is ideal for showing that the pipeline can catch edge cases clearly and deliberately. A small dataset makes it easy for a reviewer to see anomalies such as:
- invalid ages
- unexpected sex values
- missing or malformed fields

This is valuable because it makes the validation logic easy to inspect and understand quickly. In portfolio terms, it shows that the project is thoughtful about data quality, not just capable of processing data.

### 2. Larger dashboard dataset: the production-style example
A larger synthetic dataset is necessary to demonstrate how the dashboard behaves in a more realistic setting. A file with 500 to 2,000 rows makes it easier to show:
- aggregation and summarization
- filtering by study or demographic variables
- responsive user experience under realistic data volume

This helps communicate that the project is not only validating data correctly, but also delivering an experience that could plausibly support end-user analysis.

### Recommended approach
The most effective structure is a dual-dataset design:
1. Keep a small edge-case file for validation and testing.
2. Use a larger synthetic file in data/raw for the dashboard experience.

A helper script is included to generate a larger synthetic CSV automatically:

```bash
python -c "from project_1.data_generation.generate_large_dataset import generate_large_dataset; generate_large_dataset('data/raw/dm_large.csv', rows=1000)"
```

This approach shows both technical rigor and application-level maturity, which is exactly what hiring managers and reviewers tend to look for.

## 🛡️ Data Privacy and Security
- This repository uses synthetic mock data only.
- No real protected health information is included.
- The Docker build and CI workflow are configured with basic security-conscious practices.

## ✅ Quality Checks
- Automated tests with pytest
- Linting with pylint
- CI/CD workflows for validation and deployment
