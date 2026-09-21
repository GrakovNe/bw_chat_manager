VENV ?= .venv
PY := $(VENV)/bin/python
RUFF := $(VENV)/bin/ruff

.PHONY: venv install run test lint fmt check clean

venv:
	python3 -m venv $(VENV)
	$(PY) -m pip install --upgrade pip
	$(PY) -m pip install -e ".[dev]"

install:
	$(PY) -m pip install -e ".[dev]"

run:
	$(PY) -m bwbot

test:
	$(PY) -m pytest -q

lint:
	$(RUFF) check .

fmt:
	$(RUFF) format .
	$(RUFF) check --fix .

check: lint test

clean:
	rm -rf .pytest_cache .ruff_cache build dist *.egg-info src/*.egg-info
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
