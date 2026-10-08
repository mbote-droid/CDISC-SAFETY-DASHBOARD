"""Interactive clinical safety dashboard (Streamlit).

Run locally with:  streamlit run app/streamlit_app.py
"""

from __future__ import annotations

import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:  # allow running without installing the package (e.g. Streamlit Community Cloud)
    sys.path.insert(0, str(SRC))

import altair as alt  # noqa: E402
import pandas as pd  # noqa: E402
import streamlit as st  # noqa: E402

from cdisc_safety import __version__  # noqa: E402
from cdisc_safety.io import InputError, read_table, sha256_bytes  # noqa: E402
from cdisc_safety.pipeline import STATUS_FAILED, RunResult, outputs_zip, run  # noqa: E402
from cdisc_safety.synthetic import generate  # noqa: E402
from cdisc_safety.tables import HYS_ALT_AST_ULN, HYS_BILI_ULN  # noqa: E402

st.set_page_config(page_title="CDISC Safety Dashboard", page_icon="🩺", layout="wide")


@st.cache_data(show_spinner="Generating synthetic study and running the pipeline...")
def demo_run(n_subjects: int, seed: int, inject_errors: bool) -> RunResult:
    raw = generate(n_subjects, seed, inject_errors)
    return run({"dm": raw.dm, "ae": raw.ae, "lb": raw.lb})


@st.cache_data(show_spinner="Validating uploaded files and running the pipeline...")
def upload_run(files: tuple[tuple[str, str, bytes], ...]) -> tuple[RunResult | None, list[str]]:
    frames: dict[str, pd.DataFrame | None] = {"dm": None, "ae": None, "lb": None}
    hashes, errors, messages = {}, {}, []
    for domain, name, data in files:
        try:
            frames[domain] = read_table(data, name, domain)
            hashes[domain] = sha256_bytes(data)
        except InputError as exc:
            errors[domain] = str(exc)
            messages.append(str(exc))
    if frames["dm"] is None:
        return None, messages or ["A demographics (DM) file is required."]
    return run(frames, None, hashes, errors), messages


@st.cache_data(show_spinner=False)
def raw_zip(n_subjects: int, seed: int, inject_errors: bool) -> bytes:
    import io
    import zipfile

    raw = generate(n_subjects, seed, inject_errors)
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, df in (("dm_raw.csv", raw.dm), ("ae_raw.csv", raw.ae), ("lb_raw.csv", raw.lb)):
            zf.writestr(name, df.to_csv(index=False))
    return buffer.getvalue()


@st.cache_data(show_spinner="Packaging outputs...")
def zipped(_result: RunResult, key: str) -> bytes:
    return outputs_zip(_result)


def visible(df: pd.DataFrame) -> pd.DataFrame:
    return df.loc[:, [c for c in df.columns if not str(c).startswith("_")]]


def sidebar() -> RunResult | None:
    st.sidebar.title("CDISC Safety Dashboard")
    st.sidebar.caption(f"v{__version__} · SDTM · ADaM · safety analytics")
    source = st.sidebar.radio("Data source", ["Synthetic demo study", "Upload raw files"])
    if source == "Synthetic demo study":
        n = st.sidebar.slider("Subjects", 30, 1500, 300, step=30)
        seed = st.sidebar.number_input("Random seed", 0, 1_000_000, 42)
        faults = st.sidebar.checkbox(
            "Inject data-entry faults",
            help="Adds an impossible age, a duplicate subject, an orphan AE, a bad date and more, to show the data-quality layer.",
        )
        st.sidebar.download_button(
            "Download these raw files (upload template)",
            data=raw_zip(int(n), int(seed), faults),
            file_name="raw_template.zip",
            mime="application/zip",
        )
        return demo_run(int(n), int(seed), faults)

    st.sidebar.markdown("Upload EDC-style exports (CSV or Parquet). DM is required; AE and LB are optional.")
    uploads = {
        "dm": st.sidebar.file_uploader("Demographics (dm_raw)", type=["csv", "parquet"]),
        "ae": st.sidebar.file_uploader("Adverse events (ae_raw)", type=["csv", "parquet"]),
        "lb": st.sidebar.file_uploader("Laboratory (lb_raw)", type=["csv", "parquet"]),
    }
    with st.sidebar.expander("Required columns"):
        st.markdown(
            "- **DM**: SUBJID, SITEID, AGE, SEX, RACE, ARMCD (PBO/DRGA50/DRGA100), ARM, TRTSDT, TRTEDT\n"
            "- **AE**: SUBJID, AEDECOD, AEBODSYS, AESTDT, AETOXGR, AESER\n"
            "- **LB**: SUBJID, VISITNUM, VISIT, LBDT, LBTESTCD, LBORRES, LBORNRLO, LBORNRHI\n\n"
            "Dates must be ISO 8601 (YYYY-MM-DD). Use *Synthetic demo study* and download the raw files for a template."
        )
    if uploads["dm"] is None:
        st.info("Upload at least a demographics file, or switch to the synthetic demo study.")
        return None
    files = tuple((d, f.name, f.getvalue()) for d, f in uploads.items() if f is not None)
    result, messages = upload_run(files)
    for m in messages:
        st.sidebar.error(m)
    return result


