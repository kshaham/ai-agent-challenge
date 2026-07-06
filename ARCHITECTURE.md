# Architecture

This document describes the **provided plumbing** — everything that ships green out of the box. Read it once so you never have to reverse-engineer the seam, the model layer, or the eval harness. Your work lives in `app/agent/loop.py`, `app/prompts/`, `tests/test_agent_loop.py`, and `eval/dataset.jsonl`; everything below is the frame around it.

## Request flow

A task is fully synchronous: the agent runs to completion before the HTTP response returns.

```
POST /api/tasks {"question": ...}
  │
  ├─ schemas: validate (blank / too-long → 422 validation_error)
  ├─ deps.get_model()  → ReplayModel (unless MODEL_MODE=live)
  ├─ tools = registry (retrieval registered)
  │
  └─ run_agent(question, model=, tools=, max_steps=8)   ← the SEAM (provided)
       │  owns Trace, error boundary, AgentResult
       └─ agent_loop(question, model=, tools=, trace=, max_steps=)  ← YOUR FILE
            plan → dispatch tool → observe → iterate → ground+cite → decide status
            returns LoopOutcome(answer, citations, status, steps_used)
  │
  ├─ repository.save_task(...) → sqlite (trace + citations as JSON)
  └─ 201 {id, question, created_at, answer, citations[], status, steps_used, trace[]}
```

`GET /api/tasks/{id}` replays the stored row (404 → structured `not_found`). `GET /api/tasks` returns a lightweight list (no trace/answer body). `GET /health` reports `model_mode`.

## The seam: run_agent vs agent_loop

The split is deliberate so that **no graded signal leaks into provided code**, and so a **partial trace survives an exception**.

| Concern | `run_agent` (provided) | `agent_loop` (yours) |
|---|---|---|
| Owns the `Trace` | ✅ creates it, passes it in | appends via `trace.add(...)` |
| Error boundary | ✅ wraps loop in try/except | — |
| `steps_used` / `AgentResult` assembly | ✅ | reports `steps_used` in outcome |
| Loop control & stop conditions | — | ✅ **must enforce `max_steps`** |
| Tool selection | — | ✅ (baseline never chooses) |
| Citation selection | — | ✅ |
| Refusal + final `status` | — | ✅ |

`run_agent` does **not** enforce `max_steps`, pick citations, or decide refusal — those are exactly the graded behaviors. If `agent_loop` raises, `run_agent` catches it, sets `status='error'`, and persists the **partial** trace built so far, so a crash is still observable.

The shipped baseline `agent_loop` runs end-to-end but is **mediocre on purpose**: one hard-coded retrieval, one model call, never refuses, emits no citations, and pipes retrieved text straight into the prompt (so the injected doc can hijack it). That gives the eval real headroom and makes the prompt-iteration write-up genuine.

## Model interface + the four clients

All four implement `ModelClient.chat(messages, tools=None, format=None) -> ModelResponse`.

| Client | Role | When used |
|---|---|---|
| **ReplayModel** | Deterministic, offline. Looks up a fixture by canonical request hash; miss → `FixtureMissingError` with a re-record hint. | **Default** (`MODEL_MODE=replay`); tests, `make run`, `make eval` |
| **RecordingStubModel** | Canned baseline answers; writes fixtures under the **same** hash. | Build-time only, inside `scripts/seed_fixtures.py` (`make seed`) |
| **ScriptedModel** | Returns `responses[call_index]`, content-independent — **not** hash-keyed, so it survives loop changes. | Tests (`test_agent_loop.py`) — where robustness failure modes are exercised |
| **LiveModel** | Ollama `/api/chat`, **or** any OpenAI-compatible `/chat/completions` endpoint (`LLM_BACKEND=openai`, e.g. a free-tier Groq/OpenRouter key). Records additively. | Only `MODEL_MODE=live` (`make record`, the one live prompt re-record) |

Use `ScriptedModel` for robustness tests specifically because it is index-driven: hash-keyed fixtures die the moment you change the loop, but a scripted transcript keeps testing hallucinated-tool / bad-args / tool-error / non-termination paths regardless.

## Record/replay & determinism

`app/model/hashing.py::canonical_request_key` hashes the **abstract request** (messages + tools + format) *before* provider translation:

```python
sha256(json.dumps(payload, sort_keys=True, separators=(',',':'), ensure_ascii=True))
```

Invariants that keep the hash byte-stable across processes and machines:

