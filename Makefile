PYTHON ?= python3
export PYTHONDONTWRITEBYTECODE := 1

.PHONY: verify test runtime reproduce check

verify:
	$(PYTHON) docs/milestone1-evidence/evidence.py verify

test:
	$(PYTHON) docs/milestone1-evidence/run_tests.py

runtime:
	$(PYTHON) tools/reproducibility/bootstrap_runtime.py

reproduce: runtime
	$(PYTHON) docs/milestone1-evidence/reproduce.py

check: test
	$(MAKE) reproduce
