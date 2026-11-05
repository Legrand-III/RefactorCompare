"""Get two commits of a repository side by side on disk.

The repo is cloned once into a temporary directory, then each commit is
checked out into its own `git worktree`. Everything is deleted afterwards
unless keep=True.
"""

import shutil
import subprocess
import tempfile
from contextlib import contextmanager
from pathlib import Path


class GitError(RuntimeError):
    pass


def _git(*args, cwd=None):
    result = subprocess.run(
        ["git", *args], cwd=cwd, capture_output=True, text=True
    )
    if result.returncode != 0:
        raise GitError(f"git {' '.join(args)} failed:\n{result.stderr.strip()}")
    return result.stdout.strip()


@contextmanager
def checkout_versions(repo, commit1, commit2, keep=False):
    """Yield (version1_dir, version2_dir) for the two commits.

    `repo` can be a URL or a local path. A commit can be anything git
    accepts: a hash, a tag, or a branch name such as origin/some-branch.
    """
    workdir = Path(tempfile.mkdtemp(prefix="refactorcompare_"))
    try:
        base = workdir / "repo"
        print(f"Cloning {repo} ...")
        _git("clone", "--quiet", "--no-checkout", str(repo), str(base))

        dirs = []
        for label, commit in (("Version1", commit1), ("Version2", commit2)):
            target = workdir / label
            _git("worktree", "add", "--detach", "--quiet", str(target), commit, cwd=base)
            short = _git("rev-parse", "--short", "HEAD", cwd=target)
            print(f"  {label}: {commit} ({short}) -> {target}")
            dirs.append(target)

        yield dirs[0], dirs[1]
    finally:
        if keep:
            print(f"Kept checkouts in {workdir}")
        else:
            shutil.rmtree(workdir, ignore_errors=True)
