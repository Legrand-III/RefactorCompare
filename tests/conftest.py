"""Shared fixtures: build small throwaway git repos to run RefactorCompare against."""

import subprocess
import textwrap

import pytest


def _git(repo, *args):
    # Name/email passed inline so tests don't depend on the machine's git config.
    subprocess.run(
        ["git", "-c", "user.name=test", "-c", "user.email=test@example.com", *args],
        cwd=repo, check=True, capture_output=True,
    )


@pytest.fixture
def make_repo(tmp_path):
    """Return a function that builds a git repo with one commit per version.

    Usage:
        repo = make_repo(
            {"math.py": "def f(x: int): return x"},       # commit 1 (tagged v1)
            {"math.py": "def f(x: int): return x + 0"},   # commit 2 (tagged v2)
        )

    Each dict maps file paths to their contents in that commit. Files not
    mentioned in a later commit stay as they were. Commits are tagged v1, v2, ...
    """
    def build(*versions):
        repo = tmp_path / "repo"
        repo.mkdir()
        _git(repo, "init", "-q")
        for number, files in enumerate(versions, start=1):
            for rel_path, content in files.items():
                path = repo / rel_path
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(textwrap.dedent(content))
            _git(repo, "add", "-A")
            _git(repo, "commit", "-q", "--allow-empty", "-m", f"v{number}")
            _git(repo, "tag", f"v{number}")
        return repo

    return build
