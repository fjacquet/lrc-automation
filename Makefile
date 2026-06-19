# lrc-automation Makefile — fjacquet/ci standard interface (do not rename canonical targets)
.DEFAULT_GOAL := all
DIST ?= dist

.PHONY: all clean install tools lint format typecheck test build vuln sbom security docs docs-serve coverage-upload release ci

all: clean lint typecheck test build

clean:
	rm -rf $(DIST) build site htmlcov .coverage coverage.xml *.sarif .mypy_cache .pytest_cache .ruff_cache *.egg-info
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true

install:
	uv sync --all-extras --all-groups

tools: install

lint:
	uv run ruff check .
	uv run ruff format --check .

format:
	uv run ruff format .

typecheck:
	uv run mypy src/

test:
	uv run pytest --cov --cov-report=xml --cov-report=term-missing

build:
	uv build

vuln:
	uvx osv-scanner scan --lockfile=uv.lock || true

sbom:
	mkdir -p $(DIST)
	uv run cyclonedx-py environment --output-format JSON --output-file $(DIST)/sbom.cdx.json

security:  # advisory: reports findings but never blocks the build (CodeQL/osv are the blocking gates)
	uvx semgrep scan --config auto --skip-unknown-extensions || true

docs:
	uv run mkdocs build --strict --site-dir site

docs-serve:
	uv run mkdocs serve

coverage-upload:
	uvx --from codecov-cli codecov upload-process --file coverage.xml || true

release:
	uv build
	uv publish --trusted-publishing always

ci: lint test build