def header(result: RunResult) -> None:
    adsl, overview = result.adam["ADSL"], result.tables.get("teae_overview", pd.DataFrame())
    n = int(adsl["SAFFL"].eq("Y").sum())

    def total(cat: str) -> int:
        row = overview[overview["Category"].eq(cat)] if not overview.empty else overview
        return int(row["_n_Total"].iloc[0]) if not row.empty else 0

    cols = st.columns(6)
    cols[0].metric("Safety population", f"{n:,}")
    cols[1].metric("Any TEAE", f"{100 * total('Any TEAE') / n:.1f}%" if n else "-")
    cols[2].metric("Serious TEAE", total("Any serious TEAE"))
    cols[3].metric("Grade ≥3 TEAE", total("Any grade >=3 TEAE"))
    cols[4].metric("Deaths", total("TEAE leading to death"))
    hys = result.tables.get("hys_law", pd.DataFrame())
    cols[5].metric("Potential Hy's law", int(hys["Potential Hy's law"].sum()) if not hys.empty else 0)
    if result.status != "PASSED":
        f = result.manifest.get("findings", {})
        st.warning(
            f"Run status: **{result.status}**: {f.get('ERROR', 0)} error and {f.get('WARNING', 0)} warning rule(s) fired. See *Data quality*."
        )
    else:
        st.success("Run status: **PASSED**. All data-quality and conformance rules passed.")


