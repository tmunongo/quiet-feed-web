.PHONY: dev test check bump-patch bump-minor bump-major

dev:
	uv run python -m quiet_feed

test:
	uv run pytest

check:
	uv run ruff check .
	uv run ruff format --check .

bump-patch:
	uv version --bump patch

bump-minor:
	uv version --bump minor

bump-major:
	uv version --bump major
