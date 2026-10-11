STORAGE ?= $(if $(EPISODE_STORAGE),$(EPISODE_STORAGE),/Volumes/External Storage/Episode)
export EPISODE_STORAGE := $(STORAGE)
PY = $(STORAGE)/venv/bin/python
.PHONY: setup doctor start test browser-test build benchmark
setup:
	python3.11 scripts/setup.py
doctor:
	./scripts/episode doctor
start:
	python3.11 scripts/start.py
build:
	npm run --prefix web build
test:
	"$(PY)" -B -m pytest -q -p no:cacheprovider --basetemp "$(STORAGE)/tmp/pytest"
browser-test:
	PLAYWRIGHT_BROWSERS_PATH="$(STORAGE)/cache/browsers" TMPDIR="$(STORAGE)/tmp" npm run --prefix web test
benchmark:
	"$(PY)" -B scripts/benchmark.py
