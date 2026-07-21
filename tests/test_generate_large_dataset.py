from pathlib import Path

from project_1.data_generation.generate_large_dataset import generate_large_dataset


def test_generate_large_dataset_creates_expected_file(tmp_path):
    output_path = tmp_path / "dm_large.csv"

    rows_written = generate_large_dataset(output_path, rows=50)

    assert rows_written == 50
    assert output_path.exists()

    with output_path.open(encoding="utf-8") as handle:
        content = handle.read().splitlines()

    assert len(content) == 51
    assert content[0] == "STUDYID,USUBJID,AGE,SEX,RACE"
