PYTHON ?= python

.PHONY: demo test lint clean

demo:
	$(PYTHON) -m causal_pipeline.cli run --config configs/demo.yaml

lint:
	$(PYTHON) -m ruff check src tests

test: lint
	$(PYTHON) -m pytest

clean:
	$(PYTHON) -c "import shutil, pathlib; p=pathlib.Path('runs'); shutil.rmtree(p) if p.exists() else None"
