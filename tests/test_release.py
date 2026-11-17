import os
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def release_repo(tmp_path):
    repo = tmp_path / "release-repo"
    (repo / "scripts").mkdir(parents=True)
    shutil.copyfile(ROOT / "scripts/bump_version.py", repo / "scripts/bump_version.py")
    (repo / "pyproject.toml").write_text(
        '[project]\nname = "release-test"\nversion = "0.3.0"\nrequires-python = ">=3.12"\n'
    )
    env = {
        **os.environ,
        "UV_CACHE_DIR": str(tmp_path / "uv-cache"),
        "UV_PYTHON": sys.executable,
        "UV_OFFLINE": "1",
    }

    def command(*args, check=True):
        return subprocess.run(args, cwd=repo, env=env, text=True, capture_output=True, check=check)

    command("uv", "lock", "--offline")
    command("git", "init", "--initial-branch=main")
    command("git", "config", "user.name", "Release Test")
    command("git", "config", "user.email", "release-test@example.com")
    command("git", "config", "commit.gpgsign", "false")
    command("git", "add", ".")
    command("git", "commit", "-m", "Initial test project")
    return repo, command


@pytest.mark.parametrize(
    "kind,expected", [("patch", "0.3.1"), ("minor", "0.4.0"), ("major", "1.0.0")]
)
def test_bump_updates_both_files_and_tags_release_commit(release_repo, kind, expected):
    repo, command = release_repo
    before = command("git", "rev-parse", "HEAD").stdout.strip()
    result = command(sys.executable, "scripts/bump_version.py", kind)
    assert f"tag v{expected}" in result.stdout
    assert tomllib.loads((repo / "pyproject.toml").read_text())["project"]["version"] == expected
    package = next(
        package
        for package in tomllib.loads((repo / "uv.lock").read_text())["package"]
        if package["name"] == "release-test"
    )
    assert package["version"] == expected
    assert (
        command("git", "rev-parse", f"v{expected}").stdout
        == command("git", "rev-parse", "HEAD").stdout
    )
    assert command("git", "rev-parse", "HEAD^").stdout.strip() == before
    assert set(command("git", "show", "--format=", "--name-only", "HEAD").stdout.split()) == {
        "pyproject.toml",
        "uv.lock",
    }
    assert command("git", "status", "--porcelain").stdout == ""


@pytest.mark.parametrize("dirty", ["untracked", "modified"])
def test_bump_refuses_dirty_tree_without_changing_versions(release_repo, dirty):
    repo, command = release_repo
    if dirty == "untracked":
        (repo / "pending.txt").write_text("Uncommitted work")
    else:
        with (repo / "pyproject.toml").open("a") as file:
            file.write("# Uncommitted work\n")
    before = {name: (repo / name).read_bytes() for name in ["pyproject.toml", "uv.lock"]}
    result = command(sys.executable, "scripts/bump_version.py", "patch", check=False)
    assert result.returncode == 1
    assert "Working tree is not clean" in result.stderr
    assert command("git", "tag", "--list").stdout == ""
    assert all((repo / name).read_bytes() == value for name, value in before.items())


def test_existing_tag_is_rejected_before_version_change(release_repo):
    repo, command = release_repo
    command("git", "tag", "v0.3.1")
    before = command("git", "rev-parse", "HEAD").stdout
    result = command(sys.executable, "scripts/bump_version.py", "patch", check=False)
    assert result.returncode == 1
    assert "already exists" in result.stderr
    assert command("git", "rev-parse", "HEAD").stdout == before
    assert command("git", "status", "--porcelain").stdout == ""
    assert tomllib.loads((repo / "pyproject.toml").read_text())["project"]["version"] == "0.3.0"
