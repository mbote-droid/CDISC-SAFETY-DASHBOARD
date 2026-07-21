from pathlib import Path

import pandas as pd

from project_1.app.dashboard import filter_dataset_by_study, resolve_dataset_path


def test_resolve_dataset_path_creates_large_dataset_when_missing(tmp_path):
    dataset_path = resolve_dataset_path(tmp_path)

    assert dataset_path == tmp_path / "data" / "raw" / "dm_large.csv"
    assert dataset_path.exists()
    assert dataset_path.stat().st_size > 0


def test_filter_dataset_by_study_returns_matching_rows():
    df = pd.DataFrame(
        {
            "STUDYID": ["ABC-123", "XYZ-789", "ABC-123"],
            "USUBJID": ["P001", "P002", "P003"],
            "AGE": [25, 40, 30],
            "SEX": ["M", "F", "M"],
            "RACE": ["WHITE", "BLACK OR AFRICAN AMERICAN", "WHITE"],
        }
    )

    filtered = filter_dataset_by_study(df, "ABC-123")

    assert filtered.shape[0] == 2
    assert filtered["USUBJID"].tolist() == ["P001", "P003"]
