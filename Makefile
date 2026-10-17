PYTHON ?= python3
export PYTHONDONTWRITEBYTECODE := 1

.PHONY: verify test runtime reproduce validate-milestone2 check

verify:
	$(PYTHON) docs/milestone1-evidence/evidence.py verify

test:
	$(PYTHON) docs/milestone1-evidence/run_tests.py
	$(PYTHON) docs/milestone2-evidence/run_tests.py

runtime:
	$(PYTHON) tools/reproducibility/bootstrap_runtime.py

reproduce: runtime
	$(PYTHON) docs/milestone1-evidence/reproduce.py

validate-milestone2: runtime
	$(PYTHON) docs/milestone2-evidence/validate.py

check: test
	$(MAKE) reproduce
	$(MAKE) validate-milestone2
