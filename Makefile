PYTHON ?= python3
NODE ?= node
export PYTHONDONTWRITEBYTECODE := 1

.PHONY: verify test runtime reproduce validate-milestone2 validate-milestone3 test-phase7 validate-phase7 test-live validate-live check

verify:
	$(PYTHON) docs/milestone1-evidence/evidence.py verify

test:
	$(PYTHON) docs/milestone1-evidence/run_tests.py
	$(PYTHON) docs/milestone2-evidence/run_tests.py
	$(PYTHON) docs/milestone3-evidence/run_tests.py

runtime:
	$(PYTHON) tools/reproducibility/bootstrap_runtime.py

reproduce: runtime
	$(PYTHON) docs/milestone1-evidence/reproduce.py

validate-milestone2: runtime
	$(PYTHON) docs/milestone2-evidence/validate.py

validate-milestone3: runtime
	$(PYTHON) docs/milestone3-evidence/validate.py

test-phase7: runtime
	$(PYTHON) docs/phase7-evidence/run_tests.py

validate-phase7: runtime
	$(PYTHON) docs/phase7-evidence/validate.py

test-live:
	$(PYTHON) -m unittest discover -s backend/tests -v
	$(PYTHON) -m unittest discover -s frontend/tests -p test_replay.py -v
	$(NODE) --test frontend/tests/replay.test.mjs frontend/tests/live.test.mjs

validate-live: runtime
	$(PYTHON) docs/live-control-evidence/run_validation.py
	$(PYTHON) docs/live-control-evidence/run_http_validation.py

check: test
	$(MAKE) reproduce
	$(MAKE) validate-milestone2
	$(MAKE) validate-milestone3
	$(MAKE) test-phase7
	$(MAKE) validate-phase7
