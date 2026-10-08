from __future__ import annotations

import io
import json
import zipfile

import pandas as pd
import pyreadstat
import pytest

from cdisc_safety import cli, pipeline
from cdisc_safety.conformance import check_sdtm
from cdisc_safety.export import write_dataset
from cdisc_safety.findings import Findings
from cdisc_safety.io import sha256_file
from cdisc_safety.synthetic import write_raw


def test_clean_run_passes(result):
    assert result.status == pipeline.STATUS_PASSED and result.ok
    assert result.findings.empty and not result.quarantine
    assert result.manifest["records"]["DM"] == 90


def test_faulty_run_quarantines_and_reports(result_faulty):
    r = result_faulty
    assert r.status == pipeline.STATUS_WARN and r.ok
    rules = set(r.findings["rule_id"])
    assert {"DM-R02", "DM-R03", "DM-R05", "AE-R01", "AE-R02", "AE-R04", "LB-R04"} <= rules
    assert {"dm", "ae"} <= set(r.quarantine)
    assert r.sdtm["DM"]["USUBJID"].is_unique


def test_conformance_clean_outputs_have_no_errors(result):
    f = Findings()
    check_sdtm(result.sdtm, f)
    assert f.count("ERROR") == 0


def test_conformance_detects_broken_sdtm(result):
    dm = result.sdtm["DM"].copy()
    dm.loc[0, "SEX"] = "X"
    dm = pd.concat([dm, dm.iloc[[1]]])
    dm.loc[:, "DTHFL"] = "Y"
    ae = result.sdtm["AE"].copy()
    ae.loc[0, "USUBJID"] = "ghost"
    ae.loc[1, "AESTDTC"] = "10/01/2025"
    ae.loc[2, "AESEV"] = "TERRIBLE"
    ae.loc[3, "AESER"] = "?"
    ae.loc[4, "AESTDY"] = 0
    ae.loc[5, "AEOUT"] = "FATAL"
    ae.loc[5, "AESER"] = "N"
    ae.loc[6, ["AETOXGR", "AESEV"]] = [4, "MILD"]
    ae = pd.concat([ae, ae.iloc[[7]]])
    ae["LONGVARIABLE"] = 1
    lb = result.sdtm["LB"].copy()
    lb.loc[0, "LBNRIND"] = "WEIRD"
    lb.loc[lb["USUBJID"].eq(lb["USUBJID"].iloc[0]), "LBBLFL"] = ""
    f = Findings()
    check_sdtm({"DM": dm.drop(columns=["AGEU"]), "AE": ae, "LB": lb}, f)
    rules = {x.rule_id for x in f.items}
    assert {
        "SD0001",
        "SD0002",
        "SD0005",
        "SD0006",
        "SD0007",
        "SD0008",
        "DM0001",
        "DM0002",
        "DM0003",
        "AE0001",
        "AE0002",
        "AE0004",
        "AE0005",
        "LB0001",
        "LB0002",
    } <= rules


def test_missing_dm_fails():
    r = pipeline.run({"dm": None, "ae": None, "lb": None})
    assert r.status == pipeline.STATUS_FAILED and not r.ok and "required" in r.message


def test_all_dm_invalid_fails(raw):
    dm = raw.dm.head(5).copy()
    dm["AGE"] = "abc"
    r = pipeline.run({"dm": dm})
    assert r.status == pipeline.STATUS_FAILED
    assert len(r.quarantine["dm"]) == 5


def test_dm_only_run_is_usable(raw):
    r = pipeline.run({"dm": raw.dm})
    assert r.ok
    assert r.sdtm["AE"].empty and r.adam["ADAE"].empty
    assert (r.findings["rule_id"] == "PIPE-02").sum() == 2
    assert not r.tables["teae_overview"].empty


def test_stage_failure_is_isolated(monkeypatch, raw):
    def boom(*_args):
        raise RuntimeError("simulated failure")

    monkeypatch.setattr(pipeline.adam, "build_adlb", boom)
    r = pipeline.run({"dm": raw.dm, "ae": raw.ae, "lb": raw.lb})
    assert r.ok
    assert "PIPE-01" in set(r.findings["rule_id"])
    assert r.adam["ADLB"].empty and not r.adam["ADAE"].empty


