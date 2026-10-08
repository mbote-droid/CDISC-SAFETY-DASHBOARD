"""End-to-end pipeline: raw tables -> cleaning -> SDTM -> conformance -> ADaM -> tables -> outputs.

Fault tolerance:
* Demographics are mandatory; without usable DM the run stops with status FAILED.
* AE and LB are optional; a missing or broken table yields an empty domain and a finding.
* Bad records are quarantined with a reason, never silently dropped.
* Each stage is isolated, so a failure in one domain does not lose the others.
* Every run writes a manifest with input and output SHA-256 checksums.
"""

from __future__ import annotations

import logging
import platform
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

from cdisc_safety import __version__, adam, cleaning, sdtm, tables
from cdisc_safety.conformance import check_sdtm
from cdisc_safety.export import dataset_metadata, write_dataset, write_json
from cdisc_safety.findings import Findings
from cdisc_safety.io import InputError, sha256_bytes, sha256_file

log = logging.getLogger(__name__)

STATUS_PASSED = "PASSED"
STATUS_WARN = "PASSED WITH FINDINGS"
STATUS_FAILED = "FAILED"


@dataclass
class RunResult:
    """Everything produced by one pipeline run."""

    run_id: str
    status: str
    message: str = ""
    sdtm: dict[str, pd.DataFrame] = field(default_factory=dict)
    adam: dict[str, pd.DataFrame] = field(default_factory=dict)
    tables: dict[str, pd.DataFrame] = field(default_factory=dict)
    quarantine: dict[str, pd.DataFrame] = field(default_factory=dict)
    findings: pd.DataFrame = field(default_factory=pd.DataFrame)
    manifest: dict = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        """True unless the run failed outright."""
        return self.status != STATUS_FAILED


def _stage(name: str, findings: Findings, func, *args, default=None):
    """Run one stage; on an unexpected error record a finding and return ``default``."""
    try:
        return func(*args)
    except Exception as exc:  # noqa: BLE001 - isolation boundary between stages
        log.exception("stage %s failed", name)
        findings.add("PIPE-01", name, "ERROR", f"Stage failed and was skipped: {exc.__class__.__name__}: {exc}", count=1)
        return default


def run(
    raw: dict[str, pd.DataFrame | None],
    out_dir: str | Path | None = None,
    input_hashes: dict[str, str] | None = None,
    input_errors: dict[str, str] | None = None,
) -> RunResult:
    """Run the pipeline on raw tables keyed 'dm', 'ae' and 'lb'."""
    run_id = uuid.uuid4().hex[:12]
    started = datetime.now(UTC)
    findings = Findings()
    for domain, err in (input_errors or {}).items():
        findings.add("PIPE-03", domain.upper(), "ERROR", f"Input file unusable and skipped: {err}", count=1)
    dm_raw = raw.get("dm")
    if dm_raw is None or dm_raw.empty:
        return RunResult(run_id, STATUS_FAILED, "Demographics (DM) are required and were not provided or are empty.")

    dm_clean, q_dm = cleaning.clean_dm(dm_raw, findings)
    if dm_clean.empty:
        res = RunResult(run_id, STATUS_FAILED, "No valid subjects remained after cleaning demographics.")
        res.findings = findings.to_frame()
        res.quarantine = {"dm": q_dm}
        return res
    subjects = set(dm_clean["SUBJID"])

    empty = pd.DataFrame()
    ae_raw, lb_raw = raw.get("ae"), raw.get("lb")
    if ae_raw is None and "ae" not in (input_errors or {}):
        findings.add("PIPE-02", "AE", "NOTE", "No adverse-event table provided; AE outputs are empty", count=1)
    if lb_raw is None and "lb" not in (input_errors or {}):
        findings.add("PIPE-02", "LB", "NOTE", "No laboratory table provided; lab outputs are empty", count=1)
    ae_clean, q_ae = (
        _stage("AE", findings, cleaning.clean_ae, ae_raw, subjects, findings, default=(empty, empty))
        if ae_raw is not None
        else (empty, empty)
    )
    lb_clean, q_lb = (
        _stage("LB", findings, cleaning.clean_lb, lb_raw, subjects, findings, default=(empty, empty))
        if lb_raw is not None
        else (empty, empty)
    )

    dm_s = sdtm.build_dm(dm_clean)
    ae_s = (
        _stage("AE", findings, sdtm.build_ae, ae_clean, dm_s, default=pd.DataFrame(columns=sdtm.AE_VARS))
        if not ae_clean.empty
        else pd.DataFrame(columns=sdtm.AE_VARS)
    )
    lb_s = (
        _stage("LB", findings, sdtm.build_lb, lb_clean, dm_s, default=pd.DataFrame(columns=sdtm.LB_VARS))
        if not lb_clean.empty
        else pd.DataFrame(columns=sdtm.LB_VARS)
    )
    sdtm_sets = {"DM": dm_s, "AE": ae_s, "LB": lb_s}
    _stage("CONFORMANCE", findings, check_sdtm, sdtm_sets, findings)

    adsl = adam.build_adsl(dm_s, dm_clean)
    adae = _stage("ADAE", findings, adam.build_adae, ae_s, adsl, default=pd.DataFrame(columns=adam.ADAE_VARS))
    adlb = _stage("ADLB", findings, adam.build_adlb, lb_s, adsl, default=pd.DataFrame(columns=adam.ADLB_VARS))
    adam_sets = {"ADSL": adsl, "ADAE": adae, "ADLB": adlb}

    table_builders = {
        "demographics": (tables.demographics, (adsl,)),
        "teae_overview": (tables.teae_overview, (adsl, adae)),
        "teae_soc_pt": (tables.teae_by_soc_pt, (adsl, adae)),
        "risk_differences": (tables.risk_differences, (adsl, adae)),
        "lab_shift": (tables.lab_shift, (adlb,)),
        "hys_law": (tables.hys_law, (adlb,)),
        "lab_mean_change": (tables.lab_mean_change, (adlb,)),
    }
    table_sets = {
        name: _stage(f"TABLE:{name}", findings, fn, *args, default=pd.DataFrame()) for name, (fn, args) in table_builders.items()
    }

    findings_df = findings.to_frame()
    quarantine = {k: v for k, v in {"dm": q_dm, "ae": q_ae, "lb": q_lb}.items() if not v.empty}
    status = STATUS_WARN if (findings.count("ERROR") or findings.count("WARNING") or quarantine) else STATUS_PASSED

    manifest = {
        "run_id": run_id,
        "tool": "cdisc-safety-dashboard",
        "version": __version__,
        "python": platform.python_version(),
        "pandas": pd.__version__,
        "started_utc": started.isoformat(),
        "finished_utc": datetime.now(UTC).isoformat(),
        "status": status,
        "inputs": input_hashes or {k: sha256_bytes(v.to_csv(index=False).encode()) for k, v in raw.items() if v is not None},
        "records": {**{k: int(len(v)) for k, v in sdtm_sets.items()}, **{k: int(len(v)) for k, v in adam_sets.items()}},
        "quarantined": {k: int(len(v)) for k, v in quarantine.items()},
        "findings": {s: findings.count(s) for s in ("ERROR", "WARNING", "NOTE")},
        "outputs": {},
    }
    result = RunResult(run_id, status, "", sdtm_sets, adam_sets, table_sets, quarantine, findings_df, manifest)
    if out_dir is not None:
        write_outputs(result, Path(out_dir))
    return result


