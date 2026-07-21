import pandas as pd


class DemographicsSchema:
    """Compatibility validator for DM-style demographics data."""

    REQUIRED_COLUMNS = {"STUDYID", "USUBJID", "AGE", "SEX", "RACE"}

    @classmethod
    def validate(cls, df: pd.DataFrame, lazy: bool = True) -> pd.DataFrame:
        missing_columns = cls.REQUIRED_COLUMNS - set(df.columns)
        if missing_columns:
            raise ValueError(f"Missing required columns: {sorted(missing_columns)}")

        validated = df.copy()
        validated["AGE"] = pd.to_numeric(validated["AGE"], errors="raise").astype(int)
        validated["SEX"] = validated["SEX"].astype(str).str.strip().str.upper()
        validated["RACE"] = validated["RACE"].astype(str).str.strip()

        if (validated["AGE"] < 0).any() or (validated["AGE"] > 120).any():
            raise ValueError("AGE must be between 0 and 120")
        if validated["RACE"].eq("").any() or validated["RACE"].isna().any():
            raise ValueError("RACE cannot be empty")
        if validated["SEX"].isin(["M", "F"]).all() is False:
            raise ValueError("SEX must be 'M' or 'F'")

        return validated