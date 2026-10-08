"""Fault-tolerant reading of raw input tables."""

from __future__ import annotations

import hashlib
import io
from pathlib import Path

import pandas as pd

MAX_BYTES = 200 * 1024 * 1024  # refuse inputs larger than 200 MB
REQUIRED_RAW: dict[str, tuple[str, ...]] = {
    "dm": ("SUBJID", "SITEID", "AGE", "SEX", "RACE", "ARMCD", "ARM", "TRTSDT", "TRTEDT"),
    "ae": ("SUBJID", "AEDECOD", "AEBODSYS", "AESTDT", "AETOXGR", "AESER"),
    "lb": ("SUBJID", "VISITNUM", "VISIT", "LBDT", "LBTESTCD", "LBORRES", "LBORNRLO", "LBORNRHI"),
}


class InputError(ValueError):
    """Raised when an input file cannot be used at all (as opposed to row-level problems)."""


def sha256_bytes(data: bytes) -> str:
    """Return the SHA-256 hex digest of ``data``."""
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: str | Path) -> str:
    """Return the SHA-256 hex digest of a file, read in chunks."""
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _decode(data: bytes) -> str:
    for encoding in ("utf-8-sig", "latin-1"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise InputError("could not decode file as UTF-8 or Latin-1")  # pragma: no cover - latin-1 never fails


def read_table(data: bytes, name: str, domain: str) -> pd.DataFrame:
    """Parse CSV or Parquet bytes into a DataFrame with normalised column names.

    All values are read as strings so that type problems become row-level
    validation findings instead of crashes.
    """
    if not data:
        raise InputError(f"{name}: file is empty")
    if len(data) > MAX_BYTES:
        raise InputError(f"{name}: file is larger than {MAX_BYTES // (1024 * 1024)} MB")
    lower = name.lower()
    try:
        if lower.endswith(".parquet"):
            df = pd.read_parquet(io.BytesIO(data)).astype(str)
        else:
            df = pd.read_csv(io.StringIO(_decode(data)), dtype=str, keep_default_na=False, sep=None, engine="python")
    except InputError:
        raise
    except Exception as exc:  # noqa: BLE001 - any parser failure is an unusable file
        raise InputError(f"{name}: could not be parsed ({exc.__class__.__name__}: {exc})") from exc
    df.columns = [str(c).strip().upper() for c in df.columns]
    df = df.apply(lambda col: col.astype(str).str.strip()).replace({"nan": "", "None": "", "NaT": "", "<NA>": ""})
    missing = [c for c in REQUIRED_RAW[domain] if c not in df.columns]
    if missing:
        raise InputError(f"{name}: missing required column(s) {', '.join(missing)}")
    if df.empty and domain == "dm":
        raise InputError(f"{name}: contains no subjects")
    return df


def read_path(path: str | Path, domain: str) -> tuple[pd.DataFrame, str]:
    """Read a raw table from disk; return the frame and the file's SHA-256."""
    p = Path(path)
    if not p.is_file():
        raise InputError(f"{p.name}: file not found")
    data = p.read_bytes()
    return read_table(data, p.name, domain), sha256_bytes(data)
