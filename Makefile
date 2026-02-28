.PHONY: install lint format typecheck test check docs docs-serve clean all

all: install check docs

install:
	uv sync

lint:
	uv run ruff check . --fix

format:
	uv run ruff format .

typecheck:
	uv run mypy src/

test:
	uv run pytest -v

check: lint typecheck test
	uv run ruff format --check .

docs:
	uv run mkdocs build

docs-serve:
	uv run mkdocs serve

clean:
	rm -rf build/ dist/ site/ htmlcov/ .mypy_cache/ .pytest_cache/ .ruff_cache/ *.egg-info
