PYTHON ?= python3
NODE ?= node
PORT ?= 4173
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

.PHONY: demo demo-verify demo-reproduce

# Recorded original guidance; Python only, no native toolchain required.
demo:
	$(PYTHON) -B tools/demo/demo.py launch --port $(PORT)

demo-verify:
	$(PYTHON) -B tools/demo/demo.py verify

# Rebuild/replay the unchanged frozen Phase 10 experiment in an isolated copy.
demo-reproduce:
	$(PYTHON) -B tools/demo/demo.py reproduce

.PHONY: test-frontend frontend-check

# Static application: verify exported evidence and check source syntax; no bundler.
frontend-check:
	$(PYTHON) -B frontend/tools/export_guidance.py --check
	$(PYTHON) -B frontend/tools/export_propulsion.py --check
	@for source in frontend/dist/*.mjs; do $(NODE) --check "$$source" || exit 1; done

# Read-only export/provenance and presentation-contract regression tests.
test-frontend:
	$(PYTHON) -B -m unittest discover -s frontend/tests -p 'test_*.py' -v
	$(NODE) --test frontend/tests/*.test.mjs

.PHONY: play

# Unified crew launch, historical procedures and independent educational flight.
play:
	$(PYTHON) -B tools/final_demo.py --port $(PORT)

.PHONY: demo-final test-final

demo-final: play

test-final:
	$(PYTHON) -B -m unittest discover -s backend/tests -v
	$(PYTHON) -B -m unittest discover -s frontend/tests -p 'test_*.py' -v
	$(NODE) --test frontend/tests/*.test.mjs