def tab_adverse_events(result: RunResult) -> None:
    st.subheader("Treatment-emergent adverse events (TEAE)")
    st.caption(
        "Subjects with at least one event, n (%), safety population. Treatment-emergent: onset from first dose to 30 days after last dose."
    )
    st.dataframe(visible(result.tables["teae_overview"]), hide_index=True, width="stretch")

    adae = result.adam["ADAE"]
    teae = adae[adae["TRTEMFL"].eq("Y")] if not adae.empty else adae
    if teae.empty:
        st.info("No treatment-emergent adverse events in this dataset.")
        return
    n = result.adam["ADSL"].query("SAFFL == 'Y'").groupby("TRT01A")["USUBJID"].nunique()
    top_n = st.slider("Preferred terms to show", 5, 25, 12)
    counts = teae.groupby(["AEDECOD", "TRTA"])["USUBJID"].nunique().reset_index(name="Subjects")
    counts["Percent"] = 100 * counts["Subjects"] / counts["TRTA"].map(n)
    top = counts.groupby("AEDECOD")["Subjects"].sum().nlargest(top_n).index
    chart = (
        alt.Chart(counts[counts["AEDECOD"].isin(top)])
        .mark_bar()
        .encode(
            y=alt.Y("AEDECOD:N", sort=list(top), title=None),
            x=alt.X("Percent:Q", title="Subjects (%)"),
            color=alt.Color("TRTA:N", title="Arm"),
            yOffset="TRTA:N",
            tooltip=["AEDECOD", "TRTA", "Subjects", alt.Tooltip("Percent:Q", format=".1f")],
        )
        .properties(height=28 * top_n)
    )
    st.altair_chart(chart, width="stretch")

    st.subheader("Risk difference versus placebo")
    st.caption("Active minus placebo incidence, percentage points, with Newcombe hybrid-score 95% confidence intervals.")
    rd = result.tables["risk_differences"]
    if not rd.empty:
        arm = st.selectbox("Active arm", sorted(rd["Arm"].unique()), index=len(rd["Arm"].unique()) - 1)
        sub = rd[rd["Arm"].eq(arm) & ((rd["n_active"] + rd["n_control"]) >= 3)].sort_values("Diff", ascending=False)
        base = alt.Chart(sub).encode(y=alt.Y("PT:N", sort=list(sub["PT"]), title=None))
        forest = (
            base.mark_rule().encode(x=alt.X("Lower:Q", title="Risk difference (percentage points)"), x2="Upper:Q")
            + base.mark_point(filled=True, size=60).encode(
                x="Diff:Q",
                tooltip=[
                    "PT",
                    alt.Tooltip("Diff:Q", format=".1f"),
                    alt.Tooltip("Lower:Q", format=".1f"),
                    alt.Tooltip("Upper:Q", format=".1f"),
                    "n_active",
                    "n_control",
                ],
            )
            + alt.Chart(pd.DataFrame({"x": [0]})).mark_rule(strokeDash=[4, 4]).encode(x="x:Q")
        )
        st.altair_chart(forest.properties(height=max(200, 22 * len(sub))), width="stretch")

    st.subheader("TEAEs by system organ class and preferred term")
    soc_pt = visible(result.tables["teae_soc_pt"]).copy()
    query = st.text_input("Search SOC or preferred term")
    if query:
        mask = soc_pt["SOC"].str.contains(query, case=False, na=False) | soc_pt["PT"].str.contains(query, case=False, na=False)
        soc_pt = soc_pt[mask]
    soc_pt["PT"] = soc_pt["PT"].replace("", "— any term in SOC —")
    st.dataframe(soc_pt, hide_index=True, width="stretch")


def tab_labs(result: RunResult) -> None:
    adlb = result.adam["ADLB"]
    if adlb.empty:
        st.info("No laboratory data in this dataset.")
        return
    st.subheader("Hepatic safety: eDISH plot")
    st.caption(
        f"Peak post-baseline values as multiples of the upper limit of normal. Potential Hy's law: ALT or AST ≥{HYS_ALT_AST_ULN:g}×ULN with bilirubin ≥{HYS_BILI_ULN:g}×ULN."
    )
    hys = result.tables["hys_law"].dropna(subset=["Peak ALT/AST xULN", "Peak bilirubin xULN"])
    if not hys.empty:
        scale = alt.Scale(type="log", domain=[0.1, 20])
        points = (
            alt.Chart(hys)
            .mark_circle(size=70, opacity=0.8)
            .encode(
                x=alt.X("Peak ALT/AST xULN:Q", scale=scale, title="Peak ALT or AST (×ULN)"),
                y=alt.Y("Peak bilirubin xULN:Q", scale=scale, title="Peak total bilirubin (×ULN)"),
                color=alt.Color("TRTA:N", title="Arm"),
                shape=alt.Shape("Potential Hy's law:N"),
                tooltip=[
                    "USUBJID",
                    "TRTA",
                    alt.Tooltip("Peak ALT/AST xULN:Q", format=".2f"),
                    alt.Tooltip("Peak bilirubin xULN:Q", format=".2f"),
                ],
            )
        )
        vline = alt.Chart(pd.DataFrame({"x": [HYS_ALT_AST_ULN]})).mark_rule(strokeDash=[4, 4]).encode(x="x:Q")
        hline = alt.Chart(pd.DataFrame({"y": [HYS_BILI_ULN]})).mark_rule(strokeDash=[4, 4]).encode(y="y:Q")
        st.altair_chart((points + vline + hline).properties(height=420), width="stretch")
        flagged = hys[hys["Potential Hy's law"]]
        if not flagged.empty:
            st.error(f"{len(flagged)} subject(s) meet potential Hy's law criteria and need medical review.")
            st.dataframe(flagged, hide_index=True, width="stretch")

    st.subheader("Mean change from baseline")
    change = result.tables["lab_mean_change"]
    if not change.empty:
        param = st.selectbox("Parameter", sorted(change["PARAM"].unique()))
        sub = change[change["PARAM"].eq(param)].copy()
        sub["lo"] = sub["Mean CHG"] - 1.96 * sub["SE"]
        sub["hi"] = sub["Mean CHG"] + 1.96 * sub["SE"]
        base = alt.Chart(sub).encode(x=alt.X("AVISITN:O", title="Visit number"), color=alt.Color("TRTA:N", title="Arm"))
        st.altair_chart(
            (
                base.mark_line(point=True).encode(y=alt.Y("Mean CHG:Q", title="Mean change (95% CI)"))
                + base.mark_errorbar().encode(y="lo:Q", y2="hi:Q")
            ).properties(height=320),
            width="stretch",
        )

    st.subheader("Shift from baseline to worst post-baseline")
    shift = result.tables["lab_shift"]
    if not shift.empty:
        param = st.selectbox("Shift parameter", sorted(shift["PARAMCD"].unique()), key="shift_param")
        pivot = shift[shift["PARAMCD"].eq(param)].pivot_table(
            index=["TRTA", "BNRIND"], columns="Worst post-baseline", values="Subjects", fill_value=0
        )
        st.dataframe(pivot, width="stretch")


