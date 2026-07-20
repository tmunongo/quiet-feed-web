.PHONY: bump-patch bump-minor bump-major

bump-patch:
	bun ./scripts/bump-version.js patch

bump-minor:
	bun ./scripts/bump-version.js minor

bump-major:
	bun ./scripts/bump-version.js major
