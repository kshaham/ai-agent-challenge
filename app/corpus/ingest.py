"""Corpus ingestion — turn markdown files into citeable chunks.

Deterministic by construction: files are globbed in sorted order, each doc is
split into sections at markdown headings, and chunk ids are stable
(`{doc_id}#p{n}`). Determinism matters because chunk text ends up inside the
model's messages, which are hashed for record/replay.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from app.paths import CORPUS_DIR, read_text_normalized


@dataclass(frozen=True)
class Chunk:
    doc_id: str
    chunk_id: str
    text: str


def _split_sections(text: str) -> list[str]:
    """Split a doc into sections, each starting at a markdown heading (`#`)."""
    sections: list[list[str]] = []
    current: list[str] = []
    for line in text.split("\n"):
        if line.startswith("#") and current:
            sections.append(current)
            current = [line]
        else:
            current.append(line)
    if current:
        sections.append(current)
    # collapse each section to trimmed text; drop empties
    out = []
    for lines in sections:
        block = "\n".join(lines).strip()
        if block:
            out.append(block)
    return out


def load_chunks(corpus_dir: Optional[Path] = None) -> list[Chunk]:
    corpus_dir = corpus_dir or CORPUS_DIR
    chunks: list[Chunk] = []
    for path in sorted(corpus_dir.glob("*.md")):
        doc_id = path.stem
        text = read_text_normalized(path)
        for i, section in enumerate(_split_sections(text)):
            chunks.append(Chunk(doc_id=doc_id, chunk_id=f"{doc_id}#p{i}", text=section))
    return chunks
