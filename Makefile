.PHONY: help install prebake app test lint eval clean

PYTHON ?= python3
VENV   ?= venv
BIN    := $(VENV)/bin

help:  ## Show available targets
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

install:  ## Create venv and install deps (incl. dev tools)
	$(PYTHON) -m venv $(VENV)
	$(BIN)/pip install --upgrade pip
	$(BIN)/pip install -e ".[dev]"

prebake:  ## Run prebake: extract frames + cache OpenAI responses to disk
	@test -n "$$OPENAI_API_KEY" || (echo "ERROR: export OPENAI_API_KEY first" && exit 1)
	$(BIN)/python prebake.py

app:  ## Run the Streamlit app locally
	$(BIN)/streamlit run app.py

test:  ## Run the smoke test suite
	$(BIN)/pytest

lint:  ## Run ruff over the codebase
	$(BIN)/ruff check .

eval:  ## Run the offline structural eval over the cached manifest
	$(BIN)/python -m eval.compare

clean:  ## Remove caches but KEEP responses/ and manifest.json (those are pre-baked)
	rm -rf __pycache__ */__pycache__ .pytest_cache .ruff_cache
