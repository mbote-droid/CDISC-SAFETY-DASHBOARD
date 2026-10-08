from __future__ import annotations

import pytest

from cdisc_safety.pipeline import run
from cdisc_safety.synthetic import generate


@pytest.fixture(scope="session")
def raw():
    return generate(n_subjects=90, seed=7)


@pytest.fixture(scope="session")
def raw_faulty():
    return generate(n_subjects=90, seed=7, inject_errors=True)


@pytest.fixture(scope="session")
def result(raw):
    return run({"dm": raw.dm, "ae": raw.ae, "lb": raw.lb})


@pytest.fixture(scope="session")
def result_faulty(raw_faulty):
    return run({"dm": raw_faulty.dm, "ae": raw_faulty.ae, "lb": raw_faulty.lb})
