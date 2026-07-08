PYTHON ?= python

.PHONY: demo test clean

demo:
	$(PYTHON) -m portfolio_case.cli run --config configs/demo.yaml

test:
	$(PYTHON) -m pytest

clean:
	$(PYTHON) -c "import shutil, pathlib; p=pathlib.Path('runs'); shutil.rmtree(p) if p.exists() else None"
