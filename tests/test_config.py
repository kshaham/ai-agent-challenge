"""The minimal .env loader fills unset vars without overriding the shell."""

from __future__ import annotations

import os

from app.config import _load_dotenv


def test_dotenv_fills_unset_but_respects_existing(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    env.write_text('FOO_TEST_VAR="bar"\n# a comment\nMODEL_MODE=live\n', encoding="utf-8")

    monkeypatch.delenv("FOO_TEST_VAR", raising=False)
    monkeypatch.setenv("MODEL_MODE", "replay")  # already set in the shell -> wins

    _load_dotenv(env)

    assert os.environ["FOO_TEST_VAR"] == "bar"  # unset -> filled (quotes stripped)
    assert os.environ["MODEL_MODE"] == "replay"  # not overridden


def test_dotenv_missing_file_is_a_noop(tmp_path):
    _load_dotenv(tmp_path / "does-not-exist.env")  # must not raise


def test_dotenv_non_utf8_is_ignored_not_crashing(tmp_path):
    # a Windows UTF-16 save must not crash every import of the app
    env = tmp_path / ".env"
    env.write_bytes("MODEL_MODE=live\n".encode("utf-16"))
    _load_dotenv(env)  # must not raise