def test_write_outputs_and_manifest(tmp_path, raw):
    r = pipeline.run({"dm": raw.dm, "ae": raw.ae, "lb": raw.lb}, tmp_path)
    manifest = json.loads((tmp_path / "manifest.json").read_text())
    assert manifest["status"] == pipeline.STATUS_PASSED
    for rel, digest in manifest["outputs"].items():
        assert sha256_file(tmp_path / rel) == digest
    df, meta = pyreadstat.read_xport(str(tmp_path / "adam" / "adsl.xpt"))
    assert len(df) == len(r.adam["ADSL"])
    assert meta.column_names_to_labels["SAFFL"] == "Safety Population Flag"
    assert meta.original_variable_types["TRTSDT"].startswith("DATE")
    assert all(len(c) <= 8 for c in df.columns)
    datasets = json.loads((tmp_path / "define" / "datasets.json").read_text())
    assert {d["dataset"] for d in datasets} == {"DM", "AE", "LB", "ADSL", "ADAE", "ADLB"}


def test_outputs_are_reproducible(tmp_path, raw):
    a = pipeline.run({"dm": raw.dm, "ae": raw.ae, "lb": raw.lb}, tmp_path / "a").manifest["outputs"]
    b = pipeline.run({"dm": raw.dm, "ae": raw.ae, "lb": raw.lb}, tmp_path / "b").manifest["outputs"]
    csvs = [k for k in a if k.endswith(".csv")]
    assert csvs and all(a[k] == b[k] for k in csvs)


def test_outputs_zip(result):
    data = pipeline.outputs_zip(result)
    names = zipfile.ZipFile(io.BytesIO(data)).namelist()
    assert "manifest.json" in names and "adam/adae.xpt" in names and "tables/teae_overview.csv" in names


def test_write_dataset_tolerates_bad_format(tmp_path, result):
    written = write_dataset(result.sdtm["DM"], tmp_path, "DM", formats=("csv", "nope"))
    assert set(written) == {"csv"}


def test_run_from_dir_reports_unusable_optional_file(tmp_path, raw):
    write_raw(raw, tmp_path)
    (tmp_path / "ae_raw.csv").write_text("NOT,A,VALID,AE\n1,2,3,4\n")
    r = pipeline.run_from_dir(tmp_path)
    assert r.ok
    assert "PIPE-03" in set(r.findings["rule_id"])
    assert r.sdtm["AE"].empty and not r.sdtm["LB"].empty


def test_run_from_dir_bad_dm_fails(tmp_path):
    (tmp_path / "dm_raw.csv").write_text("")
    r = pipeline.run_from_dir(tmp_path)
    assert not r.ok and "empty" in r.message


def test_cli_generate_run_and_strict(tmp_path, capsys):
    raw_dir = tmp_path / "raw"
    assert cli.main(["generate", "--out", str(raw_dir), "--subjects", "30", "--inject-errors"]) == 0
    assert cli.main(["run", "--raw", str(raw_dir), "--out", str(tmp_path / "out")]) == 0
    assert cli.main(["run", "--raw", str(raw_dir), "--out", str(tmp_path / "out2"), "--strict"]) == 2
    out = capsys.readouterr().out
    assert "PASSED WITH FINDINGS" in out and "Quarantined" in out


def test_cli_demo_and_failures(tmp_path, capsys):
    assert cli.main(["demo", "--out", str(tmp_path / "demo"), "--subjects", "30"]) == 0
    assert (tmp_path / "demo" / "manifest.json").is_file()
    assert cli.main(["run", "--raw", str(tmp_path / "nothing"), "--out", str(tmp_path / "o")]) == 1
    assert cli.main(["generate", "--subjects", "1", "--out", str(tmp_path / "g")]) == 1
    with pytest.raises(SystemExit):
        cli.main(["--version"])
    assert "required" in capsys.readouterr().out
