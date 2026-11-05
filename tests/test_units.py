"""Fast tests of individual pieces, no git involved."""

import math
from pathlib import Path

import pytest

import Testing
from checkout import checkout_versions


# ---------- Testing.parse_type ----------

@pytest.mark.parametrize("text, expected", [
    ("int", int),
    ("str", str),
    ("list[int]", list[int]),
    ("Optional[float]", Testing.typing.Optional[float]),
])
def test_parse_type(text, expected):
    assert Testing.parse_type(text) == expected


def test_parse_type_rejects_nonsense():
    with pytest.raises(Testing.StrategyError):
        Testing.parse_type("not_a_type")


# ---------- Testing.same_outcome ----------

def test_nan_equals_nan():
    nan = float("nan")
    assert Testing.same_outcome(("returned", nan), ("returned", math.nan))


def test_return_vs_raise_differs():
    assert not Testing.same_outcome(("returned", None), ("raised", ValueError))


def test_different_exception_types_differ():
    assert not Testing.same_outcome(("raised", ValueError), ("raised", TypeError))


# ---------- Testing.compare with plain functions ----------

def square_a(x: int) -> int:
    return x * x


def square_b(x: int) -> int:
    return x ** 2


def abs_buggy(x: int) -> int:
    return x if x > 0 else x       # forgot to negate


def abs_ok(x: int) -> int:
    return abs(x)


def test_compare_equivalent():
    same, _ = Testing.compare(square_a, square_b, max_examples=50)
    assert same


def test_compare_different_reports_input():
    same, message = Testing.compare(abs_ok, abs_buggy, max_examples=50)
    assert not same
    assert "x=-1" in message


def test_inputs_are_copied_between_versions():
    """If Version1 mutates its input, Version2 must still see the original."""
    def pop_one(xs: list[int]) -> int:
        return len(xs) - (xs.pop() * 0 if xs else 0)

    def length(xs: list[int]) -> int:
        return len(xs)

    same, _ = Testing.compare(pop_one, length, max_examples=50)
    assert same


# ---------- checkout.checkout_versions ----------

def test_checkout_gives_both_commits_and_cleans_up(make_repo):
    repo = make_repo({"f.txt": "one"}, {"f.txt": "two"})
    with checkout_versions(repo, "v1", "v2") as (v1, v2):
        assert (Path(v1) / "f.txt").read_text() == "one"
        assert (Path(v2) / "f.txt").read_text() == "two"
        workdir = Path(v1).parent
    assert not workdir.exists()


def test_checkout_keep_leaves_files(make_repo):
    repo = make_repo({"f.txt": "one"}, {"f.txt": "two"})
    with checkout_versions(repo, "v1", "v2", keep=True) as (v1, _):
        workdir = Path(v1).parent
    try:
        assert workdir.exists()
    finally:
        import shutil
        shutil.rmtree(workdir)


# ---------- runner.VersionRunner ----------

def test_runner_times_out_then_keeps_working(tmp_path):
    from runner import VersionRunner

    (tmp_path / "m.py").write_text(
        "def f(x):\n    while x < 0:\n        pass\n    return x * 2\n"
    )
    with VersionRunner(tmp_path, "m.py", "f", "V", timeout=0.5) as run:
        assert run((3,), {}) == ("returned", 6)
        assert run((-1,), {}) == ("timed out", 0.5)
        assert run((4,), {}) == ("returned", 8)       # a fresh worker took over


def test_runner_reports_exception_by_name_and_crash(tmp_path):
    from runner import VersionRunner

    (tmp_path / "m.py").write_text(
        "import os\n"
        "def f(x):\n    if x == 0:\n        os._exit(3)\n    return 1 // (x - 1)\n"
    )
    with VersionRunner(tmp_path, "m.py", "f", "V", timeout=5) as run:
        assert run((1,), {}) == ("raised", "ZeroDivisionError")
        assert run((0,), {}) == ("crashed", 3)
        assert run((2,), {}) == ("returned", 1)
