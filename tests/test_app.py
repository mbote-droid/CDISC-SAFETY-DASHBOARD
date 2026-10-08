from __future__ import annotations

from pathlib import Path

import pytest

AppTest = pytest.importorskip("streamlit.testing.v1").AppTest
APP = str(Path(__file__).resolve().parents[1] / "app" / "streamlit_app.py")


@pytest.fixture
def app():
    return AppTest.from_file(APP, default_timeout=120)


def test_demo_renders_without_exceptions(app):
    at = app.run()
    assert not at.exception
    labels = {m.label: m.value for m in at.metric}
    assert labels["Safety population"] == "300"
    assert int(labels["Potential Hy's law"]) >= 1
    assert len(at.tabs) == 5
    assert any("PASSED" in s.value for s in at.success)


def test_fault_injection_shows_findings(app):
    at = app.run()
    at.sidebar.checkbox[0].check().run()
    assert not at.exception
    assert any("PASSED WITH FINDINGS" in w.value for w in at.warning)


def test_small_study_and_seed_change(app):
    at = app.run()
    at.sidebar.slider[0].set_value(30).run()
    at.sidebar.number_input[0].set_value(3).run()
    assert not at.exception
    assert {m.label: m.value for m in at.metric}["Safety population"] == "30"


def test_upload_mode_without_files_prompts(app):
    at = app.run()
    at.sidebar.radio[0].set_value("Upload raw files").run()
    assert not at.exception
    assert any("demographics" in i.value for i in at.info)


def test_prepare_download_package(app):
    at = app.run()
    prepare = [b for b in at.button if b.label == "Prepare download package"]
    assert prepare
    prepare[0].click().run()
    assert not at.exception


def test_large_study_renders(app):
    at = app.run()
    at.sidebar.slider[0].set_value(1500).run()
    assert not at.exception
    assert {m.label: m.value for m in at.metric}["Safety population"] == "1,500"
