"""Load version-controlled prompts from app/prompts/*.md.

Prompts are files, not inline string literals, so they can be diffed, reviewed,
and iterated on. Text is newline-normalized (LF) so a CRLF checkout can't change
the hashed messages.
"""

from __future__ import annotations

from app.paths import PROMPTS_DIR, read_text_normalized


def load_prompt(name: str) -> str:
    return read_text_normalized(PROMPTS_DIR / name).strip()
