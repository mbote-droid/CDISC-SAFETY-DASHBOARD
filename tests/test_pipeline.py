import pandas as pd
import pytest

from project_1.pipelines.ingestion_pipeline import preprocess_data, run_pipeline
from project_1.reporting.audit_log import AuditLogger
from project_1.transformations.clinical_transformations import (
    build_adam_adsl,
    build_sdtm_dm,
    write_outputs,
)


@pytest.fixture
def frame_values():
    return pd.DataFrame(
        {
            "STUDYID": ["ABC"],
            "USUBJID": ["subj-001"],
            "AGE": [34],
            "SEX": ["M"],
            "RACE": [" WHITE "],
        }
    )


def test_preprocess_data_strips_whitespace(frame_values):  # pylint: disable=redefined-outer-name
    cleaned = preprocess_data(frame_values)

    assert cleaned.loc[0, "RACE"] == "WHITE"


def test_run_pipeline_writes_output(tmp_path, monkeypatch):
    data_dir = tmp_path / "data" / "raw"
    results_dir = tmp_path / "results" / "staging"
    reports_dir = tmp_path / "reports"
    data_dir.mkdir(parents=True, exist_ok=True)
    results_dir.mkdir(parents=True, exist_ok=True)
    reports_dir.mkdir(parents=True, exist_ok=True)

    input_file = data_dir / "dm.csv"
    input_file.write_text(
        "STUDYID,USUBJID,AGE,SEX,RACE\nABC,subj-001,34,M,WHITE\n",
        encoding="utf-8",
    )

    monkeypatch.setattr("project_1.pipelines.ingestion_pipeline.BASE_DIR", tmp_path)
    monkeypatch.setattr("project_1.pipelines.ingestion_pipeline.DATA_DIR", data_dir)
    monkeypatch.setattr("project_1.pipelines.ingestion_pipeline.RESULTS_DIR", results_dir)
    monkeypatch.setattr("project_1.pipelines.ingestion_pipeline.REPORTS_DIR", reports_dir)

    output_path = run_pipeline("dm.csv")

    assert output_path is not None
    assert (results_dir / "dm.parquet").exists()


def test_run_pipeline_returns_none_for_invalid_schema(tmp_path, monkeypatch):
    data_dir = tmp_path / "data" / "raw"
    results_dir = tmp_path / "results" / "staging"
    reports_dir = tmp_path / "reports"
    data_dir.mkdir(parents=True, exist_ok=True)
    results_dir.mkdir(parents=True, exist_ok=True)
    reports_dir.mkdir(parents=True, exist_ok=True)

    input_file = data_dir / "dm.csv"
    input_file.write_text(
        "STUDYID,USUBJID,AGE,SEX,RACE\nABC,subj-001,999,M,\n",
        encoding="utf-8",
    )

    monkeypatch.setattr("project_1.pipelines.ingestion_pipeline.BASE_DIR", tmp_path)
    monkeypatch.setattr("project_1.pipelines.ingestion_pipeline.DATA_DIR", data_dir)
    monkeypatch.setattr("project_1.pipelines.ingestion_pipeline.RESULTS_DIR", results_dir)
    monkeypatch.setattr("project_1.pipelines.ingestion_pipeline.REPORTS_DIR", reports_dir)

    output_path = run_pipeline("dm.csv")

    assert output_path is None
    assert (reports_dir / "dm_quality_report.md").exists()


def test_build_sdtm_dm_creates_expected_columns(frame_values):  # pylint: disable=redefined-outer-name
    sdtm = build_sdtm_dm(frame_values)

    assert "DOMAIN" in sdtm.columns
    assert sdtm.loc[0, "AGEU"] == "YEARS"


def test_build_adam_adsl_adds_safety_flags(frame_values):  # pylint: disable=redefined-outer-name
    adsl = build_adam_adsl(frame_values)

    assert adsl.loc[0, "SAFETY"] == "Y"
    assert adsl.loc[0, "TRT01P"] == "PLACEBO"


def test_write_outputs_writes_parquet_files(tmp_path, frame_values):  # pylint: disable=redefined-outer-name
    output_dir = tmp_path / "outputs"
    outputs = write_outputs(frame_values, output_dir, "dm")

    assert outputs["sdtm"].exists()
    assert outputs["adam"].exists()


def test_audit_logger_appends_json_lines(tmp_path):
    log_path = tmp_path / "audit.jsonl"
    logger = AuditLogger(log_path)
    logger.append("test_event", {"status": "ok"})

    lines = log_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    assert "test_event" in lines[0]