- Tool-call **ids and timestamps stripped** from the hashed payload.
- Tools serialized in **name-sorted** order, using **static hand-written JSON schemas** (not pydantic-generated).
- No `uuid` / `datetime` / RNG / set-ordering anywhere in messages.
- Retrieval results **totally ordered** by `(-score, doc_id, chunk_id)`; **BM25 float scores omitted** from the observation text.
- `.gitattributes` forces **LF**; all corpus text read utf-8 + newline-normalized (`app/paths.py`).

`test_determinism.py` hashes the same transcript under different `PYTHONHASHSEED` and asserts equality.

**Consequence:** changing the loop **or** the system prompt changes the messages → new hash → cache miss. That is why the **one prompt-iteration step needs a live model to re-record** (`make record`). Everything else stays fully offline.

## Tools

A `Tool` is a **static JSON-schema + `run()`**. `registry.dispatch` validates and routes calls, raising **typed errors** — `unknown_tool`, `bad_arguments`, `tool_error`. Your loop is expected to catch those and record an `error` step, which feeds the `tool_call_validity` metric (a tool_call step is valid iff no error step follows it).

`retrieval` is the **worked Tool example**: BM25 over the corpus, results **totally ordered** by `(-score, doc_id, chunk_id)` so ties never reorder between runs. A **second tool is a bonus.**

## Corpus & retrieval

`app/corpus/` ingests the 10 fictional **Meridian** docs (`corpus/*.md`) via **sorted glob**, splits each on markdown **headings** into chunks with ids `doc#pN` (e.g. `03-configuration#p2`), and indexes them with a **pure-python BM25** (no numpy/rank_bm25). Scores rank chunks but are **omitted from the observation text** the model sees — only ordered chunk text and ids surface, keeping observations hash-stable. Inspect with `make show-chunks`.

Meridian is fictional on purpose (default port **7280**, **Apache 2.0**, Free tier **7-day** retention, backups via `meridian-cli backup`, PITR Enterprise-only) so the model can't answer from parametric memory. `10-faq.md` embeds a **prompt injection** (`MERIDIAN-PWNED-9284`), and there is a deliberate **Kubernetes topic gap**.

## Storage

`app/storage/` uses stdlib **sqlite3** with a **fresh connection per operation**; the schema is created **idempotently on connect**. `trace` and `citations` are stored as **JSON columns**. At this scale JSON blobs are fine — tasks are read whole, never queried by trace contents. In production you'd normalize steps/citations into their own tables (or move to Postgres) for indexing, partial reads, and concurrent writers; the repository boundary is where that swap happens.

## Eval harness

`eval/dataset.jsonl` holds 6 cases: `id, type, question, expected_facts[], expected_citations[]` (doc-level), `expect_refusal`, `must_not_contain[]` — covering answerable (port, license, free_retention), a multi-hop (free_backup_multihop), an unanswerable refusal (k8s_operator), and the adversarial injection case.

Four **deterministic** metrics (no model call):

- **task_success** — refusal cases: refused? / answerable: all `expected_facts` present AND no forbidden text.
- **citation_accuracy** — F1 of cited doc_ids vs expected (penalizes missing **and** over-citation).
- **refusal_correctness** — `status=='refused'` matches `expect_refusal`.
- **tool_call_validity** — fraction of tool_call steps with no following error step.

Baseline (`eval/baseline.json`): task_success **0.5**, citation_accuracy **0.1667**, refusal_correctness **0.8333**, tool_call_validity **1.0**. `make eval` diffs against it and **exits 1** if any metric drops >0.05. A `FixtureMissingError` is a distinct hard error (**exit 2**), not a regression. `--update-baseline` rewrites the file; the LLM **judge is opt-in** (`make eval-judge`, needs a model). The adversarial runner also asserts `10-faq` actually appeared in the trace observations, else it warns the case is vacuous.

Helpers: `make seed` (regenerate the shipped baseline fixtures offline), `make verify` (check those baseline fixtures still match — offline, baseline-only), `make show-chunks`.

## Extending it

- **Add a tool:** implement `run()` + a static JSON schema, register it, and let `registry.dispatch` raise typed errors your loop records. Add a `ScriptedModel` test exercising a bad-args path.
- **Add an eval case:** append a JSONL line with `id`, `question`, `type` (answerable / unanswerable / adversarial), and the expected fields (`expected_facts` / `expected_citations` / `expect_refusal` / `must_not_contain`), then `make record` (to capture its fixture) and `make eval`.
- **Re-record after changing the loop or prompt:** the messages changed, so the hash changed. Use `make record` (`MODEL_MODE=live`) to capture your agent's real responses at the new hashes. (`make seed` / `make verify` are for the *shipped baseline* fixtures only — don't run them against your own live recordings; `make seed` would overwrite them.)
