"""Writing datasets as Parquet, CSV and SAS v5 transport (XPT) with dataset metadata."""

from __future__ import annotations

import json
import logging
from pathlib import Path

import numpy as np
import pandas as pd

from cdisc_safety.terminology import LABELS

log = logging.getLogger(__name__)
SAS_EPOCH = pd.Timestamp("1960-01-01")

DATASET_LABELS = {
    "DM": "Demographics",
    "AE": "Adverse Events",
    "LB": "Laboratory Test Results",
    "ADSL": "Subject-Level Analysis Dataset",
    "ADAE": "Adverse Event Analysis Dataset",
    "ADLB": "Laboratory Analysis Dataset",
}


def _for_xpt(df: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, str]]:
    """Convert dates to SAS date numbers and nullable types to plain numpy types."""
    out = df.copy()
    formats: dict[str, str] = {}
    for col in out.columns:
        series = out[col]
        if pd.api.types.is_datetime64_any_dtype(series):
            out[col] = (series - SAS_EPOCH).dt.days.astype(float)
            formats[col] = "DATE9"
        elif pd.api.types.is_bool_dtype(series):
            out[col] = np.where(series, "Y", "")
        elif pd.api.types.is_numeric_dtype(series):
            out[col] = pd.to_numeric(series, errors="coerce").astype(float)
        else:
            out[col] = series.astype(object).where(series.notna(), "").astype(str)
    return out, formats


def write_xpt(df: pd.DataFrame, path: Path, name: str) -> None:
    """Write a SAS version 5 transport file, as required for FDA submissions."""
    import pyreadstat  # imported lazily: optional at runtime, required for XPT output

    data, formats = _for_xpt(df)
    labels = [LABELS.get(c, c)[:40] for c in data.columns]
    pyreadstat.write_xport(
        data,
        str(path),
        file_label=DATASET_LABELS.get(name, name)[:40],
        column_labels=labels,
        table_name=name[:8],
        file_format_version=5,
        variable_format=formats or None,
    )


def write_dataset(
    df: pd.DataFrame, out_dir: Path, name: str, formats: tuple[str, ...] = ("parquet", "csv", "xpt")
) -> dict[str, Path]:
    """Write one dataset in each requested format; a failing format is logged, not fatal."""
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = name.lower()
    written: dict[str, Path] = {}
    for fmt in formats:
        path = out_dir / f"{stem}.{fmt}"
        try:
            if fmt == "parquet":
                df.to_parquet(path, index=False)
            elif fmt == "csv":
                df.to_csv(path, index=False)
            elif fmt == "xpt":
                write_xpt(df, path, name)
            else:
                raise ValueError(f"unknown format {fmt}")
            written[fmt] = path
        except Exception as exc:  # noqa: BLE001 - one bad format must not lose the others
            log.warning("could not write %s as %s: %s", name, fmt, exc)
    return written


def dataset_metadata(datasets: dict[str, pd.DataFrame]) -> list[dict]:
    """Define-XML-style metadata (a lightweight JSON equivalent) for each dataset."""
    meta = []
    for name, df in datasets.items():
        meta.append(
            {
                "dataset": name,
                "label": DATASET_LABELS.get(name, name),
                "records": int(len(df)),
                "variables": [
                    {
                        "name": c,
                        "label": LABELS.get(c, ""),
                        "type": "Num"
                        if pd.api.types.is_numeric_dtype(df[c]) or pd.api.types.is_datetime64_any_dtype(df[c])
                        else "Char",
                    }
                    for c in df.columns
                ],
            }
        )
    return meta


def write_json(obj, path: Path) -> Path:
    """Write JSON with stable formatting."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, default=str), encoding="utf-8")
    return path
