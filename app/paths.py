"""Filesystem anchors.

Every path is resolved relative to the package, never the current working
directory, so `pytest`, `python -m eval.runner`, and `uvicorn` all read the same
corpus / prompts / fixtures no matter where they're launched from. Reading a
prompt from the wrong place would change the hashed messages and miss every
fixture.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

CORPUS_DIR = ROOT / "corpus"
FIXTURES_DIR = ROOT / "fixtures"
PROMPTS_DIR = ROOT / "app" / "prompts"
EVAL_DIR = ROOT / "eval"
DATA_DIR = ROOT / "data"


def read_text_normalized(path: Path) -> str:
    """Read UTF-8 text with newlines normalized to LF.

    Any text that feeds the request hash (prompts, corpus) must be
    newline-stable so a CRLF checkout can't invalidate fixtures.
    """
    return path.read_text(encoding="utf-8").replace("\r\n", "\n").replace("\r", "\n")
