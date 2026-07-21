# CDISC-Compliant Safety Monitoring Dashboard

Clinical data made clear — from raw trial inputs to trusted CDISC-ready insights.

![CI](https://github.com/mbote-droid/CDISC-SAFETY-DASHBOARD/actions/workflows/ci.yml/badge.svg)
![CD](https://github.com/mbote-droid/CDISC-SAFETY-DASHBOARD/actions/workflows/cd.yml/badge.svg)
![Python 3.11](https://img.shields.io/badge/python-3.11-blue)
![Docker](https://img.shields.io/badge/docker-ready-blue)
![Deploy](https://img.shields.io/badge/deploy-streamlit%20ready-green)

This project provides a Python-based clinical data ingestion and validation workflow for DM-style clinical data, with Streamlit-based visualization, auditability, and Docker-ready deployment.

## Features
- Ingestion of CSV-style clinical data
- Validation against a DM-style schema
- Transformation into SDTM DM-style and ADaM ADSL-style parquet outputs
- Audit logging and reporting for traceability
- Docker and GitHub Container Registry support

## Running locally
```bash
python -m pytest -q
python -m streamlit run project_1/app/app.py --server.port 8501 --server.address 0.0.0.0
```

## Docker
```bash
docker build -t cdisc-dashboard .
docker run -p 8501:8501 cdisc-dashboard
```

## GitHub Container Registry
Pushes are handled automatically by GitHub Actions when CI succeeds.
