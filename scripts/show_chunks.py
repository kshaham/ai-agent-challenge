"""Dump every corpus chunk's doc_id / chunk_id / preview.

    python -m scripts.show_chunks

Use this to author `expected_citations` in eval/dataset.jsonl without having to
reverse-engineer the chunker.
"""

from __future__ import annotations

from app.corpus.ingest import load_chunks


def main() -> int:
    for chunk in load_chunks():
        preview = " ".join(chunk.text.split())[:80]
        print(f"{chunk.chunk_id:<24} {preview}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
