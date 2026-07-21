from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st


try:
    import altair as alt
except ImportError:  # pragma: no cover - optional dependency fallback
    alt = None

from project_1.data_generation.generate_large_dataset import generate_large_dataset
from project_1.pipelines.ingestion_pipeline import run_pipeline


def filter_dataset_by_study(df: pd.DataFrame, study_id: str | None) -> pd.DataFrame:
    """Return a dataset filtered by study identifier when provided."""
    if not study_id:
        return df
    return df[df["STUDYID"].astype(str).str.contains(study_id, case=False, na=False)]


def resolve_dataset_path(base_dir: str | Path | None = None) -> Path:
    """Return the default larger dataset path, generating it when needed."""
    if base_dir is None:
        base_dir = Path(__file__).resolve().parents[2]
    base_dir = Path(base_dir)
    dataset_path = base_dir / "data" / "raw" / "dm_large.csv"
    if not dataset_path.exists():
        generate_large_dataset(dataset_path, rows=1000)
    return dataset_path


def render_dashboard() -> None:
    """Render a polished clinical dashboard surface for portfolio use."""
    st.set_page_config(page_title="CDISC Safety Dashboard", layout="wide")
    st.title("Clinical Safety Monitoring Dashboard")
    st.caption(
        "A portfolio-ready workflow for ingesting, validating, and exploring "
        "clinical trial data in a CDISC-inspired context."
    )

    base_dir = Path(__file__).resolve().parents[2]
    dataset_path = resolve_dataset_path(base_dir)
    default_df = pd.read_csv(dataset_path)

    st.markdown("### Live demo data")
    st.info(
        "The dashboard now loads a larger synthetic DM-style dataset by default so the UI feels "
        "more realistic and presentation-ready."
    )

    study_filter = st.text_input("Filter by study ID", placeholder="Type a study, e.g. ABC-123")
    default_df = filter_dataset_by_study(default_df, study_filter)

    col_a, col_b, col_c = st.columns(3)
    with col_a:
        st.metric("Rows", f"{len(default_df):,}")
    with col_b:
        st.metric("Studies", default_df["STUDYID"].nunique())
    with col_c:
        st.metric("Sex distribution", f"M: {int((default_df['SEX'] == 'M').sum())}, F: {int((default_df['SEX'] == 'F').sum())}")

    uploaded_file = st.file_uploader("Upload an alternate DM CSV", type=["csv"])
    if uploaded_file is not None:
        input_path = base_dir / "data" / "raw" / uploaded_file.name
        input_path.parent.mkdir(parents=True, exist_ok=True)
        input_path.write_bytes(uploaded_file.getvalue())
        default_df = pd.read_csv(input_path)

    st.subheader("Executive summary")
    chart_col1, chart_col2 = st.columns(2)
    with chart_col1:
        sex_counts = default_df["SEX"].value_counts().reset_index()
        sex_counts.columns = ["Sex", "Count"]
        if alt is not None:
            chart = alt.Chart(sex_counts).mark_bar().encode(
                x="Sex:N",
                y="Count:Q",
                color="Sex:N",
            )
            st.altair_chart(chart, use_container_width=True)
        else:
            st.bar_chart(sex_counts.set_index("Sex"))
    with chart_col2:
        age_bins = pd.cut(default_df["AGE"], bins=[0, 30, 50, 70, 120], include_lowest=True)
        age_summary = pd.DataFrame({"Age Group": age_bins.value_counts().index, "Count": age_bins.value_counts().values})
        age_summary = age_summary.sort_values("Age Group")
        if alt is not None:
            chart = alt.Chart(age_summary).mark_bar().encode(
                x="Age Group:N",
                y="Count:Q",
                color="Age Group:N",
            )
            st.altair_chart(chart, use_container_width=True)
        else:
            st.bar_chart(age_summary.set_index("Age Group"))

    st.subheader("Preview")
    st.dataframe(default_df.head(20), use_container_width=True)

    st.subheader("Data quality snapshot")
    quality_col1, quality_col2, quality_col3 = st.columns(3)
    with quality_col1:
        st.metric("Missing age values", int(default_df["AGE"].isna().sum()))
    with quality_col2:
        st.metric("Missing race values", int(default_df["RACE"].isna().sum()))
    with quality_col3:
        st.metric("Unique subjects", default_df["USUBJID"].nunique())

    col1, col2 = st.columns(2)
    with col1:
        if st.button("Run validation and transformation", use_container_width=True):
            outputs = run_pipeline(dataset_path.name)
            if outputs is None:
                st.error("The pipeline failed validation. Review the generated report.")
            else:
                st.success("Pipeline completed successfully.")
                st.json({k: str(v) for k, v in outputs.items()})
    with col2:
        st.markdown("### Expected outputs")
        st.markdown("- Validated parquet snapshot")
        st.markdown("- SDTM DM-style parquet")
        st.markdown("- ADaM ADSL-style parquet")
        st.markdown("- Audit log")


if __name__ == "__main__":
    render_dashboard()
