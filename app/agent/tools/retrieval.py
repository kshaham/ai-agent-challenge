"""The document-retrieval tool — the worked example of the Tool abstraction.

Read this to see the contract a tool follows: a static JSON-Schema for its
arguments (`parameters`), and a `run(**args)` that returns a plain,
JSON-serializable dict. The result deliberately omits BM25 scores (floats would
make the observation text — and thus the request hash — non-portable); it returns
only ordered chunks with their doc_id / chunk_id so the model can ground and cite.
"""

from __future__ import annotations

from typing import Any, Optional

from app.agent.tools.base import Tool
from app.corpus.index import BM25Index, get_index


class RetrievalTool(Tool):
    name = "search_documents"
    description = (
        "Full-text search over the Meridian documentation corpus. "
        "Returns the most relevant chunks, each with a doc_id and chunk_id to cite."
    )
    parameters: dict[str, Any] = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Search query — keywords or a natural-language question.",
            },
            "k": {
                "type": "integer",
                "minimum": 1,
                "description": "Maximum number of chunks to return (default 3).",
            },
        },
        "required": ["query"],
        "additionalProperties": False,
    }

    def __init__(self, index: Optional[BM25Index] = None) -> None:
        self._index = index or get_index()

    def run(self, *, query: str, k: int = 3) -> dict[str, Any]:
        hits = self._index.search(query, k=k)
        return {
            "results": [
                {"doc_id": h.doc_id, "chunk_id": h.chunk_id, "text": h.text}
                for h in hits
            ]
        }
