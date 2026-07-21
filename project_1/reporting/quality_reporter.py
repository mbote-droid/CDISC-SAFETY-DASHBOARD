from __future__ import annotations

from pathlib import Path
from typing import Any


def generate_dq_report(error: Any, output_path: str | Path, source_file: str) -> Path:
    """Create a structured markdown data quality report when validation fails."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    report_lines = [
        "# Data Quality Report",
        "",
        f"Source file: {source_file}",
        "",
        "## Validation Failure",
        str(error),
        "",
        "## Recommended Actions",
        "- Review source data values for missing or out-of-range fields.",
        "- Validate the source file against the expected DM schema before reprocessing.",
        "- Re-run the pipeline after corrective actions are applied.",
        "",
        "This report was generated automatically because the validation gate failed.",
    ]
    output_path.write_text("\n".join(report_lines), encoding="utf-8")
    return output_path
