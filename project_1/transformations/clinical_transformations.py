from __future__ import annotations

from pathlib import Path

import pandas as pd


class TransformationError(ValueError):
    """Raised when a clinical transformation cannot be completed safely."""


def build_sdtm_dm(df: pd.DataFrame) -> pd.DataFrame:
    """Create a simplified SDTM DM-like dataset from raw demographics data."""
    required = {"STUDYID", "USUBJID", "AGE", "SEX", "RACE"}
    missing = required - set(df.columns)
    if missing:
        raise TransformationError(f"Missing required columns for SDTM DM: {sorted(missing)}")

    out = df[["STUDYID", "USUBJID", "AGE", "SEX", "RACE"]].copy()
    out = out.rename(columns={"STUDYID": "STUDYID", "USUBJID": "USUBJID"})
    out["DOMAIN"] = "DM"
    out["AGEU"] = "YEARS"
    out["RACE"] = out["RACE"].astype(str).str.strip()
    return out


def build_adam_adsl(df: pd.DataFrame) -> pd.DataFrame:
    """Create a simplified ADaM ADSL-like dataset from SDTM DM-like data."""
    required = {"STUDYID", "USUBJID", "AGE", "SEX", "RACE"}
    missing = required - set(df.columns)
    if missing:
        raise TransformationError(f"Missing required columns for ADaM ADSL: {sorted(missing)}")

    out = df[["STUDYID", "USUBJID", "AGE", "SEX", "RACE"]].copy()
    out["SAFETY"] = "Y"
    out["TRT01P"] = "PLACEBO"
    return out


def write_outputs(df: pd.DataFrame, output_dir: str | Path, stem: str) -> dict[str, Path]:
    """Write SDTM and ADaM outputs to disk in a legacy-friendly layout."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    sdtm_path = output_dir / f"{stem}_sdtm_dm.parquet"
    adam_path = output_dir / f"{stem}_adam_adsl.parquet"

    sdtm_df = build_sdtm_dm(df)
    adam_df = build_adam_adsl(sdtm_df)

    sdtm_df.to_parquet(sdtm_path, index=False)
    adam_df.to_parquet(adam_path, index=False)

    return {"sdtm": sdtm_path, "adam": adam_path}
