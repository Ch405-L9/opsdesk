.PHONY: install lint type test check

install:
	uv sync --extra dev

lint:
	uv run ruff check .

type:
	uv run mypy src

test:
	uv run pytest

check: lint type test
