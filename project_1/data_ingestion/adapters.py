from __future__ import annotations

from pathlib import Path
from typing import Protocol

import pandas as pd


class DataReader(Protocol):
    def read(self, path: str | Path) -> pd.DataFrame:
        ...


class CSVReader:
    """Read CSV files into a pandas DataFrame."""

    def read(self, path: str | Path) -> pd.DataFrame:
        return pd.read_csv(path)


class SASReader:
    """Read SAS7BDAT files when the optional dependency is available."""

    def read(self, path: str | Path) -> pd.DataFrame:
        try:
            import pyreadstat
        except ImportError as exc:  # pragma: no cover - exercised in tests if dependency missing
            raise ImportError("pyreadstat is required to read SAS files") from exc

        data, _ = pyreadstat.read_sas7bdat(path)
        return data


def get_reader(path: str | Path) -> DataReader:
    path = Path(path)
    suffix = path.suffix.lower()
    if suffix == ".csv":
        return CSVReader()
    if suffix in {".sas7bdat", ".xpt"}:
        return SASReader()
    raise ValueError(f"Unsupported file type: {path.suffix}")
