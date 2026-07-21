import pandas as pd
import pytest

from project_1.data_ingestion.adapters import CSVReader, SASReader, get_reader
from project_1.data_ingestion.schemas import DM_SCHEMA
from project_1.reporting.quality_reporter import generate_dq_report


def test_csv_reader_reads_csv(tmp_path):
    csv_path = tmp_path / "dm.csv"
    csv_path.write_text(
        "STUDYID,USUBJID,AGE,SEX,RACE\nABC,subj-001,34,M,WHITE\n",
        encoding="utf-8",
    )

    reader = CSVReader()
    df = reader.read(csv_path)

    assert list(df.columns) == ["STUDYID", "USUBJID", "AGE", "SEX", "RACE"]
    assert df.loc[0, "USUBJID"] == "subj-001"


def test_get_reader_returns_csv_reader_for_csv_files(tmp_path):
    csv_path = tmp_path / "dm.csv"
    csv_path.write_text("a,b\n1,2\n", encoding="utf-8")

    reader = get_reader(csv_path)

    assert isinstance(reader, CSVReader)


def test_dm_schema_validates_expected_columns():
    df = pd.DataFrame(
        {
            "STUDYID": ["ABC"],
            "USUBJID": ["subj-001"],
            "AGE": [34],
            "SEX": ["M"],
            "RACE": ["WHITE"],
        }
    )

    validated = DM_SCHEMA.validate(df, lazy=True)

    assert validated.shape[0] == 1
    assert validated.loc[0, "SEX"] == "M"


def test_get_reader_raises_for_unsupported_file_type(tmp_path):
    file_path = tmp_path / "notes.txt"
    file_path.write_text("hello", encoding="utf-8")

    with pytest.raises(ValueError):
        get_reader(file_path)


def test_sas_reader_requires_pyreadstat(monkeypatch):
    monkeypatch.setitem(__import__("sys").modules, "pyreadstat", None)

    with pytest.raises(ImportError):
        SASReader().read("dummy.sas7bdat")


def test_generate_dq_report_writes_markdown(tmp_path):
    report_path = generate_dq_report("schema failed", tmp_path / "report.md", "dm.csv")

    assert report_path.exists()
    assert "Data Quality Report" in report_path.read_text(encoding="utf-8")
