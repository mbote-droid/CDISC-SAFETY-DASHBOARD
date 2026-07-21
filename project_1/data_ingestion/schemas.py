from __future__ import annotations

import pandas as pd


class SchemaValidationError(ValueError):
    """Raised when the DM dataset fails validation."""


class DMSchema:
    """Validation schema for demographics (DM) data."""

    REQUIRED_COLUMNS = {"STUDYID", "USUBJID", "AGE", "SEX", "RACE"}

    @classmethod
    def validate(cls, df: pd.DataFrame, lazy: bool = True) -> pd.DataFrame:
        del lazy
        if not isinstance(df, pd.DataFrame):
            raise SchemaValidationError("Input must be a pandas DataFrame")

        missing_columns = cls.REQUIRED_COLUMNS - set(df.columns)
        if missing_columns:
            raise SchemaValidationError(f"Missing required columns: {sorted(missing_columns)}")

        validated = df.copy()
        validated["STUDYID"] = validated["STUDYID"].astype(str).str.strip()
        validated["USUBJID"] = validated["USUBJID"].astype(str).str.strip()
        validated["SEX"] = validated["SEX"].astype(str).str.strip().str.upper()
        validated["RACE"] = validated["RACE"].astype(str).str.strip()

        try:
            validated["AGE"] = pd.to_numeric(validated["AGE"], errors="raise").astype(int)
        except (TypeError, ValueError) as exc:
            raise SchemaValidationError("AGE must contain numeric values") from exc

        if (validated["AGE"] < 0).any() or (validated["AGE"] > 120).any():
            raise SchemaValidationError("AGE must be between 0 and 120")

        invalid_sex = validated.loc[~validated["SEX"].isin(["M", "F"]), "SEX"]
        if not invalid_sex.empty:
            raise SchemaValidationError("SEX must be 'M' or 'F'")

        if validated["RACE"].eq("").any() or validated["RACE"].isna().any():
            raise SchemaValidationError("RACE cannot be empty")

        return validated