def write_outputs(result: RunResult, out: Path) -> None:
    """Write every dataset, table, report and the manifest under ``out``."""
    outputs: dict[str, str] = {}
    for group, sets in (("sdtm", result.sdtm), ("adam", result.adam)):
        for name, df in sets.items():
            for path in write_dataset(df, out / group, name).values():
                outputs[f"{group}/{path.name}"] = sha256_file(path)
    for name, df in result.tables.items():
        path = out / "tables" / f"{name}.csv"
        path.parent.mkdir(parents=True, exist_ok=True)
        df.loc[:, [c for c in df.columns if not str(c).startswith("_")]].to_csv(path, index=False)
        outputs[f"tables/{path.name}"] = sha256_file(path)
    reports = out / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    result.findings.to_csv(reports / "findings.csv", index=False)
    outputs["reports/findings.csv"] = sha256_file(reports / "findings.csv")
    for name, df in result.quarantine.items():
        path = reports / f"quarantine_{name}.csv"
        df.to_csv(path, index=False)
        outputs[f"reports/{path.name}"] = sha256_file(path)
    meta_path = write_json(dataset_metadata({**result.sdtm, **result.adam}), out / "define" / "datasets.json")
    outputs["define/datasets.json"] = sha256_file(meta_path)
    result.manifest["outputs"] = outputs
    write_json(result.manifest, out / "manifest.json")


def run_from_dir(raw_dir: str | Path, out_dir: str | Path | None = None) -> RunResult:
    """Read dm_raw/ae_raw/lb_raw (CSV or Parquet) from a directory and run the pipeline."""
    from cdisc_safety.io import read_path

    raw_dir = Path(raw_dir)
    frames: dict[str, pd.DataFrame | None] = {}
    hashes: dict[str, str] = {}
    errors: dict[str, str] = {}
    for domain in ("dm", "ae", "lb"):
        candidates = [raw_dir / f"{domain}_raw.csv", raw_dir / f"{domain}_raw.parquet", raw_dir / f"{domain}.csv"]
        path = next((p for p in candidates if p.is_file()), None)
        if path is None:
            frames[domain] = None
            continue
        try:
            frames[domain], hashes[domain] = read_path(path, domain)
        except InputError as exc:
            if domain == "dm":
                return RunResult(uuid.uuid4().hex[:12], STATUS_FAILED, str(exc))
            log.warning("%s", exc)
            errors[domain] = str(exc)
            frames[domain] = None
    return run(frames, out_dir, hashes, errors)


def outputs_zip(result: RunResult) -> bytes:
    """Write all outputs to a temporary directory and return them as a ZIP archive."""
    import io
    import tempfile
    import zipfile

    buffer = io.BytesIO()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        write_outputs(result, root)
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            for path in sorted(root.rglob("*")):
                if path.is_file():
                    zf.write(path, path.relative_to(root).as_posix())
    return buffer.getvalue()
