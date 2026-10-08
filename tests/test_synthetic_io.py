from __future__ import annotations

import io

import pandas as pd
import pytest

from cdisc_safety import io as cio
from cdisc_safety.synthetic import generate, write_raw


def test_generate_is_deterministic():
    a, b = generate(30, seed=1), generate(30, seed=1)
    pd.testing.assert_frame_equal(a.dm, b.dm)
    pd.testing.assert_frame_equal(a.ae, b.ae)
    pd.testing.assert_frame_equal(a.lb, b.lb)


def test_generate_differs_by_seed():
    assert not generate(30, seed=1).ae.equals(generate(30, seed=2).ae)


def test_generate_balanced_arms_and_ranges(raw):
    counts = raw.dm["ARMCD"].value_counts()
    assert set(counts.index) == {"PBO", "DRGA50", "DRGA100"}
    assert counts.max() - counts.min() <= 1
    assert raw.dm["AGE"].between(18, 85).all()
    assert raw.ae["AETOXGR"].between(1, 5).all()


def test_generate_rejects_too_few_subjects():
    with pytest.raises(ValueError):
        generate(2)


def test_inject_errors_adds_faults(raw_faulty):
    assert (raw_faulty.dm["AGE"] == 150).any()
    assert raw_faulty.dm["SUBJID"].duplicated().any()
    assert "999-9999" in set(raw_faulty.ae["SUBJID"])
    assert "<5" in set(raw_faulty.lb["LBORRES"])


def test_write_raw(tmp_path, raw):
    paths = write_raw(raw, tmp_path)
    assert {p.name for p in paths.values()} == {"dm_raw.csv", "ae_raw.csv", "lb_raw.csv"}
    assert len(pd.read_csv(paths["dm"])) == len(raw.dm)


def _csv(df: pd.DataFrame, **kw) -> bytes:
    return df.to_csv(index=False, **kw).encode()


def test_read_table_csv_normalises_columns(raw):
    df = raw.dm.rename(columns=str.lower)
    out = cio.read_table(_csv(df), "dm.csv", "dm")
    assert "SUBJID" in out.columns
    assert out["AGE"].map(type).eq(str).all()


def test_read_table_semicolon_and_latin1(raw):
    data = raw.dm.head(5).to_csv(index=False, sep=";").encode("latin-1")
    assert len(cio.read_table(data, "dm.csv", "dm")) == 5


def test_read_table_parquet(raw):
    buf = io.BytesIO()
    raw.lb.head(10).to_parquet(buf)
    out = cio.read_table(buf.getvalue(), "lb.parquet", "lb")
    assert len(out) == 10
    assert not out.isin(["nan", "None"]).any().any()


@pytest.mark.parametrize(
    ("data", "match"),
    [
        (b"", "empty"),
        (b"\x00\x01\x02 not a table", "missing required"),
        (b"SUBJID,AGE\n1,30\n", "missing required"),
    ],
)
def test_read_table_errors(data, match):
    with pytest.raises(cio.InputError, match=match):
        cio.read_table(data, "dm.csv", "dm")


def test_read_table_unparseable_parquet():
    with pytest.raises(cio.InputError, match="could not be parsed"):
        cio.read_table(b"not parquet", "x.parquet", "dm")


def test_read_table_no_subjects(raw):
    with pytest.raises(cio.InputError, match="no subjects"):
        cio.read_table(_csv(raw.dm.head(0)), "dm.csv", "dm")


def test_read_table_size_limit(monkeypatch, raw):
    monkeypatch.setattr(cio, "MAX_BYTES", 10)
    with pytest.raises(cio.InputError, match="larger than"):
        cio.read_table(_csv(raw.dm), "dm.csv", "dm")


def test_read_path(tmp_path, raw):
    with pytest.raises(cio.InputError, match="not found"):
        cio.read_path(tmp_path / "missing.csv", "dm")
    p = tmp_path / "dm.csv"
    p.write_bytes(_csv(raw.dm))
    df, digest = cio.read_path(p, "dm")
    assert len(df) == len(raw.dm)
    assert digest == cio.sha256_file(p) == cio.sha256_bytes(p.read_bytes())


def test_treatment_end_never_precedes_start():
    for seed in range(5):
        dm = generate(600, seed=seed).dm
        assert (pd.to_datetime(dm["TRTEDT"]) >= pd.to_datetime(dm["TRTSDT"])).all()
