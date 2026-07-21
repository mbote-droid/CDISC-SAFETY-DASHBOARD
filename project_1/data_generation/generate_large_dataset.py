from __future__ import annotations

import csv
from pathlib import Path


def generate_large_dataset(output_path: str | Path, rows: int = 1000) -> int:
    """Generate a larger synthetic DM-style CSV dataset for dashboard demos."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    study_ids = ["ABC-123", "XYZ-789", "MNO-456"]
    races = ["WHITE", "BLACK OR AFRICAN AMERICAN", "ASIAN", "AMERICAN INDIAN OR ALASKA NATIVE"]
    sexes = ["M", "F"]

    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["STUDYID", "USUBJID", "AGE", "SEX", "RACE"])
        for index in range(1, rows + 1):
            study_id = study_ids[(index - 1) % len(study_ids)]
            writer.writerow(
                [
                    study_id,
                    f"P{index:03d}",
                    20 + ((index + 3) % 60),
                    sexes[(index + 1) % len(sexes)],
                    races[(index - 1) % len(races)],
                ]
            )

    return rows
