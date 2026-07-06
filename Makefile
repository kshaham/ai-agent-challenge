.DEFAULT_GOAL := help
PY ?= python

.PHONY: help install run test eval eval-judge record seed verify show-chunks clean

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'

install: ## Create a venv and install deps (offline-capable once wheels are cached)
	$(PY) -m venv .venv
	. .venv/bin/activate && pip install -e '.[dev]'

run: ## Start the API (offline replay model by default) on :8000
	uvicorn app.main:app --reload --port 8000

test: ## Run the full test suite (fully offline, no Ollama/GPU/key)
	pytest -q

eval: ## Run the eval suite in replay mode and diff vs the baseline (offline)
	$(PY) -m eval.runner

eval-judge: ## Run the eval INCLUDING the LLM-judge metric (needs live model or judge fixtures)
	$(PY) -m eval.runner --judge

record: ## Re-record fixtures against a live backend (Ollama, or LLM_BACKEND=openai). See README.
	MODEL_MODE=live $(PY) -m scripts.seed_fixtures --live

seed: ## (Re)generate the committed fixtures fully offline from the baseline agent
	$(PY) -m scripts.seed_fixtures

verify: ## Prove committed fixtures still match the corpus/prompts/dataset (offline)
	$(PY) -m scripts.seed_fixtures --check

show-chunks: ## Dump doc_id / chunk_id / preview so you can author expected_citations
	$(PY) -m scripts.show_chunks

clean: ## Remove caches and the local DB
	rm -rf .pytest_cache data/*.db
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
