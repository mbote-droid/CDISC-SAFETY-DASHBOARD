"""Ingestion pipeline for DM-style clinical data."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
from loguru import logger

from project_1.data_ingestion.adapters import get_reader
from project_1.data_ingestion.schemas import DM_SCHEMA, SchemaValidationError
from project_1.reporting.audit_log import AuditLogger
from project_1.reporting.quality_reporter import generate_dq_report
from project_1.transformations.clinical_transformations import write_outputs


def preprocess_data(df: pd.DataFrame) -> pd.DataFrame:
    """Apply basic cleaning before validation."""
    logger.info("Performing pre-validation cleaning...")
    df_clean = df.copy()
    for col in df_clean.select_dtypes(include=["object"]).columns:
        df_clean[col] = df_clean[col].str.strip()
    logger.success("Pre-validation cleaning complete.")
    return df_clean


BASE_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = BASE_DIR / "data" / "raw"
RESULTS_DIR = BASE_DIR / "results"
REPORTS_DIR = BASE_DIR / "reports"
AUDIT_DIR = BASE_DIR / "results" / "audit"


def run_pipeline(file_name: str) -> dict[str, Path] | None:
    """Run the validation pipeline for a single input file and write SDTM/ADaM outputs."""
    input_file = DATA_DIR / file_name
    staging_path = RESULTS_DIR / "staging"
    if str(RESULTS_DIR).endswith("staging"):
        staging_path = RESULTS_DIR
    else:
        staging_path = RESULTS_DIR / "staging"
    staging_path.mkdir(parents=True, exist_ok=True)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    audit_logger = AuditLogger(AUDIT_DIR / f"{input_file.stem}_audit.jsonl")
    audit_logger.append("pipeline_started", {"source_file": str(input_file)})

    logger.add(f"logs/ingestion_{input_file.stem}.log", rotation="10 MB")
    logger.info(f"Starting ingestion pipeline for {input_file}...")

    try:
        reader = get_reader(input_file)
        data = reader.read(input_file)
        logger.success("Data read successfully.")
        audit_logger.append("data_read", {"rows": int(len(data))})

        preprocessed_data = preprocess_data(data)
        validated_data = DM_SCHEMA.validate(preprocessed_data, lazy=True)
        logger.success("Validation passed.")
        audit_logger.append("validation_succeeded", {"columns": sorted(validated_data.columns.tolist())})

        output_file = staging_path / f"{input_file.stem}.parquet"
        validated_data.to_parquet(output_file, index=False)
        outputs = write_outputs(validated_data, staging_path, input_file.stem)
        outputs["validated"] = output_file
        audit_logger.append("transformation_completed", {"outputs": {k: str(v) for k, v in outputs.items()}})
        logger.success(f"Validated data saved to {output_file}")
        return outputs

    except SchemaValidationError as err:
        report_path = REPORTS_DIR / f"{input_file.stem}_quality_report.md"
        logger.error(f"Validation failed. Generating report at {report_path}")
        audit_logger.append("validation_failed", {"error": str(err)})
        generate_dq_report(err, report_path, file_name)
        return None

    except (FileNotFoundError, ValueError) as err:
        logger.error(f"Pipeline failed during file reading: {err}")
        audit_logger.append("pipeline_error", {"error": str(err)})
        return None

    except Exception as err:  # pragma: no cover - defensive catch-all
        logger.critical(f"An unexpected error occurred: {err}")
        audit_logger.append("pipeline_error", {"error": str(err)})
        return None


if __name__ == "__main__":
    run_pipeline("dm.csv")