def tab_quality(result: RunResult) -> None:
    st.subheader("Data-quality and conformance findings")
    findings = result.findings
    if findings.empty:
        st.success("No findings: every cleaning and conformance rule passed.")
    else:
        st.dataframe(findings, hide_index=True, width="stretch")
    if result.quarantine:
        st.subheader("Quarantined records")
        st.caption("Records that could not be mapped safely. They are excluded from analysis and kept here with the reason.")
        for name, df in result.quarantine.items():
            with st.expander(f"{name.upper()}: {len(df)} record(s)"):
                st.dataframe(df, hide_index=True, width="stretch")


def tab_datasets(result: RunResult) -> None:
    st.subheader("Datasets")
    choice = st.selectbox("Dataset", [*result.sdtm.keys(), *result.adam.keys()])
    df = result.sdtm.get(choice, result.adam.get(choice))
    st.caption(f"{len(df):,} records × {df.shape[1]} variables")
    st.dataframe(df.head(500), hide_index=True, width="stretch")
    st.caption(
        "Package every output: SDTM and ADaM as SAS XPT v5, Parquet and CSV; safety tables; findings; define metadata; manifest."
    )
    key = f"zip_{result.run_id}"
    if st.button("Prepare download package", width="stretch"):
        st.session_state[key] = zipped(result, result.run_id)
    if key in st.session_state:
        st.download_button(
            "Download ZIP",
            data=st.session_state[key],
            file_name=f"cdisc_safety_{result.run_id}.zip",
            mime="application/zip",
            width="stretch",
        )
    with st.expander("Run manifest"):
        st.json({k: v for k, v in result.manifest.items() if k != "outputs"})


def main() -> None:
    try:
        result = sidebar()
    except Exception as exc:  # noqa: BLE001 - never show a stack trace to the user
        st.error(f"Could not process the data: {exc}")
        return
    st.title("Clinical trial safety dashboard")
    st.caption(
        "Raw EDC-style data → cleaned → SDTM (DM, AE, LB) → ADaM (ADSL, ADAE, ADLB) → safety tables. Synthetic data only; not for clinical decisions."
    )
    if result is None:
        return
    if result.status == STATUS_FAILED:
        st.error(f"The run failed: {result.message}")
        if not result.findings.empty:
            st.dataframe(result.findings, hide_index=True, width="stretch")
        return
    header(result)
    tabs = st.tabs(["Adverse events", "Laboratory", "Demographics", "Data quality", "Datasets & downloads"])
    sections = (
        (tabs[0], tab_adverse_events),
        (tabs[1], tab_labs),
        (tabs[2], lambda r: st.dataframe(r.tables["demographics"], hide_index=True, width="stretch")),
        (tabs[3], tab_quality),
        (tabs[4], tab_datasets),
    )
    for tab, render in sections:
        with tab:
            try:
                render(result)
            except Exception as exc:  # noqa: BLE001 - one broken view must not take down the others
                st.error(f"This view could not be rendered: {exc}")


main()
