# ai-agent-challenge

A small, **green-out-of-the-box** agent-over-a-corpus service: a FastAPI app that answers questions about a fictional time-series DB ("Meridian") by running an agent loop over a local document corpus, with grounded citations and refusal when the answer isn't supported. Everything runs **fully offline** on committed fixtures — no Ollama, GPU, or API key needed.

- **The brief you're graded on:** [`CHALLENGE.md`](CHALLENGE.md)
- **How the plumbing works:** [`ARCHITECTURE.md`](ARCHITECTURE.md)

## Quickstart

```sh
make install      # python -m venv .venv && pip install -e '.[dev]'
make test         # pytest -q  → 48 passed, 1 skipped, fully offline
```

Run the API (offline replay model):

```sh
make run          # uvicorn app.main:app --reload --port 8000
```

POST a question, then read it back:

```sh
curl -s -X POST http://localhost:8000/api/tasks \
  -H 'content-type: application/json' \
  -d '{"question": "What is the default HTTP port for Meridian?"}'
```

```json
{
  "id": "3f2b1a4c5d6e7f8091a2b3c4d5e6f708",
  "question": "What is the default HTTP port for Meridian?",
  "created_at": "2026-06-30T12:00:00+00:00",
  "answer": "The default HTTP port for Meridian is 7280.",
  "citations": [],
  "status": "completed",
  "steps_used": 1,
  "trace": [ /* append-only agent steps: tool_call → observation → final */ ]
}
```

```sh
curl -s http://localhost:8000/api/tasks/3f2b1a4c5d6e7f8091a2b3c4d5e6f708   # same shape
curl -s http://localhost:8000/api/tasks                                    # list view
```

> **Offline mode answers only the seeded questions.** `ReplayModel` has fixtures for the six
> eval questions (see `eval/dataset.jsonl`). Ask something else and you'll get
> `status: "error"` (a clean `FixtureMissingError`, not a crash) until you record it against a
> live model — see [Running against a real model](#running-against-a-real-model). This is the
> point of record/replay: the service is deterministic and free to run, and the live model is
> only needed to record new responses.

Note the shipped baseline answers with `7280` but **cites nothing** — that's the mediocre loop you're replacing. Score it:

```sh
make eval         # python -m eval.runner — diffs vs baseline, exit 1 on regression
```

Baseline scores (`eval/baseline.json`):

| metric | baseline |
| --- | --- |
| `task_success` | 0.5000 |
| `citation_accuracy` | 0.1667 |
| `refusal_correctness` | 0.8333 |
| `tool_call_validity` | 1.0000 |

## Where to start

1. **`app/agent/loop.py`** — the baseline `agent_loop()` to replace. It does one hard-coded retrieval, one model call, never refuses, never cites, and pipes retrieved text straight in (so an injected doc can hijack it). This is the file you're graded on.
2. **`app/prompts/system.md`** — a deliberately mediocre starter prompt. Improve it, then document **one live-recorded iteration** (observed failure → change → effect).
3. **Expand `eval/dataset.jsonl`** and **write `app/prompts/judge.md`** (+ a note on judge risks). Run `make show-chunks` to see `doc_id`/`chunk_id`s so you can author correct `expected_citations`.

## The commands

| target | does |
| --- | --- |
| `make install` | venv + editable install with dev deps |
| `make run` | serve the API on :8000 (offline replay model) |
| `make test` | `pytest -q` — fully offline |
| `make eval` | run the 4 metrics, diff vs baseline, fail on regression |
| `make eval-judge` | add the opt-in LLM judge (needs a model or judge fixtures) |
| `make record` | `MODEL_MODE=live` re-record fixtures (Ollama, or `LLM_BACKEND=openai`) |
| `make seed` | regenerate the **shipped baseline** fixtures offline |
| `make verify` | check the **shipped baseline** fixtures still match (offline; not for live recordings) |
| `make show-chunks` | dump `doc_id`/`chunk_id`/preview for citing |

## Project layout

```
app/
  main.py            FastAPI app + /health
  api/               routes, schemas, structured error envelope
  agent/
    loop.py          ← CANDIDATE FILE (mediocre baseline)
    runner.py        run_agent() — owns Trace + try/except seam
    trace.py types.py tools/
  model/             replay · recording-stub · scripted · live clients
  corpus/            chunking + pure-python BM25
  prompts/           system.md (mediocre) · judge.md (stub)
corpus/*.md          10 fictional "Meridian" docs (incl. an injection in 10-faq)
fixtures/*.json      committed recorded model responses (offline)
eval/                dataset.jsonl · runner.py · metrics.py · baseline.json
scripts/             seed_fixtures.py · show_chunks.py
tests/               api · validation · retrieval · determinism · agent_loop · eval · storage · live · config · …
```

## Running against a real model

You build and unit-test the loop offline (the suite needs nothing). But you'll need a live backend for two things: the **documented prompt iteration**, and running `make eval` on **your own** agent (its requests differ from the shipped baseline fixtures, so record your agent's responses with `make record`, or run the eval live). **Set one up early**, before you start on the loop, so a download or key signup isn't blocking you later.

**Local Ollama:**

```sh
ollama pull qwen2.5:7b
make record       # MODEL_MODE=live python -m scripts.seed_fixtures --live
```

We use Ollama **structured outputs** (`format=json` schema) at temperature 0 to keep small-model tool calls well-formed.

**No GPU?** Point `LiveModel` at any **OpenAI-compatible** endpoint (Groq, OpenRouter `:free`, etc.) — free-tier keys work, no paid key needed:

```sh
export MODEL_MODE=live LLM_BACKEND=openai
export OPENAI_BASE_URL=https://api.groq.com/openai/v1 OPENAI_API_KEY=<your-free-key> OPENAI_MODEL=llama-3.1-8b-instant
make record
```

`MODEL_MODE`/`LLM_BACKEND`/`OPENAI_*`/`OLLAMA_*` can also go in a `.env` file (copy `.env.example`).

## How the offline story works, in one paragraph

Every model response is keyed by a **canonical hash of the abstract request** (messages + tools + format, hashed before provider translation, with tool-call ids/timestamps stripped and tools name-sorted), so replay is deterministic across processes and `PYTHONHASHSEED`. Develop and eval entirely on the committed `fixtures/`. The **one** non-offline moment: changing `loop.py` or `system.md` changes the messages → a new hash → a fixture miss, so re-record once with `make record`. That's it — everything else stays offline and green.
