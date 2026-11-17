"""Bump Python metadata, commit it, and create the tag used by release CI."""

import argparse
import re
import subprocess
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run(*args):
    return subprocess.run(args, cwd=ROOT, check=True, text=True, capture_output=True).stdout.strip()


def bump(kind):
    if run("git", "status", "--porcelain"):
        raise ValueError("Working tree is not clean. Commit or stash your changes before bumping.")
    current = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]["version"]
    if not re.fullmatch(r"\d+\.\d+\.\d+", current):
        raise ValueError(f"Expected a major.minor.patch version; found {current!r}.")
    parts = list(map(int, current.split(".")))
    index = {"major": 0, "minor": 1, "patch": 2}[kind]
    parts[index] += 1
    parts[index + 1 :] = [0] * (2 - index)
    version = ".".join(map(str, parts))
    tag = f"v{version}"
    if run("git", "tag", "--list", tag):
        raise ValueError(f"Tag {tag} already exists; no version files were changed.")
    # Fail before editing files when Git cannot identify the release author.
    run("git", "var", "GIT_AUTHOR_IDENT")
    run("git", "var", "GIT_COMMITTER_IDENT")
    run("uv", "version", "--bump", kind, "--no-sync")
    updated = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]["version"]
    if updated != version:
        raise ValueError(
            f"uv produced {updated!r}, expected {version!r}; no commit or tag created."
        )
    run("git", "add", "--", "pyproject.toml", "uv.lock")
    run("git", "commit", "-m", f"chore(release): {tag}")
    run("git", "tag", tag)
    print(f"Updated {current} → {version}; created release commit and tag {tag}.")
    print(f"To publish: git push origin HEAD && git push origin {tag}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("kind", choices=["patch", "minor", "major"])
    args = parser.parse_args()
    try:
        bump(args.kind)
    except ValueError as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    except subprocess.CalledProcessError as error:
        print(f"Error running {' '.join(error.cmd)}: {error.stderr.strip()}", file=sys.stderr)
        print("Check git status before retrying; no changes were pushed.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
