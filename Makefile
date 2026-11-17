.PHONY: dev test check bump-patch bump-minor bump-major

dev:
	uv run python -m quiet_feed

test:
	uv run pytest

check:
	uv run ruff check .
	uv run ruff format --check .

bump-patch:
	uv run --locked python scripts/bump_version.py patch

bump-minor:
	uv run --locked python scripts/bump_version.py minor

bump-major:
	uv run --locked python scripts/bump_version.py major
