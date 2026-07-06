"""seed() tolerates a candidate-added eval case (no offline baseline answer)."""

from __future__ import annotations

from eval.runner import load_dataset
from scripts import seed_fixtures as sf


def test_seed_skips_cases_without_a_baseline_answer(tmp_path, monkeypatch):
    shipped = load_dataset()
    added = {
        "id": "candidate_added_case",
        "type": "answerable",
        "question": "a brand new question",
        "expected_facts": [],
        "expected_citations": [],
        "expect_refusal": False,
        "must_not_contain": [],
    }
    monkeypatch.setattr(sf, "load_dataset", lambda: [*shipped, added])

    # must NOT raise KeyError; seeds the shipped cases and skips the new one
    sf.seed(tmp_path)
    assert len(list(tmp_path.glob("*.json"))) == len(shipped)


def _live_fixture_bytes() -> bytes:
    # Shape LiveModel._record writes: _meta carries `backend`, never `provider`.
    return b'{"_meta": {"backend": "ollama"}, "response": {"content": "x"}}\n'


def test_seed_cli_refuses_to_clobber_live_recordings(tmp_path, monkeypatch, capsys):
    """The offline `make seed` must refuse (exit 2) when live recordings are
    present, so it can't silently overwrite a candidate's `make record` output."""
    fixture = tmp_path / "deadbeef.json"
    fixture.write_bytes(_live_fixture_bytes())
    monkeypatch.setattr(sf, "FIXTURES_DIR", tmp_path)

    rc = sf.main([])  # plain offline seed

    assert rc == 2
    assert fixture.read_bytes() == _live_fixture_bytes()  # untouched
    assert "Refusing to run the offline" in capsys.readouterr().out


def test_seed_cli_force_overrides_the_guard(tmp_path, monkeypatch):
    """--force bypasses the guard and regenerates the baseline anyway."""
    (tmp_path / "deadbeef.json").write_bytes(_live_fixture_bytes())
    monkeypatch.setattr(sf, "FIXTURES_DIR", tmp_path)

    rc = sf.main(["--force"])

    assert rc == 0
    # baseline fixtures were written alongside the pre-existing live one
    assert len(list(tmp_path.glob("*.json"))) > 1
