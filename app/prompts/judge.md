# LLM-as-Judge Prompt — STUB (rewrite this)

This is a placeholder. It is intentionally weak so you can write a real rubric.
The judge is used only by `make eval-judge` (opt-in), never on the default offline
`make eval` path.

Your task: write a prompt that scores whether ANSWER is (a) faithful to CONTEXT
(no claims that aren't supported) and (b) actually answers QUESTION. Require the
model to return STRICT JSON on a single line: {"score": <0.0-1.0>, "reason": "..."}.

In the README, note the risks of LLM-as-judge (non-determinism, self-preference,
sensitivity to phrasing, cost) and how you mitigate them here.

---

QUESTION:
{question}

ANSWER:
{answer}

CONTEXT:
{context}
