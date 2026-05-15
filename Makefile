.PHONY: help install dev test lint format build serve start stop clean clean-store eval

VENV ?= .venv
PY := $(VENV)/bin/python
PIP := $(VENV)/bin/pip

help:
	@echo "kgent: common commands"
	@echo ""
	@echo "  make install      Create venv and install kgent with all extras"
	@echo "  make dev          Install dev/test dependencies"
	@echo "  make test         Run pytest"
	@echo "  make lint         Run ruff check"
	@echo "  make format       Run ruff format"
	@echo "  make build        Build the React frontend into kgent/web/"
	@echo "  make serve        Start the server in foreground (uses .env)"
	@echo "  make start        Background start via start.sh"
	@echo "  make stop         Stop the background server"
	@echo "  make clean        Remove caches and build artifacts"
	@echo "  make clean-store  Wipe the vector store (.kgent_store/index.json, chroma_db)"

$(VENV):
	python3.12 -m venv $(VENV)

install: $(VENV)
	$(PY) -m pip install --upgrade pip
	$(PY) -m pip install -e ".[embed,graph]"

dev: install
	$(PY) -m pip install -e ".[test]"

test:
	$(PY) -m pytest

lint:
	$(PY) -m ruff check kgent tests

format:
	$(PY) -m ruff format kgent tests

build:
	cd frontend && npm install && npm run build

serve:
	$(PY) -m kgent.cli serve

start:
	./start.sh

stop:
	./stop.sh

clean:
	rm -rf .pytest_cache .ruff_cache .mypy_cache build dist *.egg-info kgent.egg-info
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
	find . -type f -name "*.py[cod]" -delete

clean-store:
	rm -rf .kgent_store/index.json .kgent_store/meta.json .kgent_store/chroma_db
	@echo "Vector store cleared. chat.db (history) and logs kept."
