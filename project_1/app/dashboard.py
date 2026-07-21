from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

from project_1.pipelines.ingestion_pipeline import run_pipeline


def render_dashboard() -> None:
    """Render a more polished clinical dashboard surface."""
    st.set_page_config(page_title="CDISC Safety Dashboard", layout="wide")
    st.title("Clinical Safety Monitoring Dashboard")
    st.caption("Secure, auditable ingestion and validation workflow for DM-style clinical data")

    uploaded_file = st.file_uploader("Upload DM CSV", type=["csv"])
    if uploaded_file is None:
        st.info("Upload a DM-style CSV to validate and transform it.")
        return

    base_dir = Path(__file__).resolve().parents[2]
    input_path = base_dir / "data" / "raw" / uploaded_file.name
    input_path.parent.mkdir(parents=True, exist_ok=True)
    input_path.write_bytes(uploaded_file.getvalue())

    df = pd.read_csv(input_path)
    st.subheader("Preview")
    st.dataframe(df.head(), use_container_width=True)

    col1, col2 = st.columns(2)
    with col1:
        if st.button("Run validation and transformation"):
            outputs = run_pipeline(uploaded_file.name)
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
