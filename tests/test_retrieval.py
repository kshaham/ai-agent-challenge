"""Unit tests for the retrieval tool + BM25 index."""

from __future__ import annotations

from app.agent.tools.retrieval import RetrievalTool


def test_finds_the_configuration_doc_for_a_port_question():
    out = RetrievalTool().run(query="default HTTP port", k=3)
    docs = [r["doc_id"] for r in out["results"]]
    assert "03-configuration" in docs


def test_empty_query_returns_no_results_without_raising():
    assert RetrievalTool().run(query="", k=3)["results"] == []


def test_out_of_corpus_query_returns_no_results():
    # Nothing in the corpus is about kubernetes — this feeds the refusal path.
    assert RetrievalTool().run(query="kubernetes operator helm", k=3)["results"] == []


def test_non_positive_k_returns_empty_not_the_whole_corpus():
    tool = RetrievalTool()
    assert tool.run(query="Meridian", k=0)["results"] == []
    assert tool.run(query="Meridian", k=-1)["results"] == []


def test_retrieval_is_deterministic_and_totally_ordered():
    tool = RetrievalTool()
    first = tool.run(query="backup restore snapshot", k=5)
    second = tool.run(query="backup restore snapshot", k=5)
    assert first == second


def test_result_shape_omits_scores():
    out = RetrievalTool().run(query="license", k=1)
    assert out["results"], "expected at least one hit"
    assert set(out["results"][0].keys()) == {"doc_id", "chunk_id", "text"}
