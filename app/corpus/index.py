"""A tiny, dependency-free BM25 keyword index over the corpus chunks.

Pure Python (no numpy / rank_bm25) both to keep install friction near zero and to
dodge scientific-wheel availability problems on new Python versions. Results are
totally ordered by (-score, doc_id, chunk_id) so retrieval — and therefore the
observation text and citations that flow from it — is byte-deterministic.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass
from functools import lru_cache
from typing import Optional

from app.corpus.ingest import Chunk, load_chunks

_TOKEN_RE = re.compile(r"[a-z0-9]+")

# A small, fixed stopword list. Used only for membership tests, so set iteration
# order never reaches any hashed output.
_STOPWORDS = frozenset(
    {
        "a", "an", "and", "are", "as", "at", "be", "by", "can", "do", "does",
        "for", "from", "how", "in", "is", "it", "of", "on", "or", "that", "the",
        "to", "was", "what", "when", "where", "which", "who", "why", "will",
        "with", "you", "your",
    }
)

_K1 = 1.5
_B = 0.75


def tokenize(text: str) -> list[str]:
    return [t for t in _TOKEN_RE.findall(text.lower()) if t not in _STOPWORDS]


@dataclass(frozen=True)
class Hit:
    doc_id: str
    chunk_id: str
    text: str
    score: float


class BM25Index:
    def __init__(self, chunks: list[Chunk]) -> None:
        self.chunks = chunks
        self._tokens: list[list[str]] = [tokenize(c.text) for c in chunks]
        self._tf: list[Counter] = [Counter(toks) for toks in self._tokens]
        self._len: list[int] = [len(toks) for toks in self._tokens]
        self._avgdl: float = (sum(self._len) / len(self._len)) if self._len else 0.0
        df: Counter = Counter()
        for toks in self._tokens:
            for term in set(toks):
                df[term] += 1
        n = len(chunks)
        self._idf: dict[str, float] = {
            term: math.log(1 + (n - freq + 0.5) / (freq + 0.5))
            for term, freq in df.items()
        }

    def search(self, query: str, k: int = 3) -> list[Hit]:
        terms = tokenize(query)
        # Clamp non-positive k: a negative slice would otherwise return
        # nearly the whole corpus instead of an empty result.
        if not terms or not self.chunks or k <= 0:
            return []
        scored: list[Hit] = []
        for i, chunk in enumerate(self.chunks):
            tf = self._tf[i]
            dl = self._len[i]
            score = 0.0
            for term in terms:
                if term not in tf:
                    continue
                idf = self._idf.get(term, 0.0)
                freq = tf[term]
                denom = freq + _K1 * (1 - _B + _B * (dl / self._avgdl if self._avgdl else 0))
                score += idf * (freq * (_K1 + 1)) / denom if denom else 0.0
            if score > 0:
                scored.append(Hit(chunk.doc_id, chunk.chunk_id, chunk.text, score))
        # total order: score desc, then stable doc_id / chunk_id
        scored.sort(key=lambda h: (-h.score, h.doc_id, h.chunk_id))
        return scored[:k]


@lru_cache(maxsize=1)
def get_index() -> BM25Index:
    """Process-wide singleton built once from the on-disk corpus."""
    return BM25Index(load_chunks())
